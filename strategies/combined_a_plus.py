"""
Стратегия: Combined A+ — комбинация 5 факторов — combined_a_plus.

Вход только при score ≥ min_score (по умолчанию 4 из 5). Если меньше —
сигнал пропускается. Сделки редкие, но с высокой вероятностью.

5 факторов (для BUY-направления; для SELL — зеркально):

  1. 200 EMA: close > EMA200 (направление)
  2. 50 EMA: цена в зоне отката (low ≤ EMA50 + 0.5×ATR)
  3. Price action: бычий пин-бар ≥ 3× ИЛИ бычье поглощение ≥ 80%
  4. Горизонтальный уровень: последний fractal_down в пределах 0.5×ATR
     от цены/EMA50 (совпадение горизонтальной поддержки с динамической)
  5. ATR в норме: atr ≥ 0.5×atr_avg_50 и atr ≤ 2×atr_avg_50

SL: 2×ATR.
Выход (трейлинг): закрытие свечи ниже EMA50.
"""

import pandas as pd
import numpy as np
import talib
from strategies.base import BaseStrategy
from strategies._price_action import (
    is_bullish_pin_bar, is_bearish_pin_bar,
    is_bullish_engulfing, is_bearish_engulfing,
    williams_fractals,
)


class CombinedAPlusStrategy(BaseStrategy):
    name = "combined_a_plus"
    description = "Combined A+ — EMA200/50 + price-action + уровень + ATR (score ≥ 4/5)"
    default_timeframe = "H4"

    def __init__(self, ema_fast=50, ema_slow=200, atr_period=14,
                 touch_atr=0.5, level_atr=0.5, sl_atr_mult=2.0,
                 atr_avg_period=50, atr_band_low=0.5, atr_band_high=2.0,
                 fractal_n=2, fractal_window=40, min_score=4,
                 pin_tail_ratio=3.0, engulf_overlap=0.8):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.touch_atr = float(touch_atr)
        self.level_atr = float(level_atr)
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.atr_avg_period = atr_avg_period
        self.atr_band_low  = float(atr_band_low)
        self.atr_band_high = float(atr_band_high)
        self.fractal_n = fractal_n
        self.fractal_window = fractal_window
        self.min_score = int(min_score)
        self.pin_tail_ratio = pin_tail_ratio
        self.engulf_overlap = engulf_overlap

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50']  = talib.EMA(close, timeperiod=self.ema_fast)
        df['ema200'] = talib.EMA(close, timeperiod=self.ema_slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['atr_avg'] = df['atr'].rolling(self.atr_avg_period).mean()

        df = williams_fractals(df, n=self.fractal_n)

        # Уровни: последний fractal_up и fractal_down в окне.
        up_levels   = np.full(len(df), np.nan)
        down_levels = np.full(len(df), np.nan)
        frac_up   = df['fractal_up'].to_numpy(dtype=bool)
        frac_down = df['fractal_down'].to_numpy(dtype=bool)
        highs = df['high'].to_numpy(dtype=float)
        lows  = df['low'].to_numpy(dtype=float)
        for i in range(len(df)):
            start = max(0, i - self.fractal_window)
            for j in range(i - self.fractal_n, start - 1, -1):
                if frac_up[j]:
                    up_levels[i] = highs[j]
                    break
            for j in range(i - self.fractal_n, start - 1, -1):
                if frac_down[j]:
                    down_levels[i] = lows[j]
                    break
        df['level_up']   = up_levels
        df['level_down'] = down_levels
        return df

    def compute_flat_indicators(self, df):
        df = super().compute_flat_indicators(df)
        for c in ('open', 'high', 'low', 'close'):
            df[f'prev_{c}'] = df[c].shift(1)
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return False

    def uses_trailing_exit(self) -> bool:
        return True

    def _score(self, row, direction: str) -> int:
        """Возвращает число удовлетворённых факторов (0..5) для направления."""
        required = ('ema200', 'ema50', 'atr', 'atr_avg')
        if any(row.get(c) is None or pd.isna(row.get(c)) for c in required):
            return 0
        atr = row['atr']
        if atr <= 0:
            return 0

        score = 0

        # 1. Направление по 200 EMA
        if direction == 'BUY' and row['close'] > row['ema200']:
            score += 1
        elif direction == 'SELL' and row['close'] < row['ema200']:
            score += 1

        # 2. Касание зоны EMA50
        ema50 = row['ema50']
        if direction == 'BUY' and row['low'] <= ema50 + self.touch_atr * atr:
            score += 1
        elif direction == 'SELL' and row['high'] >= ema50 - self.touch_atr * atr:
            score += 1

        # 3. Price action
        prev_row = {
            'open':  row.get('prev_open'),
            'close': row.get('prev_close'),
            'high':  row.get('prev_high'),
            'low':   row.get('prev_low'),
        }
        has_prev = not any(v is None or pd.isna(v) for v in prev_row.values())
        if direction == 'BUY':
            if is_bullish_pin_bar(row, self.pin_tail_ratio) or \
               (has_prev and is_bullish_engulfing(prev_row, row, self.engulf_overlap)):
                score += 1
        else:
            if is_bearish_pin_bar(row, self.pin_tail_ratio) or \
               (has_prev and is_bearish_engulfing(prev_row, row, self.engulf_overlap)):
                score += 1

        # 4. Совпадение горизонтального уровня с зоной EMA50
        level_down = row.get('level_down')
        level_up   = row.get('level_up')
        tol = self.level_atr * atr
        if direction == 'BUY' and level_down is not None and not pd.isna(level_down):
            if abs(float(level_down) - ema50) <= tol or abs(row['low'] - float(level_down)) <= tol:
                score += 1
        elif direction == 'SELL' and level_up is not None and not pd.isna(level_up):
            if abs(float(level_up) - ema50) <= tol or abs(row['high'] - float(level_up)) <= tol:
                score += 1

        # 5. ATR в норме
        atr_avg = row['atr_avg']
        if not pd.isna(atr_avg) and atr_avg > 0:
            ratio = atr / atr_avg
            if self.atr_band_low <= ratio <= self.atr_band_high:
                score += 1

        return score

    def get_entry_signal(self, row):
        buy_score  = self._score(row, 'BUY')
        sell_score = self._score(row, 'SELL')
        if buy_score >= self.min_score and buy_score > sell_score:
            return 'BUY'
        if sell_score >= self.min_score and sell_score > buy_score:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        """Трейлинг: закрытие свечи по другую сторону EMA50."""
        ema50 = row.get('ema50')
        if ema50 is None or pd.isna(ema50):
            return False
        if position['type'] == 'BUY' and row['close'] < ema50:
            return True
        if position['type'] == 'SELL' and row['close'] > ema50:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = None
        if self.sl_atr_mult > 0:
            sl = (price - self.sl_atr_mult * atr) if signal == 'BUY' \
                 else (price + self.sl_atr_mult * atr)
        return sl, None

    def indicator_columns(self):
        return ['ema50', 'ema200', 'atr', 'level_up', 'level_down']
