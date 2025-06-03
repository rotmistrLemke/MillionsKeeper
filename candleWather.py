import MetaTrader5 as mt5
from datetime import datetime
import time

class CandleWatcher:
    def __init__(self, symbol, timeFrame):
        """
        Инициализация наблюдателя за свечами
        :param symbol: Торговый символ (например "EURUSD")
        :param timeFrame: Таймфрейм из MT5 (например mt5.TIMEFRAME_H1)
        """
        self.symbol = symbol
        self.timeFrame = timeFrame
        self.currentCandleTime = None  # Время текущей свечи
        self.lastCheckedTime = None    # Время последней проверки
        
        if not mt5.initialize():
            raise ConnectionError("Ошибка подключения к MetaTrader 5")
        
        # Первичная инициализация времени свечи
        self._updateCandleTime()

    def _updateCandleTime(self):
        """Обновляет время текущей свечи"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeFrame, 0, 1)
        if rates is None or len(rates) == 0:
            raise ValueError(f"Не удалось получить данные для {self.symbol}")
        self.currentCandleTime = rates[0]['time']

    def isNewCandleOpened(self):
        """
        Проверяет, открылась ли новая свеча с момента последней проверки
        :return: True если появилась новая свеча, False если свеча та же
        """
        previousTime = self.currentCandleTime
        self._updateCandleTime()
        
        # Фиксируем момент обнаружения новой свечи
        if self.currentCandleTime != previousTime:
            self.lastCheckedTime = self.currentCandleTime
            return True
        return False

    def getCandleOpenTime(self):
        """
        Возвращает время открытия текущей свечи
        :return: datetime объекта времени открытия свечи
        """
        return datetime.fromtimestamp(self.currentCandleTime) if self.currentCandleTime else None