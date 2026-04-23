"""
Стратегия: Откат к 50 EMA в тренде 200 EMA — ema50_pullback.

Классика трендовой торговли: ловим «здоровый» тренд, где цена регулярно
тестирует 50-периодную EMA, и входим на price-action триггере у EMA50.
Выход — трейлинг через закрытие свечи по другую сторону EMA50.

Правила:
  Таймфрейм: D1 свинг / H4 активный (по умолчанию D1).
  Фильтр тренда:
    BUY:  close > EMA200
    SELL: close < EMA200
  Касание EMA50:
    BUY:  low ≤ EMA50 + touch_atr × ATR
    SELL: high ≥ EMA50 − touch_atr × ATR
  Триггер (на откате):
    BUY:  бычий пин-бар ≥ 3× ИЛИ бычье поглощение ≥ 80%
    SELL: медвежий пин-бар ИЛИ медвежье поглощение
  Вход: на открытии следующей свечи после сигнала.
  Стоп: 1×ATR ниже low сигнальной свечи (для BUY) /
        выше high (для SELL).
        Также учитывается `sl_atr_mult` от цены входа (минимум из двух
        отдаёт более консервативный стоп — т.е. ближе к цене).
  Выход: закрытие свечи по другую сторону EMA50 (трейлинг).
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy
from strategies._price_action import (
    is_bullish_pin_bar, is_bearish_pin_bar,
    is_bullish_engulfing, is_bearish_engulfing,
)


class Ema50PullbackStrategy(BaseStrategy):
    name = "ema50_pullback"
    description = "EMA50 Pullback — тренд по EMA200, вход на откате к EMA50, трейл по EMA50"
    default_timeframe = "D1"

    def __init__(self, ema_fast=50, ema_slow=200, atr_period=14,
                 touch_atr=0.5, sl_atr_mult=1.0,
                 pin_tail_ratio=3.0, engulf_overlap=0.8):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.touch_atr = float(touch_atr)
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.pin_tail_ratio = pin_tail_ratio
        self.engulf_overlap = engulf_overlap

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50']  = talib.EMA(close, timeperiod=self.ema_fast)
        df['ema200'] = talib.EMA(close, timeperiod=self.ema_slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def compute_flat_indicators(self, df):
        df = super().compute_flat_indicators(df)
        for c in ('open', 'high', 'low', 'close'):
            df[f'prev_{c}'] = df[c].shift(1)
        return df

    def is_flat(self, row) -> bool:
        # Флэт мы фильтруем через тренд 200EMA — отдельный ADX-фильтр не нужен.
        return False

    def closes_on_weekend(self) -> bool:
        return False

    def uses_trailing_exit(self) -> bool:
        return True

    def _touched_ema50(self, row, direction: str) -> bool:
        atr = row.get('atr'); ema50 = row.get('ema50')
        if atr is None or ema50 is None or pd.isna(atr) or pd.isna(ema50):
            return False
        threshold = self.touch_atr * atr
        if direction == 'BUY':
            return row['low'] <= ema50 + threshold
        return row['high'] >= ema50 - threshold

    def get_entry_signal(self, row):
        ema200 = row.get('ema200'); ema50 = row.get('ema50')
        if ema200 is None or ema50 is None or pd.isna(ema200) or pd.isna(ema50):
            return None

        prev_row = {
            'open':  row.get('prev_open'),
            'close': row.get('prev_close'),
            'high':  row.get('prev_high'),
            'low':   row.get('prev_low'),
        }
        has_prev = not any(v is None or pd.isna(v) for v in prev_row.values())

        bull_pin = is_bullish_pin_bar(row, self.pin_tail_ratio)
        bear_pin = is_bearish_pin_bar(row, self.pin_tail_ratio)
        bull_eng = has_prev and is_bullish_engulfing(prev_row, row, self.engulf_overlap)
        bear_eng = has_prev and is_bearish_engulfing(prev_row, row, self.engulf_overlap)

        if row['close'] > ema200 and self._touched_ema50(row, 'BUY') and (bull_pin or bull_eng):
            return 'BUY'
        if row['close'] < ema200 and self._touched_ema50(row, 'SELL') and (bear_pin or bear_eng):
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        """Трейл: закрытие свечи по другую сторону EMA50."""
        ema50 = row.get('ema50')
        if ema50 is None or pd.isna(ema50):
            return False
        if position['type'] == 'BUY' and row['close'] < ema50:
            return True
        if position['type'] == 'SELL' and row['close'] > ema50:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point

        price = row['close']
        # SL от сигнальной свечи (1×ATR ниже low / выше high).
        if signal == 'BUY':
            sl_candle = row['low'] - atr
            sl_from_entry = price - self.sl_atr_mult * atr if self.sl_atr_mult > 0 else None
            sl = sl_candle if sl_from_entry is None else max(sl_candle, sl_from_entry)
        else:
            sl_candle = row['high'] + atr
            sl_from_entry = price + self.sl_atr_mult * atr if self.sl_atr_mult > 0 else None
            sl = sl_candle if sl_from_entry is None else min(sl_candle, sl_from_entry)
        return sl, None

    def indicator_columns(self):
        return ['ema50', 'ema200', 'atr']
