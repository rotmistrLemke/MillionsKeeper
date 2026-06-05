import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from core.event_bus import EventBus
from core.events import Event, EventType
from core.agent_registry import registry


class AgentStatus:
    IDLE    = "idle"
    RUNNING = "running"
    ERROR   = "error"
    STOPPED = "stopped"


class BaseAgent(ABC):
    description: str = ""

    def __init__(self, name: str, bus: EventBus):
        self.name = name
        self.bus = bus
        self.status = AgentStatus.IDLE
        self.last_run: Optional[datetime] = None
        self.error_count = 0
        self.metrics: dict = {}
        self._logger = logging.getLogger(f"Agent.{name}")
        self._registry_info = None  # заполняется registry.register(self)
        registry.register(self)

    async def emit(self, event_type: EventType, payload: dict, correlation_id: str = None):
        event = Event(
            type=event_type,
            source=self.name,
            payload=payload,
            correlation_id=correlation_id,
        )
        await self.bus.publish(event)

    def emit_sync(self, event_type: EventType, payload: dict):
        event = Event(type=event_type, source=self.name, payload=payload)
        self.bus.publish_sync(event)

    async def emit_status(self, status: str, detail: str = ""):
        self.status = status
        registry.update_status(self.name, status, detail, self.metrics)
        await self.emit(EventType.AGENT_STATUS, {
            "agent": self.name,
            "status": status,
            "detail": detail,
            "metrics": dict(self.metrics),
        })

    @abstractmethod
    async def run(self):
        """Основная логика агента."""
        pass

    async def start(self):
        """Запускает агент в бесконечном цикле с обработкой ошибок."""
        self._logger.info(f"{self.name} starting")
        while True:
            try:
                await self.run()
                self.last_run = datetime.now()
            except asyncio.CancelledError:
                await self.emit_status(AgentStatus.STOPPED)
                break
            except Exception as e:
                self.error_count += 1
                self._logger.error(f"{self.name} error #{self.error_count}: {e}", exc_info=True)
                await self.emit_status(AgentStatus.ERROR, str(e))
                await asyncio.sleep(5)
