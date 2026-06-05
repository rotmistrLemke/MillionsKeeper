"""
Стратегия: Возврат к среднему (10/20 EMA) — mean_revert_ema.

Идея: две быстрые EMA формируют зону «справедливой цены». В трендовом
рынке цена регулярно откатывает к этой зоне и возвращается в тренд.
Вход — по price-action триггеру в зоне EMA.

Правила:
  Таймфрейм: H4 или D1 (H4 по умолчанию).
  Тренд:
    BUY-контекст: EMA10 > EMA20
    SELL-контекст: EMA10 < EMA20
  Откат:
    Свеча должна коснуться зоны [EMA20 .. EMA10] (low ≤ max, high ≥ min)
  Триггер:
    BUY:  бычий пин-бар ИЛИ бычье поглощение (≥ 80%) в зоне EMA
    SELL: медвежий пин-бар ИЛИ медвежье поглощение
  Фильтр «улетела от EMA»:
    Цена закрытия не дальше `far_atr_mult` × ATR от EMA10,
    иначе ждём возврата.
  Стоп:
    За пин-баром (low - 0.2×ATR для BUY; high + 0.2×ATR для SELL)
    ИЛИ `sl_atr_mult` × ATR от цены входа.
  Выход (трейлинг):
    Закрытие свечи по другую сторону EMA20.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy
from strategies._price_action import (
    is_bullish_pin_bar, is_bearish_pin_bar,
    is_bullish_engulfing, is_bearish_engulfing,
)


class MeanRevertEmaStrategy(BaseStrategy):
    name = "mean_revert_ema"
    description = "Mean Revert 10/20 EMA — откат в зону EMA + pin/engulfing"
    default_timeframe = "H4"

    def __init__(self, fast=10, slow=20, atr_period=14,
                 sl_atr_mult=1.5, far_atr_mult=3.0,
                 pin_tail_ratio=3.0, engulf_overlap=0.8):
        self.fast = fast
        self.slow = slow
        self.atr_period = atr_period
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.far_atr_mult = float(far_atr_mult or 0.0)
        self.pin_tail_ratio = pin_tail_ratio
        self.engulf_overlap = engulf_overlap

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema10'] = talib.EMA(close, timeperiod=self.fast)
        df['ema20'] = talib.EMA(close, timeperiod=self.slow)
        df['atr']   = talib.ATR(high, low, close, timeperiod=self.atr_period)
        # Зона EMA
        df['ema_zone_hi'] = df[['ema10', 'ema20']].max(axis=1)
        df['ema_zone_lo'] = df[['ema10', 'ema20']].min(axis=1)
        return df

    def is_flat(self, row) -> bool:
        # Контекст задаётся взаимным положением EMA10/20.
        # Флэт не применяем — иначе пропустим большинство сигналов.
        return False

    def closes_on_weekend(self) -> bool:
        return False

    def uses_trailing_exit(self) -> bool:
        return True

    def _in_zone(self, row) -> bool:
        zh = row.get('ema_zone_hi'); zl = row.get('ema_zone_lo')
        if zh is None or zl is None or pd.isna(zh) or pd.isna(zl):
            return False
        # Касание зоны телом/тенью свечи
        return row['low'] <= zh and row['high'] >= zl

    def _far_from_ema(self, row) -> bool:
        atr = row.get('atr')
        ema10 = row.get('ema10')
        if atr is None or ema10 is None or pd.isna(atr) or pd.isna(ema10) or atr <= 0:
            return False
        return abs(row['close'] - ema10) > self.far_atr_mult * atr

    def get_entry_signal(self, row):
        ema10 = row.get('ema10'); ema20 = row.get('ema20')
        if ema10 is None or ema20 is None or pd.isna(ema10) or pd.isna(ema20):
            return None
        if not self._in_zone(row) or self._far_from_ema(row):
            return None

        prev = row.get('_prev')  # подставляется движком? — нет. См. ниже.
        # В engine'е передаётся одна row без prev, поэтому engulfing считаем
        # через row[['prev_open', 'prev_close', ...]] сохранённые в compute_indicators.
        # Упрощаем: pin-bar самодостаточен. Engulfing проверяем через shift-колонки.
        bull_pin = is_bullish_pin_bar(row, self.pin_tail_ratio)
        bear_pin = is_bearish_pin_bar(row, self.pin_tail_ratio)

        prev_row = {
            'open':  row.get('prev_open'),
            'close': row.get('prev_close'),
            'high':  row.get('prev_high'),
            'low':   row.get('prev_low'),
        }
        bull_eng = False
        bear_eng = False
        if not any(v is None or pd.isna(v) for v in prev_row.values()):
            bull_eng = is_bullish_engulfing(prev_row, row, self.engulf_overlap)
            bear_eng = is_bearish_engulfing(prev_row, row, self.engulf_overlap)

        if ema10 > ema20 and (bull_pin or bull_eng):
            return 'BUY'
        if ema10 < ema20 and (bear_pin or bear_eng):
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        """Трейл: закрытие свечи по другую сторону EMA20."""
        ema20 = row.get('ema20')
        if ema20 is None or pd.isna(ema20):
            return False
        if position['type'] == 'BUY' and row['close'] < ema20:
            return True
        if position['type'] == 'SELL' and row['close'] > ema20:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = None
        if self.sl_atr_mult > 0:
            sl = (price - self.sl_atr_mult * atr) if signal == 'BUY' \
                 else (price + self.sl_atr_mult * atr)
        # TP не задаём — работает трейлинг через get_exit_signal.
        return sl, None

    def compute_flat_indicators(self, df):
        # Добавляем prev-колонки для engulfing и вызываем базовый флэт-вычислитель.
        df = super().compute_flat_indicators(df)
        for c in ('open', 'high', 'low', 'close'):
            df[f'prev_{c}'] = df[c].shift(1)
        return df

    def indicator_columns(self):
        return ['ema10', 'ema20', 'atr']
