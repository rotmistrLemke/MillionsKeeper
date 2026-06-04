"""Характеризационные тесты PositionMonitorAgent (слайс E3).

Прод (agents/position_monitor_agent.py) не меняется. Тесты фиксируют текущее
поведение: снапшот позиций + P&L, жизненный цикл (исчезновение/закрытие/сброс
статуса), трейлинг/breakeven SL, exit-сигналы (стратегия/legacy-RSI, хедж).
Зависимости — фикстура position_monitor_agent_factory. trading НЕ импортируется
на уровне модуля (инвариант E1b).

Дефолты: tick bid=1900.0/ask=1900.5; symbol_info point=0.01; ATR=2.0 (замокан).
"""
import pandas as pd
import pytest

from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_deal, make_mt5_position, make_runtime_strategy, make_rsi, make_rates,
)


def _bar_event(symbol="XAUUSD"):
    return Event(type=EventType.NEW_BAR, source="test", payload={"symbol": symbol})


def test_pnl_buy_points(position_monitor_agent_factory):
    # BUY: (bid 1900.0 - open 1899.0)/point 0.01 = 100.0
    pos = make_mt5_position(type=0, price_open=1899.0, profit=12.34, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    out = h.agent._get_positions_with_pnl()
    assert len(out) == 1
    assert out[0]["type"] == "BUY"
    assert out[0]["pnl_points"] == pytest.approx(100.0)
    assert out[0]["pnl_money"] == pytest.approx(12.34)
    assert out[0]["stream_id"] == "s1"


def test_pnl_sell_points(position_monitor_agent_factory):
    # SELL: (open 1901.5 - ask 1900.5)/point 0.01 = 100.0
    pos = make_mt5_position(type=1, price_open=1901.5, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    out = h.agent._get_positions_with_pnl()
    assert out[0]["type"] == "SELL"
    assert out[0]["pnl_points"] == pytest.approx(100.0)


def test_pnl_tick_none_zero(position_monitor_agent_factory):
    pos = make_mt5_position(type=0, price_open=1899.0, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    h.mt5.tick = None
    out = h.agent._get_positions_with_pnl()
    assert out[0]["pnl_points"] == 0.0


def test_pnl_stream_none_when_magic_unknown(position_monitor_agent_factory):
    pos = make_mt5_position(magic=999)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    out = h.agent._get_positions_with_pnl()
    assert out[0]["stream_id"] is None
    assert out[0]["stream_name"] is None


async def test_on_new_bar_adds_symbol(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    await h.agent._on_new_bar(_bar_event("XAUUSD"))
    assert "XAUUSD" in h.agent._pending_exit_symbols


async def test_on_new_bar_empty_symbol_ignored(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    await h.agent._on_new_bar(Event(type=EventType.NEW_BAR, source="test", payload={}))
    assert h.agent._pending_exit_symbols == set()
