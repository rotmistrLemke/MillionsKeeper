"""
Стратегия: EMA 8/21 Cross Inverse (инверсия EMA Cross)

Вход:
  SELL: EMA8 пересекает EMA21 снизу вверх
  BUY:  EMA8 пересекает EMA21 сверху вниз

Выход (по сигналу-перевороту):
  SELL: EMA8 пересекает EMA21 сверху вниз
  BUY:  EMA8 пересекает EMA21 снизу вверх

SL = 3 × ATR. TP отключён. Фильтр флэта отключён.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class EmaCrossInverseStrategy(BaseStrategy):
    name = "ema_cross_inverse"
    description = "EMA 8/21 Cross Inverse — инверсия направления к EMA Cross"
    default_timeframe = "H1"

    def __init__(self, fast=8, slow=21, atr_period=14, sl_atr_mult=3.0):
        self.fast = fast
        self.slow = slow
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema8']  = talib.EMA(close, timeperiod=self.fast)
        df['ema21'] = talib.EMA(close, timeperiod=self.slow)
        df['atr']   = talib.ATR(high, low, close, timeperiod=self.atr_period)

        diff = df['ema8'] - df['ema21']
        prev = diff.shift(1)
        df['cross_up']   = (prev <= 0) & (diff > 0)
        df['cross_down'] = (prev >= 0) & (diff < 0)
        return df

    def is_flat(self, row) -> bool:
        return False

    def get_entry_signal(self, row):
        if pd.isna(row.get('ema8')) or pd.isna(row.get('ema21')):
            return None
        if bool(row.get('cross_up')):
            return 'SELL'
        if bool(row.get('cross_down')):
            return 'BUY'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row.get('ema8')) or pd.isna(row.get('ema21')):
            return False
        if position['type'] == 'SELL' and bool(row.get('cross_down')):
            return True
        if position['type'] == 'BUY' and bool(row.get('cross_up')):
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr   = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        if signal == 'BUY':
            sl = price - self.sl_atr_mult * atr
        else:
            sl = price + self.sl_atr_mult * atr
        return sl, None

    def indicator_columns(self):
        return ['ema8', 'ema21', 'atr']
