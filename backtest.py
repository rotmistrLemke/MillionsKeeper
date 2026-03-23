"""
Бэктест стратегии из основного торгового цикла.

Стратегия:
  Вход: MA simple (EMA8 > EMA21) + MACD + RSI — все три дают одинаковый сигнал
  Выход: RSI пересекает 50 (LONG: rsi < 50, SHORT: rsi > 50)

Запуск:
  python backtest.py                                        — XAUUSDrfd, 2000 баров H1
  python backtest.py --symbol EURUSDrfd                     — другой символ
  python backtest.py --bars 5000 --deposit 10000            — 10 000$ депозит
  python backtest.py --symbol XAUUSDrfd --deposit 5000 --risk 2 --spread 30
"""

import argparse
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import talib
from datetime import datetime
from authenticator import MT5Auth
from account import Account


# ─── Расчёт индикаторов на полном массиве ────────────────────────────────

def calc_ema_series(prices, period):
    """EMA по формуле из indicators.py (ручная, не pandas)."""
    alpha = 2 / (period + 1)
    ema = np.empty_like(prices)
    ema[0] = prices[0]
    for i in range(1, len(prices)):
        ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
    return ema


def compute_indicators(df):
    """
    Вычисляет все индикаторы, используемые в стратегии, на весь DataFrame.
    Возвращает тот же df с добавленными колонками.
    """
    close = df['close'].values.astype(float)
    high = df['high'].values.astype(float)
    low = df['low'].values.astype(float)

    # --- MA simple signal: EMA(8) vs EMA(21) ---
    df['ema8'] = pd.Series(close).ewm(span=8, adjust=False).mean().values
    df['ema21'] = pd.Series(close).ewm(span=21, adjust=False).mean().values

    # --- MACD (ручной расчёт как в indicators.py) ---
    ema_fast = calc_ema_series(close, 12)
    ema_slow = calc_ema_series(close, 26)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema_series(macd_line, 9)
    df['macd_line'] = macd_line
    df['macd_signal'] = signal_line
    df['macd_prev'] = np.roll(macd_line, 1)
    df['macd_prev'].iloc[0] = np.nan

    # --- RSI (talib, period=14) ---
    df['rsi'] = talib.RSI(close, timeperiod=14)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['rsi_prev2'] = df['rsi'].shift(2)

    # --- ATR (period=14) ---
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
    )
    df['atr'] = pd.Series(tr).rolling(14).mean().values

    return df


# ─── Сигналы ──────────────────────────────────────────────────────────────

def get_ma_signal(row):
    if row['ema8'] > row['ema21']:
        return 'BUY'
    elif row['ema8'] < row['ema21']:
        return 'SELL'
    return 'NO_SIGNAL'


def get_macd_signal(row):
    h = row['macd_line']
    p = row['macd_prev']
    s = row['macd_signal']
    if pd.isna(p):
        return 'NO_SIGNAL'
    if h > 0 and h > p and h > s:
        return 'BUY'
    elif h < 0 and h < p and h < s:
        return 'SELL'
    return 'NO_SIGNAL'


def get_rsi_signal(row):
    r = row['rsi']
    rp = row['rsi_prev']
    rp2 = row['rsi_prev2']
    if pd.isna(r) or pd.isna(rp) or pd.isna(rp2):
        return 'NO_SIGNAL'
    if 70 > r > 50 and r > rp and rp > rp2:
        return 'BUY'
    elif 50 > r > 30 and r < rp and rp < rp2:
        return 'SELL'
    return 'NO_SIGNAL'


def get_combined_signal(row):
    ma_s = get_ma_signal(row)
    macd_s = get_macd_signal(row)
    rsi_s = get_rsi_signal(row)
    if ma_s == 'BUY' and macd_s == 'BUY' and rsi_s == 'BUY':
        return 'BUY'
    elif ma_s == 'SELL' and macd_s == 'SELL' and rsi_s == 'SELL':
        return 'SELL'
    return 'NO_SIGNAL'


# ─── Расчёт стоимости пункта ─────────────────────────────────────────────

