"""Фикстура patched_trading: подменяет модульные глобалы trading.py фейками."""
import sys
import types
from types import SimpleNamespace

import pytest

from tests.execution.fakes import FakeMT5, FakeCache, FakeStatus


def _ensure_importable_mt5(monkeypatch):
    """Гарантирует, что sys.modules['MetaTrader5'] имеет ORDER_TYPE_BUY на момент
    ПЕРВОГО импорта trading.

    trading.py:427 вычисляет `order_type=mt5.ORDER_TYPE_BUY` как дефолт-аргумент
    на этапе определения класса. Часть legacy-тестов (test_macd_atr/
    test_moving_average/test_authenticator) оставляет в sys.modules свой НЕПОЛНЫЙ
    фейк MetaTrader5 (без ORDER_TYPE_BUY и без __getattr__). Если первый импорт
    trading приходится на такой момент — import падает AttributeError.

    Чинимся через monkeypatch.setitem (авто-восстановление после теста), не трогая
    боевой код. Импорт trading делаем лениво в фикстуре, а НЕ на уровне модуля:
    ранний импорт утащил бы `indicators` под не тот mt5 и сломал legacy-тесты,
    которые сами связывают indicators.mt5 со своим фейком на этапе сборки.
    """
    current = sys.modules.get("MetaTrader5")
    if not hasattr(current, "ORDER_TYPE_BUY"):
        stub = types.ModuleType("MetaTrader5")
        stub.__getattr__ = lambda name: (lambda *a, **k: None)  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "MetaTrader5", stub)


@pytest.fixture
def patched_trading(monkeypatch):
    """Возвращает namespace с Trading() и подменёнными фейками."""
    _ensure_importable_mt5(monkeypatch)
    import trading as trading_mod
    fake_mt5 = FakeMT5()
    fake_cache = FakeCache()
    fake_status = FakeStatus()
    monkeypatch.setattr(trading_mod, "mt5", fake_mt5)
    monkeypatch.setattr(trading_mod, "cache", fake_cache)
    monkeypatch.setattr(trading_mod, "status", fake_status)
    return SimpleNamespace(
        trading=trading_mod.Trading(),
        mt5=fake_mt5, cache=fake_cache, status=fake_status,
    )
