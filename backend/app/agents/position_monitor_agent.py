"""
agents/position_monitor_agent.py — Мониторинг позиций, RSI-выход.

Изменения vs v1:
  - Нет прямых mt5.* / Dictionary (через TradingService)
  - RSI вычисляется через TA-Lib напрямую, без старого indicators.py
"""
from __future__ import annotations

import asyncio

import MetaTrader5 as mt5
import pandas as pd
import talib

from app.agents.base_agent import BaseAgent, AgentStatus
from app.core.config import settings
from app.trading.service import TradingService
from core.event_bus import EventBus
from core.events import EventType


class PositionMonitorAgent(BaseAgent):
    description = "Мониторинг открытых позиций, RSI-выход"

    RSI_EXIT_BUY  = 45.0   # закрыть BUY если RSI < 45
    RSI_EXIT_SELL = 55.0   # закрыть SELL если RSI > 55

    def __init__(self, name: str, bus: EventBus, trading: TradingService, poll_interval: float = None):
        super().__init__(name, bus)
        self._trading = trading
        self.poll_interval = poll_interval or settings.poll_interval_position
        self.metrics["open_positions"] = 0

    async def run(self):
        await self.emit_status(AgentStatus.RUNNING, "Проверка позиций")

        positions = await self._trading.get_positions()
        self.metrics["open_positions"] = len(positions)

        pos_list = [
            {
                "ticket":     p.ticket,
                "symbol":     p.symbol,
                "type":       p.order_type,
                "volume":     p.volume,
                "open_price": p.open_price,
                "sl":         p.sl,
                "pnl_money":  round(p.profit, 2),
                "open_time":  p.open_time,
            }
            for p in positions
        ]
        await self.emit(EventType.POSITION_UPDATE, {"positions": pos_list})

        for pos in pos_list:
            await self._check_rsi_exit(pos)

        await self.emit_status(AgentStatus.IDLE, f"Позиций: {len(positions)}")
        await asyncio.sleep(self.poll_interval)

    async def _check_rsi_exit(self, pos: dict):
        symbol = pos["symbol"]
        if self._trading.get_status(symbol) == 3:
            return

        rsi_val = await asyncio.get_event_loop().run_in_executor(
            None, self._get_rsi, symbol
        )
        if rsi_val is None:
            return

        should_close = (
            (pos["type"] == "BUY"  and rsi_val < self.RSI_EXIT_BUY) or
            (pos["type"] == "SELL" and rsi_val > self.RSI_EXIT_SELL)
        )

        if should_close:
            await self.emit(EventType.RSI_EXIT_TRIGGERED, {
                "symbol": symbol, "ticket": pos["ticket"],
                "rsi_value": rsi_val, "position_type": pos["type"],
            })
            await self.emit(EventType.ORDER_CLOSE_REQUEST, {
                "ticket": pos["ticket"], "symbol": symbol,
                "reason": f"RSI={rsi_val:.1f}",
            })

    @staticmethod
    def _get_rsi(symbol: str, period: int = 14, bars: int = 50) -> float | None:
        rates = mt5.copy_rates_from_pos(symbol, settings.trend_timeframe, 0, bars)
        if rates is None or len(rates) < period + 1:
            return None
        close = pd.Series([r["close"] for r in rates]).astype(float).values
        rsi = talib.RSI(close, timeperiod=period)
        val = rsi[-1]
        return float(val) if not pd.isna(val) else None
