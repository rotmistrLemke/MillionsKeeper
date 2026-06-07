"""Чистая агрегация здоровья агентов из реестра. Без обращения к синглтону."""
from datetime import datetime


def build_report(infos, now: datetime, stale_k: float = 3.0) -> dict:
    """infos: list[AgentInfo]. Возвращает {overall, agents:[...]}."""
    agents = []
    overall = "ok"
    for info in infos:
        lh = info.last_heartbeat
        silent = int((now - lh).total_seconds()) if lh is not None else None
        stale = (info.expected_interval is not None and lh is not None
                 and silent > stale_k * info.expected_interval)
        if stale or info.status == "error":
            overall = "degraded"
        agents.append({
            "name": info.name,
            "status": info.status,
            "detail": info.detail,
            "last_heartbeat": lh.isoformat() if lh is not None else None,
            "expected_interval": info.expected_interval,
            "silent_sec": silent,
            "stale": stale,
            "error_count": info.error_count,
        })
    return {"overall": overall, "agents": agents}
