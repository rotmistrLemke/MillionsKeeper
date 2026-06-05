"""
Стратегия: Donchian Channel Breakout Scalping

Логика:
  - Donchian Channel (20 периодов) — максимум/минимум за N баров
  - ATR-фильтр: текущий ATR > средний ATR (волатильность выше нормы)
  - Вход при пробое канала с подтверждением волатильности

Вход:
  BUY:  Цена пробивает верхнюю границу канала + ATR > SMA(ATR)
  SELL: Цена пробивает нижнюю границу канала + ATR > SMA(ATR)

Выход:
  - Цена пробивает противоположную границу канала
  - Или SL = 2.0 * ATR, TP = 3.0 * ATR
"""

import pandas as pd
import numpy as np
import talib

from strategies.base import BaseStrategy


class BollingerScalpStrategy(BaseStrategy):
    name = "donchian_breakout"
    description = "Donchian Channel(20) Breakout + ATR Filter"
    default_timeframe = "H1"

    def __init__(self, channel_period=20, atr_period=14,
                 atr_filter_period=50, sl_atr_mult=2.0, tp_atr_mult=3.0):
        self.channel_period = channel_period
        self.atr_period = atr_period
        self.atr_filter_period = atr_filter_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)

        # Donchian Channel — макс/мин за предыдущие N баров (без текущего)
        df['dc_upper'] = df['high'].shift(1).rolling(self.channel_period).max()
        df['dc_lower'] = df['low'].shift(1).rolling(self.channel_period).min()
        df['dc_middle'] = (df['dc_upper'] + df['dc_lower']) / 2

        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['atr_avg'] = df['atr'].rolling(self.atr_filter_period).mean()

        return df

    def get_entry_signal(self, row):
        required = ['dc_upper', 'dc_lower', 'atr', 'atr_avg']
        if any(pd.isna(row[c]) for c in required):
            return None

        # Фильтр волатильности: ATR > средний ATR
        if row['atr'] <= row['atr_avg']:
            return None

        price = row['close']

        if price > row['dc_upper']:
            return 'BUY'
        if price < row['dc_lower']:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['dc_middle']):
            return False

        # Выход при возврате к средней линии канала
        if position['type'] == 'BUY' and row['close'] < row['dc_middle']:
            return True
        if position['type'] == 'SELL' and row['close'] > row['dc_middle']:
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
        return ['dc_upper', 'dc_lower', 'dc_middle', 'atr']
