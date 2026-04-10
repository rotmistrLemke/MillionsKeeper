"""
strategies/registry.py — Реестр всех торговых стратегий.

Автоматически собирает все подклассы BaseStrategy.
SignalAgent использует реестр для получения активной стратегии.

Usage:
    from app.strategies.registry import StrategyRegistry
    strategy = StrategyRegistry.get("bollinger_scalp")
    signal = strategy.get_entry_signal(row)
"""
from __future__ import annotations

import importlib
import logging
from typing import Optional

logger = logging.getLogger("StrategyRegistry")

# Маппинг имён стратегий → модули (для lazy-импорта)
_STRATEGY_MODULES: dict[str, str] = {
    "alligator": "app.strategies.alligator",
}


class StrategyRegistry:
    _instances: dict[str, object] = {}

    @classmethod
    def get(cls, name: str) -> Optional[object]:
        """Возвращает инстанс стратегии по имени (singleton per name)."""
        if name in cls._instances:
            return cls._instances[name]

        module_path = _STRATEGY_MODULES.get(name)
        if module_path is None:
            logger.error(f"Unknown strategy: {name}")
            return None

        try:
            module = importlib.import_module(module_path)
            # Ищем класс — либо с именем в PascalCase, либо первый BaseStrategy-наследник
            strategy_class = _find_strategy_class(module, name)
            if strategy_class is None:
                logger.error(f"No strategy class found in {module_path}")
                return None

            instance = strategy_class()
            cls._instances[name] = instance
            logger.info(f"Loaded strategy: {name} ({strategy_class.__name__})")
            return instance

        except ImportError as e:
            logger.error(f"Failed to import strategy {name}: {e}")
            return None

    @classmethod
    def all_names(cls) -> list[str]:
        return list(_STRATEGY_MODULES.keys())

    @classmethod
    def get_all(cls) -> dict[str, object]:
        """Загружает и возвращает все стратегии."""
        return {name: cls.get(name) for name in _STRATEGY_MODULES}


def _find_strategy_class(module, name: str):
    """Ищет класс стратегии в модуле."""
    # Пробуем точное PascalCase имя
    pascal = "".join(part.capitalize() for part in name.split("_"))
    cls = getattr(module, pascal, None)
    if cls is not None:
        return cls

    # Fallback — первый класс, не являющийся базовым
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if (
            isinstance(obj, type)
            and hasattr(obj, "get_entry_signal")
            and obj.__name__ != "BaseStrategy"
        ):
            return obj

    return None
