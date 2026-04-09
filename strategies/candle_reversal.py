"""
Стратегия 6: Candlestick Reversal (Свечной анализ)

Паттерны:
  - Дожи: тело < 20% от диапазона свечи — нерешительность после тренда
  - Пин-бар: длинная тень (> 2x тела) против тренда
  - Поглощение: текущая свеча полностью поглощает предыдущую
  - "Три солдата/вороны": 3 бара с длинными телами подряд → коррекция

Условия входа:
  - Паттерн формируется после направленного движения (3+ баров тренда)
  - ADX < 30 — тренд ослабевает (нет смысла разворачивать сильный тренд)

Вход:
  BUY:  Медвежий тренд + разворотный паттерн (бычий)
  SELL: Бычий тренд + разворотный паттерн (медвежий)

Выход:
  - SL = экстремум паттерна + 0.5 * ATR
  - TP = 2.0 * ATR
"""

import pandas as pd
import numpy as np
import talib
from strategies.base import BaseStrategy


class CandleReversalStrategy(BaseStrategy):
    name = "candle_reversal"
    description = "Candlestick Reversal H1 — дожи, пин-бар, поглощение"
    default_timeframe = "H1"

    def __init__(self, trend_bars=3, adx_period=14, adx_max=35,
                 atr_period=14, sl_atr_mult=1.0, tp_atr_mult=2.0):
        self.trend_bars   = trend_bars   # сколько баров образуют тренд
        self.adx_period   = adx_period
        self.adx_max      = adx_max      # не входим в разворот при очень сильном тренде
        self.atr_period   = atr_period
        self.sl_atr_mult  = sl_atr_mult
        self.tp_atr_mult  = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)
        open_ = df['open'].values.astype(float)

        df['atr'] = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['adx'] = talib.ADX(high, low, close, timeperiod=self.adx_period)

        body       = np.abs(close - open_)
        candle_rng = high - low
        lower_tail = np.minimum(open_, close) - low
        upper_tail = high - np.maximum(open_, close)

        # Дожи: тело < 15% диапазона
        df['doji'] = (candle_rng > 0) & (body / candle_rng < 0.15)

        # Пин-бар бычий: нижняя тень > 2x тела, закрытие в верхней трети
        df['pin_bull'] = (
            (lower_tail > 2.0 * body) &
            (body > 0) &
            (close > (low + candle_rng * 0.6))
        )
        # Пин-бар медвежий: верхняя тень > 2x тела, закрытие в нижней трети
        df['pin_bear'] = (
            (upper_tail > 2.0 * body) &
            (body > 0) &
            (close < (high - candle_rng * 0.6))
        )

        # Поглощение
        prev_high_body = pd.Series(np.maximum(open_, close)).shift(1)
        prev_low_body  = pd.Series(np.minimum(open_, close)).shift(1)
        curr_high_body = pd.Series(np.maximum(open_, close))
        curr_low_body  = pd.Series(np.minimum(open_, close))

        df['engulf_bull'] = (
            (close > open_) &
            (curr_high_body > prev_high_body) &
            (curr_low_body  < prev_low_body) &
            (pd.Series(close).shift(1) < pd.Series(open_).shift(1))  # предыдущая медвежья
        ).values
        df['engulf_bear'] = (
            (close < open_) &
            (curr_high_body > prev_high_body) &
            (curr_low_body  < prev_low_body) &
            (pd.Series(close).shift(1) > pd.Series(open_).shift(1))  # предыдущая бычья
        ).values

        # Три бара подряд с длинными телами (> 60% диапазона) — "завод"
        strong_bull = (body > 0.6 * candle_rng) & (close > open_)
        strong_bear = (body > 0.6 * candle_rng) & (close < open_)
        df['three_bull'] = pd.Series(strong_bull).rolling(self.trend_bars).sum() >= self.trend_bars
        df['three_bear'] = pd.Series(strong_bear).rolling(self.trend_bars).sum() >= self.trend_bars

        # Направленный тренд за последние trend_bars баров
        df['trend_up']   = pd.Series(close > open_).shift(1).rolling(self.trend_bars).sum() >= self.trend_bars
        df['trend_down'] = pd.Series(close < open_).shift(1).rolling(self.trend_bars).sum() >= self.trend_bars

        return df

    def get_entry_signal(self, row):
        required = ['atr', 'adx', 'trend_up', 'trend_down']
        if any(pd.isna(row[c]) for c in required):
            return None
        if row['adx'] > self.adx_max:
            return None

        # BUY: после медвежьего тренда или трёх медвежьих баров → бычий паттерн
        after_downtrend = row['trend_down'] or row['three_bear']
        bull_pattern = row['doji'] or row['pin_bull'] or row['engulf_bull']
        if after_downtrend and bull_pattern:
            return 'BUY'

        # SELL: после бычьего тренда или трёх бычьих баров → медвежий паттерн
        after_uptrend = row['trend_up'] or row['three_bull']
        bear_pattern = row['doji'] or row['pin_bear'] or row['engulf_bear']
        if after_uptrend and bear_pattern:
            return 'SELL'

        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        # Выход по паттерну разворота против текущей позиции
        if position['type'] == 'BUY' and (row.get('pin_bear') or row.get('engulf_bear')):
            return True
        if position['type'] == 'SELL' and (row.get('pin_bull') or row.get('engulf_bull')):
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr   = row['atr']
        price = row['close']
        if signal == 'BUY':
            sl = row['low'] - self.sl_atr_mult * atr
            tp = price + self.tp_atr_mult * atr
        else:
            sl = row['high'] + self.sl_atr_mult * atr
            tp = price - self.tp_atr_mult * atr
        return sl, tp

    def indicator_columns(self):
        return ['adx', 'atr', 'doji', 'pin_bull', 'pin_bear', 'engulf_bull', 'engulf_bear']
