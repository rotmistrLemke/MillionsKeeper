import MetaTrader5 as mt5
import pandas as pd
import time


class MarketDataCache:
    """
    Кэш рыночных данных MT5.
    Загружает данные один раз за итерацию цикла и предоставляет их всем индикаторам.
    Снижает количество API-вызовов с ~154 до ~22 за итерацию (по 1 на символ).
    """

    def __init__(self, bars=500):
        self._cache = {}
        self._symbol_info_cache = {}
        self._positions_cache = None
        self._positions_cache_time = 0
        self._account_info_cache = None
        self._account_info_cache_time = 0
        self._bars = bars
        self._cache_time = 0
        self._cache_ttl = 5  # секунд - время жизни кэша

    def invalidate(self):
        """Сбрасывает весь кэш. Вызывать в начале каждой итерации цикла."""
        self._cache.clear()
        self._symbol_info_cache.clear()
        self._positions_cache = None
        self._account_info_cache = None
        self._cache_time = time.time()

    def get_rates(self, symbol, timeframe, bars=None):
        """
        Получает данные баров из кэша или MT5 API.
        Ключ кэша: (symbol, timeframe, bars).
        """
        if bars is None:
            bars = self._bars
        key = (symbol, timeframe, bars)
        if key in self._cache:
            return self._cache[key]

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None:
            print(f"Не удалось получить данные для {symbol}: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        self._cache[key] = df
        return df

    def get_symbol_info(self, symbol):
        """Кэширует symbol_info на время итерации."""
        if symbol in self._symbol_info_cache:
            return self._symbol_info_cache[symbol]

        info = mt5.symbol_info(symbol)
        if info is not None:
            self._symbol_info_cache[symbol] = info
        return info

    def get_positions(self):
        """Кэширует список позиций на время итерации."""
        now = time.time()
        if self._positions_cache is not None and (now - self._positions_cache_time) < self._cache_ttl:
            return self._positions_cache

        positions = mt5.positions_get()
        if positions is None:
            print(f"Ошибка получения позиций: {mt5.last_error()}")
            positions = ()
        self._positions_cache = positions
        self._positions_cache_time = now
        return positions

    def get_account_info(self):
        """Кэширует информацию о счёте на время итерации."""
        now = time.time()
        if self._account_info_cache is not None and (now - self._account_info_cache_time) < self._cache_ttl:
            return self._account_info_cache

        info = mt5.account_info()
        self._account_info_cache = info
        self._account_info_cache_time = now
        return info


# Глобальный экземпляр кэша
cache = MarketDataCache()
