"""Чистая go/no-go оценка по метрикам live-трека. Пороги настраиваемы (Moderate по умолчанию)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    min_period_days: int = 90
    min_trades: int = 50
    min_trades_per_strategy: int = 20
    require_net_pnl_positive: bool = True
    max_drawdown_pct: float = 25.0
    min_profit_factor: float = 1.3


_DEFAULT = Thresholds()


def evaluate(metrics: dict, thresholds: Thresholds = _DEFAULT, *, is_strategy: bool = False) -> dict:
    """Вердикт. status: PASS | FAIL | INSUFFICIENT_DATA."""
    min_trades = thresholds.min_trades_per_strategy if is_strategy else thresholds.min_trades

    insufficient = []
    if metrics["trades"] < min_trades:
        insufficient.append(f"trades {metrics['trades']} < {min_trades}")
    if metrics["period_days"] < thresholds.min_period_days:
        insufficient.append(f"period_days {metrics['period_days']:.1f} < {thresholds.min_period_days}")
    if insufficient:
        return {"status": "INSUFFICIENT_DATA", "reasons": insufficient, "metrics": metrics}

    reasons = []
    if thresholds.require_net_pnl_positive and metrics["net_pnl"] <= 0:
        reasons.append(f"net_pnl {metrics['net_pnl']:.2f} <= 0")
    if metrics["max_drawdown_pct"] > thresholds.max_drawdown_pct:
        reasons.append(f"max_drawdown_pct {metrics['max_drawdown_pct']:.1f} > {thresholds.max_drawdown_pct}")
    if metrics["profit_factor"] < thresholds.min_profit_factor:
        reasons.append(f"profit_factor {metrics['profit_factor']:.2f} < {thresholds.min_profit_factor}")

    return {"status": "PASS" if not reasons else "FAIL", "reasons": reasons, "metrics": metrics}
