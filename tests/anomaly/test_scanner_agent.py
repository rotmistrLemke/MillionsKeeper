import pandas as pd
import pytest

from anomaly.schemas import AnomalyType, DetectResult, Snapshot
from anomaly.store import AnomalyStore


def _snap(dist=5.0, k=95.0):
    return Snapshot(price=1.0, ema50=1.0, atr=0.1, dist_atr=dist,
                    stoch_k=k, stoch_d=90.0,
                    bar_time="2026-05-11T09:00:00+00:00")


class FakeBus:
    def __init__(self):
        self.events = []

    async def publish(self, ev):
        self.events.append(ev)

    def publish_sync(self, ev):
        self.events.append(ev)


@pytest.fixture
def store(tmp_path):
    s = AnomalyStore(str(tmp_path / "a.db"))
    s.init_schema()
    return s


@pytest.fixture
def agent_factory(store):
    """Возвращает фабрику агента с подменёнными MT5/detector."""
    from agents.anomaly_scanner_agent import AnomalyScannerAgent
    from anomaly.detector import DetectorConfig

    def make(symbols, detect_map):
        agent = AnomalyScannerAgent(
            "AnomalyScanner",
            bus=FakeBus(),
            store=store,
            detector_cfg=DetectorConfig(),
            scan_interval_sec=300,
            miss_tolerance=2,
            timeframe=16385,
            bars_to_fetch=200,
            db_path=":memory:",
        )
        agent._list_symbols = lambda: list(symbols)
        agent._fetch_df = lambda symbol: pd.DataFrame({"close": [1.0] * 100})
        agent._evaluate = lambda df, symbol: detect_map.get(symbol, DetectResult())
        return agent

    return make


@pytest.mark.asyncio
async def test_scan_opens_anomaly_and_emits_event(agent_factory, store):
    agent = agent_factory(
        symbols=["EURUSDrfd"],
        detect_map={"EURUSDrfd": DetectResult(types=[AnomalyType.EMA_FAR_UP], snapshot=_snap())},
    )
    await agent.scan_once()
    active = store.list_active()
    assert len(active) == 1
    assert active[0]["symbol"] == "EURUSDrfd"
    types = [e.type.value for e in agent.bus.events if e.type.value.startswith("anomaly.")]
    assert "anomaly.opened" in types


@pytest.mark.asyncio
async def test_scan_closes_when_condition_clears(agent_factory, store):
    detect = {"X": DetectResult(types=[AnomalyType.STOCH_OB], snapshot=_snap())}
    agent = agent_factory(symbols=["X"], detect_map=detect)
    await agent.scan_once()
    assert len(store.list_active()) == 1

    detect["X"] = DetectResult(types=[], snapshot=_snap(dist=0.5, k=50))
    await agent.scan_once()
    assert store.list_active() == []
    closed_events = [e for e in agent.bus.events if e.type.value == "anomaly.closed"]
    assert len(closed_events) == 1


@pytest.mark.asyncio
async def test_per_symbol_error_does_not_break_scan(agent_factory, store):
    agent = agent_factory(
        symbols=["BAD", "GOOD"],
        detect_map={"GOOD": DetectResult(types=[AnomalyType.EMA_FAR_UP], snapshot=_snap())},
    )
    def boom(df, symbol):
        if symbol == "BAD":
            raise RuntimeError("mt5 fail")
        return DetectResult(types=[AnomalyType.EMA_FAR_UP], snapshot=_snap())
    agent._evaluate = boom

    await agent.scan_once()
    assert {r["symbol"] for r in store.list_active()} == {"GOOD"}


@pytest.mark.asyncio
async def test_missed_symbol_closes_after_miss_tolerance(agent_factory, store):
    detect = {"X": DetectResult(types=[AnomalyType.STOCH_OB], snapshot=_snap())}
    agent = agent_factory(symbols=["X"], detect_map=detect)
    await agent.scan_once()
    assert len(store.list_active()) == 1

    agent._list_symbols = lambda: []
    await agent.scan_once()
    assert len(store.list_active()) == 1   # 1-й пропуск
    await agent.scan_once()
    assert store.list_active() == []        # 2-й пропуск — закрываем


@pytest.mark.asyncio
async def test_recover_active_on_startup(store):
    from agents.anomaly_scanner_agent import AnomalyScannerAgent
    from anomaly.detector import DetectorConfig

    store.open("X", [AnomalyType.EMA_FAR_UP], _snap(), opened_at="2026-05-11T08:00:00+00:00")
    agent = AnomalyScannerAgent(
        "AnomalyScanner", bus=FakeBus(), store=store,
        detector_cfg=DetectorConfig(), scan_interval_sec=300, miss_tolerance=2,
        timeframe=16385, bars_to_fetch=200, db_path=":memory:",
    )
    agent.load_active_from_store()
    assert "X" in agent.active
    assert agent.active["X"]["id"] > 0
