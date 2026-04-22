"""
Торговые потоки (TradingStream).
Один поток = уникальная пара (strategy, symbol) с собственным TF, объёмом, SL/TP и magic.
Правила: максимум MAX_STREAMS потоков, одна пара может быть закреплена только за одним потоком.

Magic выдаётся из диапазона [MAGIC_BASE .. MAGIC_BASE + MAX_STREAMS - 1] и привязывает
открытую позицию MT5 к потоку-владельцу.
"""
import json
import logging
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Streams")

MAX_STREAMS = 10
MAGIC_BASE  = 100000

_STREAMS_FILE = Path(__file__).parent / "streams.json"


@dataclass
class TradingStream:
    id: str
    name: str
    strategy: str
    symbol: str
    timeframe: int     # mt5.TIMEFRAME_* (int enum)
    volume: float
    sl_atr: float
    tp_atr: float
    magic: int
    deposit: float = 0.0   # выделенный поток-бюджет ($); используется для per-stream DD
    enabled: bool = True

    def to_dict(self) -> dict:
        from settings import TF_REVERSE
        d = asdict(self)
        d["timeframe"] = TF_REVERSE.get(self.timeframe, "H1")
        return d


class StreamRegistry:
    def __init__(self):
        self._streams: dict[str, TradingStream] = {}
        self._lock = threading.RLock()
        self._next_seq = 1

    # ── Read ──────────────────────────────────────────────────────────
    def all(self) -> list[TradingStream]:
        with self._lock:
            return list(self._streams.values())

    def enabled(self) -> list[TradingStream]:
        return [s for s in self.all() if s.enabled]

    def get(self, stream_id: str) -> Optional[TradingStream]:
        with self._lock:
            return self._streams.get(stream_id)

    def by_symbol(self, symbol: str) -> Optional[TradingStream]:
        with self._lock:
            for s in self._streams.values():
                if s.symbol == symbol:
                    return s
        return None

    def by_magic(self, magic) -> Optional[TradingStream]:
        try:
            magic = int(magic or 0)
        except (TypeError, ValueError):
            return None
        if magic <= 0:
            return None
        with self._lock:
            for s in self._streams.values():
                if s.magic == magic:
                    return s
        return None

    # ── Mutate ────────────────────────────────────────────────────────
    def _allocate_magic_locked(self) -> int:
        used = {s.magic for s in self._streams.values()}
        for i in range(MAX_STREAMS):
            m = MAGIC_BASE + i
            if m not in used:
                return m
        raise ValueError(f"Нет свободных magic-номеров ({MAX_STREAMS} максимум)")

    def _allocate_id_locked(self) -> str:
        while True:
            sid = f"s{self._next_seq}"
            self._next_seq += 1
            if sid not in self._streams:
                return sid

    def create(self, *, name: str, strategy: str, symbol: str,
               timeframe: int, volume: float = 0.0,
               sl_atr: float = 0.0, tp_atr: float = 0.0,
               deposit: float = 0.0,
               enabled: bool = True) -> TradingStream:
        with self._lock:
            if len(self._streams) >= MAX_STREAMS:
                raise ValueError(f"Достигнут лимит потоков ({MAX_STREAMS})")
            for s in self._streams.values():
                if s.symbol == symbol:
                    raise ValueError(f"Пара {symbol} уже закреплена за потоком «{s.name}»")
            stream = TradingStream(
                id=self._allocate_id_locked(),
                name=(name or "").strip() or symbol,
                strategy=strategy,
                symbol=symbol,
                timeframe=int(timeframe),
                volume=float(volume or 0.0),
                sl_atr=float(sl_atr or 0.0),
                tp_atr=float(tp_atr or 0.0),
                magic=self._allocate_magic_locked(),
                deposit=float(deposit or 0.0),
                enabled=bool(enabled),
            )
            self._streams[stream.id] = stream
        save()
        _sync_trading_status()
        return stream

    def update(self, stream_id: str, **fields) -> TradingStream:
        with self._lock:
            stream = self._streams.get(stream_id)
            if stream is None:
                raise KeyError(stream_id)
            new_symbol = fields.get("symbol")
            if new_symbol and new_symbol != stream.symbol:
                for s in self._streams.values():
                    if s.id != stream_id and s.symbol == new_symbol:
                        raise ValueError(f"Пара {new_symbol} уже закреплена за потоком «{s.name}»")
            for k in ("name", "strategy", "symbol", "timeframe",
                      "volume", "sl_atr", "tp_atr", "deposit", "enabled"):
                if k in fields and fields[k] is not None:
                    v = fields[k]
                    if k in ("volume", "sl_atr", "tp_atr", "deposit"):
                        v = float(v)
                    elif k == "timeframe":
                        v = int(v)
                    elif k == "enabled":
                        v = bool(v)
                    elif k == "name":
                        v = str(v).strip() or stream.name
                    setattr(stream, k, v)
        save()
        _sync_trading_status()
        return stream

    def delete(self, stream_id: str) -> bool:
        with self._lock:
            removed = self._streams.pop(stream_id, None)
        if removed is not None:
            save()
            _sync_trading_status()
            return True
        return False

    # ── Persist ───────────────────────────────────────────────────────
    def _load_raw_locked(self, items: list):
        from settings import TF_MAP
        self._streams.clear()
        max_seq = 0
        for d in items or []:
            try:
                tf = d.get("timeframe")
                if isinstance(tf, str):
                    import MetaTrader5 as mt5
                    tf = TF_MAP.get(tf, mt5.TIMEFRAME_H1)
                stream = TradingStream(
                    id=str(d["id"]),
                    name=str(d.get("name") or d["id"]),
                    strategy=str(d.get("strategy", "default")),
                    symbol=str(d["symbol"]),
                    timeframe=int(tf),
                    volume=float(d.get("volume", 0.0) or 0.0),
                    sl_atr=float(d.get("sl_atr", 0.0) or 0.0),
                    tp_atr=float(d.get("tp_atr", 0.0) or 0.0),
                    magic=int(d.get("magic") or 0),
                    deposit=float(d.get("deposit", 0.0) or 0.0),
                    enabled=bool(d.get("enabled", True)),
                )
                self._streams[stream.id] = stream
                if stream.id.startswith("s"):
                    try:
                        max_seq = max(max_seq, int(stream.id[1:]))
                    except ValueError:
                        pass
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Пропуск некорректной записи потока: {e}")

        # Переназначаем недостающие/конфликтующие magic.
        used: set[int] = set()
        for s in self._streams.values():
            if s.magic in used or not (MAGIC_BASE <= s.magic < MAGIC_BASE + MAX_STREAMS):
                s.magic = 0
            else:
                used.add(s.magic)
        for s in self._streams.values():
            if s.magic == 0:
                for i in range(MAX_STREAMS):
                    m = MAGIC_BASE + i
                    if m not in used:
                        s.magic = m
                        used.add(m)
                        break
        self._next_seq = max_seq + 1


