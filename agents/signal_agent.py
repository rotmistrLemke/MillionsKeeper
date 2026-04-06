import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event
from settings import Dictionary


class SignalAgent(BaseAgent):
    """
    Подписывается на INDICATORS_READY.
    Формирует итоговый торговый сигнал (BUY/SELL/NO_SIGNAL).
    Публикует SIGNAL_GENERATED.
    """
    description = "Формирование итогового сигнала MA+MACD+RSI"

    def __init__(self, name: str, bus: EventBus):
        super().__init__(name, bus)
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["buy_signals"] = 0
        self.metrics["sell_signals"] = 0
        bus.subscribe(EventType.INDICATORS_READY, self._on_indicators_ready)

    async def _on_indicators_ready(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание индикаторов")
        event = await self._queue.get()
        p = event.payload
        symbol = p["symbol"]

        signal_ma = p.get("signal_ma", "NO_SIGNAL")
        signal_critical = p.get("signal_critical_angle", "NO_SIGNAL")
        macd_signal = p.get("macd_signal", "NO_SIGNAL")
        rsi_signal = p.get("rsi_signal", "NO_SIGNAL")

        # Та же логика, что и в alligatorBot.checkOpen
        if (signal_ma == "BUY" and signal_critical == "BUY"
                and macd_signal == "BUY" and rsi_signal == "BUY"):
            combined = "BUY"
            self.metrics["buy_signals"] = self.metrics.get("buy_signals", 0) + 1
        elif (signal_ma == "SELL" and signal_critical == "SELL"
              and macd_signal == "SELL" and rsi_signal == "SELL"):
            combined = "SELL"
            self.metrics["sell_signals"] = self.metrics.get("sell_signals", 0) + 1
        else:
            combined = "NO_SIGNAL"

        await self.emit_status(AgentStatus.RUNNING, f"{symbol} → {combined}")
        await self.emit(EventType.SIGNAL_GENERATED, {
            "symbol": symbol,
            "signal": combined,
            "trading_status": Dictionary.symbolTradingStatus.get(symbol, 3),
            "indicators": {
                "ma": signal_ma,
                "ma_angle": signal_critical,
                "macd": macd_signal,
                "rsi": rsi_signal,
                "rsi_value": p.get("rsi_value"),
                "atr_value": p.get("atr_value"),
                "adx_value": p.get("adx_value"),
                "ema8": p.get("ema8"),
                "ema21": p.get("ema21"),
            },
        }, correlation_id=event.correlation_id)
