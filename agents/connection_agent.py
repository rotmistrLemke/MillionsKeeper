"""ConnectionAgent — здоровье MT5-соединения: детект разрыва + авто-реконнект."""
import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType


class ConnectionAgent(BaseAgent):
    """Поллит mt5.terminal_info(); при разрыве реконнектит через MT5Auth с backoff.
    Эмитит MT5_DISCONNECTED/MT5_CONNECTED на ПЕРЕХОДАХ. Боевой путь не трогает."""
    description = "Здоровье MT5: детект разрыва + авто-реконнект"

    def __init__(self, name: str, bus: EventBus, mt5_auth, poll_interval: float = 15.0,
                 base_backoff: float = 5.0, max_backoff: float = 60.0):
        super().__init__(name, bus)
        self.mt5_auth = mt5_auth
        self.poll_interval = poll_interval
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._backoff = base_backoff
        self._connected = True  # на старте main.py уже залогинен
        self.metrics["connected"] = True
        self.metrics["disconnects"] = 0
        self.metrics["reconnect_attempts"] = 0

    async def run(self):
        import MetaTrader5 as mt5

        if mt5.terminal_info() is not None:
            # соединение есть
            self._backoff = self._base_backoff
            self.metrics["connected"] = True
            self._connected = True
            await self.emit_status(AgentStatus.IDLE, "MT5 ок")
            await asyncio.sleep(self.poll_interval)
            return

        # соединения нет
        if self._connected:
            self._connected = False
            self.metrics["disconnects"] += 1
            await self.emit(EventType.MT5_DISCONNECTED, {})

        self.metrics["connected"] = False
        await self.emit_status(AgentStatus.RUNNING, "Реконнект MT5…")
        self.metrics["reconnect_attempts"] += 1
        ok = self.mt5_auth.reconnect()

        if ok:
            self._connected = True
            self._backoff = self._base_backoff
            self.metrics["connected"] = True
            await self.emit(EventType.MT5_CONNECTED, {})
            await self.emit_status(AgentStatus.IDLE, "MT5 восстановлен")
            await asyncio.sleep(self.poll_interval)
        else:
            await self.emit_status(AgentStatus.ERROR, "MT5 реконнект не удался")
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, self._max_backoff)
