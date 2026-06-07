"""WatchdogAgent: эмит AGENT_STALE на переход в stale, без дублей."""
from datetime import datetime, timedelta
from core.events import EventType
from core.agent_registry import AgentInfo
from tests.execution.fakes import FakeBus


def _stale_info(name, age, interval=10.0):
    i = AgentInfo(name, name)
    i.expected_interval = interval
    i.last_heartbeat = datetime.now() - timedelta(seconds=age)
    return i


def _count(bus, etype):
    return sum(1 for e in bus.events if e.type == etype)


async def test_emits_stale_on_transition_once(monkeypatch):
    import agents.watchdog_agent as wd_mod
    from core.agent_registry import registry

    monkeypatch.setattr(registry, "_agents", {"Stuck": _stale_info("Stuck", 100)})
    agent = wd_mod.WatchdogAgent("Watchdog", FakeBus(), poll_interval=0)

    await agent.run()  # переход → AGENT_STALE
    await agent.run()  # уже известен stale → без нового эмита
    assert _count(agent.bus, EventType.AGENT_STALE) == 1
    ev = next(e for e in agent.bus.events if e.type == EventType.AGENT_STALE)
    assert ev.payload["agent"] == "Stuck"
    assert agent.metrics["stale_count"] == 1


async def test_recovery_clears_known(monkeypatch):
    import agents.watchdog_agent as wd_mod
    from core.agent_registry import registry

    agents_map = {"Stuck": _stale_info("Stuck", 100)}
    monkeypatch.setattr(registry, "_agents", agents_map)
    agent = wd_mod.WatchdogAgent("Watchdog", FakeBus(), poll_interval=0)
    await agent.run()  # stale

    # агент восстановился (свежий heartbeat)
    agents_map["Stuck"].last_heartbeat = datetime.now()
    await agent.run()
    assert agent.metrics["stale_count"] == 0
    # снова протух → новый эмит (переход повторился)
    agents_map["Stuck"].last_heartbeat = datetime.now() - timedelta(seconds=100)
    await agent.run()
    assert _count(agent.bus, EventType.AGENT_STALE) == 2


async def test_no_stale_no_emit(monkeypatch):
    import agents.watchdog_agent as wd_mod
    from core.agent_registry import registry
    fresh = AgentInfo("Fresh", "d")
    fresh.expected_interval = 10.0
    fresh.last_heartbeat = datetime.now()
    monkeypatch.setattr(registry, "_agents", {"Fresh": fresh})
    agent = wd_mod.WatchdogAgent("Watchdog", FakeBus(), poll_interval=0)
    await agent.run()
    assert _count(agent.bus, EventType.AGENT_STALE) == 0
