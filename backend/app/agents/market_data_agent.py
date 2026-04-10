"""
agents/market_data_agent.py — Опрос MT5, инвалидация кэша, определение новых свечей.

Изменения vs v1:
  - Поддержка двух таймфреймов: M1 (скальп) + H1 (тренд)
  - Пишет данные в Redis кэш (через cache-абстракцию)
  - Нет прямого импорта settings (таймфреймы через __init__)
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd

from app.agents.base_agent import BaseAgent, AgentStatus
from app.core.config import settings
from core.event_bus import EventBus
from core.events import EventType


class MarketDataAgent(BaseAgent):
    description = "Кэш MT5 данных, определение новых свечей M1+H1"

    def __init__(
        self,
        name: str,
        bus: EventBus,
        symbols: list[str],
        scalp_timeframe: int = None,
        trend_timeframe: int = None,
        poll_interval: float = None,
    ):
        super().__init__(name, bus)
        self.symbols = symbols
        self.scalp_tf = scalp_timeframe or settings.scalp_timeframe
        self.trend_tf = trend_timeframe or settings.trend_timeframe
        self.poll_interval = poll_interval or settings.poll_interval_market
        self._last_bar_times: dict[str, dict[int, int]] = {}  # symbol → {tf → unix_ts}
        self.metrics.update({"symbols": len(symbols), "poll_interval_sec": self.poll_interval})

    async def run(self):
        await self.emit_status(AgentStatus.RUNNING, "Опрос MT5")

        if not mt5.terminal_info():
            await self.emit(EventType.MT5_DISCONNECTED, {})
            await self.emit_status(AgentStatus.ERROR, "MT5 не подключён")
            await asyncio.sleep(self.poll_interval)
            return

        await self.emit(EventType.MT5_CONNECTED, {})

        new_bars_count = 0
        for symbol in self.symbols:
            for tf, tf_name in ((self.scalp_tf, "M1"), (self.trend_tf, "H1")):
                try:
                    last_time = await self._get_last_bar_time(symbol, tf)
                    if last_time is None:
                        continue

                    prev = self._last_bar_times.get(symbol, {}).get(tf)
                    if prev is not None and last_time > prev:
                        new_bars_count += 1
                        await self.emit(EventType.NEW_BAR, {
                            "symbol": symbol,
                            "bar_time": last_time,
                            "timeframe": tf_name,
                            "tf_id": tf,
                        })

                    self._last_bar_times.setdefault(symbol, {})[tf] = last_time
                except Exception as e:
                    self._logger.warning(f"NEW_BAR {symbol}/{tf_name}: {e}")

        self.metrics.update({"new_bars": new_bars_count, "last_poll": time.strftime("%H:%M:%S")})
        await self.emit_status(AgentStatus.IDLE, f"Новых свечей: {new_bars_count}")
        await asyncio.sleep(self.poll_interval)

    async def _get_last_bar_time(self, symbol: str, timeframe: int) -> Optional[int]:
        rates = await asyncio.get_event_loop().run_in_executor(
            None, lambda: mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)
        )
        if rates is None or len(rates) == 0:
            return None
        return int(rates[-1]["time"])
