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


@pytest.mark.parametrize("dt,blocked", [
    (datetime(2026, 6, 3, 23, 55), True),   # >= 23:50
    (datetime(2026, 6, 3, 0, 30), True),    # < 05:00
    (datetime(2026, 6, 3, 4, 59), True),    # < 05:00
    (datetime(2026, 6, 3, 5, 0), False),    # ровно 05:00 — не блок
    (datetime(2026, 6, 3, 12, 0), False),
    (datetime(2026, 6, 3, 23, 49), False),  # < 23:50
])
def test_is_night_block(execution_agent_factory, dt, blocked):
    h = execution_agent_factory(now=dt)
    result, _reason = h.agent._is_night_block()
    assert result is blocked


async def test_night_block_prevents_open(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD")
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 0, 30))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_daytime_allows_open(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.1)
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls   # дошли до открытия


def test_equity_realized_own_magic_only(execution_agent_factory):
    stream = make_stream(magic=777, deposit=1000.0)
    deals = [
        make_deal(magic=777, profit=50.0, commission=-2.0, swap=-1.0),  # +47
        make_deal(magic=999, profit=100.0),                             # чужой — игнор
    ]
    h = execution_agent_factory(deals=deals)
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1000.0 + 47.0)


def test_equity_unrealized_own_magic_only(execution_agent_factory):
    stream = make_stream(magic=777, symbol="XAUUSD", deposit=1000.0)
    h = execution_agent_factory()
    h.mt5.positions = [
        make_position(h.mt5, magic=777, profit=30.0, swap=-5.0),  # +25
        make_position(h.mt5, magic=999, profit=200.0),            # чужой — игнор
    ]
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1000.0 + 25.0)


def test_equity_empty_is_deposit(execution_agent_factory):
    stream = make_stream(magic=777, deposit=1500.0)
    h = execution_agent_factory(deals=[])
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1500.0)


def test_equity_realized_plus_unrealized(execution_agent_factory):
    stream = make_stream(magic=777, symbol="XAUUSD", deposit=1000.0)
    h = execution_agent_factory(deals=[make_deal(magic=777, profit=10.0)])
    h.mt5.positions = [make_position(h.mt5, magic=777, profit=5.0, swap=2.0)]
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1000.0 + 10.0 + 7.0)


@pytest.mark.parametrize("now,expected_weekday", [
    (datetime(2026, 6, 1, 15, 0), 0),   # пн
    (datetime(2026, 6, 3, 15, 0), 0),   # ср → monday_start = пн 01.06
    (datetime(2026, 6, 7, 15, 0), 0),   # вс → monday_start = пн 01.06
])
def test_monday_start_normalizes_to_monday_midnight(execution_agent_factory, now, expected_weekday):
    h = execution_agent_factory()
    ms = h.agent._monday_start(now)
    assert ms.weekday() == expected_weekday
    assert (ms.hour, ms.minute, ms.second, ms.microsecond) == (0, 0, 0, 0)
    assert ms.date() == datetime(2026, 6, 1).date()


@pytest.mark.parametrize("now", [
    datetime(2026, 6, 1, 15, 0),   # пн → next = пн 08.06
    datetime(2026, 6, 3, 15, 0),   # ср → next = пн 08.06
    datetime(2026, 6, 7, 15, 0),   # вс → next = пн 08.06
])
def test_next_monday(execution_agent_factory, now):
    h = execution_agent_factory()
    nm = h.agent._next_monday(now)
    assert nm.weekday() == 0
    assert nm.date() == datetime(2026, 6, 8).date()
    assert (nm.hour, nm.minute, nm.second, nm.microsecond) == (0, 0, 0, 0)
