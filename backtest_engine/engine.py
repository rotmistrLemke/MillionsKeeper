"""Движки бэктеста TradingHouse: основная (default) и модульные стратегии."""

import MetaTrader5 as mt5
import pandas as pd
from backtest_engine.filters import _is_night_bar, _is_daily_or_higher_tf
from backtest_engine.default_strategy import compute_indicators, get_combined_signal, get_macd_signal
from backtest_engine.result import BacktestResult
from backtest_engine.trades import _calc_pnl_points, _make_default_trade, _make_strategy_trade
from backtest_engine.sizing import calc_volume
from backtest_engine.data import load_rates
from backtest_engine._scaffolding import next_monday, is_weekend_block


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
            dd_block_until = next_monday(ts)

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
            weekend_block = is_weekend_block(weekday, hour)

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
            dd_block_until = next_monday(ts)

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
            weekend_block = is_weekend_block(weekday, hour)

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
