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
    make_stream, make_deal, make_mt5_position, make_runtime_strategy, make_rsi,
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


@pytest.mark.parametrize("comment,expected", [
    ("sl 1897.0", "SL"),
    ("stop loss", "SL"),
    ("tp reached", "TP"),
    ("take profit", "TP"),
    ("strategy:ema", "SIGNAL"),
    ("manual close", "MANUAL"),
])
def test_classify_close_reason_from_comment(position_monitor_agent_factory, comment, expected):
    h = position_monitor_agent_factory(deals=[make_deal(comment=comment)])
    assert h.agent._classify_close_reason(1001) == expected


def test_classify_close_reason_no_deals(position_monitor_agent_factory):
    h = position_monitor_agent_factory(deals=[])
    assert h.agent._classify_close_reason(1001) == "MANUAL"


def test_classify_close_reason_exception(position_monitor_agent_factory, monkeypatch):
    h = position_monitor_agent_factory()
    def boom(*a, **k):
        raise RuntimeError("hist boom")
    monkeypatch.setattr(h.mt5, "history_deals_get", boom)
    assert h.agent._classify_close_reason(1001) == "MANUAL"


# ---------------------------------------------------------------------------
# _apply_trailing_sl — характеризационные тесты (Task 7, E3)
# ---------------------------------------------------------------------------

def _posd(ticket=1001, symbol="XAUUSD", type="BUY", open_price=1899.0, sl=0.0, magic=777):
    return {"ticket": ticket, "symbol": symbol, "type": type, "open_price": open_price,
            "sl": sl, "magic": magic}


def test_trail_no_stream_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={})   # by_magic → None
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_no_be_no_trail_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_rates_none_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.mt5.rates = []                # len 0 < 15
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_atr_zero_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)}, atr=0.0)
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_tick_none_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.mt5.tick = None
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_buy_breakeven_sets_entry(position_monitor_agent_factory):
    # bid 1900 - entry 1897 = 3.0 >= be(1.0)*atr(2.0)=2.0 → candidate=entry=1897.0
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=1.0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd(open_price=1897.0, sl=0.0))
    assert len(h.trading.modify_calls) == 1
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1897.0)
    assert 1001 in h.agent._be_done


def test_trail_buy_breakeven_idempotent(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=1.0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd(open_price=1897.0))   # 1-й раз — двигает
    h.agent._apply_trailing_sl(_posd(open_price=1897.0))   # 2-й — _be_done, trail off → нечего двигать
    assert len(h.trading.modify_calls) == 1


def test_trail_buy_trailing_sets_below_price(position_monitor_agent_factory):
    # cand = bid 1900 - trail(1.0)*atr(2.0) = 1898.0
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=0, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=0.0))
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1898.0)


def test_trail_buy_does_not_move_sl_down(position_monitor_agent_factory):
    # cur_sl=1899.0; cand=1898.0 < cur → не двигаем (и порог)
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=1899.0))
    assert h.trading.modify_calls == []


def test_trail_sell_trailing_sets_above_price(position_monitor_agent_factory):
    # SELL: cand = ask 1900.5 + trail(1.0)*atr(2.0) = 1902.5
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(type="SELL", open_price=1902.0, sl=0.0))
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1902.5)


def test_trail_threshold_skips_small_move(position_monitor_agent_factory):
    # cur_sl=1897.9; cand=1898.0; |Δ|=0.1 < 0.1*atr(2.0)=0.2 → не двигаем
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=1897.9))
    assert h.trading.modify_calls == []


def test_trail_modifysl_exception_does_not_crash(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    def boom(*a, **k):
        raise RuntimeError("modify boom")
    h.trading.modifySL = boom
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=0.0))   # не должно бросить


# ---------------------------------------------------------------------------
# _is_hedge_position / _find_paired_hedge_ticket / _check_rsi_exit (Task 8, E3)
# ---------------------------------------------------------------------------

