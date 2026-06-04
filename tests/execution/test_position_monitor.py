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


async def test_run_emits_position_update_and_metrics(position_monitor_agent_factory):
    pos = make_mt5_position(ticket=1001, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    await h.agent.run()
    updates = [e for e in h.bus.events if e.type == EventType.POSITION_UPDATE]
    assert len(updates) == 1
    assert len(updates[0].payload["positions"]) == 1
    assert h.agent.metrics["open_positions"] == 1
    assert 1001 in h.agent._prev_positions


async def test_run_detects_disappeared_position(position_monitor_agent_factory):
    # 1-й цикл: позиция есть; 2-й: пропала → ORDER_CLOSED
    pos = make_mt5_position(ticket=1001, symbol="XAUUSD", magic=777)
    h = position_monitor_agent_factory(
        positions=[pos], streams={"s1": make_stream(magic=777)},
        status_seed={"XAUUSD": 1},
    )
    await h.agent.run()                       # зафиксировали в _prev_positions
    h.trading.positions_list = []             # позиция исчезла
    await h.agent.run()
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    assert closed[0].payload["ticket"] == 1001


async def test_run_checks_exit_only_for_pending_symbols(position_monitor_agent_factory):
    # exit проверяется только для символов с новой свечой
    pos = make_mt5_position(symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        positions=[pos], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    # без pending — exit не вызывается
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []
    # с pending по символу — вызывается
    await h.agent._on_new_bar(_bar_event("XAUUSD"))
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert h.agent._pending_exit_symbols == set()   # очищено


def _prev(ticket=1001, symbol="XAUUSD", type="BUY", open_price=1899.0, magic=777):
    return {"ticket": ticket, "symbol": symbol, "type": type, "open_price": open_price, "magic": magic}


async def test_disappeared_emits_order_closed_and_resets_status(position_monitor_agent_factory):
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": make_stream(magic=777)},
        status_seed={"XAUUSD": 1},   # OPEN
        deals=[make_deal(comment="tp hit")],
    )
    await h.agent._on_position_disappeared(_prev())
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    assert closed[0].payload["reason"] == "TP"
    assert closed[0].payload["stream_id"] == "s1"
    # статус сброшен OPEN→ALLOWED + TRADING_STATUS_CHANGED
    assert h.status.status_of("XAUUSD") == 0
    changed = [e for e in h.bus.events if e.type == EventType.TRADING_STATUS_CHANGED]
    assert len(changed) == 1
    assert changed[0].payload["status"] == 0


async def test_disappeared_hedge_sibling_keeps_status(position_monitor_agent_factory):
    # есть «сосед» по той же magic+symbol → статус НЕ сбрасывается
    sibling = make_mt5_position(ticket=2002, symbol="XAUUSD", magic=777)
    h = position_monitor_agent_factory(
        positions=[sibling], streams={"s1": make_stream(magic=777)},
        status_seed={"XAUUSD": 1},
    )
    await h.agent._on_position_disappeared(_prev(ticket=1001))
    assert h.status.status_of("XAUUSD") == 1   # остался OPEN
    assert [e for e in h.bus.events if e.type == EventType.TRADING_STATUS_CHANGED] == []


async def test_disappeared_calls_on_trade_closed(position_monitor_agent_factory):
    rstrat = make_runtime_strategy()
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(comment="manual")],
    )
    await h.agent._on_position_disappeared(_prev())
    assert len(rstrat.closed_calls) == 1
    assert rstrat.closed_calls[0][1] == "MANUAL"


async def test_disappeared_on_trade_closed_exception_does_not_crash(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(raise_on_closed=True)
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(comment="manual")],
    )
    await h.agent._on_position_disappeared(_prev())   # не должно бросить
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1   # ORDER_CLOSED всё равно был эмитнут до хука
