"""
Стратегия: 200 MA + фаза рынка — market_phase.

Классификатор фазы через наклон 200 MA:
  RANGE      — наклон |slope| < slope_threshold (торгуем пробои уровней)
  TREND_UP   — slope > threshold (цена выше MA; торгуем продолжение)
  TREND_DOWN — slope < -threshold (цена ниже MA; торгуем продолжение)

Уровни — фракталы Билла Вильямса (5-бар). Для пробоев/стопов берём
последние фрактальные максимумы/минимумы в окне fractal_window баров.

Правила:
  Таймфрейм: D1 (по умолчанию), H4 альтернатива.
  Глобально: строго уважаем тренд 200 MA — против него не торгуем.

  RANGE:
    BUY пробой:  close > last_resistance + 0.2×ATR (с фильтром close > EMA200)
    SELL пробой: close < last_support - 0.2×ATR (с фильтром close < EMA200)
    SL: за противоположной границей ± 0.2×ATR.

  TREND_UP (close > EMA200, slope > thr):
    BUY пробой: close > last_resistance + 0.2×ATR
    SL:        last_support - 0.2×ATR (ниже consolidation)

  TREND_DOWN (close < EMA200, slope < -thr):
    SELL пробой: close < last_support - 0.2×ATR
    SL:          last_resistance + 0.2×ATR

  Выход (трейлинг): закрытие свечи по другую сторону 200 MA.
"""

import numpy as np
import pandas as pd
import talib
from strategies.base import BaseStrategy
from strategies._price_action import ma_slope_deg, williams_fractals


class MarketPhaseStrategy(BaseStrategy):
    name = "market_phase"
    description = "200 MA + фаза рынка — пробои уровней (range) / продолжение тренда"
    default_timeframe = "D1"

    def __init__(self, ma_period=200, atr_period=14, slope_lookback=20,
                 slope_threshold=0.1, fractal_n=2, fractal_window=40,
                 breakout_atr=0.2):
        self.ma_period = ma_period
        self.atr_period = atr_period
        self.slope_lookback = slope_lookback
        self.slope_threshold = float(slope_threshold)
        self.fractal_n = fractal_n
        self.fractal_window = fractal_window
        self.breakout_atr = float(breakout_atr)

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema200'] = talib.EMA(close, timeperiod=self.ma_period)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)

        # Фракталы (5-бар) — считаются по всему фрейму.
        df = williams_fractals(df, n=self.fractal_n)

        # Наклон 200MA — отдельной колонкой, чтобы можно было использовать в
        # iloc-контексте (row).
        ma = df['ema200']
        slopes = np.full(len(df), np.nan)
        for i in range(self.slope_lookback, len(df)):
            slopes[i] = ma_slope_deg(ma.iloc[i - self.slope_lookback:i], self.slope_lookback)
        df['ma200_slope'] = slopes

        # Последние уровни в окне fractal_window.
        up_levels   = np.full(len(df), np.nan)
        down_levels = np.full(len(df), np.nan)
        frac_up   = df['fractal_up'].to_numpy(dtype=bool)
        frac_down = df['fractal_down'].to_numpy(dtype=bool)
        highs = df['high'].to_numpy(dtype=float)
        lows  = df['low'].to_numpy(dtype=float)
        for i in range(len(df)):
            start = max(0, i - self.fractal_window)
            # Самый свежий fractal_up в окне
            for j in range(i - self.fractal_n, start - 1, -1):
                if frac_up[j]:
                    up_levels[i] = highs[j]
                    break
            for j in range(i - self.fractal_n, start - 1, -1):
                if frac_down[j]:
                    down_levels[i] = lows[j]
                    break
        df['level_resistance'] = up_levels
        df['level_support']    = down_levels
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return False

    def uses_trailing_exit(self) -> bool:
        return True

    def _phase(self, row) -> str:
        slope = row.get('ma200_slope')
        if slope is None or pd.isna(slope):
            return 'UNKNOWN'
        if abs(slope) < self.slope_threshold:
            return 'RANGE'
        return 'TREND_UP' if slope > 0 else 'TREND_DOWN'

    def get_entry_signal(self, row):
        required = ('ema200', 'atr', 'level_resistance', 'level_support')
        if any(row.get(c) is None or pd.isna(row.get(c)) for c in required):
            return None

        atr = row['atr']
        if atr <= 0:
            return None
        buffer = self.breakout_atr * atr
        resistance = row['level_resistance']
        support    = row['level_support']
        close = row['close']
        ema200 = row['ema200']
        phase = self._phase(row)

        # RANGE: пробой уровня с фильтром 200 MA.
        if phase == 'RANGE':
            if close > resistance + buffer and close > ema200:
                return 'BUY'
            if close < support - buffer and close < ema200:
                return 'SELL'
            return None

        # TREND_UP: пробой сопротивления (продолжение).
        if phase == 'TREND_UP' and close > ema200:
            if close > resistance + buffer:
                return 'BUY'
            return None

        # TREND_DOWN: пробой поддержки.
        if phase == 'TREND_DOWN' and close < ema200:
            if close < support - buffer:
                return 'SELL'
            return None

        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        """Трейлинг: закрытие свечи по другую сторону 200 MA."""
        ema200 = row.get('ema200')
        if ema200 is None or pd.isna(ema200):
            return False
        if position['type'] == 'BUY' and row['close'] < ema200:
            return True
        if position['type'] == 'SELL' and row['close'] > ema200:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        buffer = self.breakout_atr * atr
        resistance = row.get('level_resistance')
        support    = row.get('level_support')
        if resistance is None or support is None or pd.isna(resistance) or pd.isna(support):
            # fallback на 2×ATR
            price = row['close']
            if signal == 'BUY':
                return price - 2 * atr, None
            return price + 2 * atr, None
        if signal == 'BUY':
            return float(support) - buffer, None
        return float(resistance) + buffer, None

    def indicator_columns(self):
        return ['ema200', 'atr', 'ma200_slope', 'level_resistance', 'level_support']

    def flat_indicator_columns(self) -> list:
        return []