def test_is_hedge_position(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    assert h.agent._is_hedge_position({"comment": "s1:strat:H"}) is True
    assert h.agent._is_hedge_position({"comment": "s1:strat"}) is False
    assert h.agent._is_hedge_position({"comment": ""}) is False


def test_find_paired_hedge_ticket(position_monitor_agent_factory):
    main = make_mt5_position(ticket=1001, symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    hedge = make_mt5_position(ticket=2002, symbol="XAUUSD", type=1, magic=777, comment="s1:strat:H")
    h = position_monitor_agent_factory(positions=[main, hedge], streams={"s1": make_stream(magic=777)})
    main_dict = {"ticket": 1001, "symbol": "XAUUSD", "type": "BUY", "magic": 777}
    assert h.agent._find_paired_hedge_ticket(main_dict) == 2002


def test_find_paired_hedge_none_when_absent(position_monitor_agent_factory):
    main = make_mt5_position(ticket=1001, symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    h = position_monitor_agent_factory(positions=[main], streams={"s1": make_stream(magic=777)})
    main_dict = {"ticket": 1001, "symbol": "XAUUSD", "type": "BUY", "magic": 777}
    assert h.agent._find_paired_hedge_ticket(main_dict) is None


async def test_check_rsi_exit_disabled_status_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777)},
                                       status_seed={"XAUUSD": 3})   # DISABLED
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 777, "ticket": 1001, "type": "BUY"})
    assert h.bus.events == []


async def test_check_rsi_exit_no_stream_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={}, status_seed={"XAUUSD": 0})
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 999, "ticket": 1001, "type": "BUY"})
    assert h.bus.events == []


async def test_check_rsi_exit_dispatches_to_strategy(position_monitor_agent_factory):
    # стратегия в STRATEGIES → идёт в _check_strategy_exit (get_exit_signal True → CLOSE)
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}), status_seed={"XAUUSD": 0},
    )
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 777, "ticket": 1001,
                                   "type": "BUY", "open_price": 1899.0, "volume": 0.1,
                                   "sl": 0.0, "comment": "s1:strat"})
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]


# ---------------------------------------------------------------------------
# _check_strategy_exit  (Task 9 / E3)
# ---------------------------------------------------------------------------

def _main_pos(ticket=1001, comment="s1:strat"):
    return {"ticket": ticket, "symbol": "XAUUSD", "type": "BUY", "open_price": 1899.0,
            "volume": 0.1, "sl": 0.0, "magic": 777, "comment": comment}


async def test_strategy_exit_no_rates_skips(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat, rates_df=None,
    )
    await h.agent._check_strategy_exit(_main_pos(), make_stream(magic=777, strategy="strat"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


async def test_strategy_exit_short_df_skips(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 10}),   # < 50
    )
    await h.agent._check_strategy_exit(_main_pos(), make_stream(magic=777, strategy="strat"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


async def test_strategy_exit_signal_false_no_close(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=False)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), make_stream(magic=777, strategy="strat"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


async def test_strategy_exit_main_emits_close(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=True, wants_hedge=False)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": stream}, strategies={"strat": object()},
        runtime_strategy=rstrat, rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), stream)
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 1
    assert reqs[0].payload["reason"] == "strategy:strat"


async def test_strategy_exit_main_with_hedge_closes_pair(position_monitor_agent_factory):
    # wants_hedge + парный хедж в позициях → 2 CLOSE (основная + pair_close)
    hedge = make_mt5_position(ticket=2002, symbol="XAUUSD", type=1, magic=777, comment="s1:strat:H")
    rstrat = make_runtime_strategy(exit_signal=True, wants_hedge=True)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        positions=[hedge], streams={"s1": stream}, strategies={"strat": object()},
        runtime_strategy=rstrat, rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), stream)
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 2
    reasons = {r.payload["reason"] for r in reqs}
    assert "strategy:strat" in reasons
    assert "strategy:strat:pair_close" in reasons


async def test_strategy_exit_hedge_leg_closes_only_itself(position_monitor_agent_factory):
    # хедж-нога (:H) + wants_hedge → get_hedge_exit_signal True → закрытие только ноги
    rstrat = make_runtime_strategy(hedge_exit_signal=True, wants_hedge=True)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        streams={"s1": stream}, strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(ticket=2002, comment="s1:strat:H"), stream)
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 1
    assert reqs[0].payload["reason"] == "strategy:strat:hedge"


