"""
Стратегия 3: CCI + RSI с D1-фильтром

Логика:
  - CCI(20) пересекает +100 (лонг) или -100 (шорт)
  - RSI(14) вышел из нейтральной зоны: > 50 для BUY, < 50 для SELL
  - D1-тренд аппроксимируется EMA(200) на H1 (~8 торговых дней)

Вход:
  BUY:  CCI пересёк +100 снизу вверх + RSI > 50 + Close > EMA200
  SELL: CCI пересёк -100 сверху вниз + RSI < 50 + Close < EMA200

Выход:
  - CCI вернулся к нулю
  - SL = 1.5 * ATR, TP = 2.5 * ATR
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class CciRsiStrategy(BaseStrategy):
    name = "cci_rsi"
    description = "CCI(20) + RSI(14) H1 с D1-фильтром EMA200"
    default_timeframe = "H1"

    def __init__(self, cci_period=20, cci_level=100,
                 rsi_period=14, ema_trend=200,
                 atr_period=14, sl_atr_mult=1.5, tp_atr_mult=2.5):
        self.cci_period  = cci_period
        self.cci_level   = cci_level
        self.rsi_period  = rsi_period
        self.ema_trend   = ema_trend
        self.atr_period  = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['cci']      = talib.CCI(high, low, close, timeperiod=self.cci_period)
        df['cci_prev'] = df['cci'].shift(1)
        df['rsi']      = talib.RSI(close, timeperiod=self.rsi_period)
        df['ema200']   = talib.EMA(close, timeperiod=self.ema_trend)
        df['atr']      = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def get_entry_signal(self, row):
        required = ['cci', 'cci_prev', 'rsi', 'ema200', 'atr']
        if any(pd.isna(row[c]) for c in required):
            return None

        cci_cross_up   = row['cci_prev'] <= self.cci_level  and row['cci'] > self.cci_level
        cci_cross_down = row['cci_prev'] >= -self.cci_level and row['cci'] < -self.cci_level

        if cci_cross_up and row['rsi'] > 50 and row['close'] > row['ema200']:
            return 'BUY'
        if cci_cross_down and row['rsi'] < 50 and row['close'] < row['ema200']:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['cci']):
            return False
        # CCI вернулся к нулю — импульс иссяк
        if position['type'] == 'BUY' and row['cci'] < 0:
            return True
        if position['type'] == 'SELL' and row['cci'] > 0:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr   = row['atr']
        price = row['close']
        if signal == 'BUY':
            sl = price - self.sl_atr_mult * atr
            tp = price + self.tp_atr_mult * atr
        else:
            sl = price + self.sl_atr_mult * atr
            tp = price - self.tp_atr_mult * atr
        return sl, tp

    def indicator_columns(self):
        return ['cci', 'rsi', 'ema200', 'atr']
