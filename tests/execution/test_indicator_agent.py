"""Характеризация IndicatorAgent (E5). Прод не трогаем."""
import pytest
from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_bars_df, make_indicator_strategy,
    fake_moving_average, fake_macd, fake_rsi_ind, fake_atr_ind,
    fake_adx_ind, fake_alligator,
)


async def _feed(h, payload, correlation_id=None):
    ev = Event(type=EventType.NEW_BAR, source="t",
               payload=payload, correlation_id=correlation_id)
    h.agent._queue.put_nowait(ev)
    await h.agent.run()


def _ready(h):
    for e in h.bus.events:
        if e.type == EventType.INDICATORS_READY:
            return e
    return None


def _statuses(h):
    return [e.payload["status"] for e in h.bus.events
            if e.type == EventType.AGENT_STATUS]


def _stub_calcs(h, recorder):
    """Подменяет оба calc-метода; пишет, какой позван, и возвращает маркер-dict."""
    def strat(symbol, name, tf):
        recorder.append(("strategy", symbol, name, tf))
        return {"symbol": symbol, "via": "strategy"}
    def default(symbol, tf):
        recorder.append(("default", symbol, tf))
        return {"symbol": symbol, "via": "default"}
    h.agent._calc_strategy = strat
    h.agent._calc_indicators = default


async def test_no_stream_early_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={})  # by_symbol → None
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert rec == []  # ни один calc не позван


async def test_disabled_stream_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", enabled=False, timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert rec == []


async def test_timeframe_mismatch_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16408})  # ≠ 16385
    assert _ready(h) is None
    assert rec == []


async def test_bar_tf_zero_skips_tf_check(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 0})  # falsy → tf-проверка пропущена
    assert _ready(h) is not None
    assert rec and rec[0][0] == "default"
