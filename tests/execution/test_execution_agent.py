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
