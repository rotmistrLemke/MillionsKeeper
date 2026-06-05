"""
Анализ сделок за последние 14 дней — для дизайна стратегии «копировать выигравшие».
Использует уже работающий MT5-терминал (без re-login). Запуск:

    python -m tools.analyze_2w
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any

import MetaTrader5 as mt5


WINDOW_DAYS = 14


def init_mt5() -> None:
    # Терминал уже залогинен ботом — просто прикрепляемся.
    if not mt5.initialize():
        # На случай отдельного запуска — пробуем явный login из .env
        login    = int(os.environ.get("MT5_LOGIN", "0") or 0)
        password = os.environ.get("MT5_PASSWORD", "")
        server   = os.environ.get("MT5_SERVER", "")
        if not (login and password and server):
            sys.exit(f"mt5.initialize() failed: {mt5.last_error()}")
        if not mt5.initialize(login=login, password=password, server=server):
            sys.exit(f"mt5.initialize(login=...) failed: {mt5.last_error()}")


def fetch_deals(days: int) -> list[Any]:
    now = datetime.now()
    date_from = now - timedelta(days=days)
    date_to   = now + timedelta(hours=3)
    deals = mt5.history_deals_get(date_from, date_to)
    return list(deals or [])


@dataclass
class Position:
    ticket_in:    int
    ticket_out:   int
    symbol:       str
    type:         str   # "BUY" / "SELL"
    open_time:    datetime
    close_time:   datetime
    open_price:   float
    close_price:  float
    volume:       float
    profit:       float    # суммарный по всем deals позиции (комиссия + своп + profit)
    magic:        int
    comment:      str
    duration_min: float

    def hour_open(self) -> int:
        return self.open_time.hour

    def dow_open(self) -> int:
        return self.open_time.weekday()


def link_positions(deals: list[Any]) -> list[Position]:
    """Линкуем IN-deal (entry=0) ↔ OUT-deal (entry=1) по position_id.
    Балансы/комиссии (type ∉ {0,1}) игнорируем. Считаем суммарный profit
    по всем deals одного position_id, но direction/время берём из IN/OUT."""
    by_pid_in:  dict[int, Any]       = {}
    by_pid_out: dict[int, Any]       = {}
    profit_sum: dict[int, float]     = defaultdict(float)
    for d in deals:
        if d.type not in (0, 1):
            continue
        if d.entry == 0:
            by_pid_in[d.position_id] = d
        elif d.entry == 1:
            by_pid_out[d.position_id] = d
        # суммируем profit/commission/swap по этому position_id
        profit_sum[d.position_id] += float(d.profit) + float(d.commission) + float(d.swap)

    positions: list[Position] = []
    for pid, d_in in by_pid_in.items():
        d_out = by_pid_out.get(pid)
        if d_out is None:
            continue
        t_in  = datetime.fromtimestamp(d_in.time)
        t_out = datetime.fromtimestamp(d_out.time)
        positions.append(Position(
            ticket_in=d_in.ticket, ticket_out=d_out.ticket,
            symbol=d_in.symbol,
            type="BUY" if d_in.type == 0 else "SELL",
            open_time=t_in, close_time=t_out,
            open_price=float(d_in.price), close_price=float(d_out.price),
            volume=float(d_in.volume),
            profit=profit_sum[pid],
            magic=int(getattr(d_in, "magic", 0) or 0),
            comment=str(getattr(d_in, "comment", "") or ""),
            duration_min=(t_out - t_in).total_seconds() / 60.0,
        ))
    positions.sort(key=lambda p: p.open_time)
    return positions


def summarize(positions: list[Position]) -> dict:
    total = len(positions)
    if total == 0:
        return {"total": 0}

    wins = [p for p in positions if p.profit > 0]
    losses = [p for p in positions if p.profit <= 0]

    sum_profit_w = sum(p.profit for p in wins)
    sum_profit_l = sum(p.profit for p in losses)

    by_symbol: dict[str, dict[str, float]] = {}
    for p in positions:
        b = by_symbol.setdefault(p.symbol, {"n": 0, "wins": 0, "pnl": 0.0, "pnl_w": 0.0, "pnl_l": 0.0})
        b["n"]     += 1
        b["pnl"]   += p.profit
        if p.profit > 0:
            b["wins"]  += 1
            b["pnl_w"] += p.profit
        else:
            b["pnl_l"] += p.profit

    by_dir: dict[str, dict[str, float]] = {"BUY": {"n":0,"wins":0,"pnl":0.0}, "SELL": {"n":0,"wins":0,"pnl":0.0}}
    for p in positions:
        bd = by_dir[p.type]
        bd["n"]   += 1
        bd["pnl"] += p.profit
        if p.profit > 0:
            bd["wins"] += 1

    by_hour: dict[int, dict[str, float]] = {h: {"n":0,"wins":0,"pnl":0.0} for h in range(24)}
    for p in positions:
        h = p.hour_open()
        by_hour[h]["n"]   += 1
        by_hour[h]["pnl"] += p.profit
        if p.profit > 0:
            by_hour[h]["wins"] += 1

    by_dow: dict[int, dict[str, float]] = {d: {"n":0,"wins":0,"pnl":0.0} for d in range(7)}
    for p in positions:
        d = p.dow_open()
        by_dow[d]["n"]   += 1
        by_dow[d]["pnl"] += p.profit
        if p.profit > 0:
            by_dow[d]["wins"] += 1

    durations_w = [p.duration_min for p in wins]
    durations_l = [p.duration_min for p in losses]
    def _avg(xs): return (sum(xs) / len(xs)) if xs else 0.0

    return {
        "window_days": WINDOW_DAYS,
        "total": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / total) if total else 0.0,
        "pnl_total": sum(p.profit for p in positions),
        "pnl_avg_win":  (sum_profit_w / len(wins))   if wins   else 0.0,
        "pnl_avg_loss": (sum_profit_l / len(losses)) if losses else 0.0,
        "profit_factor": (sum_profit_w / abs(sum_profit_l)) if sum_profit_l < 0 else float("inf") if sum_profit_w > 0 else 0.0,
        "avg_duration_min_win":  _avg(durations_w),
        "avg_duration_min_loss": _avg(durations_l),
        "by_symbol": by_symbol,
        "by_dir":    by_dir,
        "by_hour":   {str(k): v for k, v in by_hour.items() if v["n"]},
        "by_dow":    {str(k): v for k, v in by_dow.items() if v["n"]},
    }


def print_report(positions: list[Position], summary: dict) -> None:
    print(f"\n=== Отчёт по сделкам за {WINDOW_DAYS} дней ===")
    if not summary.get("total"):
        print("Сделок не найдено.")
        return
    print(f"Всего:           {summary['total']}")
    print(f"Wins / Losses:   {summary['wins']} / {summary['losses']}  (winrate={summary['win_rate']*100:.1f}%)")
    print(f"PnL total:       {summary['pnl_total']:.2f}")
    print(f"Avg win / loss:  {summary['pnl_avg_win']:.2f} / {summary['pnl_avg_loss']:.2f}")
    print(f"Profit factor:   {summary['profit_factor']:.2f}")
    print(f"Avg duration W/L:{summary['avg_duration_min_win']:.1f} / {summary['avg_duration_min_loss']:.1f} мин")

    print("\n— По символам —")
    rows = sorted(summary["by_symbol"].items(), key=lambda kv: -kv[1]["pnl"])
    for sym, b in rows:
        wr = (b["wins"] / b["n"] * 100.0) if b["n"] else 0.0
        print(f"  {sym:14s} n={b['n']:3d}  wr={wr:5.1f}%  pnl={b['pnl']:+8.2f}")

    print("\n— По направлению —")
    for d, b in summary["by_dir"].items():
        if not b["n"]:
            continue
        wr = (b["wins"] / b["n"] * 100.0)
        print(f"  {d:4s}  n={b['n']:3d}  wr={wr:5.1f}%  pnl={b['pnl']:+8.2f}")

    print("\n— По часам входа (по серверному локальному времени MT5-терминала) —")
    for h, b in sorted(summary["by_hour"].items(), key=lambda kv: int(kv[0])):
        wr = (b["wins"] / b["n"] * 100.0) if b["n"] else 0.0
        bar = "#" * int(b["n"])
        print(f"  {int(h):02d}:00  n={b['n']:3d}  wr={wr:5.1f}%  pnl={b['pnl']:+8.2f}  {bar}")

    print("\n— По дням недели (Mon=0) —")
    dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    for d, b in sorted(summary["by_dow"].items(), key=lambda kv: int(kv[0])):
        wr = (b["wins"] / b["n"] * 100.0) if b["n"] else 0.0
        print(f"  {dow_names[int(d)]}  n={b['n']:3d}  wr={wr:5.1f}%  pnl={b['pnl']:+8.2f}")

    # Топ-N выигравших / проигравших — для обзора
    print("\n— Топ-5 выигравших позиций —")
    for p in sorted(positions, key=lambda x: -x.profit)[:5]:
        print(f"  {p.open_time:%Y-%m-%d %H:%M} {p.symbol:10s} {p.type:4s} v={p.volume:.2f}  hold={p.duration_min:6.1f}m  pnl={p.profit:+8.2f}  magic={p.magic}")
    print("\n— Топ-5 проигравших позиций —")
    for p in sorted(positions, key=lambda x: x.profit)[:5]:
        print(f"  {p.open_time:%Y-%m-%d %H:%M} {p.symbol:10s} {p.type:4s} v={p.volume:.2f}  hold={p.duration_min:6.1f}m  pnl={p.profit:+8.2f}  magic={p.magic}")


def main() -> None:
    init_mt5()
    deals = fetch_deals(WINDOW_DAYS)
    positions = link_positions(deals)
    summary = summarize(positions)
    print_report(positions, summary)

    # Сохраняем JSON-дамп для дальнейшего использования (дизайн стратегии).
    out_dir = os.path.join("tools", "_out")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "deals_2w.json"), "w", encoding="utf-8") as f:
        json.dump({
            "summary":   summary,
            "positions": [
                {**asdict(p),
                 "open_time":  p.open_time.isoformat(),
                 "close_time": p.close_time.isoformat()}
                for p in positions
            ],
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nJSON-дамп сохранён: tools/_out/deals_2w.json")


if __name__ == "__main__":
    main()
