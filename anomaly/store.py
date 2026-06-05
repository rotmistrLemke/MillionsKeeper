import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from anomaly.schemas import AnomalyType, Snapshot


SCHEMA = """
CREATE TABLE IF NOT EXISTS anomalies (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol       TEXT    NOT NULL,
  types        TEXT    NOT NULL,
  opened_at    TEXT    NOT NULL,
  closed_at    TEXT,
  duration_sec INTEGER,
  open_price   REAL,
  open_ema50   REAL,
  open_atr     REAL,
  open_dist_atr REAL,
  open_stoch_k REAL,
  open_stoch_d REAL,
  close_price  REAL,
  close_ema50  REAL,
  close_atr    REAL,
  close_dist_atr REAL,
  close_stoch_k REAL,
  close_stoch_d REAL,
  max_abs_dist_atr REAL,
  peak_stoch_k     REAL
);
CREATE INDEX IF NOT EXISTS idx_anomalies_symbol_opened ON anomalies(symbol, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_active ON anomalies(closed_at) WHERE closed_at IS NULL;
"""


def _types_csv(types: Iterable[AnomalyType]) -> str:
    return ",".join(sorted({t.value if isinstance(t, AnomalyType) else str(t) for t in types}))


def _row_to_dict(r: sqlite3.Row) -> dict:
    return dict(r)


class AnomalyStore:
    """Тонкий репозиторий поверх SQLite. Потокобезопасен через Lock."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.RLock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    def init_schema(self):
        with self._lock:
            self._conn.executescript(SCHEMA)

    # ---- write ----

    def open(self, symbol: str, types: List[AnomalyType], snap: Snapshot,
             opened_at: Optional[str] = None) -> int:
        opened_at = opened_at or datetime.now(timezone.utc).isoformat()
        with self._lock:
            cur = self._conn.execute(
                "SELECT id FROM anomalies WHERE symbol = ? AND closed_at IS NULL",
                (symbol,),
            )
            if cur.fetchone() is not None:
                raise ValueError(f"anomaly already active for {symbol}")
            abs_dist = abs(snap.dist_atr)
            cur = self._conn.execute(
                """
                INSERT INTO anomalies (
                  symbol, types, opened_at,
                  open_price, open_ema50, open_atr, open_dist_atr,
                  open_stoch_k, open_stoch_d,
                  max_abs_dist_atr, peak_stoch_k
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (symbol, _types_csv(types), opened_at,
                 snap.price, snap.ema50, snap.atr, snap.dist_atr,
                 snap.stoch_k, snap.stoch_d,
                 abs_dist, snap.stoch_k),
            )
            return int(cur.lastrowid)

    def update(self, anomaly_id: int, types: List[AnomalyType], snap: Snapshot) -> None:
        abs_dist = abs(snap.dist_atr)
        with self._lock:
            self._conn.execute(
                """
                UPDATE anomalies
                   SET types            = ?,
                       max_abs_dist_atr = MAX(COALESCE(max_abs_dist_atr, 0), ?),
                       peak_stoch_k     = MAX(COALESCE(peak_stoch_k, 0), ?)
                 WHERE id = ?
                """,
                (_types_csv(types), abs_dist, snap.stoch_k, anomaly_id),
            )

    def close(self, anomaly_id: int, snap: Snapshot,
              closed_at: Optional[str] = None) -> None:
        closed_at = closed_at or datetime.now(timezone.utc).isoformat()
        with self._lock:
            row = self._conn.execute(
                "SELECT opened_at FROM anomalies WHERE id = ?",
                (anomaly_id,),
            ).fetchone()
            if row is None:
                return
            opened = datetime.fromisoformat(row["opened_at"])
            closed = datetime.fromisoformat(closed_at)
            duration = int((closed - opened).total_seconds())
            self._conn.execute(
                """
                UPDATE anomalies
                   SET closed_at      = ?,
                       duration_sec   = ?,
                       close_price    = ?,
                       close_ema50    = ?,
                       close_atr      = ?,
                       close_dist_atr = ?,
                       close_stoch_k  = ?,
                       close_stoch_d  = ?
                 WHERE id = ?
                """,
                (closed_at, duration,
                 snap.price, snap.ema50, snap.atr, snap.dist_atr,
                 snap.stoch_k, snap.stoch_d,
                 anomaly_id),
            )

    # ---- read ----

    def list_active(self) -> List[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM anomalies WHERE closed_at IS NULL ORDER BY opened_at DESC"
            )
            return [_row_to_dict(r) for r in cur.fetchall()]

    def recover_active(self) -> List[dict]:
        return self.list_active()

    def list_history(self, limit: int = 100, offset: int = 0,
                     symbol: Optional[str] = None,
                     type_: Optional[str] = None,
                     from_: Optional[str] = None,
                     to: Optional[str] = None) -> dict:
        where = []
        params: list = []
        if symbol:
            where.append("symbol = ?"); params.append(symbol)
        if type_:
            where.append("types LIKE ?"); params.append(f"%{type_}%")
        if from_:
            where.append("opened_at >= ?"); params.append(from_)
        if to:
            where.append("opened_at <= ?"); params.append(to)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM anomalies {where_sql}", params,
            ).fetchone()[0]
            cur = self._conn.execute(
                f"SELECT * FROM anomalies {where_sql} ORDER BY opened_at DESC LIMIT ? OFFSET ?",
                params + [int(limit), int(offset)],
            )
            items = [_row_to_dict(r) for r in cur.fetchall()]
            return {"items": items, "total": int(total)}

    def close_conn(self):
        with self._lock:
            self._conn.close()
