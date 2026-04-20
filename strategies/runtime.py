"""
Runtime-кэш экземпляров стратегий для live-торговли.

Одна и та же стратегия для одного и того же символа должна
использовать один экземпляр между вызовами, чтобы сохранялось
внутреннее состояние (например, `_blocked_side` в MacdHistStrategy).
"""
from strategies import STRATEGIES

_instances: dict = {}


def get_runtime_strategy(name: str, symbol: str):
    """Возвращает singleton-экземпляр стратегии для пары (name, symbol).
    Если имя неизвестно — возвращает None (caller должен упасть обратно
    на legacy MA+MACD+RSI поведение).
    """
    if name not in STRATEGIES:
        return None
    key = (name, symbol)
    inst = _instances.get(key)
    if inst is None:
        inst = STRATEGIES[name]()
        _instances[key] = inst
    return inst


def reset_runtime_strategy(name: str, symbol: str) -> None:
    _instances.pop((name, symbol), None)


def reset_all() -> None:
    _instances.clear()
