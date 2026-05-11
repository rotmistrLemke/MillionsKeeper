"""
Inside Bar Breakout — пробой диапазона материнской свечи.

Inside Bar (внутренний бар):
  bar[-1] — материнская свеча (mother bar)
  bar[0]  — текущая свеча целиком внутри диапазона материнской:
              high[0] <= high[-1]  И  low[0] >= low[-1]

Идея (price-action классика, Brooks/Sperandeo):
  Inside Bar = сжатие после импульса. Пробой high материнской → продолжение up-импульса,
  пробой low → продолжение down-импульса.

Доп. фильтр (опционально):
  Тренд по EMA50: торгуем пробои только в направлении тренда.
  По умолчанию use_trend_filter=True. Выключи, если хочешь и контртрендовые пробои.

Сигнал на текущем баре:
  BUY:  bar[-1] был inside (внутри bar[-2]) И close[0] > high[-1]  (пробой high IB)
  SELL: bar[-1] был inside И close[0] < low[-1]                    (пробой low IB)

Выход — SL/TP по ATR. SL=1.0×ATR от противоположной стороны IB, TP=2.5×ATR.
"""

import numpy as np
import pandas as pd
import talib

from strategies.base import BaseStrategy


class InsideBarBreakoutStrategy(BaseStrategy):
    name = "inside_bar_breakout"
    description = "Inside Bar Breakout — пробой диапазона материнской свечи"
    default_timeframe = "H1"

    def __init__(self, ema_period: int = 50, atr_period: int = 14,
                 use_trend_filter: bool = True,
                 sl_atr_mult: float = 1.0, tp_atr_mult: float = 2.5):
        self.ema_period       = int(ema_period)
        self.atr_period       = int(atr_period)
        self.use_trend_filter = bool(use_trend_filter)
        self.sl_atr_mult      = float(sl_atr_mult or 0.0)
        self.tp_atr_mult      = float(tp_atr_mult or 0.0)

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50'] = talib.EMA(close, timeperiod=self.ema_period)
        df['atr']   = talib.ATR(high, low, close, timeperiod=self.atr_period)

        h = pd.Series(high)
        l = pd.Series(low)
        # bar[-1] (prev) — inside bar по отношению к bar[-2] (prev_prev).
        prev_inside = (h.shift(1) <= h.shift(2)) & (l.shift(1) >= l.shift(2))
        df['ib_prev']     = prev_inside.fillna(False).values
        df['ib_high']     = h.shift(1).values    # high материнской после сжатия — high IB
        df['ib_low']      = l.shift(1).values
        # high/low «материнской материнской» (bar[-2]) — нужны для SL опционально
        df['mom_high']    = h.shift(2).values
        df['mom_low']     = l.shift(2).values
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return True

    def get_entry_signal(self, row):
        required = ('ema50', 'atr', 'ib_prev', 'ib_high', 'ib_low')
        if any(row.get(c) is None or pd.isna(row.get(c)) for c in required):
            return None
        if not row['ib_prev']:
            return None
        close = row['close']
        ema   = row['ema50']

        broke_up   = close > row['ib_high']
        broke_down = close < row['ib_low']

        if self.use_trend_filter:
            if broke_up and close > ema:
                return 'BUY'
            if broke_down and close < ema:
                return 'SELL'
            return None
        else:
            if broke_up:   return 'BUY'
            if broke_down: return 'SELL'
            return None

    def get_exit_signal(self, row, position: dict) -> bool:
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = tp = None
        # SL — за противоположной стороной IB + буфер (sl_atr_mult * ATR)
        ib_high = row.get('ib_high'); ib_low = row.get('ib_low')
        if self.sl_atr_mult > 0 and ib_high is not None and ib_low is not None and not pd.isna(ib_high):
            if signal == 'BUY':
                sl = float(ib_low)  - self.sl_atr_mult * atr
            else:
                sl = float(ib_high) + self.sl_atr_mult * atr
        if self.tp_atr_mult > 0:
            tp = (price + self.tp_atr_mult * atr) if signal == 'BUY' \
                 else (price - self.tp_atr_mult * atr)
        return sl, tp

    def indicator_columns(self):
        return ['ema50', 'atr', 'ib_prev']
