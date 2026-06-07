"""registry.heartbeat: last_heartbeat + ленивый захват expected_interval; start() зовёт heartbeat."""
import asyncio
from types import SimpleNamespace
from core.agent_registry import AgentRegistry
from agents.base_agent import BaseAgent
from tests.execution.fakes import FakeBus


def test_register_adds_heartbeat_fields():
    reg = AgentRegistry()
    info = reg.register(SimpleNamespace(name="A", description="d"))
    assert info.last_heartbeat is None
    assert info.expected_interval is None


def test_heartbeat_sets_time_and_lazy_interval():
    reg = AgentRegistry()
    reg.register(SimpleNamespace(name="A", description="d"))
    reg.heartbeat("A", expected_interval=10.0)
    info = reg.get("A")
    assert info.last_heartbeat is not None
    assert info.expected_interval == 10.0
    # повторный heartbeat без interval не затирает
    reg.heartbeat("A")
    assert reg.get("A").expected_interval == 10.0


def test_heartbeat_unknown_name_noop():
    reg = AgentRegistry()
    reg.heartbeat("missing")  # не должно кидать


async def test_start_calls_heartbeat():
    from core.agent_registry import registry as global_reg

    class Tiny(BaseAgent):
        def __init__(self, name, bus):
            super().__init__(name, bus)
            self.poll_interval = 7.0
            self._n = 0

        async def run(self):
            self._n += 1
            if self._n >= 2:
                raise asyncio.CancelledError  # выходим после первого успешного run()

    agent = Tiny("TinyHB", FakeBus())
    await agent.start()  # run()#1 ок → heartbeat; run()#2 Cancelled → STOPPED
    info = global_reg.get("TinyHB")
    assert info.last_heartbeat is not None
    assert info.expected_interval == 7.0
