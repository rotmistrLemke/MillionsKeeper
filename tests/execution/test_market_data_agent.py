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
