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


async def test_legacy_all_buy(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
    })
    assert _run_signal(h).payload["signal"] == "BUY"
    assert h.agent.metrics["buy_signals"] == 1


async def test_legacy_all_sell(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",
        "signal_ma": "SELL", "signal_critical_angle": "SELL",
        "macd_signal": "SELL", "rsi_signal": "SELL",
    })
    assert _run_signal(h).payload["signal"] == "SELL"
    assert h.agent.metrics["sell_signals"] == 1


async def test_legacy_mixed_is_no_signal(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "NO_SIGNAL",
    })
    assert _run_signal(h).payload["signal"] == "NO_SIGNAL"
    assert h.agent.metrics["buy_signals"] == 0
    assert h.agent.metrics["sell_signals"] == 0


async def test_legacy_missing_keys_default_no_signal(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD"})  # ни одного legacy-ключа
    assert _run_signal(h).payload["signal"] == "NO_SIGNAL"


async def test_correlation_id_passthrough(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY"},
                correlation_id="cid-42")
    assert _run_signal(h).correlation_id == "cid-42"


async def test_trading_status_and_stream_id_passthrough(signal_agent_factory):
    h = signal_agent_factory(status_map={"XAUUSD": 1})
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY", "stream_id": "s7"})
    p = _run_signal(h).payload
    assert p["trading_status"] == 1
    assert p["stream_id"] == "s7"


async def test_indicators_dict_keys_present(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "BUY",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
        "rsi_value": 55.0, "atr_value": 2.0, "adx_value": 30.0,
        "ema8": 1900.0, "ema21": 1899.0,
    })
    ind = _run_signal(h).payload["indicators"]
    assert ind == {
        "ma": "BUY", "ma_angle": "BUY", "macd": "BUY", "rsi": "BUY",
        "rsi_value": 55.0, "atr_value": 2.0, "adx_value": 30.0,
        "ema8": 1900.0, "ema21": 1899.0,
    }


async def test_indicators_dict_missing_values_are_none(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY"})
    ind = _run_signal(h).payload["indicators"]
    assert ind["rsi_value"] is None
    assert ind["atr_value"] is None
    assert ind["ema8"] is None
    # legacy-сигналы при отсутствии дефолтятся в "NO_SIGNAL"
    assert ind["ma"] == "NO_SIGNAL"


async def test_emits_agent_status_then_signal(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY"})
    types = [e.type for e in h.bus.events]
    # idle (старт) → running → SIGNAL_GENERATED
    assert types.count(EventType.AGENT_STATUS) == 2
    assert types[-1] == EventType.SIGNAL_GENERATED


async def test_no_signal_does_not_increment_metrics(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "NO_SIGNAL"})
    assert h.agent.metrics["buy_signals"] == 0
    assert h.agent.metrics["sell_signals"] == 0
