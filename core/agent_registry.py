from datetime import datetime
from typing import Dict, List, Optional


class AgentInfo:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "idle"
        self.detail = ""
        self.metrics: dict = {}
        self.last_run: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.expected_interval: Optional[float] = None
        self.error_count = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "detail": self.detail,
            "metrics": self.metrics,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "expected_interval": self.expected_interval,
            "error_count": self.error_count,
        }


class AgentRegistry:
    """Реестр всех агентов — используется Web UI для отображения статусов."""

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}

    def register(self, agent) -> AgentInfo:
        info = AgentInfo(
            name=agent.name,
            description=getattr(agent, "description", agent.name)
        )
        self._agents[agent.name] = info
        # Даём агенту ссылку на его info для быстрого обновления
        agent._registry_info = info
        return info

    def update_status(self, name: str, status: str, detail: str = "", metrics: dict = None):
        if name in self._agents:
            info = self._agents[name]
            info.status = status
            info.detail = detail
            if metrics:
                info.metrics.update(metrics)
            if status == "running":
                info.last_run = datetime.now()
            if status == "error":
                info.error_count += 1

    def heartbeat(self, name: str, expected_interval: float = None):
        info = self._agents.get(name)
        if info is None:
            return
        info.last_heartbeat = datetime.now()
        if expected_interval is not None and info.expected_interval is None:
            info.expected_interval = expected_interval

    def get_all_statuses(self) -> List[dict]:
        return [info.to_dict() for info in self._agents.values()]

    def get(self, name: str) -> Optional[AgentInfo]:
        return self._agents.get(name)


registry = AgentRegistry()
