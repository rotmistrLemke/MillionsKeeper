"""
Стратегия 1: Range Breakout (Пробой диапазона)

Логика:
  - Находим консолидацию: High/Low за последние N баров (5-10)
  - Если текущая свеча закрывается за пределами диапазона — пробой
  - Фильтр: ATR > средний ATR (есть волатильность для движения)

Вход:
  BUY:  Close > range_high + ATR > ATR_avg
  SELL: Close < range_low  + ATR > ATR_avg

Выход:
  - TP = entry + высота диапазона (range_high - range_low)
  - SL = противоположная граница диапазона
  - Или обратный пробой противоположной границы
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class RangeBreakoutStrategy(BaseStrategy):
    name = "range_breakout"
    description = "Range Breakout H1 — пробой консолидации"
    default_timeframe = "H1"

    def __init__(self, range_bars=8, atr_period=14, atr_avg_period=50):
        self.range_bars = range_bars
        self.atr_period = atr_period
        self.atr_avg_period = atr_avg_period

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        # Диапазон последних N баров (без текущего)
        df['range_high'] = df['high'].shift(1).rolling(self.range_bars).max()
        df['range_low']  = df['low'].shift(1).rolling(self.range_bars).min()
        df['range_size'] = df['range_high'] - df['range_low']

        df['atr']     = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['atr_avg'] = df['atr'].rolling(self.atr_avg_period).mean()
        return df

    def get_entry_signal(self, row):
        required = ['range_high', 'range_low', 'range_size', 'atr', 'atr_avg']
        if any(pd.isna(row[c]) for c in required):
            return None
        if row['atr'] <= row['atr_avg']:
            return None

        if row['close'] > row['range_high']:
            return 'BUY'
        if row['close'] < row['range_low']:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['range_high']) or pd.isna(row['range_low']):
            return False
        if position['type'] == 'BUY' and row['close'] < row['range_low']:
            return True
        if position['type'] == 'SELL' and row['close'] > row['range_high']:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        price      = row['close']
        range_size = row['range_size']
        if signal == 'BUY':
            sl = row['range_low']
            tp = price + range_size
        else:
            sl = row['range_high']
            tp = price - range_size
        return sl, tp

    def indicator_columns(self):
        return ['range_high', 'range_low', 'range_size', 'atr']