registry = StreamRegistry()


# ── Module-level API ─────────────────────────────────────────────────
def load() -> None:
    """Загружает потоки из streams.json. Если файла нет — мигрирует из legacy active_state."""
    if not _STREAMS_FILE.exists():
        _migrate_from_legacy()
        return
    try:
        data = json.loads(_STREAMS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Не удалось прочитать {_STREAMS_FILE.name}: {e}")
        return
    items = data.get("streams", []) if isinstance(data, dict) else data
    with registry._lock:
        registry._load_raw_locked(items)
    _sync_trading_status()
    logger.info(f"Загружено потоков: {len(registry.all())}")


def save() -> None:
    items = [s.to_dict() for s in registry.all()]
    try:
        _STREAMS_FILE.write_text(
            json.dumps({"streams": items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(f"Не удалось сохранить {_STREAMS_FILE.name}: {e}")


def _migrate_from_legacy() -> None:
    """Разовая миграция: создаём поток из legacy GlobalValues.active_* и/или active_state.json."""
    from settings import GlobalValues, Dictionary
    # Попытка догрузить legacy-файл (если main.py ещё не вызвал active_state.load()).
    legacy_file = Path(__file__).parent / "active_state.json"
    if legacy_file.exists():
        try:
            import active_state  # noqa: F401
            active_state.load()
        except Exception as e:
            logger.warning(f"Legacy active_state.load() failed: {e}")

    symbol = GlobalValues.active_symbol
    if symbol not in Dictionary.symbolTradingStatus:
        logger.warning(f"Миграция отменена: symbol {symbol} неизвестен")
        return
    try:
        registry.create(
            name="Поток 1",
            strategy=GlobalValues.active_strategy,
            symbol=symbol,
            timeframe=GlobalValues.time_frame,
            volume=GlobalValues.active_volume,
            sl_atr=GlobalValues.active_sl_atr,
            tp_atr=GlobalValues.active_tp_atr,
            enabled=True,
        )
        logger.info("Миграция: создан «Поток 1» из legacy active_* настроек")
    except Exception as e:
        logger.warning(f"Миграция не удалась: {e}")


def _sync_trading_status() -> None:
    """Приводит Dictionary.symbolTradingStatus к enabled-потокам.
    0 = разрешено, 3 = выключено. Символы со статусом 1 (открытая позиция) не трогаем.
    """
    from settings import Dictionary
    enabled_symbols = {s.symbol for s in registry.enabled()}
    for sym, cur in list(Dictionary.symbolTradingStatus.items()):
        if cur == 1:
            continue
        Dictionary.symbolTradingStatus[sym] = 0 if sym in enabled_symbols else 3


def unique_symbol_tf_pairs() -> set[tuple[str, int]]:
    """Уникальные (symbol, timeframe) по всем enabled-потокам. Для MarketDataAgent."""
    return {(s.symbol, s.timeframe) for s in registry.enabled()}