async def test_strategy_exit_exception_does_not_crash(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(raise_on_exit=True)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        streams={"s1": stream}, strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), stream)   # не должно бросить
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


# ---------------------------------------------------------------------------
# _check_legacy_rsi_exit
# ---------------------------------------------------------------------------

async def test_legacy_rsi_buy_exit(position_monitor_agent_factory, monkeypatch):
    # BUY + RSI < 45 → RSI_EXIT_TRIGGERED + ORDER_CLOSE_REQUEST
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(40.0))
    stream = make_stream(magic=777, strategy="nonstrat")   # НЕ в STRATEGIES → legacy
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={},
                                       status_seed={"XAUUSD": 0})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "BUY"}, stream)
    assert [e for e in h.bus.events if e.type == EventType.RSI_EXIT_TRIGGERED]
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 1
    assert reqs[0].payload["reason"].startswith("RSI=")


async def test_legacy_rsi_sell_exit(position_monitor_agent_factory, monkeypatch):
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(60.0))   # SELL + >55
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "SELL"}, stream)
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]


async def test_legacy_rsi_no_exit_when_neutral(position_monitor_agent_factory, monkeypatch):
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(50.0))   # BUY: 50 не <45
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "BUY"}, stream)
    assert h.bus.events == []


async def test_legacy_rsi_no_data_skips(position_monitor_agent_factory, monkeypatch):
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(None))   # get_rsi_talib → None
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "BUY"}, stream)
    assert h.bus.events == []


# ---------------------------------------------------------------------------
# Task 11 / E3 — dispatch: _on_new_bar + run() → ORDER_CLOSE_REQUEST
# ---------------------------------------------------------------------------

async def test_dispatch_new_bar_then_run_triggers_exit(position_monitor_agent_factory):
    pos = make_mt5_position(symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        positions=[pos], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._on_new_bar(_bar_event("XAUUSD"))
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]


def test_trail_sell_breakeven_sets_entry(position_monitor_agent_factory):
    # SELL breakeven: entry 1903 - ask 1900.5 = 2.5 >= be(1.0)*atr(2.0)=2.0 → candidate=entry=1903.0
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=1.0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd(type="SELL", open_price=1903.0, sl=0.0))
    assert len(h.trading.modify_calls) == 1
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1903.0)
    assert 1001 in h.agent._be_done


async def test_disappeared_stream_none_payload(position_monitor_agent_factory):
    # ни by_magic, ни by_symbol не находят поток → stream_id=None в ORDER_CLOSED
    h = position_monitor_agent_factory(positions=[], streams={}, status_seed={"XAUUSD": 1})
    await h.agent._on_position_disappeared(_prev(magic=777))
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    assert closed[0].payload["stream_id"] is None


async def test_check_rsi_exit_dispatches_to_legacy(position_monitor_agent_factory, monkeypatch):
    # стратегия НЕ в STRATEGIES → _check_rsi_exit маршрутизирует в legacy-RSI
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(40.0))   # BUY + <45 → CLOSE
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={},
                                       status_seed={"XAUUSD": 0})
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 777, "ticket": 1001, "type": "BUY"})
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]


async def test_run_error_path_emits_error_status_event(position_monitor_agent_factory, monkeypatch):
    # исключение внутри run() → ловится (без краша), эмитится AGENT_STATUS=error.
    # Характеризация тонкости: финальный статус всё равно IDLE — run() безусловно
    # эмитит IDLE в конце цикла (стр. 74), перетирая транзиентный ERROR.
    from agents.base_agent import AgentStatus
    h = position_monitor_agent_factory(positions=[make_mt5_position(magic=777)],
                                       streams={"s1": make_stream(magic=777)})
    def boom():
        raise RuntimeError("positions boom")
    monkeypatch.setattr(h.agent, "_get_positions_with_pnl", boom)
    await h.agent.run()   # не должно бросить
    emitted = [e.payload["status"] for e in h.bus.events if e.type == EventType.AGENT_STATUS]
    assert AgentStatus.ERROR in emitted          # ERROR наблюдаемо эмитнут
    assert h.agent.status == AgentStatus.IDLE     # но финальный статус — IDLE
