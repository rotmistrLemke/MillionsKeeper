"""
Стратегия: MACD Histogram vs Signal

Вход:
  BUY:  MACD_hist > MACD_signal
  SELL: MACD_hist < MACD_signal

Выход: только по SL или TP.

Работает на любом таймфрейме — таймфрейм задаётся в бэктесте.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class MacdHistStrategy(BaseStrategy):
    name = "macd_hist"
    description = "MACD Histogram vs Signal — вход по пересечению, выход по SL/TP"
    default_timeframe = "H1"

    def __init__(self, fast=12, slow=26, signal=9,
                 atr_period=14, sl_atr_mult=30, tp_atr_mult=100):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.atr_period = atr_period
        self.sl_atr_mult = sl_atr_mult
        self.tp_atr_mult = tp_atr_mult
        # Сторона, заблокированная после выхода по TP.
        # Снимается при появлении противоположного сигнала.
        self._blocked_side = None

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        macd_line, macd_signal, macd_hist = talib.MACD(
            close, fastperiod=self.fast, slowperiod=self.slow, signalperiod=self.signal
        )
        df['macd_line']   = macd_line
        df['macd_signal'] = macd_signal
        df['macd_hist']   = macd_hist
        df['atr']         = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def is_flat(self, row) -> bool:
        # Чистая MACD-стратегия — фильтр флэта отключён
        return False

    def get_entry_signal(self, row):
        h = row.get('macd_hist')
        s = row.get('macd_signal')
        if h is None or s is None or pd.isna(h) or pd.isna(s):
            return None
        desired = 'BUY' if h > s else ('SELL' if h < s else None)
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
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr   = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        if signal == 'BUY':
            sl = price - self.sl_atr_mult * atr
            tp = price + self.tp_atr_mult * atr
        else:
            sl = price + self.sl_atr_mult * atr
            tp = price - self.tp_atr_mult * atr
        return sl, tp

    def indicator_columns(self):
        return ['macd_line', 'macd_signal', 'macd_hist', 'atr']
