"""
Стратегия: Parabolic SAR + ADX Trend Scalping

Логика:
  - Parabolic SAR определяет направление и точку разворота
  - ADX(14) > 25 подтверждает наличие тренда (фильтрует флэт)
  - +DI/-DI подтверждают направление

Вход:
  BUY:  SAR переключился под цену + ADX > 25 + +DI > -DI
  SELL: SAR переключился над ценой + ADX > 25 + -DI > +DI

Выход:
  - SAR меняет сторону (разворот)
  - Или SL = 1.5 * ATR, TP = 2.5 * ATR
"""

import pandas as pd
import talib

from strategies.base import BaseStrategy


class EmaScalpStrategy(BaseStrategy):
    name = "sar_adx"
    description = "Parabolic SAR + ADX(14) Trend Scalping"
    default_timeframe = "H1"

    def __init__(self, adx_period=14, adx_threshold=25,
                 sar_accel=0.02, sar_max=0.2,
                 atr_period=14, sl_atr_mult=1.5, tp_atr_mult=2.5):
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.sar_accel = sar_accel
        self.sar_max = sar_max
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)

        df['sar'] = talib.SAR(high, low, acceleration=self.sar_accel, maximum=self.sar_max)
        df['sar_prev'] = df['sar'].shift(1)
        df['adx'] = talib.ADX(high, low, close, timeperiod=self.adx_period)
        df['plus_di'] = talib.PLUS_DI(high, low, close, timeperiod=self.adx_period)
        df['minus_di'] = talib.MINUS_DI(high, low, close, timeperiod=self.adx_period)
        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)

        return df

    def get_entry_signal(self, row):
        required = ['sar', 'sar_prev', 'adx', 'plus_di', 'minus_di', 'atr']
        if any(pd.isna(row[c]) for c in required):
            return None

        price = row['close']
        sar_flipped_up = row['sar_prev'] > row['close'] and row['sar'] < row['close']
        sar_flipped_down = row['sar_prev'] < row['close'] and row['sar'] > row['close']

        if row['adx'] < self.adx_threshold:
            return None

        if sar_flipped_up and row['plus_di'] > row['minus_di']:
            return 'BUY'
        if sar_flipped_down and row['minus_di'] > row['plus_di']:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['sar']):
            return False
        if position['type'] == 'BUY' and row['sar'] > row['close']:
            return True
        if position['type'] == 'SELL' and row['sar'] < row['close']:
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
        return ['sar', 'adx', 'plus_di', 'minus_di', 'atr']
