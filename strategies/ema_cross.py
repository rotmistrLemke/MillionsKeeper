"""
Стратегия: EMA 50/200 Cross

Вход (проверяется на открытии каждой новой свечи):
  BUY:  EMA50 выше EMA200
  SELL: EMA50 ниже EMA200

Выход: только по SL/TP (множители ATR; 0 = выкл).
После выхода по SL/TP та же сторона не переоткрывается, пока EMA50/EMA200
не пересекутся в обратную сторону (блокировка _blocked_side).

SL/TP задаются множителями ATR через конструктор (sl_atr_mult, tp_atr_mult).
В бэктесте/лайве пользовательские sl_atr / tp_atr из формы перекрывают
дефолты стратегии.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class EmaCrossStrategy(BaseStrategy):
    name = "ema_cross"
    description = "EMA 50/200 Cross — вход по взаимному положению EMA, выход только по SL/TP"
    default_timeframe = "H1"

    def __init__(self, fast=50, slow=200, atr_period=14,
                 sl_atr_mult=2.0, tp_atr_mult=3.0):
        self.fast = fast
        self.slow = slow
        self.atr_period = atr_period
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.tp_atr_mult = float(tp_atr_mult or 0.0)
        # Сторона, заблокированная после выхода по SL/TP.
        # Снимается при появлении противоположного сигнала.
        self._blocked_side = None

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50']  = talib.EMA(close, timeperiod=self.fast)
        df['ema200'] = talib.EMA(close, timeperiod=self.slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        # Сигналы редкие — не срезаем позицию на выходных.
        return False

    def get_entry_signal(self, row):
        ema50  = row.get('ema50')
        ema200 = row.get('ema200')
        if ema50 is None or ema200 is None or pd.isna(ema50) or pd.isna(ema200):
            return None
        desired = 'BUY' if ema50 > ema200 else ('SELL' if ema50 < ema200 else None)
        if desired is None:
            return None
        if self._blocked_side == desired:
            return None
        self._blocked_side = None
        return desired

    def on_trade_closed(self, position: dict, reason: str) -> None:
        if reason in ('TP', 'SL'):
            self._blocked_side = position.get('type')
        else:
            self._blocked_side = None

    def get_exit_signal(self, row, position: dict) -> bool:
        # Выход только по SL/TP — сигнального выхода нет.
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
