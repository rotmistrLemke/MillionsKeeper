"""
core/agent_registry.py — Реестр агентов (статус, метрики).

Используется AgentStatusGrid на фронтенде через /api/agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.agents.base_agent import BaseAgent


@dataclass
class AgentInfo:
    name: str
    status: str = "idle"
    detail: str = ""
    metrics: dict = field(default_factory=dict)
    description: str = ""
    last_updated: Optional[datetime] = None


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}

    def register(self, agent: "BaseAgent") -> None:
        self._agents[agent.name] = AgentInfo(
            name=agent.name,
            description=getattr(agent, "description", ""),
        )

    def update_status(
        self,
        name: str,
        status: str,
        detail: str = "",
        metrics: dict = None,
    ) -> None:
        info = self._agents.get(name)
        if info is None:
            return
        info.status = status
        info.detail = detail
        if metrics:
            info.metrics = dict(metrics)
        info.last_updated = datetime.utcnow()

    def all_agents(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def get(self, name: str) -> Optional[AgentInfo]:
        return self._agents.get(name)


# Глобальный синглтон
registry = AgentRegistry()
