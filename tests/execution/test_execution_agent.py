"""Характеризационные тесты ExecutionAgent (слайс E2).

Прод (agents/execution_agent.py) не меняется. Тесты фиксируют текущее поведение:
gating, ночная блокировка, DD-блок, equity, SL/TP по ATR, хедж, эмит/метрики,
закрытие, _reason_to_tag. Зависимости подменяются фикстурой execution_agent_factory.
"""
import asyncio
from datetime import datetime

import pytest

from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_deal, make_position, make_strategy,
)


def _signal_event(**payload):
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("signal", "BUY")
    payload.setdefault("indicators", {})
    return Event(type=EventType.SIGNAL_GENERATED, source="test", payload=payload)


def _close_event(**payload):
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("ticket", 555)
    return Event(type=EventType.ORDER_CLOSE_REQUEST, source="test", payload=payload)


@pytest.mark.parametrize("reason,expected", [
    ("strategy:ema50", "SIGNAL"),
    ("rsi_overbought", "RSI"),
    ("sl", "SL"),
    ("stop_loss", "SL"),
    ("tp", "TP"),
    ("take_profit", "TP"),
    ("manual_close_by_user", "MANUAL"),
    ("something_else_long_reason_text", "something_else_long_"),  # [:20]
    (None, "MANUAL"),
])
def test_reason_to_tag(execution_agent_factory, reason, expected):
    h = execution_agent_factory()
    assert h.agent._reason_to_tag(reason) == expected


async def test_no_signal_does_not_open(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD")
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="NO_SIGNAL"))
    assert h.trading.open_calls == []


async def test_trading_status_nonzero_rejects(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD")
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    h.status._status["XAUUSD"] = 1   # OPEN
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_no_stream_skips(execution_agent_factory):
    h = execution_agent_factory(streams={}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_disabled_stream_skips(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", enabled=False)
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_stream_selected_by_id_when_provided(execution_agent_factory):
    by_id = make_stream(id="s2", symbol="XAUUSD", name="ById")
    by_sym = make_stream(id="s1", symbol="XAUUSD", name="BySym")
    h = execution_agent_factory(
        streams={"s1": by_sym, "s2": by_id}, now=datetime(2026, 6, 3, 12, 0),
    )
    await h.agent._handle_signal(_signal_event(signal="BUY", stream_id="s2"))
    # comment в orderOpen начинается с id потока → подтверждает выбор by-id (s2).
    assert h.trading.open_calls
    assert h.trading.open_calls[0]["comment"].startswith("s2:")
