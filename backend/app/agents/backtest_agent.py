"""
agents/backtest_agent.py — Запуск бэктеста по событию BACKTEST_STARTED.
Результат сохраняет в PostgreSQL и публикует BACKTEST_RESULT.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.base_agent import BaseAgent, AgentStatus
from app.core.database import db_session
from app.models.db import BacktestRun
from core.event_bus import EventBus
from core.events import Event, EventType


class BacktestAgent(BaseAgent):
    description = "Запуск бэктеста по запросу, сохранение результатов в PostgreSQL"

    def __init__(self, name: str, bus: EventBus):
        super().__init__(name, bus)
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["runs_total"] = 0
        bus.subscribe(EventType.BACKTEST_STARTED, self._on_start)

    async def _on_start(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание запроса бэктеста")
        event = await self._queue.get()
        p = event.payload

        strategy = p.get("strategy", "alligator")
        symbol   = p.get("symbol", "XAUUSDrfd")
        bars     = int(p.get("bars", 2000))
        deposit  = float(p.get("deposit", 10000.0))
        spread   = int(p.get("spread", 0))
        risk     = float(p.get("risk", 1.0))
        tf_str   = p.get("timeframe", "H1")

        await self.emit_status(AgentStatus.RUNNING, f"{strategy} {symbol} {bars}bars")
        self.metrics["runs_total"] = self.metrics.get("runs_total", 0) + 1

        try:
            from app.backtest.engine import BacktestEngine
            from app.strategies.registry import StrategyRegistry

            strategy_obj = StrategyRegistry.get(strategy)
            if strategy_obj is None:
                await self.emit(EventType.ORDER_ERROR, {"error": f"Strategy '{strategy}' not found"})
                return

            started_at = datetime.now(tz=timezone.utc)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: BacktestEngine().run(
                    strategy=strategy_obj,
                    symbol=symbol,
                    bars=bars,
                    deposit=deposit,
                    spread_points=spread,
                    risk_pct=risk,
                    timeframe_str=tf_str,
                ),
            )
            finished_at = datetime.now(tz=timezone.utc)

            if result is None:
                await self.emit_status(AgentStatus.ERROR, "Нет данных для бэктеста")
                return

            run_id = await self._save_result(result, strategy, symbol, tf_str, bars, deposit, spread, risk, started_at, finished_at)

            await self.emit(EventType.BACKTEST_RESULT, {
                "id":         run_id,
                "strategy":   strategy,
                "symbol":     symbol,
                "bars":       bars,
                "metrics":    result.metrics_dict(),
                "equity_curve": result.equity_curve[:500],  # обрезаем для WS
            })
            await self.emit_status(AgentStatus.IDLE, f"{strategy} {symbol}: WR={result.win_rate:.0%}")

        except Exception as e:
            self._logger.error(f"Backtest error: {e}", exc_info=True)
            await self.emit_status(AgentStatus.ERROR, str(e))

    async def _save_result(self, result, strategy, symbol, timeframe, bars, deposit, spread, risk, started_at, finished_at) -> int | None:
        try:
            async with db_session() as session:
                run = BacktestRun(
                    strategy      = strategy,
                    symbol        = symbol,
                    timeframe     = timeframe,
                    bars          = bars,
                    deposit       = deposit,
                    spread        = spread,
                    risk_percent  = risk,
                    total_trades  = result.total_trades,
                    win_rate      = result.win_rate,
                    profit_factor = result.profit_factor,
                    sharpe_ratio  = result.sharpe_ratio,
                    max_drawdown  = result.max_drawdown_pct,
                    total_profit  = result.total_pnl_money,
                    equity_curve  = result.equity_curve,
                    started_at    = started_at,
                    finished_at   = finished_at,
                )
                session.add(run)
                await session.flush()
                return run.id
        except Exception as e:
            self._logger.error(f"DB save backtest error: {e}")
            return None
