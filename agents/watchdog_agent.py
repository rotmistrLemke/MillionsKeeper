"""WatchdogAgent — детект протухших (stale) агентов и алерт через AGENT_STALE."""
import asyncio
from datetime import datetime

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType
from core.agent_registry import registry
from core.health import build_report


class WatchdogAgent(BaseAgent):
    """Периодически считает build_report; на переходе агента в stale эмитит AGENT_STALE."""
    description = "Watchdog: детект зависших агентов"

    def __init__(self, name: str, bus: EventBus, poll_interval: float = 60.0, stale_k: float = 3.0):
        super().__init__(name, bus)
        self.poll_interval = poll_interval
        self._stale_k = stale_k
        self._known_stale: set[str] = set()
        self.metrics["stale_count"] = 0

    async def run(self):
        report = build_report(list(registry._agents.values()), datetime.now(), self._stale_k)
        by_name = {a["name"]: a for a in report["agents"]}
        current = {name for name, a in by_name.items() if a["stale"]}

        for name in current - self._known_stale:
            await self.emit(EventType.AGENT_STALE, {
                "agent": name,
                "silent_sec": by_name[name].get("silent_sec"),
            })

        self._known_stale = current
        self.metrics["stale_count"] = len(current)
        await self.emit_status(AgentStatus.IDLE, f"stale: {len(current)}")
        await asyncio.sleep(self.poll_interval)
