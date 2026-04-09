"""
Стратегия 5: Post-News Breakout (Торговля после новостей)

Логика:
  - Новостной выброс определяем по ATR-спайку: ATR текущего бара > 2x среднего ATR
  - Ждём 1-2 бара (H1) после спайка для стабилизации
  - Если цена пробила и закрепилась выше/ниже уровня начала спайка — входим

Вход:
  BUY:  Был ATR-спайк 1-2 бара назад + Close > max за спайк (закрепление)
  SELL: Был ATR-спайк 1-2 бара назад + Close < min за спайк (закрепление)

Выход:
  - SL = 1.5 * ATR, TP = 3.0 * ATR (широкий TP, т.к. движение сильное)
  - Или цена вернулась к уровню начала спайка
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class NewsBreakoutStrategy(BaseStrategy):
    name = "news_breakout"
    description = "Post-News Breakout H1 — пробой после волатильного бара"
    default_timeframe = "H1"

    def __init__(self, atr_period=14, atr_avg_period=50,
                 spike_mult=2.0, wait_bars=2,
                 sl_atr_mult=1.5, tp_atr_mult=3.0):
        self.atr_period    = atr_period
        self.atr_avg_period = atr_avg_period
        self.spike_mult    = spike_mult    # ATR > spike_mult * avg → новостной бар
        self.wait_bars     = wait_bars     # сколько баров ждём после спайка
        self.sl_atr_mult   = sl_atr_mult
        self.tp_atr_mult   = tp_atr_mult

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['atr']     = talib.ATR(high, low, close, timeperiod=self.atr_period)
        df['atr_avg'] = df['atr'].rolling(self.atr_avg_period).mean()

        # Отмечаем "новостные" бары — ATR-спайк
        df['spike'] = df['atr'] > self.spike_mult * df['atr_avg']

        # Уровень начала спайка (цена до спайка) и его High/Low
        for lag in range(1, self.wait_bars + 1):
            df[f'spike_lag{lag}'] = df['spike'].shift(lag)
            df[f'spike_high{lag}'] = df['high'].shift(lag)
            df[f'spike_low{lag}']  = df['low'].shift(lag)

        # Максимум/минимум за период спайка (1..wait_bars баров назад)
        spike_highs = pd.concat(
            [df[f'spike_high{lag}'] for lag in range(1, self.wait_bars + 1)], axis=1
        )
        spike_lows = pd.concat(
            [df[f'spike_low{lag}'] for lag in range(1, self.wait_bars + 1)], axis=1
        )
        df['spike_range_high'] = spike_highs.max(axis=1)
        df['spike_range_low']  = spike_lows.min(axis=1)

        # Был ли спайк за последние wait_bars баров
        spike_flags = pd.concat(
            [df[f'spike_lag{lag}'] for lag in range(1, self.wait_bars + 1)], axis=1
        )
        df['recent_spike'] = spike_flags.any(axis=1)

        return df

    def get_entry_signal(self, row):
        required = ['atr', 'atr_avg', 'recent_spike', 'spike_range_high', 'spike_range_low']
        if any(pd.isna(row[c]) for c in required):
            return None

        if not row['recent_spike']:
            return None

        # Не торгуем в момент самого спайка
        spike_val = row.get('spike', False)
        if pd.isna(spike_val):
            spike_val = False
        if spike_val:
            return None

        price = row['close']
        if price > row['spike_range_high']:
            return 'BUY'
        if price < row['spike_range_low']:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        # Используем уровни спайка, зафиксированные на момент входа,
        # а не текущие смещённые значения (они меняются каждый бар)
        entry_inds = position.get('indicators', {})
        spike_high = entry_inds.get('spike_range_high')
        spike_low  = entry_inds.get('spike_range_low')
        if spike_high is None or spike_low is None:
            return False
        # Выходим если цена вернулась обратно внутрь диапазона спайка
        if position['type'] == 'BUY' and row['close'] < spike_high:
            return True
        if position['type'] == 'SELL' and row['close'] > spike_low:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr   = row['atr']
        price = row['close']
        if signal == 'BUY':
            sl = price - self.sl_atr_mult * atr
            tp = price + self.tp_atr_mult * atr
        else:
            sl = price + self.sl_atr_mult * atr
            tp = price - self.tp_atr_mult * atr
        return sl, tp

    def indicator_columns(self):
        return ['atr', 'atr_avg', 'spike_range_high', 'spike_range_low']
