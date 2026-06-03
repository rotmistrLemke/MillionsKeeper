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


@pytest.fixture
def execution_agent_factory(monkeypatch):
    """Фабрика ExecutionAgent с подменёнными зависимостями.

    Подменяет: agents.execution_agent.status, streams.registry,
    strategies.STRATEGIES, market_data_cache.cache, sys.modules['MetaTrader5'],
    agents.execution_agent.datetime. Прод не трогаем.
    """
    from tests.execution.fakes import (
        FakeMT5, FakeCache, FakeStatus, FakeTrading, FakeBus, FakeRegistry, make_clock,
    )

    def make(*, streams=None, strategies=None, now=None,
             positions=None, deals=None, calc_result=None):
        import agents.execution_agent as ea_mod
        import streams as streams_mod
        import strategies as strat_mod
        import market_data_cache as mdc_mod

        fake_mt5 = FakeMT5()
        if positions is not None:
            fake_mt5.positions = positions
        if deals is not None:
            fake_mt5.deals = deals
        fake_cache = FakeCache()
        fake_status = FakeStatus()
        fake_trading = FakeTrading()
        if calc_result is not None:
            fake_trading.set_calc_result(calc_result)
        fake_registry = FakeRegistry(streams or {})
        strat_map = {} if strategies is None else strategies

        monkeypatch.setattr(ea_mod, "status", fake_status)
        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(strat_mod, "STRATEGIES", strat_map)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
        if now is not None:
            monkeypatch.setattr(ea_mod, "datetime", make_clock(now))

        agent = ea_mod.ExecutionAgent("Execution", FakeBus(), fake_trading)
        return SimpleNamespace(
            agent=agent, bus=agent.bus, trading=fake_trading,
            mt5=fake_mt5, cache=fake_cache, status=fake_status, registry=fake_registry,
        )

    return make
