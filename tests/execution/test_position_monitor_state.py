"""Закрытие позиции: надёжная причина, журнал и персист состояния стратегии.

Августовские серии из 6–9 стопов подряд означали, что `_blocked_side` после
SL не доживал до следующего бара, а по логам это было не видно вовсе —
причина закрытия нигде не печаталась. Здесь заперты три вещи:

  1. причина берётся из `deal.reason` (DEAL_REASON_SL/TP), а не из текста
     комментария брокера, который может смениться в любой момент;
  2. каждое закрытие пишет в лог поток, стратегию, причину и состояние
     блокировки до и после хука;
  3. состояние стратегии сохраняется на диск сразу после хука.
"""
import logging

import pytest

from tests.execution.fakes import (make_deal, make_position, make_stream,
                                   make_runtime_strategy)


def _prev(ticket=1001, symbol="XAUUSD", magic=777, type_="BUY"):
    return {"ticket": ticket, "symbol": symbol, "magic": magic,
            "type": type_, "open_price": 1900.0}


class _Blocking:
    """Стратегия с состоянием — как ema_cross/macd_hist/aroon."""
    def __init__(self):
        self._blocked_side = None
        self.closed_calls = []

    def on_trade_closed(self, position, reason):
        self.closed_calls.append((position, reason))
        self._blocked_side = position.get("type") if reason in ("TP", "SL") else None

    def state_fields(self):
        return ["_blocked_side"]

    def state_dict(self):
        return {"_blocked_side": self._blocked_side}


# ── 1. причина закрытия из deal.reason ────────────────────────────────

@pytest.mark.parametrize("reason_code,expected", [
    (4, "SL"),        # DEAL_REASON_SL
    (5, "TP"),        # DEAL_REASON_TP
    (3, "SIGNAL"),    # DEAL_REASON_EXPERT — закрыл советник
    (0, "MANUAL"),    # DEAL_REASON_CLIENT
    (1, "MANUAL"),    # DEAL_REASON_MOBILE
])
def test_classify_uses_deal_reason(position_monitor_agent_factory, reason_code, expected):
    h = position_monitor_agent_factory(deals=[make_deal(reason=reason_code, comment="")])
    assert h.agent._classify_close_reason(1001) == expected


def test_stop_loss_is_not_read_as_signal_when_history_holds_the_entry(
        position_monitor_agent_factory):
    """Регрессия 07–11.09.2026: десять стопов подряд, определённых как SIGNAL.

    В истории лежат обе сделки позиции — вход (reason=EXPERT) и выход по
    стопу (reason=SL). Код брал последний доступный deal и попадал во вход,
    потому что запрос смешивал position с диапазоном дат: фильтр позиции MT5
    игнорирует, а окно по локальным часам отсекало свежий выход. Результат —
    on_trade_closed('SIGNAL') не ставил блокировку переоткрытия, а снимал её.
    """
    h = position_monitor_agent_factory(deals=[
        make_deal(reason=3, comment="s6:aroon", entry=0, position_id=1001, time=100),
        make_deal(reason=4, comment="[sl 4407.63]", entry=1, position_id=1001, time=200),
    ])
    assert h.agent._classify_close_reason(1001) == "SL"


def test_closing_deal_of_another_position_is_not_used(position_monitor_agent_factory):
    """Свежая сделка соседнего потока не должна определять нашу причину."""
    h = position_monitor_agent_factory(deals=[
        make_deal(reason=4, comment="[sl 1.0]", entry=1, position_id=1001, time=100),
        make_deal(reason=5, comment="[tp 2.0]", entry=1, position_id=2002, time=300),
    ])
    assert h.agent._classify_close_reason(1001) == "SL"


def test_deal_reason_wins_over_misleading_comment(position_monitor_agent_factory):
    # Комментарий потока «s16:ema50_overstretch» содержит подстроку sl — раньше
    # такой текст мог быть прочитан как стоп. Код причины важнее текста.
    h = position_monitor_agent_factory(deals=[make_deal(reason=5, comment="s16:ema50_sl_x")])
    assert h.agent._classify_close_reason(1001) == "TP"


def test_falls_back_to_comment_when_reason_absent(position_monitor_agent_factory):
    # Старые сборки MT5-пакета могут не отдавать reason — поведение сохраняем.
    h = position_monitor_agent_factory(deals=[make_deal(comment="[sl 1897.00]")])
    assert h.agent._classify_close_reason(1001) == "SL"


# ── 2. журнал закрытия ────────────────────────────────────────────────

async def test_close_is_logged_with_reason_and_blocked_side(
        position_monitor_agent_factory, monkeypatch, caplog):
    import strategies.runtime as runtime_mod
    strat = _Blocking()
    h = position_monitor_agent_factory(
        positions=[], streams={"s3": make_stream(id="s3", magic=777, strategy="ema_cross")},
        strategies={"ema_cross": object()}, runtime_strategy=strat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(reason=4)],
    )
    monkeypatch.setattr(runtime_mod, "save_runtime_state", lambda *a: None)

    with caplog.at_level(logging.INFO):
        await h.agent._on_position_disappeared(_prev())

    line = "\n".join(r.getMessage() for r in caplog.records)
    assert "SL" in line
    assert "s3" in line and "ema_cross" in line
    assert "None" in line and "BUY" in line, "нужно состояние блокировки до и после хука"


async def test_close_without_stream_is_logged_as_warning(
        position_monitor_agent_factory, caplog):
    """Пустой реестр — самая опасная тишина: хук не вызывается вообще."""
    h = position_monitor_agent_factory(
        positions=[], streams={}, status_seed={"XAUUSD": 1},
        deals=[make_deal(reason=4)],
    )
    with caplog.at_level(logging.WARNING):
        await h.agent._on_position_disappeared(_prev())

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("777" in m for m in warnings), "в логе должен быть magic ненайденного потока"


