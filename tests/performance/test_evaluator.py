"""Характеризация go/no-go оценки performance."""
import math
from performance.evaluator import Thresholds, evaluate


def _metrics(*, trades=60, period_days=120.0, net_pnl=500.0, max_drawdown_pct=10.0, profit_factor=1.6):
    return {"trades": trades, "period_days": period_days, "net_pnl": net_pnl,
            "max_drawdown_pct": max_drawdown_pct, "profit_factor": profit_factor}


def test_pass_when_all_thresholds_met():
    v = evaluate(_metrics())
    assert v["status"] == "PASS" and v["reasons"] == []


def test_insufficient_when_too_few_trades():
    v = evaluate(_metrics(trades=10))
    assert v["status"] == "INSUFFICIENT_DATA"
    assert any("trades" in r for r in v["reasons"])


def test_insufficient_when_period_too_short():
    v = evaluate(_metrics(period_days=30.0))
    assert v["status"] == "INSUFFICIENT_DATA"
    assert any("period_days" in r for r in v["reasons"])


def test_fail_negative_pnl():
    v = evaluate(_metrics(net_pnl=-100.0))
    assert v["status"] == "FAIL" and any("net_pnl" in r for r in v["reasons"])


def test_fail_drawdown_exceeds():
    v = evaluate(_metrics(max_drawdown_pct=30.0))
    assert v["status"] == "FAIL" and any("drawdown" in r for r in v["reasons"])


def test_fail_low_profit_factor():
    v = evaluate(_metrics(profit_factor=1.1))
    assert v["status"] == "FAIL" and any("profit_factor" in r for r in v["reasons"])


def test_boundaries_inclusive_pass():
    # ровно на границах moderate: dd 25.0 (не >25), pf 1.3 (не <1.3) → PASS
    v = evaluate(_metrics(max_drawdown_pct=25.0, profit_factor=1.3))
    assert v["status"] == "PASS"


def test_profit_factor_inf_passes():
    v = evaluate(_metrics(profit_factor=math.inf))
    assert v["status"] == "PASS"


def test_strategy_uses_lower_trade_floor():
    # 25 сделок: для счёта (min 50) — мало; для стратегии (min 20) — достаточно
    assert evaluate(_metrics(trades=25))["status"] == "INSUFFICIENT_DATA"
    assert evaluate(_metrics(trades=25), is_strategy=True)["status"] == "PASS"
