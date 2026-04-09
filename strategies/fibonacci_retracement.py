"""
Стратегия 4: Fibonacci Retracement

Логика:
  - Находим импульс: серия из N сильных баров в одну сторону
  - Вычисляем уровни Фибоначчи 38.2% и 50% от начала до конца импульса
  - Ждём откат к этим уровням
  - Подтверждение: разворотная свеча (пин-бар или поглощение)

Вход:
  BUY:  Бычий импульс → откат к 38.2%/50% → бычья свеча
  SELL: Медвежий импульс → отскок к 38.2%/50% → медвежья свеча

Выход:
  - TP = обновление экстремума импульса (или 2.5 * ATR)
  - SL = чуть ниже 61.8% (или 1.5 * ATR)
"""

import pandas as pd
import numpy as np
import talib
from strategies.base import BaseStrategy


class FibonacciRetracementStrategy(BaseStrategy):
    name = "fibonacci_retracement"
    description = "Fibonacci Retracement H1 — откат к 38.2%/50%"
    default_timeframe = "H1"

    def __init__(self, impulse_bars=5, min_impulse_atr=1.5,
                 atr_period=14, sl_atr_mult=1.5, tp_atr_mult=2.5):
        self.impulse_bars    = impulse_bars      # сколько баров составляет импульс
        self.min_impulse_atr = min_impulse_atr   # минимальный размер импульса в ATR
        self.atr_period      = atr_period
        self.sl_atr_mult     = sl_atr_mult
        self.tp_atr_mult     = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)

        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)

        # Уровни Фибоначчи: импульс за последние impulse_bars баров (без текущего)
        n = self.impulse_bars
        impulse_high = df['high'].shift(1).rolling(n).max()
        impulse_low  = df['low'].shift(1).rolling(n).min()

        # Бычий импульс: close N баров назад значительно ниже текущего high
        df['imp_high'] = impulse_high
        df['imp_low']  = impulse_low
        df['fib_382_bull'] = impulse_high - (impulse_high - impulse_low) * 0.382
        df['fib_500_bull'] = impulse_high - (impulse_high - impulse_low) * 0.500
        df['fib_618_bull'] = impulse_high - (impulse_high - impulse_low) * 0.618
        df['fib_382_bear'] = impulse_low  + (impulse_high - impulse_low) * 0.382
        df['fib_500_bear'] = impulse_low  + (impulse_high - impulse_low) * 0.500
        df['fib_618_bear'] = impulse_low  + (impulse_high - impulse_low) * 0.618

        # Определяем направление импульса: закрытие N баров назад vs текущего
        past_close = df['close'].shift(n)
        df['impulse_bull'] = (df['close'].shift(1) > past_close) & \
                             ((impulse_high - impulse_low) > self.min_impulse_atr * df['atr'])
        df['impulse_bear'] = (df['close'].shift(1) < past_close) & \
                             ((impulse_high - impulse_low) > self.min_impulse_atr * df['atr'])

        # Свечные паттерны подтверждения
        body       = abs(pd.Series(close) - pd.Series(open_))
        candle     = pd.Series(high) - pd.Series(low)
        lower_tail = pd.Series(open_).combine(pd.Series(close), min) - pd.Series(low)
        upper_tail = pd.Series(high) - pd.Series(open_).combine(pd.Series(close), max)

        df['confirm_bull'] = ((lower_tail > 1.5 * body) | (close > open_)).values
        df['confirm_bear'] = ((upper_tail > 1.5 * body) | (close < open_)).values

        return df

    def get_entry_signal(self, row):
        required = ['atr', 'fib_382_bull', 'fib_618_bull', 'impulse_bull', 'impulse_bear']
        if any(pd.isna(row[c]) for c in required):
            return None

        price = row['close']
        atr   = row['atr']

        # BUY: был бычий импульс, цена откатила к 38.2%-50%, подтверждение
        if row['impulse_bull']:
            at_fib_bull = (row['fib_618_bull'] <= price <= row['fib_382_bull'])
            if at_fib_bull and row['confirm_bull']:
                return 'BUY'

        # SELL: был медвежий импульс, цена откатила к 38.2%-50%, подтверждение
        if row['impulse_bear']:
            at_fib_bear = (row['fib_382_bear'] <= price <= row['fib_618_bear'])
            if at_fib_bear and row['confirm_bear']:
                return 'SELL'

        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['imp_high']) or pd.isna(row['imp_low']):
            return False
        # Цена достигла экстремума импульса — фиксируем
        if position['type'] == 'BUY' and row['high'] >= row['imp_high']:
            return True
        if position['type'] == 'SELL' and row['low'] <= row['imp_low']:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr   = row['atr']
        price = row['close']
        if signal == 'BUY':
            sl = row['fib_618_bull'] - 0.5 * atr if not pd.isna(row['fib_618_bull']) else price - self.sl_atr_mult * atr
            tp = row['imp_high'] if not pd.isna(row['imp_high']) else price + self.tp_atr_mult * atr
        else:
            sl = row['fib_618_bear'] + 0.5 * atr if not pd.isna(row['fib_618_bear']) else price + self.sl_atr_mult * atr
            tp = row['imp_low'] if not pd.isna(row['imp_low']) else price - self.tp_atr_mult * atr
        return sl, tp

    def indicator_columns(self):
        return ['imp_high', 'imp_low', 'fib_382_bull', 'fib_500_bull', 'atr']
