"""
Стратегия: Triple EMA Momentum Scalping

Логика:
  - 3 EMA (8, 21, 50) выстраиваются в одном направлении
  - MACD гистограмма подтверждает нарастающий импульс
  - Вход когда все 3 EMA выстроены + MACD усиливается

Вход:
  BUY:  EMA8 > EMA21 > EMA50 + MACD hist > 0 и растёт
  SELL: EMA8 < EMA21 < EMA50 + MACD hist < 0 и падает

Выход:
  - EMA8 пересекает EMA21 против позиции
  - Или MACD hist меняет направление
  - Или SL = 1.5 * ATR, TP = 2.0 * ATR
"""

import pandas as pd
import talib

from strategies.base import BaseStrategy


class StochasticScalpStrategy(BaseStrategy):
    name = "triple_ema"
    description = "Triple EMA(8/21/50) + MACD Momentum Scalping"
    default_timeframe = "H1"

    def __init__(self, ema_fast=8, ema_mid=21, ema_slow=50,
                 macd_fast=12, macd_slow=26, macd_signal=9,
                 atr_period=14, sl_atr_mult=1.5, tp_atr_mult=2.0):
        self.ema_fast = ema_fast
        self.ema_mid = ema_mid
        self.ema_slow = ema_slow
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)

        df['ema8'] = talib.EMA(close, timeperiod=self.ema_fast)
        df['ema21'] = talib.EMA(close, timeperiod=self.ema_mid)
        df['ema50'] = talib.EMA(close, timeperiod=self.ema_slow)

        macd_line, signal_line, hist = talib.MACD(
            close, fastperiod=self.macd_fast,
            slowperiod=self.macd_slow, signalperiod=self.macd_signal
        )
        df['macd_hist'] = hist
        df['macd_hist_prev'] = df['macd_hist'].shift(1)

        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)

        return df

    def get_entry_signal(self, row):
        required = ['ema8', 'ema21', 'ema50', 'macd_hist', 'macd_hist_prev', 'atr']
        if any(pd.isna(row[c]) for c in required):
            return None

        emas_bullish = row['ema8'] > row['ema21'] > row['ema50']
        emas_bearish = row['ema8'] < row['ema21'] < row['ema50']

        hist = row['macd_hist']
        hist_prev = row['macd_hist_prev']
        macd_growing = hist > 0 and hist > hist_prev
        macd_falling = hist < 0 and hist < hist_prev

        if emas_bullish and macd_growing:
            return 'BUY'
        if emas_bearish and macd_falling:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['ema8']) or pd.isna(row['ema21']) or pd.isna(row['macd_hist']) or pd.isna(row['macd_hist_prev']):
            return False

        hist = row['macd_hist']
        hist_prev = row['macd_hist_prev']

        if position['type'] == 'BUY':
            if row['ema8'] < row['ema21']:
                return True
            if hist < hist_prev and hist_prev > 0:
                return True
        elif position['type'] == 'SELL':
            if row['ema8'] > row['ema21']:
                return True
            if hist > hist_prev and hist_prev < 0:
                return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row['atr']
        price = row['close']
        if signal == 'BUY':
            sl = price - self.sl_atr_mult * atr
            tp = price + self.tp_atr_mult * atr
        else:
            sl = price + self.sl_atr_mult * atr
            tp = price - self.tp_atr_mult * atr
        return sl, tp

    def indicator_columns(self):
        return ['ema8', 'ema21', 'ema50', 'macd_hist', 'atr']
