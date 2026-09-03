"""
Runtime-кэш экземпляров стратегий для live-торговли.

Одна и та же стратегия для одного и того же символа должна
использовать один экземпляр между вызовами, чтобы сохранялось
внутреннее состояние (например, `_blocked_side` в MacdHistStrategy).

Состояние переживает и рестарт процесса: поля из `state_fields()`
пишутся в runtime_state.json и восстанавливаются при следующем
создании экземпляра. Без этого любой перезапуск снимал блокировку
переоткрытия, и стратегия заходила в ту же сторону сразу после стопа.
"""
import json
import logging
import os
from pathlib import Path

from strategies import STRATEGIES

logger = logging.getLogger("StrategyRuntime")

_instances: dict = {}
_STATE_FILE = Path(__file__).parent / "runtime_state.json"


def _state_key(name: str, symbol: str) -> str:
    return f"{name}|{symbol}"


def _read_all() -> dict:
    """Всё сохранённое состояние. Битый или отсутствующий файл — пустой dict."""
    try:
        data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Не удалось прочитать {_STATE_FILE.name}: {e} — состояние сброшено")
        return {}
    return data if isinstance(data, dict) else {}


def _write_all(data: dict) -> None:
    tmp = _STATE_FILE.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _STATE_FILE)
    except OSError as e:
        logger.warning(f"Не удалось сохранить {_STATE_FILE.name}: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def get_runtime_strategy(name: str, symbol: str):
    """Возвращает singleton-экземпляр стратегии для пары (name, symbol).
    Новый экземпляр поднимает сохранённое состояние с диска.
    Если имя неизвестно — возвращает None (caller должен упасть обратно
    на legacy MA+MACD+RSI поведение).
    """
    if name not in STRATEGIES:
        return None
    key = (name, symbol)
    inst = _instances.get(key)
    if inst is None:
        inst = STRATEGIES[name]()
        saved = _read_all().get(_state_key(name, symbol))
        if saved:
            inst.load_state(saved)
            logger.info(f"Состояние восстановлено {name}/{symbol}: {saved}")
        _instances[key] = inst
    return inst


def save_runtime_state(name: str, symbol: str) -> None:
    """Сохраняет состояние экземпляра (name, symbol) на диск.
    Стратегии без состояния из файла удаляются, чтобы он не рос мусором."""
    inst = _instances.get((name, symbol))
    if inst is None:
        return
    try:
        state = inst.state_dict()
    except Exception as e:                       # стратегия не обязана быть идеальной
        logger.warning(f"state_dict() упал для {name}/{symbol}: {e}")
        return
    data = _read_all()
    key = _state_key(name, symbol)
    if state:
        data[key] = state
    else:
        data.pop(key, None)
    _write_all(data)


def reset_runtime_strategy(name: str, symbol: str) -> None:
    _instances.pop((name, symbol), None)


def reset_all() -> None:
    _instances.clear()
