"""
Стратегия Default Hedge.

Вход — как у основной MA+MACD+RSI:
  BUY:  EMA8 > EMA21 + MACD бычий (выше 0, растёт, выше signal)
        + RSI в 55..70 и растёт
  SELL: EMA8 < EMA21 + MACD медвежий (ниже 0, падает, ниже signal)
        + RSI в 30..45 и падает

После входа ОТКРЫВАЮТСЯ ДВЕ сделки: основная и противоположная (хедж).

Выход:
  Основная (закрывает обе сделки):
    BUY:  RSI выходит из зоны 70..100 — был ≥ 70, стал < 70
    SELL: RSI выходит из зоны 0..30  — был ≤ 30, стал > 30
  Хедж (закрывается только сам):
    SELL-хедж при основной BUY: RSI > 60
    BUY-хедж  при основной SELL: RSI < 40
"""

import numpy as np
import pandas as pd
import talib
from strategies.base import BaseStrategy


def _calc_ema_series(prices, period):
    alpha = 2 / (period + 1)
    ema = np.empty_like(prices)
    ema[0] = prices[0]
    for i in range(1, len(prices)):
        ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
    return ema


class DefaultHedgeStrategy(BaseStrategy):
    name = "default_hedge"
    description = "Default (MA+MACD+RSI) + парный хедж, выход по RSI-зонам"
    default_timeframe = "H1"

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema8']  = pd.Series(close).ewm(span=8,  adjust=False).mean().values
        df['ema21'] = pd.Series(close).ewm(span=21, adjust=False).mean().values

        ema_fast    = _calc_ema_series(close, 12)
        ema_slow    = _calc_ema_series(close, 26)
        macd_line   = ema_fast - ema_slow
        signal_line = _calc_ema_series(macd_line, 9)
        df['macd_line']   = macd_line
        df['macd_signal'] = signal_line
        df['macd_hist']   = macd_line - signal_line
        macd_prev = np.empty_like(macd_line)
        macd_prev[0]  = np.nan
        macd_prev[1:] = macd_line[:-1]
        df['macd_prev'] = macd_prev

        df['rsi']       = talib.RSI(close, timeperiod=14)
        df['rsi_prev']  = df['rsi'].shift(1)
        df['rsi_prev2'] = df['rsi'].shift(2)

        df['atr'] = talib.ATR(high, low, close, timeperiod=14)
        return df

    def is_flat(self, row) -> bool:
        return False

    def _ma(self, row):
        if row['ema8'] > row['ema21']: return 'BUY'
        if row['ema8'] < row['ema21']: return 'SELL'
        return None

    def _macd(self, row):
        h, p, s = row['macd_line'], row['macd_prev'], row['macd_signal']
        if pd.isna(p):
            return None
        if h > 0 and h > p and h > s:
            return 'BUY'
        if h < 0 and h < p and h < s:
            return 'SELL'
        return None

    def _rsi_entry(self, row):
        r, rp, rp2 = row['rsi'], row['rsi_prev'], row['rsi_prev2']
        if pd.isna(r) or pd.isna(rp) or pd.isna(rp2):
            return None
        if 70 > r > 55 and rp > rp2:
            return 'BUY'
        if 45 > r > 30 and rp < rp2:
            return 'SELL'
        return None

    def get_entry_signal(self, row):
        ma  = self._ma(row)
        mac = self._macd(row)
        rsi = self._rsi_entry(row)
        if ma == 'BUY' and mac == 'BUY' and rsi == 'BUY':
            return 'BUY'
        if ma == 'SELL' and mac == 'SELL' and rsi == 'SELL':
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        # Выход основной — движок закроет и хедж.
        rsi      = row.get('rsi')
        rsi_prev = row.get('rsi_prev')
        if rsi is None or pd.isna(rsi) or rsi_prev is None or pd.isna(rsi_prev):
            return False
        if position['type'] == 'BUY':
            # RSI был в зоне 70..100 и вышел вниз
            return rsi_prev >= 70 and rsi < 70
        # SELL: RSI был в зоне 0..30 и вышел вверх
        return rsi_prev <= 30 and rsi > 30

    def wants_hedge(self) -> bool:
        return True

    def get_hedge_exit_signal(self, row, hedge_position: dict) -> bool:
        rsi = row.get('rsi')
        if rsi is None or pd.isna(rsi):
            return False
        # Хедж BUY (основная SELL) → закрываем при RSI < 40
        if hedge_position['type'] == 'BUY':
            return rsi < 40
        # Хедж SELL (основная BUY) → закрываем при RSI > 60
        return rsi > 60

    def get_sl_tp(self, row, signal: str, point: float):
        return None, None  # управление только по RSI-зонам

    def indicator_columns(self):
        return ['ema8', 'ema21', 'macd_line', 'macd_signal', 'macd_hist', 'rsi', 'atr']