# ── 3. персист состояния после хука ───────────────────────────────────

async def test_state_is_persisted_after_hook(position_monitor_agent_factory, monkeypatch):
    import strategies.runtime as runtime_mod
    saved = []
    monkeypatch.setattr(runtime_mod, "save_runtime_state",
                        lambda name, symbol: saved.append((name, symbol)))
    strat = _Blocking()
    h = position_monitor_agent_factory(
        positions=[], streams={"s3": make_stream(id="s3", magic=777, strategy="ema_cross")},
        strategies={"ema_cross": object()}, runtime_strategy=strat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(reason=4)],
    )
    await h.agent._on_position_disappeared(_prev())

    assert strat._blocked_side == "BUY"
    assert saved == [("ema_cross", "XAUUSD")]


async def test_hook_failure_does_not_skip_persist_of_other_closes(
        position_monitor_agent_factory, monkeypatch):
    """Падение хука не должно ронять цикл монитора."""
    import strategies.runtime as runtime_mod
    monkeypatch.setattr(runtime_mod, "save_runtime_state", lambda *a: None)
    strat = make_runtime_strategy(raise_on_closed=True)
    h = position_monitor_agent_factory(
        positions=[], streams={"s3": make_stream(id="s3", magic=777, strategy="ema_cross")},
        strategies={"ema_cross": object()}, runtime_strategy=strat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(reason=4)],
    )
    await h.agent._on_position_disappeared(_prev())   # не бросает


async def test_hook_runs_even_if_strategy_has_no_state_api(
        position_monitor_agent_factory, monkeypatch):
    """Журнал состояния — диагностика, а не условие вызова хука."""
    import strategies.runtime as runtime_mod
    monkeypatch.setattr(runtime_mod, "save_runtime_state", lambda *a: None)
    strat = make_runtime_strategy()          # без state_dict/state_fields
    h = position_monitor_agent_factory(
        positions=[], streams={"s3": make_stream(id="s3", magic=777, strategy="ema_cross")},
        strategies={"ema_cross": object()}, runtime_strategy=strat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(reason=4)],
    )
    await h.agent._on_position_disappeared(_prev())
    assert [r for _, r in strat.closed_calls] == ["SL"]


# ── 4. не угадывать поток по символу ──────────────────────────────────

async def test_unknown_magic_does_not_touch_a_foreign_stream(
        position_monitor_agent_factory, monkeypatch, caplog):
    """14 потоков на XAUUSD: закрытие чужой позиции не должно ставить
    блокировку и сбрасывать OPEN случайному потоку того же символа."""
    import strategies.runtime as runtime_mod
    monkeypatch.setattr(runtime_mod, "save_runtime_state", lambda *a: None)
    strat = _Blocking()
    h = position_monitor_agent_factory(
        positions=[],
        streams={"s3": make_stream(id="s3", magic=100002, strategy="ema_cross"),
                 "s5": make_stream(id="s5", magic=100004, strategy="macd_hist")},
        strategies={"ema_cross": object(), "macd_hist": object()},
        runtime_strategy=strat, status_seed={"XAUUSD": 1},
        deals=[make_deal(reason=4)],
    )
    h.registry.mark_stream_open("s3")

    with caplog.at_level(logging.WARNING):
        await h.agent._on_position_disappeared(_prev(magic=999999))

    assert strat.closed_calls == [], "хук чужой стратегии вызывать нельзя"
    assert h.registry.is_stream_open("s3"), "OPEN чужого потока трогать нельзя"


async def test_single_stream_symbol_still_falls_back_by_symbol(
        position_monitor_agent_factory, monkeypatch):
    """Один поток на символе — прежнее поведение (legacy-позиции без magic)."""
    import strategies.runtime as runtime_mod
    monkeypatch.setattr(runtime_mod, "save_runtime_state", lambda *a: None)
    strat = _Blocking()
    h = position_monitor_agent_factory(
        positions=[], streams={"s3": make_stream(id="s3", magic=100002, strategy="ema_cross")},
        strategies={"ema_cross": object()}, runtime_strategy=strat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(reason=4)],
    )
    await h.agent._on_position_disappeared(_prev(magic=0))
    assert [r for _, r in strat.closed_calls] == ["SL"]


# ── 5. сверка реестра с реальными позициями ──────────────────────────

async def test_existing_position_marks_its_stream_open(position_monitor_agent_factory):
    """После рестарта реестр пуст, а позиция на счёте жива.

    mark_stream_open вызывается только в момент открытия ордера, поэтому
    перезапущенный бот считал поток свободным и открывал ВТОРУЮ позицию тем
    же magic. Монитор видит реальные позиции каждые 5 с — он и должен
    восстанавливать OPEN-статус.
    """
    h = position_monitor_agent_factory(
        streams={"s6": make_stream(id="s6", strategy="aroon", symbol="XAUUSD", magic=100005)},
        positions=[make_position(None, magic=100005, symbol="XAUUSD")],
    )
    assert h.registry.is_stream_open("s6") is False   # реестр пуст после старта
    await h.agent.run()
    assert h.registry.is_stream_open("s6") is True
    assert h.registry.open_count() == 1


async def test_position_without_known_stream_does_not_mark_anything(
        position_monitor_agent_factory):
    """Ручная позиция (magic=0) потоком не владеет и слот занимать не должна."""
    h = position_monitor_agent_factory(
        streams={"s6": make_stream(id="s6", strategy="aroon", symbol="XAUUSD", magic=100005)},
        positions=[make_position(None, magic=0, symbol="XAUUSD")],
    )
    await h.agent.run()
    assert h.registry.open_count() == 0
