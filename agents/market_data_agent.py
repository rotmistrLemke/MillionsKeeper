import asyncio
import time

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType
from trading_status import status


class MarketDataAgent(BaseAgent):
    """
    Опрашивает MT5 через кэш, инвалидирует кэш и определяет момент новой свечи.
    Список (symbol, timeframe) строится из активных потоков (streams.registry.enabled()).
    Публикует NEW_BAR для каждой пары, по которой открылась новая свеча.
    """
    description = "Кэш MT5 данных, детект новой свечи по всем потокам"

    def __init__(self, name: str, bus: EventBus, symbols=None, timeframe=None, poll_interval: float = 10.0):
        super().__init__(name, bus)
        self.poll_interval = poll_interval
        # Ключ: (symbol, timeframe_int) → последний bar_time (int).
        self._last_bar_times: dict[tuple[str, int], int] = {}
        self._last_seen_pairs: set[tuple[str, int]] = set()
        self.metrics["poll_interval_sec"] = poll_interval

    def _current_pairs(self) -> set[tuple[str, int]]:
        """Уникальные (symbol, tf) по enabled-потокам — с учётом статуса торговли (не DISABLED)."""
        import streams as streams_mod
        pairs: set[tuple[str, int]] = set()
        for s in streams_mod.registry.enabled():
            if status.is_disabled(s.symbol):
                continue
            pairs.add((s.symbol, int(s.timeframe)))
        return pairs

    async def run(self):
        from market_data_cache import cache
        import MetaTrader5 as mt5
        import pandas as pd

        await self.emit_status(AgentStatus.RUNNING, "Инвалидация кэша")
        cache.invalidate()

        pairs = self._current_pairs()
        # Если состав пар изменился — сбросить «последние свечи» по удалённым.
        removed = self._last_seen_pairs - pairs
        for r in removed:
            self._last_bar_times.pop(r, None)
        self._last_seen_pairs = pairs
        self.metrics["symbols"] = len({p[0] for p in pairs})
        self.metrics["pairs"]   = len(pairs)

        await self.emit(EventType.MARKET_CACHE_INVALIDATED, {"pairs": len(pairs)})

        if not mt5.terminal_info():
            await self.emit(EventType.MT5_DISCONNECTED, {})
            await self.emit_status(AgentStatus.ERROR, "MT5 не подключён")
            await asyncio.sleep(self.poll_interval)
            return

        await self.emit(EventType.MT5_CONNECTED, {})

        new_bars = 0
        for symbol, tf in pairs:
            try:
                rates = cache.get_rates(symbol, tf, bars=2)
                if rates is None or len(rates) == 0:
                    continue
                raw_time = rates.iloc[-1]['time']
                if isinstance(raw_time, pd.Timestamp):
                    last_time = int(raw_time.timestamp())
                else:
                    last_time = int(raw_time)

                key = (symbol, tf)
                prev = self._last_bar_times.get(key)
                if prev is None or last_time > prev:
                    self._last_bar_times[key] = last_time
                    if prev is not None:  # первый запуск — не считаем новой свечой
                        new_bars += 1
                        await self.emit(EventType.NEW_BAR, {
                            "symbol": symbol,
                            "bar_time": last_time,
                            "timeframe": int(tf),
                        })
            except Exception as e:
                self._logger.warning(f"NEW_BAR check failed for {symbol}/{tf}: {e}")

        self.metrics["new_bars"] = new_bars
        self.metrics["last_poll"] = time.strftime("%H:%M:%S")

        await self.emit_status(AgentStatus.IDLE, f"Новых свечей: {new_bars}")
        await asyncio.sleep(self.poll_interval)
