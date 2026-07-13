"""
Стратегия: Aroon Up/Down Cross

Вход (проверяется по последней закрытой свече):
  BUY:  Aroon Up > Aroon Down
  SELL: Aroon Up < Aroon Down

Пересечение реализовано как сравнение состояния (какая линия сверху) с
блокировкой повторного входа в ту же сторону после выхода по SL/TP — так
вход происходит на свежем флипе Aroon, а не на каждой свече (аналогично macd_hist).

Выход: только по SL или TP.

Работает на любом таймфрейме — таймфрейм задаётся в бэктесте/потоке.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class AroonStrategy(BaseStrategy):
    name = "aroon"
    description = "Aroon Up/Down Cross — вход по пересечению линий, выход по SL/TP"
    default_timeframe = "H1"

    def __init__(self, period=25, atr_period=14,
                 sl_atr_mult=2.0, tp_atr_mult=3.0):
        self.period = period
        self.atr_period = atr_period
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.tp_atr_mult = float(tp_atr_mult or 0.0)
        # Сторона, заблокированная после выхода по SL/TP.
        # Снимается при появлении противоположного сигнала.
        self._blocked_side = None

    def compute_indicators(self, df):
        high = df['high'].values.astype(float)
        low  = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        aroon_down, aroon_up = talib.AROON(high, low, timeperiod=self.period)
        df['aroon_down'] = aroon_down
        df['aroon_up']   = aroon_up
        df['atr']        = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def is_flat(self, row) -> bool:
        # Чистая Aroon-стратегия — фильтр флэта отключён.
        return False

    def get_entry_signal(self, row):
        up   = row.get('aroon_up')
        down = row.get('aroon_down')
        if up is None or down is None or pd.isna(up) or pd.isna(down):
            return None
        desired = 'BUY' if up > down else ('SELL' if up < down else None)
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
        return ['aroon_down', 'aroon_up', 'atr']
