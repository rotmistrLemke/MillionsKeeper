"""
Morning Star / Evening Star — классический 3-свечной разворот.

Паттерн (Morning Star, бычий):
  bar[-2]: длинное медвежье тело (продолжение down-тренда)
  bar[-1]: маленькое тело (звезда — индекс нерешительности), может быть бычьим/медвежьим
  bar[0]:  длинное бычье тело, закрытие глубоко в теле bar[-2]

Evening Star — зеркало бычьего на вершине up-тренда.

Контекст:
  Используем фильтр тренда по EMA200: вход против тренда (mean-reversion),
  потому что классическая Утренняя/Вечерняя звезда — пик «выгорания» тренда.

  BUY  (Morning Star):  цена ниже EMA200 (down-trend), сигнал TA-Lib CDLMORNINGSTAR > 0
  SELL (Evening Star):  цена выше EMA200 (up-trend),   сигнал TA-Lib CDLEVENINGSTAR > 0

Выход — только по SL/TP. По умолчанию SL=1.5×ATR, TP=3.0×ATR (RR=2).
"""

import pandas as pd
import talib

from strategies.base import BaseStrategy


class MorningEveningStarStrategy(BaseStrategy):
    name = "morning_evening_star"
    description = "Morning/Evening Star — 3-свечной разворот на хвосте тренда"
    default_timeframe = "H1"

    def __init__(self, ema_period: int = 200, atr_period: int = 14,
                 penetration: float = 0.3,
                 sl_atr_mult: float = 1.5, tp_atr_mult: float = 3.0):
        self.ema_period  = int(ema_period)
        self.atr_period  = int(atr_period)
        self.penetration = float(penetration)
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.tp_atr_mult = float(tp_atr_mult or 0.0)

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)

        df['ema200'] = talib.EMA(close, timeperiod=self.ema_period)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['morning_star'] = talib.CDLMORNINGSTAR(open_, high, low, close,
                                                  penetration=self.penetration)
        df['evening_star'] = talib.CDLEVENINGSTAR(open_, high, low, close,
                                                  penetration=self.penetration)
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return True

    def get_entry_signal(self, row):
        required = ('ema200', 'atr', 'morning_star', 'evening_star')
        if any(pd.isna(row.get(c)) for c in required):
            return None
        close = row['close']
        ema   = row['ema200']
        # Morning Star — внизу нисходящего тренда, ловим разворот вверх.
        if row['morning_star'] > 0 and close < ema:
            return 'BUY'
        # Evening Star — наверху восходящего тренда, ловим разворот вниз.
        if row['evening_star'] < 0 and close > ema:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = tp = None
        if self.sl_atr_mult > 0:
            sl = (price - self.sl_atr_mult * atr) if signal == 'BUY' \
                 else (price + self.sl_atr_mult * atr)
        if self.tp_atr_mult > 0:
            tp = (price + self.tp_atr_mult * atr) if signal == 'BUY' \
                 else (price - self.tp_atr_mult * atr)
        return sl, tp

    def indicator_columns(self):
        return ['ema200', 'atr', 'morning_star', 'evening_star']
