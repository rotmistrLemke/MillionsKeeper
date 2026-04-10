"""
backtest/metrics.py — Расчёт метрик бэктеста.

Все метрики вычисляются из списка сделок и equity_curve.
Не зависит от MT5 или pandas — только numpy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class BacktestResult:
    """Результат одного бэктест-прогона. Заполняется BacktestEngine."""

    initial_deposit: float = 0.0
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)  # накопительный P&L в деньгах

    # ── Базовые свойства ───────────────────────────────────────────

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> list[dict]:
        return [t for t in self.trades if t.get("pnl_money", 0) >= 0]

    @property
    def losing_trades(self) -> list[dict]:
        return [t for t in self.trades if t.get("pnl_money", 0) < 0]

    @property
    def win_rate(self) -> float:
        return len(self.winning_trades) / self.total_trades if self.total_trades else 0.0

    @property
    def total_pnl_money(self) -> float:
        return sum(t.get("pnl_money", 0) for t in self.trades)

    @property
    def total_pnl_points(self) -> float:
        return sum(t.get("pnl_points", 0) for t in self.trades)

    # ── Profit Factor ──────────────────────────────────────────────

    @property
    def profit_factor(self) -> float:
        gross_win  = sum(t["pnl_money"] for t in self.winning_trades)
        gross_loss = abs(sum(t["pnl_money"] for t in self.losing_trades))
        return gross_win / gross_loss if gross_loss > 0 else float("inf")

    # ── Drawdown ───────────────────────────────────────────────────

    @property
    def max_drawdown_pct(self) -> float:
        if not self.trades or self.initial_deposit <= 0:
            return 0.0
        equity = self.initial_deposit
        peak   = equity
        max_dd = 0.0
        for t in self.trades:
            equity += t.get("pnl_money", 0)
            peak    = max(peak, equity)
            if peak > 0:
                dd = (peak - equity) / peak * 100
                max_dd = max(max_dd, dd)
        return round(max_dd, 2)

    @property
    def max_drawdown_money(self) -> float:
        if not self.trades:
            return 0.0
        equity = self.initial_deposit
        peak   = equity
        max_dd = 0.0
        for t in self.trades:
            equity += t.get("pnl_money", 0)
            peak    = max(peak, equity)
            max_dd  = max(max_dd, peak - equity)
        return round(max_dd, 2)

    # ── Sharpe Ratio ───────────────────────────────────────────────

    @property
    def sharpe_ratio(self) -> float:
        """Упрощённый Sharpe по trade P&L (без risk-free rate)."""
        returns = [t.get("pnl_money", 0) for t in self.trades]
        if len(returns) < 2:
            return 0.0
        arr  = np.array(returns, dtype=float)
        mean = arr.mean()
        std  = arr.std(ddof=1)
        return round(mean / std * math.sqrt(len(arr)), 3) if std > 0 else 0.0

    # ── Дополнительные ────────────────────────────────────────────

    @property
    def final_balance(self) -> float:
        return self.initial_deposit + self.total_pnl_money

    @property
    def return_pct(self) -> float:
        if self.initial_deposit <= 0:
            return 0.0
        return round(self.total_pnl_money / self.initial_deposit * 100, 2)

    @property
    def avg_profit_per_trade(self) -> float:
        return round(self.total_pnl_money / self.total_trades, 2) if self.total_trades else 0.0

    @property
    def max_consecutive_losses(self) -> int:
        max_streak = current = 0
        for t in self.trades:
            if t.get("pnl_points", 0) <= 0:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    # ── Сериализация ───────────────────────────────────────────────

    def metrics_dict(self) -> dict:
        return {
            "total_trades":         self.total_trades,
            "win_rate":             round(self.win_rate, 4),
            "profit_factor":        round(self.profit_factor, 3),
            "sharpe_ratio":         self.sharpe_ratio,
            "max_drawdown":         self.max_drawdown_pct,
            "max_drawdown_money":   self.max_drawdown_money,
            "total_profit":         round(self.total_pnl_money, 2),
            "total_profit_points":  round(self.total_pnl_points, 1),
            "avg_profit_per_trade": self.avg_profit_per_trade,
            "final_balance":        round(self.final_balance, 2),
            "return_pct":           self.return_pct,
            "max_consecutive_losses": self.max_consecutive_losses,
        }
