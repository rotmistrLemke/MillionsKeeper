import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType

# Кэш последнего снапшота для мгновенной отдачи новому WS-клиенту.
_latest_snapshot: dict | None = None


def get_latest_snapshot() -> dict | None:
    return _latest_snapshot


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
        global _latest_snapshot
        await self.emit_status(AgentStatus.RUNNING, "Загрузка истории")
        try:
            snapshot = await asyncio.get_event_loop().run_in_executor(
                None, self._load_history
            )
            _latest_snapshot = snapshot
            self.metrics["today_pnl"] = snapshot.get("today", {}).get("profit", 0.0)
            await self.emit(EventType.HISTORY_SNAPSHOT, snapshot)
            await self.emit_status(AgentStatus.IDLE, f"Сегодня: {self.metrics['today_pnl']:+.2f}$")
        except Exception as e:
            self._logger.error(f"History load error: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

        await asyncio.sleep(self.poll_interval)

    # MT5 deal.reason → человекочитаемая причина закрытия (когда нет нашего тега).
    _REASON_LABELS = {
        0: "MANUAL",     # закрыто вручную в терминале
        1: "MANUAL",     # mobile — для нас тоже ручное
        2: "MANUAL",     # web terminal
        3: "SIGNAL",     # Expert без нашего комментария — наверняка стратегический выход
        4: "SL",
        5: "TP",
        6: "Stop Out",
        7: "Rollover",
        8: "VMargin",
        9: "Split",
    }

    # Теги, которые бот пишет в deal.comment при закрытии через order_send.
    _BOT_TAGS = {"SL", "TP", "SIGNAL", "RSI", "MANUAL"}

    @classmethod
    def _deal_reason(cls, d) -> str:
        """Причина закрытия: приоритет у тега бота в comment → MT5 reason-код."""
        comment = (getattr(d, "comment", "") or "").strip()
        # Бот пишет короткие теги (SL/TP/SIGNAL/RSI/MANUAL) при закрытии через order_send.
        upper = comment.upper()
        if upper in cls._BOT_TAGS:
            return upper
        # MT5-код — если наш тег не записан (например, закрытие по SL/TP через
        # встроенные стопы MT5 или ручное из терминала).
        try:
            code = int(getattr(d, "reason", -1))
        except (TypeError, ValueError):
            code = -1
        if code in cls._REASON_LABELS:
            return cls._REASON_LABELS[code]
        return comment or "—"

    def _load_history(self) -> dict:
        """Один запрос к MT5 за месяц → локальная нарезка на today/week/month."""
        from datetime import datetime, timedelta
        import MetaTrader5 as mt5

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start  = (today_start - timedelta(days=now.weekday()))
        month_start = today_start.replace(day=1)
        date_to     = now + timedelta(hours=3)  # запас под MT5 server time

        deals = mt5.history_deals_get(month_start, date_to)

        today = {"profit": 0.0, "deals": []}
        week  = {"profit": 0.0, "deals": []}
        month = {"profit": 0.0, "deals": []}

        if deals:
            for d in deals:
                if d.entry != 1 or d.type not in (0, 1):
                    continue
                t_dt = datetime.fromtimestamp(d.time)
                item = {
                    "ticket": d.ticket,
                    "symbol": d.symbol,
                    "type":   "BUY" if d.type == 0 else "SELL",
                    "profit": d.profit,
                    "volume": d.volume,
                    "time":   t_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": self._deal_reason(d),
                }
                month["profit"] += d.profit
                month["deals"].append(item)
                if t_dt >= week_start:
                    week["profit"] += d.profit
                    week["deals"].append(item)
                if t_dt >= today_start:
                    today["profit"] += d.profit
                    today["deals"].append(item)

        return {"today": today, "week": week, "month": month}
