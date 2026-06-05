"""
Базовый класс для скальпинг-стратегий.
Каждая стратегия реализует:
  - compute_indicators(df) — добавляет колонки индикаторов
  - get_entry_signal(row) — возвращает 'BUY', 'SELL' или None
  - get_exit_signal(row, position) — возвращает True если нужно закрыть
  - get_sl_tp(row, signal, point) — возвращает (stop_loss_price, take_profit_price)

Встроенный фильтр флэта:
  - ADX < 20 → флэт (нет тренда)
  - Bollinger Band Width < среднего → сжатие (консолидация)
  - ATR < среднего → низкая волатильность
  Флэт = 2 из 3 условий. Во время флэта вход запрещён.
"""

from abc import ABC, abstractmethod
import pandas as pd
import talib


class BaseStrategy(ABC):
    name: str = "base"
    description: str = ""
    default_timeframe: str = "H1"

    # Параметры детекции флэта
    flat_adx_period: int = 14
    flat_adx_threshold: float = 20.0
    flat_bb_period: int = 20
    flat_bb_std: float = 2.0
    flat_bb_avg_period: int = 50
    flat_atr_period: int = 14
    flat_atr_avg_period: int = 50

    def compute_flat_indicators(self, df):
        """Вычисляет индикаторы для детекции флэта. Вызывается после compute_indicators."""
        close = df['close'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)

        # ADX
        if 'flat_adx' not in df.columns:
            df['flat_adx'] = talib.ADX(high, low, close, timeperiod=self.flat_adx_period)

        # Bollinger Band Width = (upper - lower) / middle
        upper, middle, lower = talib.BBANDS(close, timeperiod=self.flat_bb_period,
                                             nbdevup=self.flat_bb_std, nbdevdn=self.flat_bb_std)
        bb_width = pd.Series((upper - lower) / middle, index=df.index)
        df['flat_bb_width'] = bb_width
        df['flat_bb_width_avg'] = bb_width.rolling(self.flat_bb_avg_period).mean()

        # ATR vs средний ATR
        if 'flat_atr' not in df.columns:
            df['flat_atr'] = talib.ATR(high, low, close, timeperiod=self.flat_atr_period)
        df['flat_atr_avg'] = df['flat_atr'].rolling(self.flat_atr_avg_period).mean()

        return df

    def is_flat(self, row) -> bool:
        """Определяет, находится ли рынок во флэте. True = не торгуем."""
        required = ['flat_adx', 'flat_bb_width', 'flat_bb_width_avg', 'flat_atr', 'flat_atr_avg']
        if any(c not in row.index or pd.isna(row[c]) for c in required):
            return True  # нет данных — считаем флэтом, не торгуем

        signals = 0

        # 1. ADX < порога — нет тренда
        if row['flat_adx'] < self.flat_adx_threshold:
            signals += 1

        # 2. BB сжаты — ширина ниже средней
        if row['flat_bb_width'] < row['flat_bb_width_avg']:
            signals += 1

        # 3. ATR ниже среднего — волатильность упала
        if row['flat_atr'] < row['flat_atr_avg']:
            signals += 1

        return signals >= 2

    @abstractmethod
    def compute_indicators(self, df):
        """Добавляет индикаторы в DataFrame. Возвращает df."""
        pass

    @abstractmethod
    def get_entry_signal(self, row):
        """Возвращает 'BUY', 'SELL' или None."""
        pass

    @abstractmethod
    def get_exit_signal(self, row, position: dict) -> bool:
        """True если позицию нужно закрыть по сигналу (без SL/TP)."""
        pass

    @abstractmethod
    def get_sl_tp(self, row, signal: str, point: float):
        """Возвращает (sl_price, tp_price)."""
        pass

    def wants_hedge(self) -> bool:
        """Если True — движок открывает парную противоположную (хедж) позицию
        одновременно с основной."""
        return False

    def closes_on_weekend(self) -> bool:
        """Если True — бэктест принудительно закрывает позицию перед выходными
        (пт ≥23:00, сб/вс, пн <02:00) с причиной WEEKEND.
        Стратегии с редкими сильными сигналами (напр. EMA 8/200) могут вернуть
        False и удерживать позицию через выходные."""
        return True

    def uses_trailing_exit(self) -> bool:
        """Если True — выход полностью контролируется `get_exit_signal`
        (например, трейл по EMA). Движок не должен подменять TP на
        фиксированный ATR-уровень из пользовательской формы, иначе
        позиция закроется по цели до того, как трейлинг успеет развиться.
        SL — по-прежнему применяется, он защищает от провала."""
        return False

    def get_hedge_exit_signal(self, row, hedge_position: dict) -> bool:
        """True если нужно закрыть только хедж (основная продолжает работать)."""
        return False

    def on_trade_closed(self, position: dict, reason: str) -> None:
        """Хук — вызывается движком после закрытия позиции.
        reason: 'SL' | 'TP' | 'SIGNAL' | 'WEEKEND' | 'END_OF_DATA'.
        По умолчанию — no-op. Стратегии могут использовать для внутреннего состояния
        (например, блокировка входа в определённую сторону).
        """
        pass

    def indicator_columns(self) -> list:
        """Список колонок индикаторов для сохранения в результатах."""
        return []

    def flat_indicator_columns(self) -> list:
        """Колонки флэт-детектора для результатов."""
        return ['flat_adx', 'flat_bb_width', 'flat_atr']
