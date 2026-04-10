"""
agents/signal_agent.py — Формирование торгового сигнала.

Изменения vs v1:
  - Поддержка мультистратегийного режима (active_strategy из БД)
  - Нет прямого импорта Dictionary (статус торговли через TradingService)
  - Flat-detection делегирована стратегии
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.agents.base_agent import BaseAgent, AgentStatus
from app.strategies.registry import StrategyRegistry
from app.trading.service import TradingService
from core.event_bus import EventBus
from core.events import Event, EventType


class SignalAgent(BaseAgent):
    description = "Формирование торгового сигнала через активную стратегию"

    def __init__(
        self,
        name: str,
        bus: EventBus,
        trading_service: TradingService,
        active_strategy: str = "alligator",
    ):
        super().__init__(name, bus)
        self._trading = trading_service
        self._active_strategy = active_strategy
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics.update({"buy_signals": 0, "sell_signals": 0, "strategy": active_strategy})
        bus.subscribe(EventType.INDICATORS_READY, self._on_indicators)

    async def _on_indicators(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание индикаторов")
        event = await self._queue.get()
        p = event.payload
        symbol: str = p["symbol"]

        # Базовый сигнал из индикаторов (MA+MACD+RSI)
        signal = self._combine_indicator_signals(p)

        # Дополнительная проверка через активную стратегию (если есть данные)
        strategy = StrategyRegistry.get(self._active_strategy)
        if strategy and hasattr(strategy, "get_entry_signal"):
            # Если стратегия умеет работать с dict (row-like)
            strategy_signal = self._try_strategy_signal(strategy, p)
            if strategy_signal is not None:
                signal = strategy_signal

        if signal in ("BUY", "SELL"):
            self.metrics[f"{signal.lower()}_signals"] = self.metrics.get(f"{signal.lower()}_signals", 0) + 1

        await self.emit_status(AgentStatus.RUNNING, f"{symbol} → {signal or 'NO_SIGNAL'}")
        await self.emit(EventType.SIGNAL_GENERATED, {
            "symbol": symbol,
            "signal": signal or "NO_SIGNAL",
            "strategy": self._active_strategy,
            "trading_status": self._trading.get_status(symbol),
            "indicators": {
                "ma":        p.get("signal_ma"),
                "ma_angle":  p.get("signal_critical_angle"),
                "macd":      p.get("macd_signal"),
                "rsi":       p.get("rsi_signal"),
                "rsi_value": p.get("rsi_value"),
                "atr_value": p.get("atr_value"),
                "adx_value": p.get("adx_value"),
                "ema8":      p.get("ema8"),
                "ema21":     p.get("ema21"),
            },
        }, correlation_id=event.correlation_id)

    @staticmethod
    def _combine_indicator_signals(p: dict) -> Optional[str]:
        ma   = p.get("signal_ma", "NO_SIGNAL")
        ang  = p.get("signal_critical_angle", "NO_SIGNAL")
        macd = p.get("macd_signal", "NO_SIGNAL")
        rsi  = p.get("rsi_signal", "NO_SIGNAL")

        if ma == "BUY"  and ang == "BUY"  and macd == "BUY"  and rsi == "BUY":
            return "BUY"
        if ma == "SELL" and ang == "SELL" and macd == "SELL" and rsi == "SELL":
            return "SELL"
        return None

    @staticmethod
    def _try_strategy_signal(strategy, payload: dict) -> Optional[str]:
        try:
            import pandas as pd
            row = pd.Series(payload)
            return strategy.get_entry_signal(row)
        except Exception:
            return None
