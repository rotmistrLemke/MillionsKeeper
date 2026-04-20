import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event
from settings import Dictionary


class ExecutionAgent(BaseAgent):
    """
    Подписывается на SIGNAL_GENERATED и ORDER_CLOSE_REQUEST.
    Открывает / закрывает позиции через trading.py.
    """
    description = "Открытие и закрытие ордеров"

    def __init__(self, name: str, bus: EventBus, trading):
        super().__init__(name, bus)
        self.trading = trading
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["opened_today"] = 0
        self.metrics["closed_today"] = 0
        bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal)
        bus.subscribe(EventType.ORDER_CLOSE_REQUEST, self._on_close_request)

    async def _on_signal(self, event: Event):
        await self._queue.put(("signal", event))

    async def _on_close_request(self, event: Event):
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
        symbol = p["symbol"]
        signal = p["signal"]
        trading_status = Dictionary.symbolTradingStatus.get(symbol, 3)

        if signal == "NO_SIGNAL":
            await self.emit_status(AgentStatus.IDLE, f"{symbol}: NO_SIGNAL")
            return
        if trading_status != 0:
            await self.emit_status(
                AgentStatus.IDLE,
                f"{symbol}: сигнал {signal} отброшен (trading_status={trading_status})"
            )
            return

        await self.emit_status(AgentStatus.RUNNING, f"Открытие {signal} {symbol}")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._open_order, symbol, signal, p.get("indicators", {})
            )
            if result:
                self.metrics["opened_today"] = self.metrics.get("opened_today", 0) + 1
                await self.emit(EventType.ORDER_OPENED, {
                    "symbol": symbol,
                    "type": signal,
                    "volume": result.get("volume"),
                    "price": result.get("price"),
                    "ticket": result.get("ticket"),
                    "indicators": p.get("indicators", {}),
                })
                Dictionary.symbolTradingStatus[symbol] = 1
                await self.emit(EventType.TRADING_STATUS_CHANGED, {
                    "symbol": symbol,
                    "status": 1,
                    "reason": "order_opened",
                })
        except Exception as e:
            self._logger.error(f"Open order failed {symbol}: {e}")
            await self.emit(EventType.ORDER_ERROR, {"symbol": symbol, "error": str(e)})

    def _open_order(self, symbol: str, signal: str, indicators: dict) -> dict:
        import MetaTrader5 as mt5
        from market_data_cache import cache
        from settings import GlobalValues

        atr = indicators.get("atr_value", 0)
        symbol_info = cache.get_symbol_info(symbol)
        if symbol_info is None:
            return None

        order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        stop_loss_pips = 2 * atr / symbol_info.point if atr > 0 else 100

        fixed_volume = getattr(GlobalValues, 'active_volume', 0.0) or 0.0
        if fixed_volume > 0:
            volume = fixed_volume
        else:
            volume = self.trading.calculateSafeTradeWithMargin(
                symbol, 80 if signal == "BUY" else 90, stop_loss_pips, order_type
            )
        if not volume or volume <= 0:
            return None

        result = self.trading.orderOpen(symbol, order_type, volume, "sum_signal")
        # trading.orderOpen возвращает dict {"order":..., "price":..., ...} при успехе.
        # На ошибке — либо dict с order=None, либо дергает исключение.
        if isinstance(result, dict) and result.get("order"):
            return {
                "ticket": result["order"],
                "volume": volume,
                "price": result.get("price"),
            }
        return None

    async def _handle_close(self, event: Event):
        p = event.payload
        ticket = p.get("ticket")
        symbol = p.get("symbol")

        await self.emit_status(AgentStatus.RUNNING, f"Закрытие позиции {symbol}")
        try:
            ok = await asyncio.get_event_loop().run_in_executor(
                None, self.trading.orderClose, ticket, symbol
            )
            if ok:
                self.metrics["closed_today"] = self.metrics.get("closed_today", 0) + 1
                await self.emit(EventType.ORDER_CLOSED, {
                    "ticket": ticket,
                    "symbol": symbol,
                    "reason": p.get("reason", "manual"),
                })
        except Exception as e:
            self._logger.error(f"Close order failed {ticket}: {e}")
            await self.emit(EventType.ORDER_ERROR, {"ticket": ticket, "error": str(e)})
