"""
Единый бэктест-движок TradingHouse.

Поддерживает:
  - Основную стратегию MA + MACD + RSI (strategy="default")
  - Любую модульную стратегию из strategies/ (strategy=<name>)

Запуск:
  python backtest.py                                         — default, XAUUSDrfd, 2000 баров H1
  python backtest.py --strategy sr_bounce                    — модульная стратегия
  python backtest.py --strategy all                          — все модульные стратегии
  python backtest.py --symbol EURUSDrfd --deposit 10000      — с депозитом
  python backtest.py --start 2025-01-01 --end 2025-12-31     — по датам
"""

import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import talib
from datetime import datetime
from authenticator import MT5Auth
from account import Account
from backtest_engine.filters import _is_night_bar, _is_daily_or_higher_tf
from backtest_engine.default_strategy import (
    calc_ema_series, compute_indicators,
    get_ma_signal, get_macd_signal, get_rsi_signal, get_combined_signal,
)
from backtest_engine.result import BacktestResult
from backtest_engine.trades import _calc_pnl_points, _make_default_trade, _make_strategy_trade
from backtest_engine.sizing import get_pip_value, calc_volume
from backtest_engine.data import load_rates


# ─── Движок: основная стратегия (default) ────────────────────────────────

def run_backtest(symbol, timeframe, bars=2000, spread_points=0, deposit=0.0,
                 risk_pct=80, fixed_volume=0.0, date_from=None, date_to=None):
    rates = load_rates(symbol, timeframe, bars, date_from, date_to)
    if rates is None or len(rates) < 100:
        print(f"Недостаточно данных для бэктеста {symbol}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    symbol_info = mt5.symbol_info(symbol)
    point       = symbol_info.point if symbol_info else 0.0001
    return _run_default_on_df(
        df, point=point, symbol_info=symbol_info,
        skip_weekend_filter=_is_daily_or_higher_tf(timeframe),
        spread_points=spread_points, deposit=deposit,
        risk_pct=risk_pct, fixed_volume=fixed_volume,
    )


def _run_default_on_df(df, *, point, symbol_info, skip_weekend_filter,
                       spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0):
    df = compute_indicators(df)
    pip_value_per_lot = 1

    result          = BacktestResult(initial_deposit=deposit)
    position        = None
    cumulative_pnl  = 0.0
    current_balance = deposit if deposit > 0 else 0.0
    peak_balance    = current_balance
    dd_block_until  = None
    trade_status    = 0
    warmup          = 50

    def _next_monday(ts: pd.Timestamp) -> pd.Timestamp:
        days = 7 - ts.weekday() if ts.weekday() > 0 else 7
        return (ts + pd.Timedelta(days=days)).normalize()

    def _update_dd_block(ts: pd.Timestamp):
        nonlocal peak_balance, dd_block_until
        if peak_balance <= 0:
            return
        if current_balance > peak_balance:
            peak_balance = current_balance
            return
        if dd_block_until is not None:
            return
        dd_pct = (peak_balance - current_balance) / peak_balance
        if dd_pct > 0.35:
            dd_block_until = _next_monday(ts)

    for i in range(warmup, len(df)):
        row = df.iloc[i]
        if pd.isna(row['rsi']) or pd.isna(row['atr']) or pd.isna(row['macd_prev']):
            continue

        bar_time = row['time']
        if not isinstance(bar_time, pd.Timestamp):
            bar_time = pd.Timestamp(bar_time, unit='s')
        weekday = bar_time.weekday()
        hour    = bar_time.hour

        if dd_block_until is not None and bar_time >= dd_block_until:
            dd_block_until = None

        if skip_weekend_filter:
            weekend_block = False
        else:
            is_friday_close = weekday == 4 and hour >= 23
            is_weekend      = weekday in (5, 6)
            is_monday_early = weekday == 0 and hour < 2
            weekend_block   = is_friday_close or is_weekend or is_monday_early

        if weekend_block and position is not None:
            if position['type'] == 'BUY':
                pnl_points = (row['close'] - position['entry_price']) / point
            else:
                pnl_points = (position['entry_price'] - row['close']) / point
            pnl_points    -= spread_points
            pnl_money      = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
            current_balance += pnl_money
            cumulative_pnl  += pnl_points
            result.trades.append(_make_default_trade(position, row, i, pnl_points, pnl_money, current_balance, 'WEEKEND'))
            _update_dd_block(bar_time)
            result.equity_curve.append(cumulative_pnl)
            trade_status = 0
            position = None
            continue

        if weekend_block:
            result.equity_curve.append(cumulative_pnl)
            continue

        combined = get_combined_signal(row)

        if position is not None:
            current_rsi = row['rsi']
            if position['type'] == 'BUY':
                pnl_points  = (row['close'] - position['entry_price']) / point
                should_close = current_rsi < 45
            else:
                pnl_points  = (position['entry_price'] - row['close']) / point
                should_close = current_rsi > 55

            if should_close:
                pnl_points    -= spread_points
                pnl_money      = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
                current_balance += pnl_money
                cumulative_pnl  += pnl_points
                result.trades.append(_make_default_trade(position, row, i, pnl_points, pnl_money, current_balance, 'RSI'))
                _update_dd_block(bar_time)
                result.equity_curve.append(cumulative_pnl)
                trade_status = 1
                position = None
                continue

        if trade_status == 1:
            trade_status = 0
        elif trade_status == 2:
            if get_macd_signal(row) == 'NO_SIGNAL':
                trade_status = 0

        if (position is None and trade_status == 0 and combined != 'NO_SIGNAL'
                and dd_block_until is None
                and (skip_weekend_filter or not _is_night_bar(bar_time))):
            entry_price = row['close']
            if combined == 'BUY':
                entry_price += spread_points * point
            else:
                entry_price -= spread_points * point

            if fixed_volume > 0:
                volume = fixed_volume
            elif deposit > 0 and current_balance > 0:
                atr_val        = row['atr']
                stop_loss_pips = 2 * atr_val / point if atr_val > 0 else 100
                r_pct          = risk_pct if combined == 'BUY' else min(risk_pct + 10, 100)
                order_type     = mt5.ORDER_TYPE_BUY if combined == 'BUY' else mt5.ORDER_TYPE_SELL
                volume = calc_volume(current_balance, r_pct, stop_loss_pips, pip_value_per_lot,
                                     symbol_info, entry_price=entry_price, order_type=order_type)
            else:
                volume = 1.0

            position = {
                'type':        combined,
                'entry_price': entry_price,
                'entry_bar':   i,
                'entry_time':  row['time'],
                'volume':      volume,
                'indicators': {
                    'ema8':        row['ema8'],
                    'ema21':       row['ema21'],
                    'macd_line':   row['macd_line'],
                    'macd_signal': row['macd_signal'],
                    'rsi':         row['rsi'],
                    'atr':         row['atr'],
                },
            }
            trade_status = 1

        result.equity_curve.append(cumulative_pnl)

    if position is not None:
        row            = df.iloc[-1]
        if position['type'] == 'BUY':
            pnl_points = (row['close'] - position['entry_price']) / point
        else:
            pnl_points = (position['entry_price'] - row['close']) / point
        pnl_points    -= spread_points
        pnl_money      = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
        current_balance += pnl_money
        cumulative_pnl  += pnl_points
        result.trades.append(_make_default_trade(position, row, len(df) - 1, pnl_points, pnl_money, current_balance, 'END_OF_DATA'))
        result.equity_curve.append(cumulative_pnl)

    return result


# ─── Движок: модульные стратегии ─────────────────────────────────────────

def run_strategy_backtest(strategy, symbol, timeframe, bars=2000, spread_points=0,
                          deposit=0.0, risk_pct=80, fixed_volume=0.0,
                          date_from=None, date_to=None,
                          sl_atr_mult=0.0, tp_atr_mult=0.0,
                          breakeven_atr_mult=0.0, trail_atr_mult=0.0):
    rates = load_rates(symbol, timeframe, bars, date_from, date_to)
    if rates is None or len(rates) < 100:
        print(f"  Недостаточно данных для {symbol}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    symbol_info = mt5.symbol_info(symbol)
    point       = symbol_info.point if symbol_info else 0.0001
    return _run_strategy_on_df(
        strategy, df, point=point, symbol_info=symbol_info,
        skip_weekend_filter=_is_daily_or_higher_tf(timeframe),
        spread_points=spread_points, deposit=deposit, risk_pct=risk_pct,
        fixed_volume=fixed_volume, sl_atr_mult=sl_atr_mult, tp_atr_mult=tp_atr_mult,
        breakeven_atr_mult=breakeven_atr_mult, trail_atr_mult=trail_atr_mult,
    )


def _run_strategy_on_df(strategy, df, *, point, symbol_info, skip_weekend_filter,
                        spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0,
                        sl_atr_mult=0.0, tp_atr_mult=0.0,
                        breakeven_atr_mult=0.0, trail_atr_mult=0.0):
    df = strategy.compute_indicators(df)

    # ATR нужен для SL/TP/breakeven/trail — считаем, если стратегия не предоставила.
    need_atr = (sl_atr_mult > 0 or tp_atr_mult > 0
                or breakeven_atr_mult > 0 or trail_atr_mult > 0)
    if need_atr and 'atr' not in df.columns:
        import talib
        df['atr'] = talib.ATR(
            df['high'].values.astype(float),
            df['low'].values.astype(float),
            df['close'].values.astype(float),
            timeperiod=14,
        )

    pip_value_per_lot = 1

    result          = BacktestResult(initial_deposit=deposit)
    position        = None
    cumulative_pnl  = 0.0
    current_balance = deposit if deposit > 0 else 0.0
    peak_balance    = current_balance
    dd_block_until  = None  # pd.Timestamp; запрет входов до начала следующей недели
    warmup          = 60

    def _next_monday(ts: pd.Timestamp) -> pd.Timestamp:
        days = 7 - ts.weekday() if ts.weekday() > 0 else 7
        return (ts + pd.Timedelta(days=days)).normalize()

    def _update_dd_block(ts: pd.Timestamp):
        nonlocal peak_balance, dd_block_until
        if peak_balance <= 0:
            return
        if current_balance > peak_balance:
            peak_balance = current_balance
            return
        if dd_block_until is not None:
            return
        dd_pct = (peak_balance - current_balance) / peak_balance
        if dd_pct > 0.35:
            dd_block_until = _next_monday(ts)

    for i in range(warmup, len(df)):
        row = df.iloc[i]

        bar_time = row['time']
        if not isinstance(bar_time, pd.Timestamp):
            bar_time = pd.Timestamp(bar_time, unit='s')
        weekday = bar_time.weekday()
        hour    = bar_time.hour

        # Снимаем блокировку по просадке с началом новой недели.
        if dd_block_until is not None and bar_time >= dd_block_until:
            dd_block_until = None

        if skip_weekend_filter:
            weekend_block = False
        else:
            is_friday_close = weekday == 4 and hour >= 23
            is_weekend      = weekday in (5, 6)
            is_monday_early = weekday == 0 and hour < 2
            weekend_block   = is_friday_close or is_weekend or is_monday_early

        def _close_hedge(ref_row, ref_i, reason):
            nonlocal current_balance, cumulative_pnl
            if position is None:
                return
            h = position.get('hedge')
            if not h:
                return
            h_pnl_points = _calc_pnl_points(h, ref_row['close'], point, spread_points)
            h_pnl_money  = h_pnl_points * pip_value_per_lot * h['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
            current_balance += h_pnl_money
            cumulative_pnl  += h_pnl_points
            result.trades.append(_make_strategy_trade(h, ref_row, ref_i, h_pnl_points, h_pnl_money, current_balance, reason))
            position['hedge'] = None

        if weekend_block and position is not None and strategy.closes_on_weekend():
            pnl_points      = _calc_pnl_points(position, row['close'], point, spread_points)
            pnl_money       = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
            current_balance += pnl_money
            cumulative_pnl  += pnl_points
            result.trades.append(_make_strategy_trade(position, row, i, pnl_points, pnl_money, current_balance, 'WEEKEND'))
            _close_hedge(row, i, 'WEEKEND')
            _update_dd_block(bar_time)
            result.equity_curve.append(cumulative_pnl)
            strategy.on_trade_closed(position, 'WEEKEND')
            position = None
            continue

        # Breakeven + trailing SL — перед проверкой SL/TP.
        # Breakeven: после прохода +breakeven_mult × ATR в нашу сторону двигаем
        # SL в цену входа. Trail: SL не ниже (high - trail_mult × ATR) для BUY
        # / не выше (low + trail_mult × ATR) для SELL. SL только ужесточается.
        if position is not None and (breakeven_atr_mult > 0 or trail_atr_mult > 0):
            atr_val = row.get('atr') if 'atr' in row.index else None
            if atr_val is not None and not pd.isna(atr_val) and atr_val > 0:
                entry = position['entry_price']
                cur_sl = position.get('sl')
                if position['type'] == 'BUY':
                    new_sl = cur_sl
                    if breakeven_atr_mult > 0 and not position.get('_be_done'):
                        if row['high'] - entry >= breakeven_atr_mult * atr_val:
                            cand = entry
                            if new_sl is None or cand > new_sl:
                                new_sl = cand
                            position['_be_done'] = True
                    if trail_atr_mult > 0:
                        cand = row['high'] - trail_atr_mult * atr_val
                        if new_sl is None or cand > new_sl:
                            new_sl = cand
                    if new_sl is not None and new_sl != cur_sl:
                        position['sl'] = new_sl
                else:
                    new_sl = cur_sl
                    if breakeven_atr_mult > 0 and not position.get('_be_done'):
                        if entry - row['low'] >= breakeven_atr_mult * atr_val:
                            cand = entry
                            if new_sl is None or cand < new_sl:
                                new_sl = cand
                            position['_be_done'] = True
                    if trail_atr_mult > 0:
                        cand = row['low'] + trail_atr_mult * atr_val
                        if new_sl is None or cand < new_sl:
                            new_sl = cand
                    if new_sl is not None and new_sl != cur_sl:
                        position['sl'] = new_sl

        # SL/TP проверяем до weekend-skip: даже в «блокированные» часы (пт 23:00)
        # цена ещё ходит, и стоп/тейк должны срабатывать.
        if position is not None:
            hit_sl = hit_tp = False
            sl = position.get('sl')
            tp = position.get('tp')
            if position['type'] == 'BUY':
                if sl is not None and row['low']  <= sl: hit_sl = True
                if tp is not None and row['high'] >= tp: hit_tp = True
            else:
                if sl is not None and row['high'] >= sl: hit_sl = True
                if tp is not None and row['low']  <= tp: hit_tp = True

            if hit_sl:
                exit_price      = position['sl']
                pnl_points      = _calc_pnl_points(position, exit_price, point, spread_points)
                pnl_money       = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
                current_balance += pnl_money
                cumulative_pnl  += pnl_points
                result.trades.append(_make_strategy_trade(position, row, i, pnl_points, pnl_money, current_balance, 'SL', exit_price))
                _close_hedge(row, i, 'SL')
                _update_dd_block(bar_time)
                result.equity_curve.append(cumulative_pnl)
                strategy.on_trade_closed(position, 'SL')
                position = None
                continue

            if hit_tp:
                exit_price      = position['tp']
                pnl_points      = _calc_pnl_points(position, exit_price, point, spread_points)
                pnl_money       = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
                current_balance += pnl_money
                cumulative_pnl  += pnl_points
                result.trades.append(_make_strategy_trade(position, row, i, pnl_points, pnl_money, current_balance, 'TP', exit_price))
                _close_hedge(row, i, 'TP')
                _update_dd_block(bar_time)
                result.equity_curve.append(cumulative_pnl)
                strategy.on_trade_closed(position, 'TP')
                position = None
                continue

        if weekend_block:
            # Новые входы и strategy-exit на выходных заблокированы. Позиция
            # удерживается (если стратегия не закрывает по WEEKEND).
            result.equity_curve.append(cumulative_pnl)
            continue

        # Хедж-выход (закрывает только хедж, основная продолжает работать)
        if position is not None and position.get('hedge') is not None:
            if strategy.get_hedge_exit_signal(row, position['hedge']):
                _close_hedge(row, i, 'HEDGE_SIGNAL')

        if position is not None:
            if strategy.get_exit_signal(row, position):
                pnl_points      = _calc_pnl_points(position, row['close'], point, spread_points)
                pnl_money       = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
                current_balance += pnl_money
                cumulative_pnl  += pnl_points
                result.trades.append(_make_strategy_trade(position, row, i, pnl_points, pnl_money, current_balance, 'SIGNAL'))
                _close_hedge(row, i, 'SIGNAL')
                _update_dd_block(bar_time)
                result.equity_curve.append(cumulative_pnl)
                strategy.on_trade_closed(position, 'SIGNAL')
                position = None
                continue

        if (position is None and dd_block_until is None
                and (skip_weekend_filter or not _is_night_bar(bar_time))):
            signal = strategy.get_entry_signal(row)
            if signal:
                entry_price = row['close']
                if signal == 'BUY':
                    entry_price += spread_points * point
                else:
                    entry_price -= spread_points * point

                sl, tp = strategy.get_sl_tp(row, signal, point)

                # Пользовательские множители SL/TP переопределяют значения стратегии.
                # 0 = не использовать соответствующий уровень.
                # Стратегии с трейлинг-выходом (uses_trailing_exit) сохраняют
                # свой TP=None, иначе фиксированный TP закроет позицию до того,
                # как трейлинг успеет развиться.
                trailing = bool(getattr(strategy, 'uses_trailing_exit', lambda: False)())
                if sl_atr_mult > 0 or (tp_atr_mult > 0 and not trailing):
                    atr_val = row.get('atr') if 'atr' in row.index else None
                    if atr_val is not None and not pd.isna(atr_val) and atr_val > 0:
                        if sl_atr_mult > 0:
                            sl = (entry_price - sl_atr_mult * atr_val) if signal == 'BUY' \
                                 else (entry_price + sl_atr_mult * atr_val)
                        elif not trailing:
                            sl = None
                        if tp_atr_mult > 0 and not trailing:
                            tp = (entry_price + tp_atr_mult * atr_val) if signal == 'BUY' \
                                 else (entry_price - tp_atr_mult * atr_val)
                        elif tp_atr_mult <= 0 and not trailing:
                            tp = None

                if fixed_volume > 0:
                    volume = fixed_volume
                elif deposit > 0 and current_balance > 0 and sl is not None:
                    sl_pips    = abs(entry_price - sl) / point
                    order_type = mt5.ORDER_TYPE_BUY if signal == 'BUY' else mt5.ORDER_TYPE_SELL
                    volume = calc_volume(current_balance, risk_pct, sl_pips, pip_value_per_lot,
                                         symbol_info, entry_price=entry_price, order_type=order_type)
                else:
                    volume = 1.0

                indicators = {}
                for col in strategy.indicator_columns():
                    if col in row.index:
                        val = row[col]
                        indicators[col] = float(val) if not pd.isna(val) else None

                position = {
                    'type':        signal,
                    'entry_price': entry_price,
                    'entry_bar':   i,
                    'entry_time':  row['time'],
                    'volume':      volume,
                    'sl':          sl,
                    'tp':          tp,
                    'indicators':  indicators,
                }

                if strategy.wants_hedge():
                    hedge_side  = 'SELL' if signal == 'BUY' else 'BUY'
                    hedge_entry = row['close']
                    if hedge_side == 'BUY':
                        hedge_entry += spread_points * point
                    else:
                        hedge_entry -= spread_points * point
                    position['hedge'] = {
                        'type':        hedge_side,
                        'entry_price': hedge_entry,
                        'entry_bar':   i,
                        'entry_time':  row['time'],
                        'volume':      volume,
                        'sl':          None,
                        'tp':          None,
                        'indicators':  dict(indicators),
                    }

        result.equity_curve.append(cumulative_pnl)

    if position is not None:
        row             = df.iloc[-1]
        pnl_points      = _calc_pnl_points(position, row['close'], point, spread_points)
        pnl_money       = pnl_points * pip_value_per_lot * position['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
        current_balance += pnl_money
        cumulative_pnl  += pnl_points
        result.trades.append(_make_strategy_trade(position, row, len(df) - 1, pnl_points, pnl_money, current_balance, 'END_OF_DATA'))
        h = position.get('hedge')
        if h:
            h_pnl_points = _calc_pnl_points(h, row['close'], point, spread_points)
            h_pnl_money  = h_pnl_points * pip_value_per_lot * h['volume'] if (deposit > 0 or fixed_volume > 0) else 0.0
            current_balance += h_pnl_money
            cumulative_pnl  += h_pnl_points
            result.trades.append(_make_strategy_trade(h, row, len(df) - 1, h_pnl_points, h_pnl_money, current_balance, 'END_OF_DATA'))
        result.equity_curve.append(cumulative_pnl)
        strategy.on_trade_closed(position, 'END_OF_DATA')

    return result


# ─── Вывод результатов ───────────────────────────────────────────────────

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


# ─── CLI ──────────────────────────────────────────────────────────────────

def main():
    from strategies import STRATEGIES

    all_strategies = ['default'] + list(STRATEGIES.keys())

    parser = argparse.ArgumentParser(description='Бэктест торговых стратегий TradingHouse')
    parser.add_argument('--strategy', default='default',
                        choices=all_strategies + ['all'],
                        help='Стратегия: default, all или имя из strategies/')
    parser.add_argument('--symbol',    default='XAUUSDrfd')
    parser.add_argument('--bars',      type=int,   default=2000)
    parser.add_argument('--spread',    type=int,   default=0)
    parser.add_argument('--deposit',   type=float, default=0)
    parser.add_argument('--risk',      type=float, default=80)
    parser.add_argument('--volume',    type=float, default=0)
    parser.add_argument('--timeframe', default=None,
                        choices=['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'])
    parser.add_argument('--start',     default=None, help='YYYY-MM-DD')
    parser.add_argument('--end',       default=None, help='YYYY-MM-DD')
    args = parser.parse_args()

    tf_map = {
        'M1':  mt5.TIMEFRAME_M1,  'M5':  mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
        'H1':  mt5.TIMEFRAME_H1,  'H4':  mt5.TIMEFRAME_H4,
        'D1':  mt5.TIMEFRAME_D1,
    }

    date_from = datetime.strptime(args.start, '%Y-%m-%d') if args.start else None
    date_to   = datetime.strptime(args.end,   '%Y-%m-%d') if args.end   else None

    account = Account.account
    auth = MT5Auth(account)
    auth.login()

    # Определяем список стратегий для запуска
    if args.strategy == 'all':
        strategies_to_run = list(STRATEGIES.keys())
    elif args.strategy == 'default':
        strategies_to_run = ['default']
    else:
        strategies_to_run = [args.strategy]

    date_str = ''
    if date_from: date_str += f', с {args.start}'
    if date_to:   date_str += f' по {args.end}'

    for strat_name in strategies_to_run:
        if strat_name == 'default':
            tf_name  = args.timeframe or 'H1'
            timeframe = tf_map[tf_name]
            desc     = 'MA + MACD + RSI (основная)'
            print(f"\nЗапуск {desc}: {args.symbol}, {tf_name}, {args.bars} баров{date_str}...")
            result = run_backtest(
                args.symbol, timeframe, bars=args.bars, spread_points=args.spread,
                deposit=args.deposit, risk_pct=args.risk, fixed_volume=args.volume,
                date_from=date_from, date_to=date_to
            )
        else:
            strat    = STRATEGIES[strat_name]()
            tf_name  = args.timeframe or strat.default_timeframe
            timeframe = tf_map[tf_name]
            desc     = strat.description
            print(f"\nЗапуск {desc}: {args.symbol}, {tf_name}, {args.bars} баров{date_str}...")
            result = run_strategy_backtest(
                strat, args.symbol, timeframe, bars=args.bars, spread_points=args.spread,
                deposit=args.deposit, risk_pct=args.risk, fixed_volume=args.volume,
                date_from=date_from, date_to=date_to
            )

        print_report(desc, args.symbol, tf_name, result, deposit=args.deposit)


if __name__ == '__main__':
    main()
