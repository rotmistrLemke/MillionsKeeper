"""/health: degraded при stale-агенте. Вызываем корутину health() напрямую
(без TestClient/httpx — чтобы не зависеть от наличия httpx)."""
from datetime import datetime, timedelta


async def test_health_degraded_when_stale(monkeypatch):
    from core.agent_registry import registry, AgentInfo
    from web.app import health

    info = AgentInfo("Stuck", "d")
    info.expected_interval = 10.0
    info.last_heartbeat = datetime.now() - timedelta(seconds=100)  # >3*10 → stale
    monkeypatch.setattr(registry, "_agents", {"Stuck": info})

    body = await health()
    assert body["status"] == "degraded" and body["overall"] == "degraded"
    assert body["agents"][0]["name"] == "Stuck" and body["agents"][0]["stale"] is True


async def test_health_ok_when_fresh(monkeypatch):
    from core.agent_registry import registry, AgentInfo
    from web.app import health

    info = AgentInfo("Fresh", "d")
    info.expected_interval = 10.0
    info.last_heartbeat = datetime.now()
    monkeypatch.setattr(registry, "_agents", {"Fresh": info})

    body = await health()
    assert body["status"] == "ok"
