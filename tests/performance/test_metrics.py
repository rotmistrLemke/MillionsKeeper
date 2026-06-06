"""Характеризация чистых метрик performance (forward-track)."""
import math
import pytest
from performance.metrics import compute, per_strategy


def _t(time, profit, commission=0.0, swap=0.0, magic=0):
    return {"time": time, "profit": profit, "commission": commission, "swap": swap, "magic": magic}


def test_empty_returns_zeros():
    m = compute([])
    assert m["trades"] == 0 and m["net_pnl"] == 0.0
    assert m["profit_factor"] == 0.0 and m["sharpe"] is None and m["period_days"] == 0.0


def test_mixed_trades_pinned():
    # nets: +10, -4, +5, -3 → net 8; wins 2 losses 2
    trades = [_t(0, 10), _t(100, -4), _t(200, 6, commission=-1), _t(300, -2, swap=-1)]
    m = compute(trades)
    assert m["net_pnl"] == pytest.approx(8.0)
    assert m["trades"] == 4 and m["wins"] == 2 and m["losses"] == 2
    assert m["win_rate"] == pytest.approx(0.5)
    assert m["gross_profit"] == pytest.approx(15.0) and m["gross_loss"] == pytest.approx(7.0)
    assert m["profit_factor"] == pytest.approx(15.0 / 7.0)
    assert m["avg_win"] == pytest.approx(7.5) and m["avg_loss"] == pytest.approx(-3.5)
    assert m["expectancy"] == pytest.approx(2.0)
    # equity cum: 10,6,11,8 → max peak-to-trough decline = 4 (пик 10 → дно 6);
    # pct = max_dd_money / глоб.пик(11) * 100 (конвенция compute())
    assert m["max_drawdown_money"] == pytest.approx(4.0)
    assert m["max_drawdown_pct"] == pytest.approx(4.0 / 11.0 * 100.0)
    assert m["longest_loss_streak"] == 1
    assert m["sharpe"] is not None
    assert m["period_days"] == pytest.approx(300.0 / 86400.0)


def test_all_wins_profit_factor_inf():
    m = compute([_t(0, 5), _t(10, 3)])
    assert m["profit_factor"] == math.inf
    assert m["max_drawdown_money"] == 0.0 and m["max_drawdown_pct"] == 0.0


def test_all_losses_profit_factor_zero():
    m = compute([_t(0, -5), _t(10, -3)])
    assert m["profit_factor"] == 0.0
    assert m["net_pnl"] == pytest.approx(-8.0)
    assert m["longest_loss_streak"] == 2


def test_single_trade_sharpe_none():
    m = compute([_t(0, 7)])
    assert m["sharpe"] is None and m["trades"] == 1


def test_per_strategy_groups_by_magic():
    trades = [_t(0, 10, magic=1001), _t(10, -2, magic=1001), _t(20, 5, magic=1002), _t(30, 1, magic=9999)]
    out = per_strategy(trades, {1001: "alpha", 1002: "beta"})
    assert set(out) == {"alpha", "beta", "unmapped"}
    assert out["alpha"]["trades"] == 2 and out["alpha"]["net_pnl"] == pytest.approx(8.0)
    assert out["beta"]["net_pnl"] == pytest.approx(5.0)
    assert out["unmapped"]["net_pnl"] == pytest.approx(1.0)
