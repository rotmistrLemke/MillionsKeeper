"""
Стратегия: Default Inverse (инверсия MA + MACD + RSI)

Вход — когда все три фильтра основной стратегии согласованы,
но направление перевёрнуто:
  MA+MACD+RSI → BUY   →   открываем SELL
  MA+MACD+RSI → SELL  →   открываем BUY

Выход по RSI (тоже инвертирован относительно default):
  BUY  закрывается при RSI > 50
  SELL закрывается при RSI < 50

SL/TP отключены по умолчанию — управляются множителями ATR
из настроек потока (stream.sl_atr / stream.tp_atr; 0 = выкл).

Флэт-фильтр ИНВЕРТИРОВАН: торгуем ТОЛЬКО во флэте.
Флэт детектируется по 2-из-3 условий (ADX < 20, BB-ширина ниже средней,
ATR ниже среднего). Если рынок в тренде — вход запрещён.
Метод is_flat() возвращает False (чтобы движок не блокировал торговлю);
реальная проверка встроена в get_entry_signal().
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class DefaultInverseStrategy(BaseStrategy):
    name = "default_inverse"
    description = "Инверсия основной стратегии MA + MACD + RSI"
    default_timeframe = "H1"

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema8']  = pd.Series(close).ewm(span=8,  adjust=False).mean().values
        df['ema21'] = pd.Series(close).ewm(span=21, adjust=False).mean().values

        ema_fast    = pd.Series(close).ewm(span=12, adjust=False).mean().values
        ema_slow    = pd.Series(close).ewm(span=26, adjust=False).mean().values
        macd_line   = ema_fast - ema_slow
        signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
        df['macd_line']   = macd_line
        df['macd_signal'] = signal_line
        df['macd_prev']   = pd.Series(macd_line).shift(1).values

        df['rsi']       = talib.RSI(close, timeperiod=14)
        df['rsi_prev']  = df['rsi'].shift(1)
        df['rsi_prev2'] = df['rsi'].shift(2)

        df['atr'] = talib.ATR(high, low, close, timeperiod=14)

        # Флэт-индикаторы — нужны для внутренней проверки в get_entry_signal.
        df = self.compute_flat_indicators(df)
        return df

    def is_flat(self, row) -> bool:
        # Возвращаем False, чтобы движок не блокировал вход.
        # Фактическая проверка «в флэте?» делается в get_entry_signal.
        return False

    def _market_is_flat(self, row) -> bool:
        """True, если рынок сейчас во флэте (исходная логика BaseStrategy.is_flat)."""
        required = ['flat_adx', 'flat_bb_width', 'flat_bb_width_avg', 'flat_atr', 'flat_atr_avg']
        for c in required:
            if c not in row.index or pd.isna(row[c]):
                return False
        signals = 0
        if row['flat_adx'] < self.flat_adx_threshold:
            signals += 1
        if row['flat_bb_width'] < row['flat_bb_width_avg']:
            signals += 1
        if row['flat_atr'] < row['flat_atr_avg']:
            signals += 1
        return signals >= 2

    def _ma_signal(self, row):
        if row['ema8'] > row['ema21']:   return 'BUY'
        if row['ema8'] < row['ema21']:   return 'SELL'
        return 'NO_SIGNAL'

    def _macd_signal(self, row):
        h, p, s = row['macd_line'], row['macd_prev'], row['macd_signal']
        if pd.isna(p):                           return 'NO_SIGNAL'
        if h > 0 and h > p and h > s:            return 'BUY'
        if h < 0 and h < p and h < s:            return 'SELL'
        return 'NO_SIGNAL'

    def _rsi_signal(self, row):
        r, rp, rp2 = row['rsi'], row['rsi_prev'], row['rsi_prev2']
        if pd.isna(r) or pd.isna(rp) or pd.isna(rp2): return 'NO_SIGNAL'
        if 70 > r > 55 and rp > rp2:                  return 'BUY'
        if 45 > r > 30 and rp < rp2:                  return 'SELL'
        return 'NO_SIGNAL'

    def _combined(self, row):
        ma, macd, rsi = self._ma_signal(row), self._macd_signal(row), self._rsi_signal(row)
        if ma == 'BUY'  and macd == 'BUY'  and rsi == 'BUY':  return 'BUY'
        if ma == 'SELL' and macd == 'SELL' and rsi == 'SELL': return 'SELL'
        return 'NO_SIGNAL'

    def get_entry_signal(self, row):
        for col in ('ema8', 'ema21', 'macd_line', 'macd_prev', 'macd_signal',
                    'rsi', 'rsi_prev', 'rsi_prev2'):
            v = row.get(col)
            if v is None or pd.isna(v):
                return None
        # Торгуем ТОЛЬКО во флэте.
        if not self._market_is_flat(row):
            return None
        combined = self._combined(row)
        if combined == 'BUY':  return 'SELL'
        if combined == 'SELL': return 'BUY'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        r = row.get('rsi')
        if r is None or pd.isna(r):
            return False
        if position['type'] == 'BUY'  and r > 50: return True
        if position['type'] == 'SELL' and r < 50: return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        return None, None

    def indicator_columns(self):
        return ['ema8', 'ema21', 'macd_line', 'macd_signal', 'rsi', 'atr']
