import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event


class BacktestAgent(BaseAgent):
    """
    Запускает бэктест по запросу (событие BACKTEST_STARTED).
    Публикует BACKTEST_RESULT с результатами.
    """
    description = "Бэктест стратегии"

    def __init__(self, name: str, bus: EventBus):
        super().__init__(name, bus)
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["runs"] = 0
        bus.subscribe(EventType.BACKTEST_STARTED, self._on_backtest_request)

    async def _on_backtest_request(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание запроса")
        event = await self._queue.get()
        p = event.payload
        symbol = p.get("symbol", "XAUUSDrfd")
        bars = p.get("bars", 2000)
        deposit = p.get("deposit", 0.0)
        spread = p.get("spread", 0)
        timeframe = p.get("timeframe", None)
        volume = p.get("volume", 0.0)

        await self.emit_status(AgentStatus.RUNNING, f"Бэктест {symbol} {bars} баров")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_backtest, symbol, bars, deposit, spread, timeframe, volume
            )
            self.metrics["runs"] = self.metrics.get("runs", 0) + 1
            await self.emit(EventType.BACKTEST_RESULT, {
                "symbol": symbol,
                "bars": bars,
                "deposit": deposit,
                "result": result,
            }, correlation_id=event.correlation_id)
            await self.emit_status(AgentStatus.IDLE, f"Готово: {symbol}")
        except Exception as e:
            self._logger.error(f"Backtest failed {symbol}: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

    def _run_backtest(self, symbol, bars, deposit, spread, timeframe, volume=0.0) -> dict:
        from backtest import run_backtest
        import MetaTrader5 as mt5

        tf = timeframe if timeframe is not None else mt5.TIMEFRAME_H1
        result = run_backtest(symbol, tf, bars=bars, spread_points=spread, deposit=deposit, fixed_volume=volume)
        if result is None:
            return {}
        return {
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "total_pnl_points": result.total_pnl_points,
            "total_pnl_money": result.total_pnl_money,
            "final_balance": result.final_balance,
            "return_pct": result.return_pct,
            "max_drawdown_money": result.max_drawdown_money,
            "max_drawdown_pct": result.max_drawdown_pct,
            "profit_factor": result.profit_factor,
            "avg_win_money": result.avg_win_money,
            "avg_loss_money": result.avg_loss_money,
            "trades": result.trades[-50:],  # последние 50 сделок для UI
        }
