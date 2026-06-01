"""
Стратегия: EMA Triple Touch — пересечение 20/50 EMA с фильтром 200 EMA.

Суть: в глобальном тренде (по 200 EMA) ждём пересечения 20/50 EMA.
Это формирует «динамическую поддержку/сопротивление». После двух
подтверждающих тестов зоны входим на третьем или любом последующем.

Правила:
  Таймфрейм: H4 или D1 (по умолчанию H4).
  Глобальный тренд:
    BUY: цена > EMA200
    SELL: цена < EMA200
  Пересечение 20/50:
    BUY: EMA20 пересекает EMA50 снизу вверх → счётчик тестов = 0,
         направление = UP
    SELL: зеркально
  Тест зоны [EMA20..EMA50] = касание + закрытие свечи ВНУТРИ зоны.
  Вход: когда count_touches ≥ 3 И контекст не нарушен.
  Сброс:
    - обратное пересечение 20/50
    - закрытие цены на «неправильной» стороне 200 EMA
  SL: `sl_atr_mult` × ATR от цены входа.
  Выход: закрытие свечи ниже EMA50 (для BUY) / выше EMA50 (для SELL).

State (per symbol через runtime cache):
  _cross_side: 'UP' | 'DOWN' | None
  _touch_count: int
  _counted_dip: bool  — тест засчитан за текущий «провал» в зону; сбрасывается,
                        когда цена закрывается ВНЕ зоны (соседние бары внутри
                        зоны не считаются отдельными тестами)
"""

import pandas as pd
import talib
from strategies.base import BaseStrategy


class EmaTripleTouchStrategy(BaseStrategy):
    name = "ema_triple_touch"
    description = "EMA 20/50 Cross + 200 EMA фильтр — вход на 3-м тесте зоны"
    default_timeframe = "H4"

    def __init__(self, fast=20, mid=50, slow=200, atr_period=14,
                 sl_atr_mult=2.0, min_tests: int = 3):
        self.fast = fast
        self.mid = mid
        self.slow = slow
        self.atr_period = atr_period
        self.sl_atr_mult = float(sl_atr_mult or 0.0)
        self.min_tests = int(min_tests)
        # Состояние
        self._cross_side = None        # 'UP' | 'DOWN'
        self._touch_count = 0
        self._counted_dip = False      # тест засчитан за текущий заход в зону

    def compute_indicators(self, df):
        close = df['close'].values.astype(float)
        high  = df['high'].values.astype(float)
        low   = df['low'].values.astype(float)

        df['ema20']  = talib.EMA(close, timeperiod=self.fast)
        df['ema50']  = talib.EMA(close, timeperiod=self.mid)
        df['ema200'] = talib.EMA(close, timeperiod=self.slow)
        df['atr']    = talib.ATR(high, low, close, timeperiod=self.atr_period)

        diff = df['ema20'] - df['ema50']
        prev = diff.shift(1)
        df['cross20_50_up']   = (prev <= 0) & (diff > 0)
        df['cross20_50_down'] = (prev >= 0) & (diff < 0)

        df['zone_hi'] = df[['ema20', 'ema50']].max(axis=1)
        df['zone_lo'] = df[['ema20', 'ema50']].min(axis=1)
        return df

    def is_flat(self, row) -> bool:
        return False

    def closes_on_weekend(self) -> bool:
        return False

    def _update_state(self, row):
        """Обновляет внутреннее состояние на основе свежего бара."""
        ema200 = row.get('ema200')
        if ema200 is None or pd.isna(ema200):
            return

        # Пересечение 20/50 — сброс счётчика и установка стороны.
        if bool(row.get('cross20_50_up')):
            self._cross_side = 'UP'
            self._touch_count = 0
            self._counted_dip = False
        elif bool(row.get('cross20_50_down')):
            self._cross_side = 'DOWN'
            self._touch_count = 0
            self._counted_dip = False

        # Сброс если тренд сломан 200 EMA.
        if self._cross_side == 'UP' and row['close'] < ema200:
            self._cross_side = None
            self._touch_count = 0
        elif self._cross_side == 'DOWN' and row['close'] > ema200:
            self._cross_side = None
            self._touch_count = 0

        # Подсчёт теста: касание зоны + закрытие внутри.
        zh = row.get('zone_hi'); zl = row.get('zone_lo')
        if self._cross_side is None or zh is None or zl is None or pd.isna(zh) or pd.isna(zl):
            return
        touched = row['low'] <= zh and row['high'] >= zl
        closed_inside = zl <= row['close'] <= zh
        if touched and closed_inside:
            # Засчитываем тест один раз за «провал»: пока цена остаётся
            # внутри зоны, соседние бары не считаются отдельными тестами.
            if not self._counted_dip:
                self._touch_count += 1
                self._counted_dip = True
        else:
            # Цена закрылась вне зоны — провал завершён; следующий заход
            # в зону засчитается как новый тест.
            self._counted_dip = False

    def get_entry_signal(self, row):
        required = ('ema20', 'ema50', 'ema200', 'atr')
        if any(row.get(c) is None or pd.isna(row.get(c)) for c in required):
            return None

        self._update_state(row)

        if self._cross_side is None or self._touch_count < self.min_tests:
            return None
        # На этом же баре вход: должен быть «свежий» тест, т.е. закрытие внутри зоны
        zh = row['zone_hi']; zl = row['zone_lo']
        if not (zl <= row['close'] <= zh):
            return None

        ema200 = row['ema200']
        if self._cross_side == 'UP' and row['close'] > ema200:
            return 'BUY'
        if self._cross_side == 'DOWN' and row['close'] < ema200:
            return 'SELL'
        return None

    def get_exit_signal(self, row, position: dict) -> bool:
        """Закрытие свечи по другую сторону EMA50 → выход."""
        ema50 = row.get('ema50')
        if ema50 is None or pd.isna(ema50):
            return False
        if position['type'] == 'BUY' and row['close'] < ema50:
            return True
        if position['type'] == 'SELL' and row['close'] > ema50:
            return True
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        atr = row.get('atr')
        price = row['close']
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = 100 * point
        sl = None
        if self.sl_atr_mult > 0:
            sl = (price - self.sl_atr_mult * atr) if signal == 'BUY' \
                 else (price + self.sl_atr_mult * atr)
        return sl, None

    def uses_trailing_exit(self) -> bool:
        return True

    def on_trade_closed(self, position: dict, reason: str) -> None:
        # После выхода по EMA50 зона уже «обслужена» — ждём нового пересечения,
        # прежде чем снова накапливать тесты.
        if reason in ('SIGNAL', 'SL', 'TP'):
            self._cross_side = None
            self._touch_count = 0
            self._counted_dip = False

    def indicator_columns(self):
        return ['ema20', 'ema50', 'ema200', 'atr']
