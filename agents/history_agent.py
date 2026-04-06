import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType


class HistoryAgent(BaseAgent):
    """
    Периодически читает историю сделок из MT5.
    Публикует HISTORY_SNAPSHOT с агрегированной статистикой.
    """
    description = "История сделок: день/неделя/месяц"

    def __init__(self, name: str, bus: EventBus, poll_interval: float = 300.0):
        super().__init__(name, bus)
        self.poll_interval = poll_interval
        self.metrics["today_pnl"] = 0.0

    async def run(self):
        await self.emit_status(AgentStatus.RUNNING, "Загрузка истории")
        try:
            snapshot = await asyncio.get_event_loop().run_in_executor(
                None, self._load_history
            )
            self.metrics["today_pnl"] = snapshot.get("today", {}).get("profit", 0.0)
            await self.emit(EventType.HISTORY_SNAPSHOT, snapshot)
            await self.emit_status(AgentStatus.IDLE, f"Сегодня: {self.metrics['today_pnl']:+.2f}$")
        except Exception as e:
            self._logger.error(f"History load error: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

        await asyncio.sleep(self.poll_interval)

    def _load_history(self) -> dict:
        from history import History
        h = History()

        def extract_profit(result):
            # get_closed_profit_period возвращает (float, list) или просто 0
            if isinstance(result, tuple):
                return {"profit": result[0], "deals": result[1]}
            return {"profit": result if result else 0.0}

        return {
            "today": extract_profit(h.get_profit_today()),
            "week":  extract_profit(h.get_profit_this_week()),
            "month": extract_profit(h.get_profit_this_month()),
        }
