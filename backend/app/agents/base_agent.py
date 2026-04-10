"""
agents/base_agent.py — Базовый класс агента (v2).

Изменения vs v1:
  - DI через __init__ (нет прямых импортов settings, trading, mt5)
  - AgentRegistry регистрирует автоматически
  - emit_status публикует в EventBus + обновляет реестр
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from core.agent_registry import registry
from core.event_bus import EventBus
from core.events import Event, EventType


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
        registry.register(self)

    async def emit(self, event_type: EventType, payload: dict, correlation_id: str = None):
        await self.bus.publish(Event(
            type=event_type,
            source=self.name,
            payload=payload,
            correlation_id=correlation_id,
        ))

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
        pass

    async def start(self):
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
