import asyncio
import time

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType


class MarketDataAgent(BaseAgent):
    """
    Опрашивает MT5 через кэш, инвалидирует кэш и определяет момент новой свечи.
    Публикует NEW_BAR для каждого символа, по которому открылась новая H1-свеча.
    """
    description = "Кэш MT5 данных, определение новых свечей"

    def __init__(self, name: str, bus: EventBus, symbols: list, timeframe, poll_interval: float = 10.0):
        super().__init__(name, bus)
        self._initial_symbols = list(symbols)
        self.poll_interval = poll_interval
        self._last_bar_times: dict = {}
        self._last_seen_tf = None
        self._last_seen_symbols: tuple = ()
        self.metrics["poll_interval_sec"] = poll_interval

    @property
    def symbols(self):
        """Динамический список: все символы с trading_status != 3."""
        from settings import Dictionary
        syms = [s for s, v in Dictionary.symbolTradingStatus.items() if v != 3]
        current = tuple(sorted(syms))
        if self._last_seen_symbols and current != self._last_seen_symbols:
            # Состав символов сменился — обнуляем «последние свечи» по удалённым,
            # иначе при возврате символа первая новая свеча не детектируется.
            removed = set(self._last_seen_symbols) - set(current)
            for r in removed:
                self._last_bar_times.pop(r, None)
        self._last_seen_symbols = current
        self.metrics["symbols"] = len(syms)
        return syms

    @property
    def timeframe(self):
        from settings import GlobalValues
        tf = GlobalValues.time_frame
        if self._last_seen_tf is not None and tf != self._last_seen_tf:
            # TF сменился — сбросим кэш «последних свечей», чтобы корректно
            # определить первую новую свечу на новом TF
            self._last_bar_times.clear()
        self._last_seen_tf = tf
        return tf

    async def run(self):
        from market_data_cache import cache
        import MetaTrader5 as mt5

        await self.emit_status(AgentStatus.RUNNING, "Инвалидация кэша")

        # Инвалидируем кэш в начале каждой итерации
        cache.invalidate()
        await self.emit(EventType.MARKET_CACHE_INVALIDATED, {"symbols": len(self.symbols)})

        # Проверяем соединение MT5
        if not mt5.terminal_info():
            await self.emit(EventType.MT5_DISCONNECTED, {})
            await self.emit_status(AgentStatus.ERROR, "MT5 не подключён")
            await asyncio.sleep(self.poll_interval)
            return

        await self.emit(EventType.MT5_CONNECTED, {})

        # Определяем новые свечи по каждому символу
        new_bar_symbols = []
        for symbol in self.symbols:
            try:
                rates = cache.get_rates(symbol, self.timeframe, bars=2)
                if rates is None or len(rates) == 0:
                    continue
                raw_time = rates.iloc[-1]['time']
                # cache.get_rates возвращает DataFrame где time уже pd.Timestamp
                import pandas as pd
                if isinstance(raw_time, pd.Timestamp):
                    last_time = int(raw_time.timestamp())
                else:
                    last_time = int(raw_time)

                prev = self._last_bar_times.get(symbol)
                if prev is None or last_time > prev:
                    self._last_bar_times[symbol] = last_time
                    if prev is not None:  # первый запуск — не считаем новой свечой
                        new_bar_symbols.append(symbol)
                        await self.emit(EventType.NEW_BAR, {
                            "symbol": symbol,
                            "bar_time": last_time,
                            "timeframe": str(self.timeframe),
                        })
            except Exception as e:
                self._logger.warning(f"NEW_BAR check failed for {symbol}: {e}")

        self.metrics["new_bars"] = len(new_bar_symbols)
        self.metrics["last_poll"] = time.strftime("%H:%M:%S")

        await self.emit_status(AgentStatus.IDLE, f"Новых свечей: {len(new_bar_symbols)}")
        await asyncio.sleep(self.poll_interval)
