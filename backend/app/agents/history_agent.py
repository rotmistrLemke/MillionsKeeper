"""
agents/history_agent.py — Загрузка истории и сохранение в PostgreSQL.

Изменения vs v1:
  - Сохраняет закрытые сделки в таблицу trades (через SQLAlchemy)
  - Читает историю из БД, а не только из MT5
  - Дедупликация по ticket
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import MetaTrader5 as mt5
import pandas as pd
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentStatus
from app.core.config import settings
from app.core.database import db_session
from app.models.db import Trade
from core.event_bus import EventBus
from core.events import EventType


class HistoryAgent(BaseAgent):
    description = "История сделок: загрузка из MT5, сохранение в PostgreSQL"

    def __init__(self, name: str, bus: EventBus, poll_interval: float = None):
        super().__init__(name, bus)
        self.poll_interval = poll_interval or settings.poll_interval_history
        self.metrics["today_pnl"] = 0.0
        self.metrics["saved_trades"] = 0

    async def run(self):
        await self.emit_status(AgentStatus.RUNNING, "Загрузка истории MT5")

        snapshot = await asyncio.get_event_loop().run_in_executor(None, self._load_from_mt5)
        saved = await self._persist_deals(snapshot.get("deals", []))

        today_pnl = snapshot.get("today_pnl", 0.0)
        self.metrics.update({"today_pnl": today_pnl, "saved_trades": saved})

        await self.emit(EventType.HISTORY_SNAPSHOT, {
            "today_pnl":  today_pnl,
            "week_pnl":   snapshot.get("week_pnl", 0.0),
            "month_pnl":  snapshot.get("month_pnl", 0.0),
        })
        await self.emit_status(AgentStatus.IDLE, f"Сегодня: {today_pnl:+.2f}$")
        await asyncio.sleep(self.poll_interval)

    @staticmethod
    def _load_from_mt5() -> dict:
        from datetime import timedelta
        now = datetime.now()

        def deals_profit(date_from, date_to=None):
            dt = date_to or now
            deals = mt5.history_deals_get(date_from, dt)
            if deals is None:
                return 0.0, []
            closed = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
            total  = sum(d.profit + d.swap + d.commission for d in closed)
            return round(total, 2), closed

        day_start  = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = day_start - pd.Timedelta(days=day_start.weekday())
        month_start = day_start.replace(day=1)

        today_pnl, deals = deals_profit(day_start)
        week_pnl,  _     = deals_profit(week_start)
        month_pnl, _     = deals_profit(month_start)

        return {"today_pnl": today_pnl, "week_pnl": week_pnl, "month_pnl": month_pnl, "deals": deals}

    async def _persist_deals(self, deals: list) -> int:
        if not deals:
            return 0
        saved = 0
        try:
            async with db_session() as session:
                existing_tickets = set(
                    row[0] for row in await session.execute(
                        select(Trade.ticket).where(
                            Trade.ticket.in_([d.ticket for d in deals])
                        )
                    )
                )
                for d in deals:
                    if d.ticket in existing_tickets:
                        continue
                    trade = Trade(
                        ticket     = d.ticket,
                        symbol     = d.symbol,
                        order_type = "BUY" if d.type == mt5.ORDER_TYPE_BUY else "SELL",
                        volume     = d.volume,
                        open_price = d.price,
                        close_price= d.price,
                        profit     = d.profit,
                        swap       = d.swap,
                        commission = d.commission,
                        open_time  = datetime.fromtimestamp(d.time, tz=timezone.utc),
                        close_time = datetime.fromtimestamp(d.time, tz=timezone.utc),
                    )
                    session.add(trade)
                    saved += 1
        except Exception as e:
            self._logger.error(f"DB persist error: {e}")
        return saved