def get_pip_value(symbol, volume=1.0):
    """
    Стоимость 1 пункта для данного символа и объёма.
    Использует данные MT5 symbol_info.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.0
    pip_value = info.point * info.trade_contract_size * volume
    # Конвертация если валюта прибыли != валюта депозита
    if info.currency_profit != info.currency_margin:
        conv_symbol = info.currency_profit + info.currency_margin + 'rfd'
        conv_info = mt5.symbol_info(conv_symbol)
        if conv_info is not None:
            tick = mt5.symbol_info_tick(conv_symbol)
            if tick:
                pip_value *= tick.ask
        else:
            conv_symbol = info.currency_margin + info.currency_profit + 'rfd'
            conv_info = mt5.symbol_info(conv_symbol)
            if conv_info is not None:
                tick = mt5.symbol_info_tick(conv_symbol)
                if tick:
                    pip_value /= tick.bid
    return pip_value


# ─── Бэктест-движок ──────────────────────────────────────────────────────

class BacktestResult:
    def __init__(self, initial_deposit=0.0):
        self.trades = []
        self.equity_curve = []
        self.initial_deposit = initial_deposit

    @property
    def total_trades(self):
        return len(self.trades)

    @property
    def winning_trades(self):
        return [t for t in self.trades if t['pnl_points'] > 0]

    @property
    def losing_trades(self):
        return [t for t in self.trades if t['pnl_points'] <= 0]

    @property
    def win_rate(self):
        return len(self.winning_trades) / self.total_trades * 100 if self.total_trades else 0

    @property
    def total_pnl_points(self):
        return sum(t['pnl_points'] for t in self.trades)

    @property
    def total_pnl_money(self):
        return sum(t['pnl_money'] for t in self.trades)

    @property
    def avg_win(self):
        wins = [t['pnl_points'] for t in self.winning_trades]
        return np.mean(wins) if wins else 0

    @property
    def avg_loss(self):
        losses = [t['pnl_points'] for t in self.losing_trades]
        return np.mean(losses) if losses else 0

    @property
    def avg_win_money(self):
        wins = [t['pnl_money'] for t in self.winning_trades]
        return np.mean(wins) if wins else 0

    @property
    def avg_loss_money(self):
        losses = [t['pnl_money'] for t in self.losing_trades]
        return np.mean(losses) if losses else 0

    @property
    def profit_factor(self):
        gross_win = sum(t['pnl_points'] for t in self.winning_trades)
        gross_loss = abs(sum(t['pnl_points'] for t in self.losing_trades))
        return gross_win / gross_loss if gross_loss > 0 else float('inf')

    @property
    def max_drawdown_points(self):
        if not self.equity_curve:
            return 0
        peak = self.equity_curve[0]
        max_dd = 0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def max_drawdown_money(self):
        """Макс. просадка в деньгах (по equity_curve_money)."""
        if not self.trades:
            return 0
        money_curve = []
        cumulative = self.initial_deposit
        for t in self.trades:
            cumulative += t['pnl_money']
            money_curve.append(cumulative)
        if not money_curve:
            return 0
        peak = money_curve[0]
        max_dd = 0
        for eq in money_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def max_drawdown_pct(self):
        """Макс. просадка в % от пикового баланса."""
        if not self.trades or self.initial_deposit <= 0:
            return 0
        money_curve = []
        cumulative = self.initial_deposit
        for t in self.trades:
            cumulative += t['pnl_money']
            money_curve.append(cumulative)
        peak = money_curve[0]
        max_dd_pct = 0
        for eq in money_curve:
            if eq > peak:
                peak = eq
            if peak > 0:
                dd_pct = (peak - eq) / peak * 100
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct
        return max_dd_pct

    @property
    def final_balance(self):
        return self.initial_deposit + self.total_pnl_money

    @property
    def return_pct(self):
        if self.initial_deposit <= 0:
            return 0
        return self.total_pnl_money / self.initial_deposit * 100

    @property
    def max_consecutive_losses(self):
        max_streak = 0
        current = 0
        for t in self.trades:
            if t['pnl_points'] <= 0:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak


def calc_volume(balance, risk_pct, stop_loss_pips, pip_value_per_lot, symbol_info):
    """
    Расчёт объёма сделки как в trading.calculateMaxVolumeWithMarginCheck.
    risk_pct: процент риска от баланса (напр. 80 для LONG, 90 для SHORT)
    stop_loss_pips: стоп-лосс в пунктах (2 * ATR / point)
    """
    if pip_value_per_lot <= 0 or stop_loss_pips <= 0:
        return symbol_info.volume_min if symbol_info else 0.01

    risk_money = balance * (risk_pct / 100)
    stop_loss_cost = pip_value_per_lot * stop_loss_pips
    volume = risk_money / stop_loss_cost

    if symbol_info:
        volume = min(volume, symbol_info.volume_max)
        volume = max(volume, symbol_info.volume_min)
        if symbol_info.volume_step > 0:
            volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step

    return volume


def run_backtest(symbol, timeframe, bars=2000, spread_points=0, deposit=0.0, risk_pct=80):
    """
    Запускает бэктест стратегии.

    Параметры:
        symbol:         торговый символ (напр. 'XAUUSDrfd')
        timeframe:      таймфрейм MT5 (напр. mt5.TIMEFRAME_H1)
        bars:           количество исторических баров
        spread_points:  спред в пунктах (вычитается при входе)
        deposit:        начальный депозит в $ (0 = без расчёта денег)
        risk_pct:       процент риска от баланса на сделку (по умолч. 80, как в боте)

    Возвращает:
        BacktestResult с полной статистикой
    """
    # Загружаем данные
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) < 100:
        print(f"Недостаточно данных для бэктеста {symbol}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = compute_indicators(df)

    symbol_info = mt5.symbol_info(symbol)
    point = symbol_info.point if symbol_info else 0.0001

    # Стоимость пункта для 1 лота
    pip_value_per_lot = get_pip_value(symbol, 1.0)

    result = BacktestResult(initial_deposit=deposit)
    position = None
    cumulative_pnl = 0.0
    current_balance = deposit if deposit > 0 else 0.0

    trade_status = 0
    warmup = 50

    for i in range(warmup, len(df)):
        row = df.iloc[i]

        if pd.isna(row['rsi']) or pd.isna(row['atr']) or pd.isna(row['macd_prev']):
            continue

        # --- Расписание: пятница 23:30 закрытие, понедельник 02:00 открытие ---
        bar_time = row['time']
        if not isinstance(bar_time, pd.Timestamp):
            bar_time = pd.Timestamp(bar_time, unit='s')
        weekday = bar_time.weekday()  # 0=Пн, 4=Пт
        hour = bar_time.hour
        minute = bar_time.minute

        # Пятница после 23:30 или выходные — закрыть позицию и не торговать
        is_friday_close = weekday == 4 and (hour > 23 or (hour == 23 and minute >= 30))
        is_weekend = weekday in (5, 6)
        is_monday_early = weekday == 0 and (hour < 2)
        weekend_block = is_friday_close or is_weekend or is_monday_early

        # Принудительное закрытие позиции на выходные
        if weekend_block and position is not None:
            if position['type'] == 'BUY':
                pnl_points = (row['close'] - position['entry_price']) / point
            else:
                pnl_points = (position['entry_price'] - row['close']) / point
            pnl_points -= spread_points

            pnl_money = pnl_points * pip_value_per_lot * position['volume'] if deposit > 0 else 0.0
            current_balance += pnl_money
            cumulative_pnl += pnl_points

            result.trades.append({
                'type': position['type'],
                'entry_time': position['entry_time'],
                'entry_price': position['entry_price'],
                'exit_time': row['time'],
                'exit_price': row['close'],
                'pnl_points': pnl_points,
                'pnl_money': pnl_money,
                'volume': position['volume'],
                'bars_held': i - position['entry_bar'],
                'exit_reason': 'WEEKEND',
                'balance_after': current_balance,
                'indicators': position['indicators']
            })
            result.equity_curve.append(cumulative_pnl)

            trade_status = 0
            position = None
            continue

        # Блокировка торговли на выходных
        if weekend_block:
            result.equity_curve.append(cumulative_pnl)
            continue

        combined = get_combined_signal(row)

        # --- Проверка выхода ---
        if position is not None:
            current_rsi = row['rsi']

            if position['type'] == 'BUY':
                pnl_points = (row['close'] - position['entry_price']) / point
                should_close = current_rsi < 45
            else:
                pnl_points = (position['entry_price'] - row['close']) / point
                should_close = current_rsi > 55

            if should_close:
                pnl_points -= spread_points

                # Денежный P&L
                pnl_money = pnl_points * pip_value_per_lot * position['volume'] if deposit > 0 else 0.0
                current_balance += pnl_money
                cumulative_pnl += pnl_points

                result.trades.append({
                    'type': position['type'],
                    'entry_time': position['entry_time'],
                    'entry_price': position['entry_price'],
                    'exit_time': row['time'],
                    'exit_price': row['close'],
                    'pnl_points': pnl_points,
                    'pnl_money': pnl_money,
                    'volume': position['volume'],
                    'bars_held': i - position['entry_bar'],
                    'exit_reason': 'RSI',
                    'balance_after': current_balance,
                    'indicators': position['indicators']
                })
                result.equity_curve.append(cumulative_pnl)

                trade_status = 1
                position = None
                continue

        # --- Обновление статуса ---
        if trade_status == 1:
            trade_status = 0
        elif trade_status == 2:
            if get_macd_signal(row) == 'NO_SIGNAL':
                trade_status = 0

        # --- Проверка входа ---
        if position is None and trade_status == 0 and combined != 'NO_SIGNAL':
            entry_price = row['close']
            if combined == 'BUY':
                entry_price += spread_points * point
            else:
                entry_price -= spread_points * point

            # Расчёт объёма
            atr_val = row['atr']
            stop_loss_pips = 2 * atr_val / point if atr_val > 0 else 100

            if deposit > 0 and current_balance > 0:
                r_pct = risk_pct if combined == 'BUY' else min(risk_pct + 10, 100)  # SHORT: +10% как в боте
                volume = calc_volume(current_balance, r_pct, stop_loss_pips, pip_value_per_lot, symbol_info)
            else:
                volume = 1.0  # фиксированный лот если депозит не указан

            position = {
                'type': combined,
                'entry_price': entry_price,
                'entry_bar': i,
                'entry_time': row['time'],
                'volume': volume,
                'indicators': {
                    'ema8': row['ema8'],
                    'ema21': row['ema21'],
                    'macd_line': row['macd_line'],
                    'macd_signal': row['macd_signal'],
                    'rsi': row['rsi'],
                    'atr': row['atr'],
                }
            }
            trade_status = 1

        result.equity_curve.append(cumulative_pnl)

    # Закрываем незакрытую позицию
    if position is not None:
        row = df.iloc[-1]
        if position['type'] == 'BUY':
            pnl_points = (row['close'] - position['entry_price']) / point
        else:
            pnl_points = (position['entry_price'] - row['close']) / point
        pnl_points -= spread_points
        pnl_money = pnl_points * pip_value_per_lot * position['volume'] if deposit > 0 else 0.0
        current_balance += pnl_money
        cumulative_pnl += pnl_points
        result.trades.append({
            'type': position['type'],
            'entry_time': position['entry_time'],
            'entry_price': position['entry_price'],
            'exit_time': row['time'],
            'exit_price': row['close'],
            'pnl_points': pnl_points,
            'pnl_money': pnl_money,
            'volume': position['volume'],
            'bars_held': len(df) - 1 - position['entry_bar'],
            'exit_reason': 'END_OF_DATA',
            'balance_after': current_balance,
            'indicators': position['indicators']
        })
        result.equity_curve.append(cumulative_pnl)

    return result


# ─── Форматированный вывод (CLI) ─────────────────────────────────────────

def print_report(symbol, timeframe_name, bars, spread, result, deposit=0):
    if result is None:
        print("Бэктест не удался — нет данных.")
        return

    print(f"\n{'='*60}")
    print(f"  БЭКТЕСТ СТРАТЕГИИ: MA + MACD + RSI")
    print(f"{'='*60}")
    print(f"  Символ:           {symbol}")
    print(f"  Таймфрейм:        {timeframe_name}")
    print(f"  Баров:            {bars}")
    print(f"  Спред (пункты):   {spread}")
    if deposit > 0:
        print(f"  Начальный депозит: {deposit:,.2f} $")
    print(f"{'='*60}")
    print(f"  Всего сделок:     {result.total_trades}")
    print(f"  Прибыльных:       {len(result.winning_trades)}")
    print(f"  Убыточных:        {len(result.losing_trades)}")
    print(f"  Win Rate:         {result.win_rate:.1f}%")
    print(f"{'─'*60}")
    print(f"  Итого P&L:        {result.total_pnl_points:+.1f} пунктов")
    print(f"  Средняя прибыль:  {result.avg_win:+.1f} пунктов")
    print(f"  Средний убыток:   {result.avg_loss:+.1f} пунктов")
    print(f"  Profit Factor:    {result.profit_factor:.2f}")
    print(f"  Макс. просадка:   {result.max_drawdown_points:.1f} пунктов")
    print(f"  Макс. серия убытков: {result.max_consecutive_losses}")

    if deposit > 0:
        print(f"{'─'*60}")
        print(f"  ФИНАНСОВЫЙ РЕЗУЛЬТАТ:")
        print(f"  Итого P&L:        {result.total_pnl_money:+,.2f} $")
        print(f"  Финальный баланс: {result.final_balance:,.2f} $")
        print(f"  Доходность:       {result.return_pct:+.2f}%")
        print(f"  Средняя прибыль:  {result.avg_win_money:+,.2f} $")
        print(f"  Средний убыток:   {result.avg_loss_money:+,.2f} $")
        print(f"  Макс. просадка:   {result.max_drawdown_money:,.2f} $ ({result.max_drawdown_pct:.1f}%)")

    print(f"{'─'*60}")

    if result.trades:
        avg_bars = np.mean([t['bars_held'] for t in result.trades])
        print(f"  Среднее удержание: {avg_bars:.1f} баров")

        by_reason = {}
        for t in result.trades:
            r = t['exit_reason']
            if r not in by_reason:
                by_reason[r] = 0
            by_reason[r] += 1
        print(f"  Причины выхода:")
        for reason, count in by_reason.items():
            print(f"    {reason}: {count}")

    print(f"\n{'─'*60}")
    if deposit > 0:
        print(f"  Последние 10 сделок:")
        print(f"  {'Тип':<6} {'Вход':<16} {'Объём':>6} {'P&L $':>10} {'P&L пунк.':>10} {'Баланс':>10}")
        print(f"  {'─'*60}")
        for t in result.trades[-10:]:
            entry_t = t['entry_time'].strftime('%d.%m %H:%M') if hasattr(t['entry_time'], 'strftime') else str(t['entry_time'])
            print(f"  {t['type']:<6} {entry_t:<16} {t['volume']:>6.2f} {t['pnl_money']:>+10.2f} {t['pnl_points']:>+10.1f} {t.get('balance_after', 0):>10,.2f}")
            ind = t.get('indicators', {})
            if ind:
                print(f"         EMA8={ind['ema8']:.5f}  EMA21={ind['ema21']:.5f}  MACD={ind['macd_line']:.5f}  Sig={ind['macd_signal']:.5f}  RSI={ind['rsi']:.1f}  ATR={ind['atr']:.5f}")
    else:
        print(f"  Последние 10 сделок:")
        print(f"  {'Тип':<6} {'Вход':<20} {'Выход':<20} {'P&L':>10} {'Баров':>6} {'Причина':<12}")
        print(f"  {'─'*76}")
        for t in result.trades[-10:]:
            entry_t = t['entry_time'].strftime('%Y-%m-%d %H:%M') if hasattr(t['entry_time'], 'strftime') else str(t['entry_time'])
            exit_t = t['exit_time'].strftime('%Y-%m-%d %H:%M') if hasattr(t['exit_time'], 'strftime') else str(t['exit_time'])
            print(f"  {t['type']:<6} {entry_t:<20} {exit_t:<20} {t['pnl_points']:>+10.1f} {t['bars_held']:>6} {t['exit_reason']:<12}")
            ind = t.get('indicators', {})
            if ind:
                print(f"         EMA8={ind['ema8']:.5f}  EMA21={ind['ema21']:.5f}  MACD={ind['macd_line']:.5f}  Sig={ind['macd_signal']:.5f}  RSI={ind['rsi']:.1f}  ATR={ind['atr']:.5f}")

    print(f"{'='*60}\n")


# ─── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Бэктест торговой стратегии MA+MACD+RSI')
    parser.add_argument('--symbol', default='XAUUSDrfd', help='Торговый символ (по умолчанию XAUUSDrfd)')
    parser.add_argument('--bars', type=int, default=2000, help='Количество баров истории (по умолчанию 2000)')
    parser.add_argument('--spread', type=int, default=0, help='Спред в пунктах (по умолчанию 0)')
    parser.add_argument('--deposit', type=float, default=0, help='Начальный депозит в $ (0 = без расчёта денег)')
    parser.add_argument('--risk', type=float, default=80, help='Процент риска на сделку (по умолчанию 80)')
    parser.add_argument('--timeframe', default='H1', choices=['M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
                        help='Таймфрейм (по умолчанию H1)')
    args = parser.parse_args()

    tf_map = {
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    timeframe = tf_map[args.timeframe]

    account = Account.account
    auth = MT5Auth(account)
    auth.login()

    dep_str = f", депозит={args.deposit}$" if args.deposit > 0 else ""
    print(f"Запуск бэктеста: {args.symbol}, {args.timeframe}, {args.bars} баров, спред={args.spread}{dep_str}...")

    if args.symbol == 'ALL':
        from settings import Dictionary
        symbols = [s for s in Dictionary.symbolTradingStatus.keys()
                   if Dictionary.symbolTradingStatus[s] < 3]
        for sym in symbols:
            print(f"\nБэктест {sym}...")
            res = run_backtest(sym, timeframe, bars=args.bars, spread_points=args.spread,
                               deposit=args.deposit, risk_pct=args.risk)
            print_report(sym, args.timeframe, args.bars, args.spread, res, deposit=args.deposit)
    else:
        result = run_backtest(args.symbol, timeframe, bars=args.bars, spread_points=args.spread,
                              deposit=args.deposit, risk_pct=args.risk)
        print_report(args.symbol, args.timeframe, args.bars, args.spread, result, deposit=args.deposit)


if __name__ == '__main__':
    main()
