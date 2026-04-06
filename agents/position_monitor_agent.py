import asyncio
import time

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType


class PositionMonitorAgent(BaseAgent):
    """
    Периодически опрашивает открытые позиции.
    Публикует POSITION_UPDATE с live P&L.
    Проверяет RSI-выход и публикует ORDER_CLOSE_REQUEST.
    """
    description = "Мониторинг открытых позиций, RSI-выход"

    def __init__(self, name: str, bus: EventBus, trading, poll_interval: float = 5.0):
        super().__init__(name, bus)
        self.trading = trading
        self.poll_interval = poll_interval
        self.metrics["open_positions"] = 0

    async def run(self):
        await self.emit_status(AgentStatus.RUNNING, "Проверка позиций")
        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None, self._get_positions_with_pnl
            )
            self.metrics["open_positions"] = len(positions)
            await self.emit(EventType.POSITION_UPDATE, {"positions": positions})

            # Проверяем RSI-выход
            for pos in positions:
                await self._check_rsi_exit(pos)

        except Exception as e:
            self._logger.error(f"Position monitor error: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

        await self.emit_status(AgentStatus.IDLE, f"Позиций: {self.metrics['open_positions']}")
        await asyncio.sleep(self.poll_interval)

    def _get_positions_with_pnl(self) -> list:
        import MetaTrader5 as mt5
        positions = self.trading.getPositions()
        result = []
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            if tick:
                if p.type == mt5.ORDER_TYPE_BUY:
                    pnl = (tick.bid - p.price_open) / mt5.symbol_info(p.symbol).point
                else:
                    pnl = (p.price_open - tick.ask) / mt5.symbol_info(p.symbol).point
            else:
                pnl = 0.0

            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "sl": p.sl,
                "pnl_points": round(pnl, 1),
                "pnl_money": round(p.profit, 2),
                "open_time": int(p.time),
            })
        return result

    async def _check_rsi_exit(self, pos: dict):
        from settings import Dictionary, GlobalValues
        from indicators import RSI

        symbol = pos["symbol"]
        trading_status = Dictionary.symbolTradingStatus.get(symbol, 3)
        if trading_status == 3:
            return

        try:
            rsi_ind = RSI()
            _, rsi_value = await asyncio.get_event_loop().run_in_executor(
                None, rsi_ind.RSI_signal, symbol, GlobalValues.timeFrame
            )
            if rsi_value is None:
                return

            should_close = (
                (pos["type"] == "BUY" and rsi_value < 45) or
                (pos["type"] == "SELL" and rsi_value > 55)
            )
            if should_close:
                await self.emit(EventType.RSI_EXIT_TRIGGERED, {
                    "symbol": symbol,
                    "ticket": pos["ticket"],
                    "rsi_value": rsi_value,
                    "position_type": pos["type"],
                })
                await self.emit(EventType.ORDER_CLOSE_REQUEST, {
                    "ticket": pos["ticket"],
                    "symbol": symbol,
                    "reason": f"RSI={rsi_value:.1f}",
                })
        except Exception as e:
            self._logger.warning(f"RSI exit check failed {symbol}: {e}")
