"""
Стратегия: EMA50 Overstretch — контртренд на перерастяжении от EMA50.

Идея: в устойчивом EMA-контексте (EMA50 vs EMA200) цена периодически
«улетает» слишком далеко от EMA50. Мы фейдим это перерастяжение,
ожидая возврата к средней.

Правила:
  SELL:
    EMA50 > EMA200 (восходящий EMA-контекст)
    Закрытие свечи ≥ 3.5×ATR ВЫШЕ EMA50 → фейдим SELL
  BUY:
    EMA50 < EMA200 (нисходящий EMA-контекст)
    Закрытие свечи ≥ 3.5×ATR НИЖЕ EMA50 → фейдим BUY

Выход: только по установленным SL/TP (множители ATR из формы
  или дефолтные 1.5 / 3.0). Трейла нет.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class Ema50OverstretchStrategy(BaseStrategy):
    name = "ema50_overstretch"
    description = "EMA50 Overstretch — фейдим перерастяжение от EMA50 (≥ 3.5×ATR)"
    default_timeframe = "H1"

    def __init__(self, ema_fast=50, ema_slow=200, atr_period=14,
                 stretch_atr=3.5, sl_atr_mult=1.5, tp_atr_mult=3.0):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.stretch_atr = float(stretch_atr)
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.tp_atr_mult = float(tp_atr_mult or 0.0)

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50']  = talib.EMA(close, timeperiod=self.ema_fast)
        df['ema200'] = talib.EMA(close, timeperiod=self.ema_slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return True

    def uses_trailing_exit(self) -> bool:
        return False

    def get_entry_signal(self, row):
        required = ('ema50', 'ema200', 'atr')
        if any(row.get(c) is None or pd.isna(row.get(c)) for c in required):
            return None
        ema50  = row['ema50']
        ema200 = row['ema200']
        atr    = row['atr']
        close  = row['close']
        if atr <= 0:
            return None

        threshold = self.stretch_atr * atr
        distance  = close - ema50

        # Up-контекст + перерастяжение вверх → фейдим SELL.
        if ema50 > ema200 and distance >= threshold:
            return 'SELL'
        # Down-контекст + перерастяжение вниз → фейдим BUY.
        if ema50 < ema200 and distance <= -threshold:
            return 'BUY'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = None
        tp = None
        if self.sl_atr_mult > 0:
            sl = (price - self.sl_atr_mult * atr) if signal == 'BUY' \
                 else (price + self.sl_atr_mult * atr)
        if self.tp_atr_mult > 0:
            tp = (price + self.tp_atr_mult * atr) if signal == 'BUY' \
                 else (price - self.tp_atr_mult * atr)
        return sl, tp

    def indicator_columns(self):
        return ['ema50', 'ema200', 'atr']
