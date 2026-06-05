"""Характеризация SignalAgent (E4). Прод не трогаем."""
import pytest
from core.events import Event, EventType


def _run_signal(h):
    """Вернуть payload первого SIGNAL_GENERATED."""
    for e in h.bus.events:
        if e.type == EventType.SIGNAL_GENERATED:
            return e
    return None


async def _feed(h, payload, correlation_id=None):
    ev = Event(type=EventType.INDICATORS_READY, source="t",
               payload=payload, correlation_id=correlation_id)
    h.agent._queue.put_nowait(ev)
    await h.agent.run()


async def test_entry_signal_buy_wins_over_legacy(signal_agent_factory):
    h = signal_agent_factory()
    # legacy сказал бы SELL, но entry_signal=BUY перебивает
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "BUY",
        "signal_ma": "SELL", "signal_critical_angle": "SELL",
        "macd_signal": "SELL", "rsi_signal": "SELL",
    })
    assert _run_signal(h).payload["signal"] == "BUY"
    assert h.agent.metrics["buy_signals"] == 1
    assert h.agent.metrics["sell_signals"] == 0


async def test_entry_signal_sell(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "SELL"})
    assert _run_signal(h).payload["signal"] == "SELL"
    assert h.agent.metrics["sell_signals"] == 1


async def test_entry_no_signal_short_circuits_legacy(signal_agent_factory):
    """entry_signal=NO_SIGNAL перебивает даже полностью-BUY legacy (нюанс)."""
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "NO_SIGNAL",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
    })
    assert _run_signal(h).payload["signal"] == "NO_SIGNAL"
    assert h.agent.metrics["buy_signals"] == 0


async def test_entry_signal_missing_falls_to_legacy(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",  # entry_signal отсутствует
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
    })
    assert _run_signal(h).payload["signal"] == "BUY"


async def test_entry_signal_garbage_falls_to_legacy(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "FOO",
        "signal_ma": "SELL", "signal_critical_angle": "SELL",
        "macd_signal": "SELL", "rsi_signal": "SELL",
    })
    assert _run_signal(h).payload["signal"] == "SELL"
