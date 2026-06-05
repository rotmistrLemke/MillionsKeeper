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
    monkeypatch.setattr(trading_mod.time, "sleep", lambda *a, **k: None)
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
             deals=None, calc_result=None):
        import agents.execution_agent as ea_mod
        import streams as streams_mod
        import strategies as strat_mod
        import market_data_cache as mdc_mod

        fake_mt5 = FakeMT5()
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


@pytest.fixture
def position_monitor_agent_factory(monkeypatch):
    """Фабрика PositionMonitorAgent с подменёнными зависимостями.

    status → реальный TradingStatusRegistry(seed); streams.registry/STRATEGIES/
    get_runtime_strategy/cache/sys.modules['MetaTrader5']/talib.ATR — фейки.
    Прод не трогаем. trading не импортируется на уровне модуля.
    """
    from tests.execution.fakes import (
        FakeMT5, FakeCache, FakeTrading, FakeBus, FakeRegistry, make_runtime_strategy,
    )

    def make(*, positions=None, streams=None, strategies=None, runtime_strategy=None,
             status_seed=None, symbol="XAUUSD", rates_df=None, deals=None,
             atr=2.0, modify_result=True):
        import agents.position_monitor_agent as pm_mod
        import streams as streams_mod
        import strategies as strat_mod
        import strategies.runtime as runtime_mod
        import market_data_cache as mdc_mod
        import talib
        from trading_status import TradingStatusRegistry

        fake_mt5 = FakeMT5()
        fake_mt5.symbol_infos[symbol] = SimpleNamespace(point=0.01)
        if deals is not None:
            fake_mt5.deals = deals
        fake_cache = FakeCache()
        fake_cache.rates_df = rates_df
        fake_trading = FakeTrading()
        fake_trading.positions_list = positions or []
        fake_trading._modify_result = modify_result
        fake_registry = FakeRegistry(streams or {})
        real_status = TradingStatusRegistry(
            seed=status_seed if status_seed is not None else {symbol: 0}
        )
        strat_map = {} if strategies is None else strategies
        rstrat = runtime_strategy if runtime_strategy is not None else make_runtime_strategy()

        monkeypatch.setattr(pm_mod, "status", real_status)
        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(strat_mod, "STRATEGIES", strat_map)
        monkeypatch.setattr(runtime_mod, "get_runtime_strategy", lambda name, sym: rstrat)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
        monkeypatch.setattr(talib, "ATR", lambda h, l, c, timeperiod=14: [atr] * len(c))

        agent = pm_mod.PositionMonitorAgent("PositionMonitor", FakeBus(), fake_trading,
                                            poll_interval=0)
        return SimpleNamespace(
            agent=agent, bus=agent.bus, trading=fake_trading, mt5=fake_mt5,
            cache=fake_cache, status=real_status, registry=fake_registry,
            runtime_strategy=rstrat,
        )

    return make


@pytest.fixture
def signal_agent_factory(monkeypatch):
    """Фабрика SignalAgent с подменённым status. Прод не трогаем.

    Драйв: положить INDICATORS_READY-event в agent._queue, затем `await agent.run()`
    (run читает ровно одно событие из очереди и завершается).
    """
    from tests.execution.fakes import FakeStatus, FakeBus

    def make(*, status_map=None):
        import agents.signal_agent as sa_mod

        fake_status = FakeStatus()
        if status_map:
            fake_status._status.update(status_map)
        monkeypatch.setattr(sa_mod, "status", fake_status)

        agent = sa_mod.SignalAgent("Signal", FakeBus())
        return SimpleNamespace(agent=agent, bus=agent.bus, status=fake_status)

    return make


@pytest.fixture
def market_data_agent_factory(monkeypatch):
    """Фабрика MarketDataAgent с подменёнными зависимостями. Прод не трогаем.

    Патчит streams.registry, agents.market_data_agent.status,
    market_data_cache.cache, sys.modules['MetaTrader5']. poll_interval=0.
    `trading` не импортируется (инвариант трека).
    """
    from tests.execution.fakes import FakeMT5, FakeCache, FakeStatus, FakeBus, FakeRegistry

    def make(*, streams=None, rates_df=None, terminal=True, disabled=None):
        import agents.market_data_agent as md_mod
        import streams as streams_mod
        import market_data_cache as mdc_mod

        fake_mt5 = FakeMT5()
        fake_mt5.terminal = None if terminal is None else fake_mt5.terminal
        fake_cache = FakeCache()
        fake_cache.rates_df = rates_df
        fake_status = FakeStatus()
        for sym in (disabled or []):
            fake_status.mark_disabled(sym)
        fake_registry = FakeRegistry(streams or {})

        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(md_mod, "status", fake_status)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)

        agent = md_mod.MarketDataAgent("MarketData", FakeBus(), poll_interval=0)
        return SimpleNamespace(
            agent=agent, bus=agent.bus, registry=fake_registry,
            status=fake_status, cache=fake_cache, mt5=fake_mt5,
        )

    return make
