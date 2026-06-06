"""ConnectionAgent: детект разрыва, реконнект с backoff, события MT5_*."""
import sys
import types
from types import SimpleNamespace

from core.events import EventType
from tests.execution.fakes import FakeBus


class _FakeMT5Conn(types.ModuleType):
    def __init__(self, seq):
        super().__init__("MetaTrader5")
        self._seq = list(seq)

    def terminal_info(self):
        # каждый вызов отдаёт следующий из seq; после конца — None
        return self._seq.pop(0) if self._seq else None


class _FakeAuth:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def reconnect(self):
        self.calls += 1
        return self._results.pop(0) if self._results else True


def _counts(bus, etype):
    return sum(1 for e in bus.events if e.type == etype)


async def test_disconnect_then_reconnect(monkeypatch):
    import agents.connection_agent as ca_mod
    # terminal_info всегда None — восстановление определяется успехом auth.reconnect()
    monkeypatch.setitem(sys.modules, "MetaTrader5", _FakeMT5Conn([None, None, None]))
    auth = _FakeAuth([False, False, True])
    agent = ca_mod.ConnectionAgent("Conn", FakeBus(), auth,
                                   poll_interval=0, base_backoff=0, max_backoff=0)

    await agent.run()  # None → переход down: MT5_DISCONNECTED, reconnect→False
    await agent.run()  # уже down: без нового DISCONNECTED, reconnect→False
    await agent.run()  # reconnect→True: MT5_CONNECTED

    assert _counts(agent.bus, EventType.MT5_DISCONNECTED) == 1
    assert _counts(agent.bus, EventType.MT5_CONNECTED) == 1
    assert agent.metrics["disconnects"] == 1
    assert agent.metrics["reconnect_attempts"] == 3
    assert auth.calls == 3
    assert agent.metrics["connected"] is True


async def test_stays_connected_no_events(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", _FakeMT5Conn([object(), object()]))
    auth = _FakeAuth([])
    import agents.connection_agent as ca_mod
    agent = ca_mod.ConnectionAgent("Conn", FakeBus(), auth, poll_interval=0)

    await agent.run()
    await agent.run()
    # был connected на старте и остаётся → ни одного MT5_* и нет попыток реконнекта
    assert _counts(agent.bus, EventType.MT5_DISCONNECTED) == 0
    assert _counts(agent.bus, EventType.MT5_CONNECTED) == 0
    assert auth.calls == 0
