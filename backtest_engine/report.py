"""Текстовый отчёт по результатам бэктеста."""

import numpy as np


def print_report(strategy_name, symbol, timeframe_name, result, deposit=0):
    if result is None:
        print(f"  {strategy_name}: нет данных")
        return
    if result.total_trades == 0:
        print(f"  {strategy_name}: 0 сделок")
        return

    print(f"\n{'='*70}")
    print(f"  СТРАТЕГИЯ: {strategy_name}")
    print(f"  Символ: {symbol} | Таймфрейм: {timeframe_name}")
    print(f"{'='*70}")
    print(f"  Сделок: {result.total_trades}  |  Win: {len(result.winning_trades)}  |  Loss: {len(result.losing_trades)}")
    print(f"  Win Rate: {result.win_rate * 100:.1f}%  |  Profit Factor: {result.profit_factor:.2f}")
    print(f"  P&L: {result.total_pnl_points:+.1f} пунктов")
    print(f"  Средняя прибыль: {result.avg_win:+.1f} pt  |  Средний убыток: {result.avg_loss:+.1f} pt")
    print(f"  Макс. просадка: {result.max_drawdown_points:.1f} pt")
    print(f"  Макс. серия убытков: {result.max_consecutive_losses}")

    if deposit > 0:
        print(f"{'─'*70}")
        print(f"  Депозит: {deposit:,.2f}$ → Баланс: {result.final_balance:,.2f}$")
        print(f"  Доходность: {result.return_pct:+.2f}%  |  Макс. просадка: {result.max_drawdown_pct:.1f}%")
        print(f"  P&L: {result.total_pnl_money:+,.2f}$")

    by_reason = {}
    for t in result.trades:
        by_reason[t['exit_reason']] = by_reason.get(t['exit_reason'], 0) + 1
    print(f"{'─'*70}")
    print(f"  Причины выхода: {', '.join(f'{r}: {c}' for r, c in by_reason.items())}")

    if result.trades:
        avg_bars = np.mean([t['bars_held'] for t in result.trades])
        print(f"  Среднее удержание: {avg_bars:.1f} баров")

    print(f"\n{'─'*70}")
    if deposit > 0:
        print(f"  {'#':>4}  {'Тип':<5}  {'Вход':<16}  {'P&L пт':>9}  {'P&L $':>10}  {'Баланс':>12}  {'Выход по':<10}")
        print(f"  {'─'*70}")
        for idx, t in enumerate(result.trades, 1):
            entry_t = t['entry_time'].strftime('%d.%m %H:%M') if hasattr(t['entry_time'], 'strftime') else str(t['entry_time'])[:16]
            print(f"  {idx:>4}  {t['type']:<5}  {entry_t:<16}  {t['pnl_points']:>+8.1f}  {t['pnl_money']:>+9.2f}  {t.get('balance_after', 0):>12,.2f}  {t['exit_reason']:<10}")
    else:
        print(f"  {'#':>4}  {'Тип':<5}  {'Вход':<16}  {'Выход':<16}  {'P&L пт':>9}  {'Баров':>5}  {'Выход по':<10}")
        print(f"  {'─'*70}")
        for idx, t in enumerate(result.trades, 1):
            entry_t = t['entry_time'].strftime('%d.%m %H:%M') if hasattr(t['entry_time'], 'strftime') else str(t['entry_time'])[:16]
            exit_t  = t['exit_time'].strftime('%d.%m %H:%M') if hasattr(t['exit_time'], 'strftime') else str(t['exit_time'])[:16]
            print(f"  {idx:>4}  {t['type']:<5}  {entry_t:<16}  {exit_t:<16}  {t['pnl_points']:>+8.1f}  {t['bars_held']:>5}  {t['exit_reason']:<10}")

    print(f"{'='*70}\n")
