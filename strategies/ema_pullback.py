"""
Стратегия 2: EMA Pullback (Возврат к скользящим средним)

Логика:
  - EMA50 и EMA200 определяют тренд
  - В бычьем тренде (close > EMA200) ждём откат к EMA50
  - Подтверждение: пин-бар или бычье поглощение при откате
  - В медвежьем тренде — зеркально

Вход:
  BUY:  Close > EMA200 + Low коснулось EMA50 (откат) + бычья свеча
  SELL: Close < EMA200 + High коснулось EMA50 (откат) + медвежья свеча

Выход:
  - TP = 2.5 * ATR (в сторону тренда)
  - SL = 1.5 * ATR за экстремумом отката
  - Или цена вернулась ниже EMA200 (тренд сломан)
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class EmaPullbackStrategy(BaseStrategy):
    name = "ema_pullback"
    description = "EMA Pullback H1 — откат к EMA50 в тренде EMA200"
    default_timeframe = "H1"

    def __init__(self, ema_fast=50, ema_slow=200, touch_atr_mult=0.3,
                 atr_period=14, sl_atr_mult=1.5, tp_atr_mult=2.5):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.touch_atr_mult = touch_atr_mult  # насколько близко low/high к EMA50 = "касание"
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)

        df['ema50']  = talib.EMA(close, timeperiod=self.ema_fast)
        df['ema200'] = talib.EMA(close, timeperiod=self.ema_slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)

        # Свечные паттерны
        # Пин-бар: тень > 2x тела, тело в верхней/нижней трети свечи
        body   = abs(close - open_)
        candle = high - low
        lower_tail = pd.Series(open_).combine(pd.Series(close), min) - pd.Series(low)
        upper_tail = pd.Series(high) - pd.Series(open_).combine(pd.Series(close), max)

        df['pin_bull'] = ((lower_tail > 2 * body) & (candle > 0)).values
        df['pin_bear'] = ((upper_tail > 2 * body) & (candle > 0)).values

        # Поглощение
        prev_body_top    = pd.Series(open_).shift(1).combine(pd.Series(close).shift(1), max)
        prev_body_bottom = pd.Series(open_).shift(1).combine(pd.Series(close).shift(1), min)
        curr_body_top    = pd.Series(open_).combine(pd.Series(close), max)
        curr_body_bottom = pd.Series(open_).combine(pd.Series(close), min)

        df['engulf_bull'] = ((close > open_) &
                             (curr_body_top > prev_body_top) &
                             (curr_body_bottom < prev_body_bottom)).values
        df['engulf_bear'] = ((close < open_) &
                             (curr_body_top > prev_body_top) &
                             (curr_body_bottom < prev_body_bottom)).values
        return df

    def get_entry_signal(self, row):
        required = ['ema50', 'ema200', 'atr']
        if any(pd.isna(row[c]) for c in required):
            return None

        atr    = row['atr']
        ema50  = row['ema50']
        ema200 = row['ema200']
        close  = row['close']

        touched_ema50_from_above = row['low'] <= ema50 + self.touch_atr_mult * atr
        touched_ema50_from_below = row['high'] >= ema50 - self.touch_atr_mult * atr

        bull_confirm = bool(row['pin_bull']) or bool(row['engulf_bull'])
        bear_confirm = bool(row['pin_bear']) or bool(row['engulf_bear'])

        if close > ema200 and touched_ema50_from_above and bull_confirm:
            return 'BUY'
        if close < ema200 and touched_ema50_from_below and bear_confirm:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        if pd.isna(row['ema200']):
            return False
        # Тренд сломан — цена пересекла EMA200
        if position['type'] == 'BUY' and row['close'] < row['ema200']:
            return True
        if position['type'] == 'SELL' and row['close'] > row['ema200']:
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
        return ['ema50', 'ema200', 'atr']
