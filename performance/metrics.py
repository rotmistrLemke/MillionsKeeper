"""Чистые функции метрик live-трека. Знают только списки сделок (dict с time/profit/commission/swap[/magic])."""
from __future__ import annotations
import math
from typing import Mapping


def _net(trade: Mapping) -> float:
    return (float(trade.get("profit", 0.0)) + float(trade.get("commission", 0.0))
            + float(trade.get("swap", 0.0)))


def compute(trades: list[dict]) -> dict:
    """Метрики по списку ЗАКРЫТЫХ сделок."""
    n = len(trades)
    if n == 0:
        return {
            "net_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "expectancy": 0.0,
            "max_drawdown_money": 0.0, "max_drawdown_pct": 0.0,
            "longest_loss_streak": 0, "sharpe": None, "period_days": 0.0,
        }
    ordered = sorted(trades, key=lambda t: t.get("time", 0))
    nets = [_net(t) for t in ordered]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)            # положительное
    net_pnl = sum(nets)
    win_rate = len(wins) / n

    if gross_loss == 0:
        profit_factor = math.inf if gross_profit > 0 else 0.0
    else:
        profit_factor = gross_profit / gross_loss

    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (-gross_loss / len(losses)) if losses else 0.0   # отрицательное
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    peak = cum = max_dd_money = 0.0
    for x in nets:
        cum += x
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd_money:
            max_dd_money = dd
    max_dd_pct = (max_dd_money / peak * 100.0) if peak > 0 else 0.0

    longest = cur = 0
    for x in nets:
        if x < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0

    if n >= 2:
        mean = net_pnl / n
        var = sum((x - mean) ** 2 for x in nets) / (n - 1)
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(n)) if std > 0 else None
    else:
        sharpe = None

    period_days = (ordered[-1].get("time", 0) - ordered[0].get("time", 0)) / 86400.0

    return {
        "net_pnl": net_pnl, "trades": n, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "gross_profit": gross_profit, "gross_loss": gross_loss,
        "profit_factor": profit_factor, "avg_win": avg_win, "avg_loss": avg_loss,
        "expectancy": expectancy, "max_drawdown_money": max_dd_money,
        "max_drawdown_pct": max_dd_pct, "longest_loss_streak": longest,
        "sharpe": sharpe, "period_days": period_days,
    }


def per_strategy(trades: list[dict], magic_to_strategy: Mapping[int, str]) -> dict[str, dict]:
    """Группирует сделки по magic→strategy и считает compute() на группу. Неизвестный magic → 'unmapped'."""
    groups: dict[str, list[dict]] = {}
    for t in trades:
        name = magic_to_strategy.get(int(t.get("magic", 0)), "unmapped")
        groups.setdefault(name, []).append(t)
    return {name: compute(ts) for name, ts in groups.items()}
