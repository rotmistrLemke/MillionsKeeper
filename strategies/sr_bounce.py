"""
Стратегия: Отскок от уровней поддержки/сопротивления (S/R Bounce).

Уровни строятся по подтверждённым свинг-пикам:
  - swing high = максимум в окне [i-N … i+N], доступен с лагом N баров
  - swing low  = минимум в окне [i-N … i+N], доступен с лагом N баров

Вход:
  BUY:  Low текущего бара коснулся support (в пределах tol × ATR)
        + закрытие выше открытия (подтверждение отскока вверх)
  SELL: High текущего бара коснулся resistance (в пределах tol × ATR)
        + закрытие ниже открытия

Выход:
  - TP: ближайший противоположный уровень (для BUY — resistance, для SELL — support)
  - SL: за уровнем (support − sl × ATR для BUY, resistance + sl × ATR для SELL)
  - SIGNAL: закрытие бара по другую сторону уровня (пробой)
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class SrBounceStrategy(BaseStrategy):
    name = "sr_bounce"
    description = "S/R Bounce — отскок от поддержки/сопротивления"
    default_timeframe = "H1"

    def __init__(self, pivot_window=5, touch_atr_mult=0.3,
                 atr_period=14, sl_atr_mult=1.0, min_tp_atr_mult=1.5):
        self.pivot_window   = pivot_window      # N баров слева и справа для подтверждения пивота
        self.touch_atr_mult = touch_atr_mult    # ширина зоны касания уровня
        self.atr_period     = atr_period
        self.sl_atr_mult    = sl_atr_mult       # SL за уровнем
        self.min_tp_atr_mult = min_tp_atr_mult  # минимальный TP, если противоположный уровень слишком близко

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)

        n = self.pivot_window
        window = 2 * n + 1

        # Свинг-high/low: бар является пиком в центрированном окне
        is_sw_high = df['high'] == df['high'].rolling(window, center=True).max()
        is_sw_low  = df['low']  == df['low'].rolling(window, center=True).min()

        # Помечаем пивоты, затем сдвигаем на N вперёд — информация доступна только с лагом N,
        # и ffill распространяет последний известный уровень до появления нового
        pivot_high = df['high'].where(is_sw_high).shift(n).ffill()
        pivot_low  = df['low'].where(is_sw_low).shift(n).ffill()

        df['resistance'] = pivot_high
        df['support']    = pivot_low
        return df

    def is_flat(self, row) -> bool:
        return False

    def get_entry_signal(self, row):
        support    = row.get('support')
        resistance = row.get('resistance')
        atr        = row.get('atr')
        if any(v is None or pd.isna(v) for v in (support, resistance, atr)):
            return None

        tol = self.touch_atr_mult * atr
        low   = row['low']
        high  = row['high']
        open_ = row['open']
        close = row['close']

        # Касание поддержки снизу + бычья свеча
        if low <= support + tol and close > open_ and close > support:
            return 'BUY'
        # Касание сопротивления сверху + медвежья свеча
        if high >= resistance - tol and close < open_ and close < resistance:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        atr = row.get('atr')
        if atr is None or pd.isna(atr):
            return False
        tol = self.touch_atr_mult * atr
        entry_inds = position.get('indicators', {})
        if position['type'] == 'BUY':
            lvl = entry_inds.get('support')
            if lvl is not None and row['close'] < lvl - tol:
                return True
        else:
            lvl = entry_inds.get('resistance')
            if lvl is not None and row['close'] > lvl + tol:
                return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        price = row['close']
        atr   = row.get('atr')
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        support    = row.get('support')
        resistance = row.get('resistance')

        min_tp = self.min_tp_atr_mult * atr
        if signal == 'BUY':
            sl = (support if support is not None else price) - self.sl_atr_mult * atr
            tp_level = resistance if resistance is not None else price + min_tp
            tp = max(tp_level, price + min_tp)
        else:
            sl = (resistance if resistance is not None else price) + self.sl_atr_mult * atr
            tp_level = support if support is not None else price - min_tp
            tp = min(tp_level, price - min_tp)
        return sl, tp

    def indicator_columns(self):
        return ['support', 'resistance', 'atr']
