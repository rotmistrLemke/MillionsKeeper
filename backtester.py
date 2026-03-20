"""
Тестер стратегии (Backtester) для торговой системы MillionsKeeper.

Воспроизводит логику основного торгового цикла (trading_loop) на исторических данных.
Загружает 1000 свечей назад для указанной пары, проходит по ним свеча за свечой,
рассчитывает индикаторы на каждом шаге и симулирует открытие/закрытие позиций.

Использование:
    python backtester.py                         # все активные пары
    python backtester.py --symbol EURUSDrfd      # одна пара
    python backtester.py --symbol XAUUSDrfd --bars 2000
"""

import argparse
import math
import os
from datetime import datetime
from dataclasses import dataclass, field

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import talib

from account import Account
from authenticator import MT5Auth
from settings import GlobalValues, Dictionary


# ───────────────────────── helpers / индикаторы ──────────────────────────

def _ema_list(prices: list, period: int) -> list:
    """EMA как список (для MACD)."""
    alpha = 2 / (period + 1)
    ema = [prices[0]]
    for i in range(1, len(prices)):
        ema.append(alpha * prices[i] + (1 - alpha) * ema[i - 1])
    return ema


def calc_macd(closes: pd.Series, fast=12, slow=26, signal_period=9):
    """Возвращает (hist_line, prev_hist_line, signal_line) или (None,)*3."""
    data = closes.tolist()
    if len(data) < slow + signal_period + 2:
        return None, None, None
    ema_fast = _ema_list(data, fast)
    ema_slow = _ema_list(data, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    sig = _ema_list(macd_line, signal_period)
    return macd_line[-2], macd_line[-3], sig[-2]


def macd_signal(hist_line, prev_hist_line, signal_line):
    if hist_line is None:
        return {'signal': 'NO_SIGNAL', 'hist_line': 0, 'prev_hist_line': 0, 'signal_line': 0}
    d = {'hist_line': hist_line, 'prev_hist_line': prev_hist_line, 'signal_line': signal_line}
    if hist_line > 0 and hist_line > prev_hist_line and hist_line > signal_line:
        return {'signal': 'BUY', **d}
    elif hist_line < 0 and hist_line < prev_hist_line and hist_line < signal_line:
        return {'signal': 'SELL', **d}
    elif hist_line > 0 and hist_line < prev_hist_line:
        return {'signal': 'CLOSE_BUY', **d}
    elif hist_line < 0 and hist_line > prev_hist_line:
        return {'signal': 'CLOSE_SELL', **d}
    return {'signal': 'NO_SIGNAL', **d}


def calc_rsi(closes: pd.Series, period=14):
    """Возвращает pd.Series RSI."""
    arr = np.array(closes, dtype=float)
    return pd.Series(talib.RSI(arr, timeperiod=period), index=closes.index)


def rsi_signal_func(rsi_val, prev_rsi, prev2_rsi):
    d = {'rsi': rsi_val, 'prev_rsi': prev_rsi, 'prev2_rsi': prev2_rsi}
    if 70 > rsi_val > 50 and rsi_val > prev_rsi and prev_rsi > prev2_rsi:
        return {'signal': 'BUY', **d}
    elif 50 > rsi_val > 30 and rsi_val < prev_rsi and prev_rsi < prev2_rsi:
        return {'signal': 'SELL', **d}
    return {'signal': 'NO_SIGNAL', **d}


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_adx(high_arr, low_arr, close_arr, adx_period=14):
    """Возвращает (adx[], pdi[], ndi[])."""
    n = len(high_arr)
    pdi = [0.0] * n
    ndi = [0.0] * n
    adx = [0.0] * n
    tmp_buf = [0.0] * n
    raw_p = [0.0] * n
    raw_n = [0.0] * n

    alpha = 2 / (adx_period + 1)

    for i in range(1, n):
        hp, pp = high_arr[i], high_arr[i - 1]
        lp, pl = low_arr[i], low_arr[i - 1]
        pc = close_arr[i - 1]
        tmp_pos = hp - pp
        tmp_neg = pl - lp
        if tmp_pos < 0:
            tmp_pos = 0
        if tmp_neg < 0:
            tmp_neg = 0
        if tmp_pos > tmp_neg:
            tmp_neg = 0
        elif tmp_neg > tmp_pos:
            tmp_pos = 0
        else:
            tmp_pos = tmp_neg = 0

        tr = max(hp - lp, abs(hp - pc), abs(lp - pc))
        raw_p[i] = 100 * tmp_pos / tr if tr != 0 else 0
        raw_n[i] = 100 * tmp_neg / tr if tr != 0 else 0
        pdi[i] = (raw_p[i] - pdi[i - 1]) * alpha + pdi[i - 1] if i else 0
        ndi[i] = (raw_n[i] - ndi[i - 1]) * alpha + ndi[i - 1] if i else 0
        s = pdi[i] + ndi[i]
        tmp_buf[i] = 100 * abs(pdi[i] - ndi[i]) / s if s != 0 else 0

    for i in range(1, n):
        adx[i] = (tmp_buf[i] - adx[i - 1]) * alpha + adx[i - 1]

    return adx, pdi, ndi


def adx_signal_func(adx_val, pdi_val, ndi_val):
    if adx_val > 25 and pdi_val > ndi_val:
        return {'signal': 'BUY'}
    elif adx_val > 25 and ndi_val > pdi_val:
        return {'signal': 'SELL'}
    return {'signal': 'NO_SIGNAL'}


def ma_simple_signal(fast_val, slow_val):
    if pd.isna(fast_val) or pd.isna(slow_val):
        return 'NO_SIGNAL'
    if fast_val > slow_val:
        return 'BUY'
    elif fast_val < slow_val:
        return 'SELL'
    return 'NO_SIGNAL'


# ───────────────────────── Проверка торговли перед выходными ──────────────

def is_trading_blocked_before_weekend(bar_time: datetime) -> bool:
    """
    Возвращает True, если торговля должна быть заблокирована.
    Блокировка: пятница с 23:30 до начала понедельника.
    """
    weekday = bar_time.weekday()  # 0=пн, 1=вт, ..., 4=пт, 5=сб, 6=вс
    hour = bar_time.hour
    minute = bar_time.minute
    
    # Пятница после 23:30
    if weekday == 4 and (hour > 23 or (hour == 23 and minute >= 30)):
        return True
    
    # Суббота и воскресенье полностью заблокированы
    if weekday in (5, 6):
        return True
    
    return False


# ───────────────────────── Позиция / Сделка ─────────────────────────────

@dataclass
class Position:
    direction: str  # 'BUY' или 'SELL'
    open_price: float
    open_time: datetime
    open_bar: int
    atr_at_open: float
    symbol: str
    volume: float  # размер лота в контрактах


@dataclass
class Trade:
    direction: str
    open_price: float
    close_price: float
    open_time: datetime
    close_time: datetime
    profit_pips: float
    profit_money: float
    open_bar: int
    close_bar: int
    close_reason: str
    volume: float  # размер лота


# ───────────────────────── Основной бэктестер ───────────────────────────

class Backtester:
    """
    Проходит по историческим барам слева направо. На каждом баре:
    1. Считает индикаторы по данным [0..i].
    2. Проверяет условия закрытия открытой позиции.
    3. Проверяет условия открытия новой позиции.
    """

    # Минимальное кол-во баров для прогрева индикаторов
    WARMUP = 50

    def __init__(self, symbol: str, timeframe, bars: int = 1000, verbose: bool = False, initial_balance: float = 10000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars
        self.verbose = verbose
        self.point = mt5.symbol_info(symbol).point
        
        # Параметры счета
        self.initial_balance = initial_balance
        self.balance = initial_balance  # текущий баланс
        self.risk_percent = 1.0  # 1% за сделку

        # Загрузка данных
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            raise ValueError(f"Нет данных для {symbol}")
        self.df = pd.DataFrame(rates)
        self.df['time'] = pd.to_datetime(self.df['time'], unit='s')
        print(f"Загружено {len(self.df)} баров для {symbol}, "
              f"период {self.df['time'].iloc[0]} — {self.df['time'].iloc[-1]}")

        self.trades: list[Trade] = []
        self.position: Position | None = None
        self.log: list[str] = []

    def _log(self, text: str):
        """Печатает и сохраняет строку в лог."""
        print(text)
        self.log.append(text)

    def _calculate_volume(self, atr_at_open: float) -> float:
        """
        Расчет объема на основе риска 1% от баланса.
        Риск = volume * atr_at_open * 2 (за 2 ATR)
        volume = (balance * 0.01) / (atr_at_open * 2)
        """
        risk_amount = self.balance * (self.risk_percent / 100)
        sl_distance = 2 * atr_at_open  # стоп в 2 ATR
        if sl_distance > 0:
            volume = risk_amount / sl_distance
        else:
            volume = 0.01  # минимальный лот
        return round(volume, 2)

    # ── Расчёт индикаторов на подмножестве [0..end] ──

    def _calc_indicators(self, end: int) -> dict | None:
        """Рассчитать все индикаторы по барам [0..end]. Возвращает dict или None."""
        sl = self.df.iloc[:end + 1]
        if len(sl) < self.WARMUP:
            return None

        closes = sl['close']
        highs = sl['high']
        lows = sl['low']

        # MA
        fast_ma = closes.ewm(span=8, adjust=False).mean()
        slow_ma = closes.ewm(span=20, adjust=False).mean()

        fast_val = fast_ma.iloc[-1]
        fast_prev = fast_ma.iloc[-2]
        slow_val = slow_ma.iloc[-1]
        slow_prev = slow_ma.iloc[-2]

        sig_ma = ma_simple_signal(fast_val, slow_val)

        # Cross signal
        if fast_prev < slow_prev and fast_val > slow_val:
            cross = 'BUY'
        elif fast_prev > slow_prev and fast_val < slow_val:
            cross = 'SELL'
        else:
            cross = 'NO_SIGNAL'

        # Angle fast MA
        atr_series = calc_atr(highs, lows, closes)
        atr_last = atr_series.iloc[-1] if not pd.isna(atr_series.iloc[-1]) else 1.0
        x = atr_last / self.point if self.point else 1.0
        y = (fast_val - fast_prev) / self.point if self.point else 0
        angle_fast = int(math.degrees(math.atan2(y, x / 2))) if x != 0 else 0

        # MACD
        h, ph, s = calc_macd(closes)
        ms = macd_signal(h, ph, s)

        # ADX
        adx_vals, pdi_vals, ndi_vals = calc_adx(
            highs.values, lows.values, closes.values, 14
        )
        adx_sig = adx_signal_func(adx_vals[-1], pdi_vals[-1], ndi_vals[-1])

        # RSI
        rsi_series = calc_rsi(closes)
        rsi_cur = rsi_series.iloc[-1]
        rsi_prev = rsi_series.iloc[-2] if len(rsi_series) >= 2 else 50.0
        rsi_prev2 = rsi_series.iloc[-3] if len(rsi_series) >= 3 else 50.0
        rs = rsi_signal_func(rsi_cur, rsi_prev, rsi_prev2)

        return {
            'signal_ma': sig_ma,
            'cross_signal_ma': cross,
            'angle_fast': angle_fast,
            'fast_ma': fast_val,
            'slow_ma': slow_val,
            'MACD_signal': ms,
            'ADX_signal': adx_sig,
            'adx_val': adx_vals[-1],
            'pdi_val': pdi_vals[-1],
            'ndi_val': ndi_vals[-1],
            'rsi_signal': rs,
            'rsi_cur': rsi_cur,
            'atr_value': atr_last,
            'close': closes.iloc[-1],
            'open': sl['open'].iloc[-1],
            'high': highs.iloc[-1],
            'low': lows.iloc[-1],
            'time': sl['time'].iloc[-1],
        }

    # ── Форматирование индикаторов для вывода ──

    @staticmethod
    def _format_indicators(ind: dict, bar_idx: int) -> str:
        """Строка с текущими значениями всех индикаторов."""
        t = ind['time'].strftime('%Y-%m-%d %H:%M')
        macd = ind['MACD_signal']
        rsi = ind['rsi_signal']
        return (
            f"Bar {bar_idx:>4} | {t} | "
            f"Close={ind['close']:.5f} | "
            f"MA8={ind['fast_ma']:.5f} MA20={ind['slow_ma']:.5f} MA_sig={ind['signal_ma']:>9} | "
            f"MACD={macd.get('hist_line',0):+.6f} sig={macd.get('signal_line',0):+.6f} MACD_sig={macd['signal']:>11} | "
            f"RSI={ind['rsi_cur']:.2f} RSI_sig={rsi['signal']:>9} | "
            f"Angle={ind['angle_fast']:>4}"
        )

    # ── Определение суммарного сигнала (как в trading_loop) ──

    @staticmethod
    def _sum_signal(ind: dict) -> str:
        ma_s = ind['signal_ma']
        macd_s = ind['MACD_signal']['signal']
        rsi_s = ind['rsi_signal']['signal']
        if ma_s == 'BUY' and macd_s == 'BUY' and rsi_s == 'BUY':
            return 'BUY'
        elif ma_s == 'SELL' and macd_s == 'SELL' and rsi_s == 'SELL':
            return 'SELL'
        return 'NO_SIGNAL'

    # ── Закрытие позиции ──

    def _close_position(self, price: float, bar_time: datetime, bar_idx: int, reason: str):
        pos = self.position
        if pos is None:
            return
        if pos.direction == 'BUY':
            profit_pips = (price - pos.open_price) / self.point
        else:
            profit_pips = (pos.open_price - price) / self.point

        # Прибыль в долларах = прибыль в пипсах * размер_лота * стоимость_пипса
        # Для большинства пар: profit_money = profit_pips * volume * point * 10
        profit_money = profit_pips * pos.volume * self.point * 10
        
        # Обновляем баланс
        self.balance += profit_money

        self.trades.append(Trade(
            direction=pos.direction,
            open_price=pos.open_price,
            close_price=price,
            open_time=pos.open_time,
            close_time=bar_time,
            profit_pips=profit_pips,
            profit_money=profit_money,
            open_bar=pos.open_bar,
            close_bar=bar_idx,
            close_reason=reason,
            volume=pos.volume,
        ))
        self.position = None

    # ── Основной прогон ──

    def run(self):
        n = len(self.df)
        status = 0  # 0 — торговля разрешена, 2 — заблокирована (ждём NO_SIGNAL для разблокировки)
        prev_bar_time = None

        for i in range(self.WARMUP, n):
            ind = self._calc_indicators(i)
            if ind is None:
                continue

            bar_time = ind['time']
            close_price = ind['close']
            rsi_cur = ind['rsi_cur']
            atr_val = ind['atr_value'] if ind['atr_value'] and not pd.isna(ind['atr_value']) else 0
            sum_sig = self._sum_signal(ind)
            macd_sig = ind['MACD_signal']['signal']

            # Считаем каждый бар «новым» (в бэктесте идём по закрытым барам)
            is_new_bar = (bar_time != prev_bar_time)
            prev_bar_time = bar_time

            if not is_new_bar:
                continue

            # Разблокировка статуса (как в trading_loop)
            if status == 1:
                status = 0
            if status == 2 and macd_sig == 'NO_SIGNAL':
                status = 0

            # ── Проверка закрытия открытой позиции ──
            if self.position is not None:
                pos = self.position
                # Расчёт текущего профита в пипсах
                if pos.direction == 'BUY':
                    current_profit_pips = (close_price - pos.open_price) / self.point
                    # Stop Loss: потеря > 2 ATR
                    atr_in_pips = pos.atr_at_open / self.point
                    condition_sl = current_profit_pips < -2 * atr_in_pips
                    condition_rsi = rsi_cur < 50
                else:
                    current_profit_pips = (pos.open_price - close_price) / self.point
                    atr_in_pips = pos.atr_at_open / self.point
                    condition_sl = current_profit_pips < -2 * atr_in_pips
                    condition_rsi = rsi_cur > 50

                # Расчет прибыли в долларах для вывода
                current_profit_money = current_profit_pips * pos.volume * self.point * 10

                # Закрыть позицию перед выходными
                condition_before_weekend = is_trading_blocked_before_weekend(bar_time)

                if condition_sl:
                    status = 2
                if condition_sl or condition_rsi or condition_before_weekend:
                    if condition_before_weekend:
                        reason = "Before Weekend"
                    elif condition_sl:
                        reason = "Stop Loss (2 ATR)"
                    else:
                        reason = "RSI"
                    # ── Вывод индикаторов при закрытии сделки ──
                    self._log(f"\n<<< ЗАКРЫТИЕ {pos.direction} @ {close_price:.5f}  P/L=${current_profit_money:+,.2f}  [{bar_time.strftime('%Y-%m-%d %H:%M')}]  Причина: {reason}")
                    self._log(f"    {self._format_indicators(ind, i)}")
                    self._log('')
                    self._close_position(close_price, bar_time, i, reason)

            # ── Вывод индикаторов на каждом баре ──
            if self.verbose:
                self._log(self._format_indicators(ind, i))

            # ── Проверка открытия новой позиции ──
            if self.position is None and sum_sig != 'NO_SIGNAL' and status == 0:
                # Не открываем позиции перед выходными
                if not is_trading_blocked_before_weekend(bar_time):
                    volume = self._calculate_volume(atr_val)
                    self.position = Position(
                        direction=sum_sig,
                        open_price=close_price,
                        open_time=bar_time,
                        open_bar=i,
                        atr_at_open=atr_val,
                        symbol=self.symbol,
                        volume=volume,
                    )
                    # ── Вывод индикаторов при открытии сделки ──
                    self._log(f"\n>>> ОТКРЫТИЕ {sum_sig} @ {close_price:.5f}  Лот: {volume:.2f}  [{bar_time.strftime('%Y-%m-%d %H:%M')}]")
                    self._log(f"    {self._format_indicators(ind, i)}")
                    self._log('')

        # Закрываем позицию на последнем баре, если осталась открытой
        if self.position is not None:
            last = self.df.iloc[-1]
            self._close_position(last['close'], self.df['time'].iloc[-1], n - 1, "End of data")

    # ── Отчёт ──

    def report(self) -> str:
        lines = []
        lines.append(f"\n{'=' * 70}")
        lines.append(f"  РЕЗУЛЬТАТЫ БЭКТЕСТА: {self.symbol}")
        lines.append(f"  Период: {self.df['time'].iloc[0]} — {self.df['time'].iloc[-1]}")
        lines.append(f"  Баров: {len(self.df)}, прогрев: {self.WARMUP}")
        lines.append(f"{'=' * 70}")
        lines.append(f"  Начальный баланс:   ${self.initial_balance:,.2f}")
        lines.append(f"  Финальный баланс:   ${self.balance:,.2f}")
        final_profit = self.balance - self.initial_balance
        profit_percent = (final_profit / self.initial_balance) * 100
        lines.append(f"  Прибыль/убыток:     ${final_profit:+,.2f} ({profit_percent:+.2f}%)")
        lines.append(f"{'=' * 70}")

        if not self.trades:
            lines.append("  Нет сделок за период.")
            return '\n'.join(lines)

        wins = [t for t in self.trades if t.profit_money > 0]
        losses = [t for t in self.trades if t.profit_money <= 0]
        total_profit = sum(t.profit_money for t in self.trades)
        avg_win = np.mean([t.profit_money for t in wins]) if wins else 0
        avg_loss = np.mean([t.profit_money for t in losses]) if losses else 0
        max_win = max((t.profit_money for t in self.trades), default=0)
        max_loss = min((t.profit_money for t in self.trades), default=0)

        win_rate = len(wins) / len(self.trades) * 100

        # Max drawdown (по долларам)
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in self.trades:
            cumulative += t.profit_money
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        # Profit factor
        gross_profit = sum(t.profit_money for t in wins) if wins else 0
        gross_loss = abs(sum(t.profit_money for t in losses)) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Средняя длительность сделки (в барах)
        avg_bars = np.mean([t.close_bar - t.open_bar for t in self.trades])

        lines.append(f"  Всего сделок:       {len(self.trades)}")
        lines.append(f"  Прибыльных:         {len(wins)} ({win_rate:.1f}%)")
        lines.append(f"  Убыточных:          {len(losses)} ({100 - win_rate:.1f}%)")
        lines.append(f"  ─────────────────────────────────────")
        lines.append(f"  Итого прибыль:      ${total_profit:+,.2f}")
        lines.append(f"  Средний выигрыш:    ${avg_win:+,.2f}")
        lines.append(f"  Средний убыток:     ${avg_loss:+,.2f}")
        lines.append(f"  Макс. выигрыш:      ${max_win:+,.2f}")
        lines.append(f"  Макс. убыток:       ${max_loss:+,.2f}")
        lines.append(f"  ─────────────────────────────────────")
        lines.append(f"  Profit Factor:      {profit_factor:.2f}")
        lines.append(f"  Max Drawdown:       ${max_dd:,.2f}")
        lines.append(f"  Средняя длит. (баров): {avg_bars:.1f}")
        lines.append(f"{'=' * 70}")

        # Список сделок
        lines.append(f"\n  {'№':>3}  {'Напр.':>5}  {'Лот':>8}  {'Откр. цена':>12}  {'Закр. цена':>12}  "
                      f"{'П/У $':>12}  {'Причина':>15}  {'Время открытия':>20}")
        lines.append(f"  {'─' * 120}")

        for idx, t in enumerate(self.trades, 1):
            emoji = "+" if t.profit_money > 0 else "-"
            lines.append(
                f"  {idx:>3}  {t.direction:>5}  {t.volume:>8.2f}  {t.open_price:>12.5f}  {t.close_price:>12.5f}  "
                f"{emoji}{abs(t.profit_money):>11,.2f}  {t.close_reason:>15}  "
                f"{t.open_time.strftime('%Y-%m-%d %H:%M'):>20}"
            )

        return '\n'.join(lines)


# ───────────────────────── main ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Тестер стратегии MillionsKeeper')
    parser.add_argument('--symbol', type=str, default=None,
                        help='Символ для тестирования (например EURUSDrfd). По умолчанию — все активные.')
    parser.add_argument('--bars', type=int, default=1000,
                        help='Количество свечей назад (по умолчанию 1000)')
    parser.add_argument('--tf', type=str, default=None,
                        help='Таймфрейм: M1, M5, M15, M30, H1, H4, D1, W1, MN1 (по умолчанию из settings)')
    parser.add_argument('--verbose', action='store_true',
                        help='Выводить индикаторы на каждом баре')
    parser.add_argument('--balance', type=float, default=10000,
                        help='Начальный баланс счета в долларах (по умолчанию 10000)')
    args = parser.parse_args()

    TIMEFRAMES = {
        'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1, 'W1': mt5.TIMEFRAME_W1,
        'MN1': mt5.TIMEFRAME_MN1,
    }

    # Подключение к MT5
    account = Account.account
    auth = MT5Auth(account)
    auth.login()

    timeframe = GlobalValues.time_frame
    if args.tf:
        tf_upper = args.tf.upper()
        if tf_upper not in TIMEFRAMES:
            print(f"Неизвестный таймфрейм: {args.tf}. Доступные: {', '.join(TIMEFRAMES.keys())}")
            mt5.shutdown()
            return
        timeframe = TIMEFRAMES[tf_upper]

    if args.symbol:
        symbols = [args.symbol]
    else:
        # Все пары со статусом < 3
        symbols = [s for s, v in Dictionary.symbolTradingStatus.items() if v < 3]
        if not symbols:
            # Если все выключены, тестируем все
            symbols = list(Dictionary.symbolTradingStatus.keys())

    results = []
    for symbol in symbols:
        print(f"\n{'─' * 40}")
        print(f"Запуск бэктеста для {symbol}...")
        try:
            bt = Backtester(symbol, timeframe, bars=args.bars, verbose=args.verbose, initial_balance=args.balance)
            bt.run()
            report = bt.report()
            results.append((report, bt.log))
            print(report)
        except Exception as e:
            msg = f"Ошибка бэктеста {symbol}: {e}"
            results.append((msg, []))
            print(msg)

    # Итоговая сводка по всем парам
    if len(results) > 1:
        print(f"\n\n{'#' * 70}")
        print(f"  СВОДКА ПО ВСЕМ ПАРАМ")
        print(f"{'#' * 70}")
        for report, _ in results:
            header_lines = [l for l in report.split('\n') if l.strip()][:7]
            for l in header_lines:
                print(l)
            print()

    # \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u043e\u0432 \u0432 \u0444\u0430\u0439\u043b
    os.makedirs('logs', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'logs/backtest_{timestamp}.txt'
    with open(filename, 'w', encoding='utf-8') as f:
        for report, log_lines in results:
            for line in log_lines:
                f.write(line + '\n')
            f.write(report + '\n')
    print(f"\n\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u044b \u0432 {filename}")

    mt5.shutdown()


if __name__ == '__main__':
    main()
