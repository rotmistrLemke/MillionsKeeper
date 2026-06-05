"""Характеризация MarketDataAgent (E4). Прод не трогаем."""
import pytest
from core.events import EventType
from tests.execution.fakes import make_stream, make_bars_df


def _types(h):
    return [e.type for e in h.bus.events]


def _payload(h, etype):
    for e in h.bus.events:
        if e.type == etype:
            return e.payload
    return None


async def test_current_pairs_dedup(market_data_agent_factory):
    h = market_data_agent_factory(streams={
        "s1": make_stream(id="s1", symbol="XAUUSD", timeframe=16385),
        "s2": make_stream(id="s2", symbol="XAUUSD", timeframe=16385),
    }, rates_df=make_bars_df(time=1000))
    await h.agent.run()
    assert h.agent.metrics["pairs"] == 1
    assert h.agent.metrics["symbols"] == 1


async def test_current_pairs_skips_disabled_status(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
        disabled=["XAUUSD"],
    )
    await h.agent.run()
    assert h.agent.metrics["pairs"] == 0


async def test_current_pairs_skips_disabled_stream(market_data_agent_factory):
    h = market_data_agent_factory(streams={
        "s1": make_stream(id="s1", symbol="XAUUSD", enabled=True),
        "s2": make_stream(id="s2", symbol="EURUSD", enabled=False),
    }, rates_df=make_bars_df(time=1000))
    await h.agent.run()
    assert h.agent.metrics["symbols"] == 1
    assert h.agent.metrics["pairs"] == 1


async def test_current_pairs_distinct_symbols(market_data_agent_factory):
    h = market_data_agent_factory(streams={
        "s1": make_stream(id="s1", symbol="XAUUSD", timeframe=16385),
        "s2": make_stream(id="s2", symbol="EURUSD", timeframe=16385),
        "s3": make_stream(id="s3", symbol="XAUUSD", timeframe=16408),
    }, rates_df=make_bars_df(time=1000))
    await h.agent.run()
    assert h.agent.metrics["symbols"] == 2
    assert h.agent.metrics["pairs"] == 3


async def test_emits_cache_invalidated(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert h.cache.invalidated is True
    assert _payload(h, EventType.MARKET_CACHE_INVALIDATED) == {"pairs": 1}


async def test_terminal_disconnected(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
        terminal=None,
    )
    await h.agent.run()
    types = _types(h)
    assert EventType.MT5_DISCONNECTED in types
    assert EventType.MT5_CONNECTED not in types
    assert EventType.NEW_BAR not in types
    # последний AGENT_STATUS — error
    statuses = [e.payload["status"] for e in h.bus.events
                if e.type == EventType.AGENT_STATUS]
    assert statuses[-1] == "error"


async def test_terminal_connected(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert EventType.MT5_CONNECTED in _types(h)


async def test_first_sight_records_no_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert h.agent.metrics["new_bars"] == 0
    assert EventType.NEW_BAR not in _types(h)
    assert h.agent._last_bar_times[("XAUUSD", 16385)] == 1000


async def test_second_run_greater_time_emits_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()                       # первый показ
    h.cache.rates_df = make_bars_df(time=2000)
    await h.agent.run()                       # новая свеча
    bars = [e for e in h.bus.events if e.type == EventType.NEW_BAR]
    assert len(bars) == 1
    assert bars[0].payload == {"symbol": "XAUUSD", "bar_time": 2000, "timeframe": 16385}


async def test_second_run_equal_time_no_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    await h.agent.run()                       # тот же time
    assert EventType.NEW_BAR not in _types(h)


async def test_second_run_lesser_time_no_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=2000),
    )
    await h.agent.run()
    h.cache.rates_df = make_bars_df(time=1000)
    await h.agent.run()                       # время «откатилось»
    assert EventType.NEW_BAR not in _types(h)


async def test_rates_none_skipped(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=None,
    )
    await h.agent.run()
    assert h.agent.metrics["new_bars"] == 0
    assert EventType.NEW_BAR not in _types(h)


async def test_rates_empty_skipped(market_data_agent_factory):
    import pandas as pd
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=pd.DataFrame({"time": []}),
    )
    await h.agent.run()
    assert h.agent.metrics["new_bars"] == 0


async def test_time_pd_timestamp_normalized(market_data_agent_factory):
    import pandas as pd
    ts = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=ts),
    )
    await h.agent.run()
    assert h.agent._last_bar_times[("XAUUSD", 16385)] == int(ts.timestamp())


async def test_time_int_normalized(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1234567890),
    )
    await h.agent.run()
    assert h.agent._last_bar_times[("XAUUSD", 16385)] == 1234567890


async def test_removed_pair_cleared_between_runs(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(id="s1", symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert ("XAUUSD", 16385) in h.agent._last_bar_times
    # пара исчезла из потоков
    h.registry._streams.clear()
    await h.agent.run()
    assert ("XAUUSD", 16385) not in h.agent._last_bar_times


async def test_symbol_exception_caught(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    def boom(*a, **k):
        raise RuntimeError("rates boom")
    h.cache.get_rates = boom
    # не должно бросить наружу; статус доходит до IDLE
    await h.agent.run()
    statuses = [e.payload["status"] for e in h.bus.events
                if e.type == EventType.AGENT_STATUS]
    assert statuses[-1] == "idle"
    assert h.agent.metrics["new_bars"] == 0
