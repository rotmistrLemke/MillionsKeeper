"""SQLite-персистинг live-трека: сделки (дедуп по ticket) + equity-снимки.
Один connection на инстанс; для кросс-тредового использования открывать
отдельный инстанс в нужном треде (см. record_poll)."""
from __future__ import annotations
import sqlite3
import time as _time
from pathlib import Path
from typing import Iterable, Optional

_DEFAULT_DB = Path(__file__).parent / "performance.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    ticket     INTEGER PRIMARY KEY,
    time       INTEGER NOT NULL,
    magic      INTEGER NOT NULL DEFAULT 0,
    symbol     TEXT,
    type       INTEGER,
    entry      INTEGER,
    volume     REAL,
    price      REAL,
    profit     REAL,
    commission REAL,
    swap       REAL
);
CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts      INTEGER NOT NULL,
    balance REAL,
    equity  REAL
);
"""

_COLS = ("ticket", "time", "magic", "symbol", "type", "entry",
         "volume", "price", "profit", "commission", "swap")


class PerformanceStore:
    def __init__(self, db_path=_DEFAULT_DB):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def upsert_deals(self, deals: Iterable[dict]) -> int:
        """INSERT OR IGNORE по ticket. Возвращает число НОВЫХ строк."""
        rows = [tuple(d.get(c) if c != "magic" else int(d.get("magic", 0)) for c in _COLS)
                for d in deals]
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            f"INSERT OR IGNORE INTO deals ({','.join(_COLS)}) "
            f"VALUES ({','.join('?' * len(_COLS))})", rows)
        self._conn.commit()
        return self._conn.total_changes - before

    def record_equity(self, balance: float, equity: float, ts: Optional[int] = None) -> None:
        self._conn.execute(
            "INSERT INTO equity_snapshots (ts,balance,equity) VALUES (?,?,?)",
            (int(ts if ts is not None else _time.time()), balance, equity))
        self._conn.commit()

    def closed_trades(self, since: Optional[int] = None) -> list[dict]:
        if since is not None:
            cur = self._conn.execute(
                "SELECT * FROM deals WHERE time >= ? ORDER BY time ASC", (int(since),))
        else:
            cur = self._conn.execute("SELECT * FROM deals ORDER BY time ASC")
        return [dict(r) for r in cur.fetchall()]

    def equity_series(self) -> list[tuple[int, float]]:
        cur = self._conn.execute("SELECT ts,equity FROM equity_snapshots ORDER BY ts ASC")
        return [(r["ts"], r["equity"]) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


def record_poll(closed_deals, balance: float, equity: float, db_path=None) -> int:
    """Открыть/записать/закрыть в одном вызове (потокобезопасно: connection в текущем треде).
    db_path резолвится на этапе ВЫЗОВА (не дефолт-параметром), чтобы monkeypatch
    _DEFAULT_DB работал в тестах и чтобы прод читал актуальный путь."""
    if db_path is None:
        db_path = _DEFAULT_DB
    store = PerformanceStore(db_path)
    try:
        n = store.upsert_deals(closed_deals)
        store.record_equity(balance, equity)
        return n
    finally:
        store.close()
