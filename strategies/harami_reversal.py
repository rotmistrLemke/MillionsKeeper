"""
Harami — 2-свечной разворотный паттерн.

Паттерн (Bullish Harami):
  bar[-1]: длинное медвежье тело
  bar[0]:  маленькое бычье тело, целиком внутри тела bar[-1]
  → ослабление продавцов, потенциал разворота вверх.

Bearish Harami — зеркало после восходящего импульса.

Идея:
  Harami работает как контр-трендовый разворот после краткосрочной перекупленности/
  перепроданности. Подтверждаем экстремум через RSI(14):

    BUY  — Bullish Harami (TA-Lib > 0)  И  RSI < oversold
    SELL — Bearish Harami (TA-Lib < 0)  И  RSI > overbought

  Дополнительный фильтр — тренд по EMA50 для контртрендовых входов в верхней/
  нижней точке (по умолчанию выключен).

Выход: SL = 1.2×ATR (за хвост сигнальной свечи), TP = 2.0×ATR (RR ~1.7).
"""

import pandas as pd
import talib

from strategies.base import BaseStrategy


class HaramiReversalStrategy(BaseStrategy):
    name = "harami_reversal"
    description = "Harami + RSI — 2-свечной разворот в перекупе/перепроданности"
    default_timeframe = "H1"

    def __init__(self, rsi_period: int = 14,
                 rsi_oversold: float = 35.0, rsi_overbought: float = 65.0,
                 atr_period: int = 14,
                 sl_atr_mult: float = 1.2, tp_atr_mult: float = 2.0,
                 use_cross: bool = True):
        self.rsi_period     = int(rsi_period)
        self.rsi_oversold   = float(rsi_oversold)
        self.rsi_overbought = float(rsi_overbought)
        self.atr_period     = int(atr_period)
        self.sl_atr_mult    = float(sl_atr_mult or 0.0)
        self.tp_atr_mult    = float(tp_atr_mult or 0.0)
        # use_cross=True — учитываем также Harami Cross (вторая свеча — дожи).
        self.use_cross      = bool(use_cross)

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)

        df['rsi'] = talib.RSI(close, timeperiod=self.rsi_period)
        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['harami']       = talib.CDLHARAMI(open_, high, low, close)
        df['harami_cross'] = talib.CDLHARAMICROSS(open_, high, low, close)
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return True

    def _harami_value(self, row) -> int:
        v = int(row.get('harami') or 0)
        if self.use_cross:
            cross = int(row.get('harami_cross') or 0)
            # Если CDLHARAMICROSS вернул сигнал, он перекрывает обычный Harami.
            if cross != 0:
                v = cross
        return v

    def get_entry_signal(self, row):
        required = ('rsi', 'atr', 'harami', 'harami_cross')
        if any(pd.isna(row.get(c)) for c in required):
            return None
        rsi = row['rsi']
        v   = self._harami_value(row)
        if v > 0 and rsi < self.rsi_oversold:
            return 'BUY'
        if v < 0 and rsi > self.rsi_overbought:
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
            # SL ставим за экстремум сигнальной свечи + буфер.
            if signal == 'BUY':
                sl = float(row['low'])  - self.sl_atr_mult * atr
            else:
                sl = float(row['high']) + self.sl_atr_mult * atr
        if self.tp_atr_mult > 0:
            tp = (price + self.tp_atr_mult * atr) if signal == 'BUY' \
                 else (price - self.tp_atr_mult * atr)
        return sl, tp

    def indicator_columns(self):
        return ['rsi', 'atr', 'harami', 'harami_cross']
