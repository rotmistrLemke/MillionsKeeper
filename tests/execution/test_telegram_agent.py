"""TelegramAgent: алерты на переходы, дедуп, guard от петли, graceful no-op."""
from core.events import Event, EventType
from tests.execution.fakes import FakeBus


def _make(monkeypatch, *, token="T", chat_id="C"):
    import agents.telegram_agent as tg_mod
    sent = []

    async def fake_sender(text):
        sent.append(text)

    agent = tg_mod.TelegramAgent("Telegram", FakeBus(), sender=fake_sender,
                                 token=token, chat_id=chat_id)
    return agent, sent


def _ev(etype, payload):
    return Event(type=etype, source="t", payload=payload)


async def test_mt5_disconnect_dedup_then_recovery(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))  # дубль
    assert len(sent) == 1 and "disconnect" in sent[0].lower()
    await agent._on_mt5_connected(_ev(EventType.MT5_CONNECTED, {}))
    assert len(sent) == 2 and "reconnect" in sent[1].lower()


async def test_agent_error_dedup(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_agent_status(_ev(EventType.AGENT_STATUS,
                                     {"agent": "Execution", "status": "error", "detail": "boom"}))
    await agent._on_agent_status(_ev(EventType.AGENT_STATUS,
                                     {"agent": "Execution", "status": "error", "detail": "boom"}))
    assert len(sent) == 1 and "Execution" in sent[0]


async def test_agent_status_self_guard(monkeypatch):
    agent, sent = _make(monkeypatch)
    # событие со СВОИМ именем → игнор (нет петли)
    await agent._on_agent_status(_ev(EventType.AGENT_STATUS,
                                     {"agent": "Telegram", "status": "error", "detail": "x"}))
    assert sent == []


async def test_noop_without_config(monkeypatch):
    agent, sent = _make(monkeypatch, token="", chat_id="")
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))
    assert sent == []  # sender не вызван — агент выключен


async def test_telegram_sent_emitted(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))
    assert any(e.type == EventType.TELEGRAM_SENT for e in agent.bus.events)


async def test_startup_ping_once(monkeypatch):
    import asyncio
    agent, sent = _make(monkeypatch)
    # run() делает ping один раз, затем долгий sleep — гоняем с таймаутом
    try:
        await asyncio.wait_for(agent.run(), timeout=0.05)
    except asyncio.TimeoutError:
        pass
    assert any("start" in s.lower() for s in sent)


async def test_on_agent_stale_alerts(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_agent_stale(_ev(EventType.AGENT_STALE,
                                    {"agent": "MarketData", "silent_sec": 120}))
    assert len(sent) == 1 and "MarketData" in sent[0] and "stale" in sent[0].lower()
