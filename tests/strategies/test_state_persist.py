"""Состояние стратегий переживает рестарт процесса.

Блокировка переоткрытия (`_blocked_side`) держалась только в памяти
singleton-экземпляра из strategies.runtime. Любой рестарт бота снимал её,
и стратегия заходила в ту же сторону сразу после стопа — в августе 2026
это дало серии из 6–9 убытков подряд (ema_cross 20 нарушений из 24
переходов, macd_hist 21 из 31).

Здесь заперты две вещи: стратегия умеет отдать и принять своё состояние,
а runtime-кэш сохраняет его на диск и поднимает при следующем старте.
"""
import json

import pytest

from strategies import STRATEGIES


BLOCKING = ["ema_cross", "macd_hist", "aroon"]


# ── контракт состояния ────────────────────────────────────────────────

def test_base_strategy_has_no_state_by_default():
    """Стратегия без внутреннего состояния отдаёт пустой dict."""
    s = STRATEGIES["cci_rsi"]()
    assert s.state_dict() == {}


@pytest.mark.parametrize("name", BLOCKING)
def test_blocked_side_round_trips(name):
    s = STRATEGIES[name]()
    s.on_trade_closed({"type": "BUY"}, "SL")
    assert s.state_dict() == {"_blocked_side": "BUY"}

    fresh = STRATEGIES[name]()
    fresh.load_state({"_blocked_side": "BUY"})
    assert fresh.state_dict() == {"_blocked_side": "BUY"}


@pytest.mark.parametrize("name", BLOCKING)
def test_restored_state_blocks_the_same_side(name):
    """Восстановленная блокировка действительно гасит вход в ту же сторону."""
    import pandas as pd
    row = pd.Series({"ema50": 2100.0, "ema200": 2000.0, "atr": 5.0,
                     "macd_hist": 1.0, "macd_signal": 0.5,
                     "aroon_up": 90.0, "aroon_down": 10.0,
                     "aroon_up_prev": 60.0, "aroon_down_prev": 40.0,
                     "close": 2100.0})
    free = STRATEGIES[name]()
    assert free.get_entry_signal(row) == "BUY", "без блокировки сигнал BUY ожидаем"

    blocked = STRATEGIES[name]()
    blocked.load_state({"_blocked_side": "BUY"})
    assert blocked.get_entry_signal(row) is None


def test_load_state_ignores_unknown_fields():
    s = STRATEGIES["ema_cross"]()
    s.load_state({"_blocked_side": "SELL", "_no_such_field": 42})
    assert s.state_dict() == {"_blocked_side": "SELL"}
    assert not hasattr(s, "_no_such_field")


def test_ema_triple_touch_persists_touch_counter():
    s = STRATEGIES["ema_triple_touch"]()
    s._cross_side, s._touch_count, s._counted_dip = "UP", 2, True
    assert s.state_dict() == {"_cross_side": "UP", "_touch_count": 2, "_counted_dip": True}

    fresh = STRATEGIES["ema_triple_touch"]()
    fresh.load_state(s.state_dict())
    assert (fresh._cross_side, fresh._touch_count, fresh._counted_dip) == ("UP", 2, True)


def test_ema50_rejection_persists_waiting_side():
    s = STRATEGIES["ema50_rejection"]()
    s._waiting_side = "UP"
    assert s.state_dict() == {"_waiting_side": "UP"}


# ── персист в runtime-кэше ────────────────────────────────────────────

@pytest.fixture
def runtime(tmp_path, monkeypatch):
    import strategies.runtime as rt
    monkeypatch.setattr(rt, "_STATE_FILE", tmp_path / "runtime_state.json")
    rt.reset_all()
    yield rt
    rt.reset_all()


def test_state_is_written_to_disk_after_trade_closed(runtime, tmp_path):
    s = runtime.get_runtime_strategy("ema_cross", "XAUUSDrfd")
    s.on_trade_closed({"type": "BUY"}, "SL")
    runtime.save_runtime_state("ema_cross", "XAUUSDrfd")

    saved = json.loads((tmp_path / "runtime_state.json").read_text(encoding="utf-8"))
    assert saved["ema_cross|XAUUSDrfd"] == {"_blocked_side": "BUY"}


def test_state_survives_restart(runtime):
    s = runtime.get_runtime_strategy("ema_cross", "XAUUSDrfd")
    s.on_trade_closed({"type": "BUY"}, "SL")
    runtime.save_runtime_state("ema_cross", "XAUUSDrfd")

    runtime.reset_all()                      # имитируем рестарт процесса
    revived = runtime.get_runtime_strategy("ema_cross", "XAUUSDrfd")
    assert revived is not s
    assert revived._blocked_side == "BUY"


def test_state_is_isolated_per_symbol(runtime):
    gold = runtime.get_runtime_strategy("ema_cross", "XAUUSDrfd")
    gold.on_trade_closed({"type": "BUY"}, "SL")
    runtime.save_runtime_state("ema_cross", "XAUUSDrfd")

    runtime.reset_all()
    euro = runtime.get_runtime_strategy("ema_cross", "EURUSDrfd")
    assert euro._blocked_side is None


def test_corrupt_state_file_does_not_break_startup(runtime, tmp_path):
    (tmp_path / "runtime_state.json").write_text("{ не json", encoding="utf-8")
    s = runtime.get_runtime_strategy("ema_cross", "XAUUSDrfd")
    assert s._blocked_side is None


def test_stateless_strategy_is_not_written(runtime, tmp_path):
    runtime.get_runtime_strategy("cci_rsi", "XAUUSDrfd")
    runtime.save_runtime_state("cci_rsi", "XAUUSDrfd")
    saved = json.loads((tmp_path / "runtime_state.json").read_text(encoding="utf-8"))
    assert "cci_rsi|XAUUSDrfd" not in saved


def test_save_is_atomic_no_tmp_left_behind(runtime, tmp_path):
    s = runtime.get_runtime_strategy("aroon", "XAUUSDrfd")
    s.on_trade_closed({"type": "SELL"}, "TP")
    runtime.save_runtime_state("aroon", "XAUUSDrfd")
    assert list(tmp_path.glob("*.tmp")) == []


def test_unknown_strategy_still_returns_none(runtime):
    assert runtime.get_runtime_strategy("no_such_strategy", "XAUUSDrfd") is None
