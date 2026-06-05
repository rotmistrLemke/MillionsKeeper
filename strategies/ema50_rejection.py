"""
Стратегия: EMA50 Rejection — откат и ретест в сильном тренде.

Суть: торгуем только в «сильном» тренде, где EMA50 отстоит от EMA200
на ≥ 2×ATR. Ждём отката за EMA50 (закрытие свечи по «неправильную»
сторону), затем ждём, чтобы следующая свеча закрылась обратно по
«правильную» сторону EMA50 — вход по направлению тренда.

Правила:
  BUY:
    Тренд: EMA50 − EMA200 ≥ 2×ATR (сильный восходящий)
    Откат: свеча закрылась ниже EMA50
    Триггер: следующая свеча закрылась выше EMA50 → вход BUY
  SELL (зеркально):
    Тренд: EMA200 − EMA50 ≥ 2×ATR (сильный нисходящий)
    Откат: свеча закрылась выше EMA50
    Триггер: следующая свеча закрылась ниже EMA50 → вход SELL

Выход: по установленным SL и TP (фиксированные уровни из формы,
       или дефолтные множители ATR — 1.5 / 3.0).

Сброс ожидания:
  Если после отката тренд потерял «силу» (sep < 2×ATR), состояние
  ожидания сбрасывается — новый цикл возможен после восстановления.
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class Ema50RejectionStrategy(BaseStrategy):
    name = "ema50_rejection"
    description = "EMA50 Rejection — откат в сильном тренде + ретест EMA50"
    default_timeframe = "H1"

    def __init__(self, ema_fast=50, ema_slow=200, atr_period=14,
                 separation_atr=2.0, sl_atr_mult=1.5, tp_atr_mult=3.0):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.separation_atr = float(separation_atr)
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.tp_atr_mult = float(tp_atr_mult or 0.0)
        # Состояние ожидания ретеста: 'UP' | 'DOWN' | None
        self._waiting_side = None

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema50']  = talib.EMA(close, timeperiod=self.ema_fast)
        df['ema200'] = talib.EMA(close, timeperiod=self.ema_slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)
        return df

    def is_flat(self, row) -> bool:
        # Фильтр «силы тренда» через separation_atr встроен в логику — отдельный
        # ADX-флэт только забьёт сигналы, которые уже прошли жёсткий отбор.
        return False

    def closes_on_weekend(self) -> bool:
        return True

    def uses_trailing_exit(self) -> bool:
        # Выход строго по SL/TP — трейла нет.
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

        sep = ema50 - ema200
        trend_up_ok   = sep >   self.separation_atr * atr
        trend_down_ok = sep < - self.separation_atr * atr

        # Сброс ожидания, если тренд больше не квалифицируется.
        if self._waiting_side == 'UP' and not trend_up_ok:
            self._waiting_side = None
        elif self._waiting_side == 'DOWN' and not trend_down_ok:
            self._waiting_side = None

        # Этап 2: ждём ретест EMA50 в направлении тренда.
        if self._waiting_side == 'UP':
            if close > ema50:
                self._waiting_side = None
                return 'BUY'
            return None
        if self._waiting_side == 'DOWN':
            if close < ema50:
                self._waiting_side = None
                return 'SELL'
            return None

        # Этап 1: IDLE — ждём откат за EMA50 в подходящем тренде.
        if trend_up_ok and close < ema50:
            self._waiting_side = 'UP'
        elif trend_down_ok and close > ema50:
            self._waiting_side = 'DOWN'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        # Выход только по SL/TP — никаких стратегических выходов.
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

    def on_trade_closed(self, position: dict, reason: str) -> None:
        # После закрытия позиции ждём новый цикл откат-ретест с нуля.
        self._waiting_side = None

    def indicator_columns(self):
        return ['ema50', 'ema200', 'atr']
