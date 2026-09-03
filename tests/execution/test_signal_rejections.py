"""Каждый отказ в исполнении попадает в журнал сигналов.

Разрыв между модельными и живыми входами (cci_rsi 2 из 18 за август)
раскладывается по причинам только если причина отказа где-то оседает.
Тесты держат покрытие всех точек, где сигнал не доходит до ордера.
"""
from datetime import datetime

import pytest

from core.events import Event, EventType
from signals.journal import Reason
from tests.execution.fakes import make_stream, make_strategy


def _signal_event(**payload):
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("signal", "BUY")
    payload.setdefault("indicators", {})
    return Event(type=EventType.SIGNAL_GENERATED, source="test", payload=payload)


@pytest.fixture
def rejections(monkeypatch):
    """Перехватывает записи журнала, не трогая диск."""
    import agents.execution_agent as ea_mod
    calls = []

    def fake_record(**kw):
        calls.append(kw)

    monkeypatch.setattr(ea_mod.journal, "record", fake_record)
    return calls


DAY = datetime(2026, 6, 3, 12, 0)
NIGHT = datetime(2026, 6, 3, 0, 30)


async def test_symbol_disabled_is_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD")}, now=DAY)
    h.status.mark_disabled("XAUUSD")
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.SYMBOL_DISABLED]
    assert rejections[0]["symbol"] == "XAUUSD"
    assert rejections[0]["signal"] == "BUY"


async def test_no_stream_is_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(streams={}, now=DAY)
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.NO_STREAM]


async def test_disabled_stream_is_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", enabled=False, strategy="cci_rsi")}, now=DAY)
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.STREAM_DISABLED]
    assert rejections[0]["strategy"] == "cci_rsi"
    assert rejections[0]["stream_id"] == "s1"


async def test_busy_stream_is_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="triple_ema")}, now=DAY)
    h.registry.mark_stream_open("s1")
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.STREAM_BUSY]
    assert rejections[0]["strategy"] == "triple_ema"


async def test_night_block_is_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD")}, now=NIGHT)
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.NIGHT_BLOCK]
    assert "23:50" in rejections[0]["detail"]


async def test_drawdown_block_is_journaled(execution_agent_factory, rejections, monkeypatch):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD")}, now=DAY)
    monkeypatch.setattr(h.agent, "_check_stream_drawdown",
                        lambda stream: (False, "просадка потока 40.0% > 35%"))
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.DRAWDOWN_BLOCK]
    assert "40.0%" in rejections[0]["detail"]


async def test_order_failure_is_journaled(execution_agent_factory, rejections, monkeypatch):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD", volume=0.1)}, now=DAY)
    monkeypatch.setattr(h.agent, "_open_order", lambda *a: None)
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.ORDER_FAILED]


async def test_order_exception_is_journaled(execution_agent_factory, rejections, monkeypatch):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD", volume=0.1)}, now=DAY)

    def boom(*a):
        raise RuntimeError("no money")

    monkeypatch.setattr(h.agent, "_open_order", boom)
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.ORDER_ERROR]
    assert "no money" in rejections[0]["detail"]


async def test_hedge_failure_is_journaled(execution_agent_factory, rejections, monkeypatch):
    stream = make_stream(symbol="XAUUSD", volume=0.1, strategy="default_hedge")
    h = execution_agent_factory(
        streams={"s1": stream}, strategies={"default_hedge": make_strategy(hedge=True)},
        now=DAY)
    monkeypatch.setattr(h.agent, "_open_hedge_order", lambda *a: None)
    await h.agent._handle_signal(_signal_event())
    assert [c["reason"] for c in rejections] == [Reason.HEDGE_FAILED]


# ── чего в журнале быть не должно ─────────────────────────────────────

async def test_no_signal_is_not_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD")}, now=DAY)
    await h.agent._handle_signal(_signal_event(signal="NO_SIGNAL"))
    assert rejections == [], "NO_SIGNAL — отсутствие сигнала, а не отказ"


async def test_successful_open_is_not_journaled(execution_agent_factory, rejections):
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD", volume=0.1)}, now=DAY)
    await h.agent._handle_signal(_signal_event())
    assert h.trading.open_calls, "ордер должен был открыться"
    assert rejections == []


async def test_journal_failure_does_not_block_trading(execution_agent_factory, monkeypatch):
    """Журнал — диагностика: его поломка не должна мешать торговле."""
    import agents.execution_agent as ea_mod

    def boom(**kw):
        raise RuntimeError("db is gone")

    monkeypatch.setattr(ea_mod.journal, "record", boom)
    h = execution_agent_factory(streams={"s1": make_stream(symbol="XAUUSD")}, now=DAY)
    h.registry.mark_stream_open("s1")
    await h.agent._handle_signal(_signal_event())      # не бросает
    assert h.trading.open_calls == []
