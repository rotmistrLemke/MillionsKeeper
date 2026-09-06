"""SQLite-журнал отклонённых сигналов.

Сигнал живёт коротко: IndicatorAgent считает его на новом баре, SignalAgent
превращает в BUY/SELL, ExecutionAgent либо открывает ордер, либо отбрасывает.
Причина отказа раньше уходила только в статус агента — строкой, которая
нигде не оседала, и разрыв между числом модельных и живых сделок
(cci_rsi 2 против 18 за август) нечем было объяснить.

Пишем ТОЛЬКО отказы: NO_SIGNAL — это отсутствие сигнала, а не отказ,
и на 14 потоках он забил бы журнал сотнями строк в сутки.

Запись никогда не бросает: журнал — диагностика, он не должен ронять торговлю.
"""
from __future__ import annotations

import logging
import sqlite3
import time as _time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("SignalJournal")

_DEFAULT_DB = Path(__file__).parent / "signals.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rejected_signals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    symbol    TEXT    NOT NULL,
    stream_id TEXT,
    strategy  TEXT,
    signal    TEXT,
    reason    TEXT    NOT NULL,
    detail    TEXT
);
CREATE INDEX IF NOT EXISTS idx_rejected_ts ON rejected_signals(ts DESC);
CREATE INDEX IF NOT EXISTS idx_rejected_strategy_reason ON rejected_signals(strategy, reason);
"""


class Reason:
    """Причины отказа. Значения уходят в БД — менять только с миграцией."""
    FLAT            = "FLAT"             # флэт-фильтр стратегии погасил бар
    SYMBOL_DISABLED = "SYMBOL_DISABLED"  # торговля по символу выключена
    NO_STREAM       = "NO_STREAM"        # поток по сигналу не найден
    STREAM_DISABLED = "STREAM_DISABLED"  # поток выключен
    STREAM_BUSY     = "STREAM_BUSY"      # у потока уже есть открытая позиция
    NIGHT_BLOCK     = "NIGHT_BLOCK"      # ночное окно 23:50–05:00
    DRAWDOWN_BLOCK  = "DRAWDOWN_BLOCK"   # просадка потока > порога
    PORTFOLIO_LIMIT = "PORTFOLIO_LIMIT"  # достигнут лимит одновременных позиций
    PORTFOLIO_DRAWDOWN = "PORTFOLIO_DRAWDOWN"  # портфельный стоп по просадке счёта
    ORDER_FAILED    = "ORDER_FAILED"     # ордер не открылся (брокер отказал)
    ORDER_ERROR     = "ORDER_ERROR"      # исключение при отправке ордера
    HEDGE_FAILED    = "HEDGE_FAILED"     # основная нога открыта, хедж — нет


def _connect(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def record(*, symbol: str, reason: str, stream_id: Optional[str] = None,
           strategy: Optional[str] = None, signal: Optional[str] = None,
           detail: Optional[str] = None, ts: Optional[int] = None,
           db_path=None) -> None:
    """Записывает отказ. Ошибки БД гасим — торговля важнее журнала."""
    if db_path is None:
        db_path = _DEFAULT_DB
    try:
        with _connect(db_path) as conn:
            conn.execute(
                "INSERT INTO rejected_signals (ts,symbol,stream_id,strategy,signal,reason,detail) "
                "VALUES (?,?,?,?,?,?,?)",
                (int(ts if ts is not None else _time.time()), symbol, stream_id,
                 strategy, signal, reason, detail),
            )
    except (sqlite3.Error, OSError) as e:
        logger.warning(f"Не удалось записать отказ {reason} по {symbol}: {e}")


def recent(*, limit: int = 100, db_path=None) -> list[dict]:
    """Последние отказы, новые сверху."""
    if db_path is None:
        db_path = _DEFAULT_DB
    if not Path(db_path).exists():
        return []
    try:
        with _connect(db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM rejected_signals ORDER BY ts DESC, id DESC LIMIT ?", (int(limit),))
            return [dict(r) for r in cur.fetchall()]
    except (sqlite3.Error, OSError) as e:
        logger.warning(f"Не удалось прочитать журнал: {e}")
        return []


def summary(*, since: Optional[int] = None, db_path=None) -> dict[tuple, int]:
    """{(strategy, reason): сколько} за период — разложение разрыва по причинам."""
    if db_path is None:
        db_path = _DEFAULT_DB
    if not Path(db_path).exists():
        return {}
    try:
        with _connect(db_path) as conn:
            if since is None:
                cur = conn.execute(
                    "SELECT strategy, reason, COUNT(*) n FROM rejected_signals "
                    "GROUP BY strategy, reason")
            else:
                cur = conn.execute(
                    "SELECT strategy, reason, COUNT(*) n FROM rejected_signals "
                    "WHERE ts >= ? GROUP BY strategy, reason", (int(since),))
            return {(r["strategy"], r["reason"]): r["n"] for r in cur.fetchall()}
    except (sqlite3.Error, OSError) as e:
        logger.warning(f"Не удалось посчитать сводку журнала: {e}")
        return {}


def purge_before(ts: int, *, db_path=None) -> int:
    """Удаляет записи старше ts. Возвращает число удалённых строк."""
    if db_path is None:
        db_path = _DEFAULT_DB
    if not Path(db_path).exists():
        return 0
    try:
        with _connect(db_path) as conn:
            cur = conn.execute("DELETE FROM rejected_signals WHERE ts < ?", (int(ts),))
            return cur.rowcount
    except (sqlite3.Error, OSError) as e:
        logger.warning(f"Не удалось почистить журнал: {e}")
        return 0
