"""
Торговые потоки (TradingStream).
Поток = связка (strategy, symbol) с собственным TF, объёмом, SL/TP и magic.
SL/TP/breakeven/trail задаются в пунктах (symbol_info.point), 0 = выкл.
Правила: максимум MAX_STREAMS потоков. Одну пару могут обслуживать несколько
потоков (разные стратегии/ТФ) — OPEN-статус отслеживается per-stream
(is_stream_open / mark_stream_open), а не по символу.

Magic выдаётся из диапазона [MAGIC_BASE .. MAGIC_BASE + MAX_STREAMS - 1] и привязывает
открытую позицию MT5 к потоку-владельцу.
"""
import json
import logging
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Streams")

MAX_STREAMS = 20
MAGIC_BASE  = 100000

_STREAMS_FILE = Path(__file__).parent / "streams.json"
# Эталон боевых потоков: трекается в git, рабочий streams.json — нет.
# Нужен как источник восстановления, если рабочий файл потерян или испорчен.
_REFERENCE_FILE = Path(__file__).parent / "config" / "streams.reference.json"
_BACKUP_DIR = Path(__file__).parent / "streams.backup"
_BACKUP_KEEP = 10


@dataclass
class TradingStream:
    id: str
    name: str
    strategy: str
    symbol: str
    timeframe: int     # mt5.TIMEFRAME_* (int enum)
    volume: float
    sl_points: float
    tp_points: float
    magic: int
    deposit: float = 0.0           # выделенный поток-бюджет ($); используется для per-stream DD
    breakeven_points: float = 0.0  # после +N пунктов прибыли двигаем SL в точку входа (0 = выкл)
    trail_points: float = 0.0      # трейлинг SL = high - N пунктов (BUY), low + N (SELL); 0 = выкл
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
        self._open_streams: set[str] = set()

    # ── Per-stream OPEN tracking ─────────────────────────────────────
    def is_stream_open(self, stream_id: str) -> bool:
        with self._lock:
            return stream_id in self._open_streams

    def mark_stream_open(self, stream_id: str) -> None:
        with self._lock:
            self._open_streams.add(stream_id)

    def mark_stream_closed(self, stream_id: str) -> None:
        with self._lock:
            self._open_streams.discard(stream_id)

    # ── Read ──────────────────────────────────────────────────────────
    def all(self) -> list[TradingStream]:
        with self._lock:
            return list(self._streams.values())

    def enabled(self) -> list[TradingStream]:
        return [s for s in self.all() if s.enabled]

    def get(self, stream_id: str) -> Optional[TradingStream]:
        with self._lock:
            return self._streams.get(stream_id)

    def by_symbol(self, symbol: str) -> list[TradingStream]:
        with self._lock:
            return [s for s in self._streams.values() if s.symbol == symbol]

    def by_symbol_first(self, symbol: str) -> Optional[TradingStream]:
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
               sl_points: float = 0.0, tp_points: float = 0.0,
               deposit: float = 0.0,
               breakeven_points: float = 0.0, trail_points: float = 0.0,
               enabled: bool = True) -> TradingStream:
        with self._lock:
            if len(self._streams) >= MAX_STREAMS:
                raise ValueError(f"Достигнут лимит потоков ({MAX_STREAMS})")
            stream = TradingStream(
                id=self._allocate_id_locked(),
                name=(name or "").strip() or symbol,
                strategy=strategy,
                symbol=symbol,
                timeframe=int(timeframe),
                volume=float(volume or 0.0),
                sl_points=float(sl_points or 0.0),
                tp_points=float(tp_points or 0.0),
                magic=self._allocate_magic_locked(),
                deposit=float(deposit or 0.0),
                breakeven_points=float(breakeven_points or 0.0),
                trail_points=float(trail_points or 0.0),
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
            for k in ("name", "strategy", "symbol", "timeframe",
                      "volume", "sl_points", "tp_points", "deposit",
                      "breakeven_points", "trail_points", "enabled"):
                if k in fields and fields[k] is not None:
                    v = fields[k]
                    if k in ("volume", "sl_points", "tp_points", "deposit",
                             "breakeven_points", "trail_points"):
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
                    sl_points=float(d.get("sl_points", 0.0) or 0.0),
                    tp_points=float(d.get("tp_points", 0.0) or 0.0),
                    magic=int(d.get("magic") or 0),
                    deposit=float(d.get("deposit", 0.0) or 0.0),
                    breakeven_points=float(d.get("breakeven_points", 0.0) or 0.0),
                    trail_points=float(d.get("trail_points", 0.0) or 0.0),
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
def _read_items(path: Path) -> Optional[list]:
    """Список потоков из файла. None — файла нет либо он нечитаем/битый."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Не удалось прочитать {path.name}: {e}")
        return None
    items = data.get("streams", []) if isinstance(data, dict) else data
    return items if isinstance(items, list) else None


def load() -> None:
    """Загружает потоки из streams.json.

    Если рабочий файл отсутствует, пуст или битый — поднимаемся из эталона
    config/streams.reference.json. Боевой конфиг однажды уже был потерян
    молча (файл остался как {"streams": []}, потоки продолжали торговать
    по magic), поэтому пустой старт при наличии эталона — всегда WARNING.
    """
    items = _read_items(_STREAMS_FILE)
    if not items:
        reference = _read_items(_REFERENCE_FILE)
        if reference:
            logger.warning(
                f"{_STREAMS_FILE.name} пуст или недоступен — "
                f"восстанавливаем {len(reference)} потоков из {_REFERENCE_FILE.name}"
            )
            items = reference
        elif items is None:
            return
    with registry._lock:
        registry._load_raw_locked(items)
    _sync_trading_status()
    logger.info(f"Загружено потоков: {len(registry.all())}")


def _backup_current() -> None:
    """Копия текущего streams.json в streams.backup/ с ротацией до _BACKUP_KEEP."""
    if not _STREAMS_FILE.exists():
        return
    try:
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        (_BACKUP_DIR / f"streams-{stamp}.json").write_bytes(_STREAMS_FILE.read_bytes())
        old = sorted(_BACKUP_DIR.glob("streams-*.json"))[:-_BACKUP_KEEP]
        for f in old:
            f.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"Не удалось сделать бэкап {_STREAMS_FILE.name}: {e}")


def save() -> None:
    """Атомарно пишет streams.json, сохранив предыдущую версию в бэкап.

    Пустой реестр поверх непустого конфига не пишется: это признак того,
    что процесс стартовал без потоков (битый файл, сбой загрузки), а не
    того, что пользователь удалил последний поток из UI.
    """
    items = [s.to_dict() for s in registry.all()]
    if not items:
        existing = _read_items(_STREAMS_FILE)
        if existing:
            logger.error(
                f"Отказ записать пустой реестр поверх {_STREAMS_FILE.name} "
                f"({len(existing)} потоков). Конфиг сохранён без изменений."
            )
            return

    _backup_current()
    tmp = _STREAMS_FILE.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps({"streams": items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, _STREAMS_FILE)
    except OSError as e:
        logger.warning(f"Не удалось сохранить {_STREAMS_FILE.name}: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _sync_trading_status() -> None:
    """Приводит статусы к enabled-потокам: enabled-символы → ALLOWED, прочие → DISABLED.
    Символы с открытой позицией (OPEN) не трогаем."""
    from trading_status import status
    status.sync_enabled({s.symbol for s in registry.enabled()})


def unique_symbol_tf_pairs() -> set[tuple[str, int]]:
    """Уникальные (symbol, timeframe) по всем enabled-потокам. Для MarketDataAgent."""
    return {(s.symbol, s.timeframe) for s in registry.enabled()}
