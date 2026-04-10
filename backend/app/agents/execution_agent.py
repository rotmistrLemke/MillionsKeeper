"""
agents/execution_agent.py — Исполнение ордеров через TradingService.

Изменения vs v1:
  - Нет прямых mt5.* вызовов и Dictionary (всё через TradingService)
  - DI: TradingService передаётся в __init__
  - Объём и SL/TP рассчитываются в TradingService.open()
"""
from __future__ import annotations

import asyncio

from app.agents.base_agent import BaseAgent, AgentStatus
from app.trading.service import TradingService
from core.event_bus import EventBus
from core.events import Event, EventType


class ExecutionAgent(BaseAgent):
    description = "Открытие и закрытие ордеров через TradingService"

    def __init__(self, name: str, bus: EventBus, trading: TradingService):
        super().__init__(name, bus)
        self._trading = trading
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics.update({"opened_today": 0, "closed_today": 0})
        bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal)
        bus.subscribe(EventType.ORDER_CLOSE_REQUEST, self._on_close)

    async def _on_signal(self, event: Event):
        await self._queue.put(("signal", event))

    async def _on_close(self, event: Event):
        await self._queue.put(("close", event))

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание сигналов")
        kind, event = await self._queue.get()

        if kind == "signal":
            await self._handle_signal(event)
        elif kind == "close":
            await self._handle_close(event)

    async def _handle_signal(self, event: Event):
        p = event.payload
        symbol: str = p["symbol"]
        signal: str = p["signal"]

        if signal == "NO_SIGNAL":
            return
        if self._trading.get_status(symbol) != 0:
            return

        await self.emit_status(AgentStatus.RUNNING, f"Открытие {signal} {symbol}")

        balance = await self._trading.get_account_balance()
        atr     = p.get("indicators", {}).get("atr_value", 0) or 0

        result = await self._trading.open(
            symbol=symbol,
            signal=signal,
            atr=float(atr),
            balance=balance,
            comment=f"mk_{p.get('strategy', 'default')}",
        )

        if result and result.success:
            self.metrics["opened_today"] = self.metrics.get("opened_today", 0) + 1
            await self.emit(EventType.ORDER_OPENED, {
                "symbol": symbol,
                "type": signal,
                "volume": None,
                "price": result.price,
                "ticket": result.ticket,
                "indicators": p.get("indicators", {}),
            })
            await self.emit(EventType.TRADING_STATUS_CHANGED, {
                "symbol": symbol, "status": 1, "reason": "order_opened",
            })

    async def _handle_close(self, event: Event):
        p = event.payload
        ticket: int = p.get("ticket")
        symbol: str = p.get("symbol", "")

        if not ticket:
            return

        await self.emit_status(AgentStatus.RUNNING, f"Закрытие {symbol} #{ticket}")
        ok = await self._trading.close(ticket, symbol)

        if ok:
            self.metrics["closed_today"] = self.metrics.get("closed_today", 0) + 1
            await self.emit(EventType.ORDER_CLOSED, {
                "ticket": ticket, "symbol": symbol, "reason": p.get("reason", "manual"),
            })
        else:
            await self.emit(EventType.ORDER_ERROR, {"ticket": ticket, "symbol": symbol, "error": "close failed"})
