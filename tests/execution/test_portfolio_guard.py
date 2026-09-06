"""Портфельные ограничения в пути исполнения ордера.

ExecutionAgent считал риск только по одному потоку за раз. Эти тесты держат
второй контур: сколько потоков стоит в рынке одновременно и сколько счёт уже
потерял от пика — оба вопроса о портфеле, а не о потоке.
"""
from datetime import datetime

import pytest

import portfolio
from core.events import Event, EventType
from signals.journal import Reason
from tests.execution.fakes import make_stream

DAY = datetime(2026, 6, 3, 12, 0)


def _signal_event(**payload):
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("signal", "BUY")
    payload.setdefault("indicators", {})
    return Event(type=EventType.SIGNAL_GENERATED, source="test", payload=payload)


@pytest.fixture
def rejections(monkeypatch):
    import agents.execution_agent as ea_mod
    calls = []
    monkeypatch.setattr(ea_mod.journal, "record", lambda **kw: calls.append(kw))
    return calls


@pytest.fixture
def with_guard(monkeypatch, tmp_path):
    """Подменяет боевой portfolio.guard настроенным на тест."""
    def make(**limit_kw):
        guard = portfolio.PortfolioGuard(
            portfolio.PortfolioLimits(**limit_kw), state_path=tmp_path / "state.json")
        monkeypatch.setattr(portfolio, "guard", guard)
        return guard
    return make


# ── Лимит одновременных позиций ──────────────────────────────────────

async def test_signal_rejected_when_position_limit_reached(
        execution_agent_factory, rejections, with_guard):
    with_guard(max_open_positions=1)
    h = execution_agent_factory(
        streams={"s1": make_stream(id="s1", symbol="XAUUSD"),
                 "s2": make_stream(id="s2", symbol="XAUUSD", strategy="aroon")},
        now=DAY)
    h.registry.mark_stream_open("s1")          # слот занят другим потоком

    await h.agent._handle_signal(_signal_event(stream_id="s2"))

    assert h.trading.open_calls == []
    assert [c["reason"] for c in rejections] == [Reason.PORTFOLIO_LIMIT]
    assert rejections[0]["stream_id"] == "s2"


async def test_signal_passes_when_slot_is_free(
        execution_agent_factory, rejections, with_guard):
    with_guard(max_open_positions=1)
    h = execution_agent_factory(streams={"s1": make_stream(id="s1", symbol="XAUUSD")},
                                now=DAY)
    await h.agent._handle_signal(_signal_event(stream_id="s1"))
    assert len(h.trading.open_calls) == 1
    assert rejections == []


async def test_no_limit_configured_lets_everything_through(
        execution_agent_factory, rejections, with_guard):
    with_guard(max_open_positions=0)
    h = execution_agent_factory(
        streams={"s1": make_stream(id="s1", symbol="XAUUSD"),
                 "s2": make_stream(id="s2", symbol="XAUUSD", strategy="aroon")},
        now=DAY)
    h.registry.mark_stream_open("s1")
    await h.agent._handle_signal(_signal_event(stream_id="s2"))
    assert len(h.trading.open_calls) == 1


# ── Стоп по просадке ─────────────────────────────────────────────────

async def test_signal_rejected_when_portfolio_drawdown_exceeded(
        execution_agent_factory, rejections, with_guard):
    with_guard(max_drawdown=0.3, deposit=2000.0)
    h = execution_agent_factory(streams={"s1": make_stream(id="s1", symbol="XAUUSD")},
                                now=DAY)
    h.mt5.equity = 1300.0                       # −35% от депозита

    await h.agent._handle_signal(_signal_event(stream_id="s1"))

    assert h.trading.open_calls == []
    assert [c["reason"] for c in rejections] == [Reason.PORTFOLIO_DRAWDOWN]
    assert "35" in rejections[0]["detail"]


async def test_healthy_equity_lets_signal_through(
        execution_agent_factory, rejections, with_guard):
    with_guard(max_drawdown=0.3, deposit=2000.0)
    h = execution_agent_factory(streams={"s1": make_stream(id="s1", symbol="XAUUSD")},
                                now=DAY)
    h.mt5.equity = 1900.0
    await h.agent._handle_signal(_signal_event(stream_id="s1"))
    assert len(h.trading.open_calls) == 1


async def test_unavailable_account_info_does_not_block_trading(
        execution_agent_factory, rejections, with_guard):
    # Терминал не отдал account_info — это обрыв связи, а не просадка.
    guard = with_guard(max_drawdown=0.3, deposit=2000.0)
    h = execution_agent_factory(streams={"s1": make_stream(id="s1", symbol="XAUUSD")},
                                now=DAY)
    h.mt5.equity = None
    await h.agent._handle_signal(_signal_event(stream_id="s1"))
    assert len(h.trading.open_calls) == 1
    assert guard.blocked is False


async def test_drawdown_stop_outranks_position_limit_in_journal(
        execution_agent_factory, rejections, with_guard):
    # Обе причины истинны; в журнал должна попасть та, что серьёзнее.
    with_guard(max_open_positions=1, max_drawdown=0.3, deposit=2000.0)
    h = execution_agent_factory(
        streams={"s1": make_stream(id="s1", symbol="XAUUSD"),
                 "s2": make_stream(id="s2", symbol="XAUUSD", strategy="aroon")},
        now=DAY)
    h.registry.mark_stream_open("s1")
    h.mt5.equity = 1300.0
    await h.agent._handle_signal(_signal_event(stream_id="s2"))
    assert [c["reason"] for c in rejections] == [Reason.PORTFOLIO_DRAWDOWN]
