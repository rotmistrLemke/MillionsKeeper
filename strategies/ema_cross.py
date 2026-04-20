"""
Стратегия: EMA 8/21 Cross

Вход:
  BUY:  EMA8 пересекает EMA21 снизу вверх (бычий кроссовер)
  SELL: EMA8 пересекает EMA21 сверху вниз (медвежий кроссовер)

Выход (по сигналу-перевороту):
  BUY:  EMA8 пересекает EMA21 сверху вниз
  SELL: EMA8 пересекает EMA21 снизу вверх

Фильтр флэта и SL/TP отключены — выход только по противоположному кроссоверу.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class EmaCrossStrategy(BaseStrategy):
    name = "ema_cross"
    description = "EMA 8/21 Cross — вход и выход по пересечению скользящих"
    default_timeframe = "H1"

    def __init__(self, fast=8, slow=21):
        self.fast = fast
        self.slow = slow

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)

        df['ema8']  = talib.EMA(close, timeperiod=self.fast)
        df['ema21'] = talib.EMA(close, timeperiod=self.slow)

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
            return 'BUY'
        if bool(row.get('cross_down')):
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row.get('ema8')) or pd.isna(row.get('ema21')):
            return False
        if position['type'] == 'BUY' and bool(row.get('cross_down')):
            return True
        if position['type'] == 'SELL' and bool(row.get('cross_up')):
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        return None, None

    def indicator_columns(self):
        return ['ema8', 'ema21']
