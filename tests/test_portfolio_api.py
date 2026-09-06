"""/api/portfolio: состояние портфельных ограничений для баннера на дашборде.

Стоп по просадке не снимается сам и не пишет никуда, кроме лога и журнала.
Пока он не виден на стартовом экране, остановленная торговля выглядит ровно
как торговля без сигналов — то есть никак.

Хендлеры зовём корутиной напрямую, как в test_health_endpoint.py.
"""
from types import SimpleNamespace

import pytest

import portfolio


@pytest.fixture
def guard(monkeypatch, tmp_path):
    def make(**limits):
        g = portfolio.PortfolioGuard(portfolio.PortfolioLimits(**limits),
                                     state_path=tmp_path / "state.json")
        monkeypatch.setattr(portfolio, "guard", g)
        return g
    return make


@pytest.fixture
def equity(monkeypatch):
    """Подменяет источник equity в кэше рыночных данных."""
    def make(value):
        from market_data_cache import cache
        monkeypatch.setattr(
            cache, "get_account_info",
            lambda: None if value is None else SimpleNamespace(equity=value))
    return make


async def _call():
    from web.api_routes import get_portfolio
    return await get_portfolio(user=None)


async def test_reports_configured_limits(guard, equity):
    guard(max_open_positions=1, deposit=2000.0, max_drawdown=0.4)
    equity(1900.0)
    body = await _call()
    assert body["max_open_positions"] == 1
    assert body["max_drawdown"] == 0.4
    assert body["blocked"] is False


async def test_reports_current_drawdown(guard, equity):
    g = guard(max_drawdown=0.4, deposit=2000.0)
    equity(1600.0)
    g.check_drawdown(1600.0)
    body = await _call()
    assert body["peak"] == 2000.0
    assert body["drawdown"] == pytest.approx(0.2)


async def test_reports_the_block_with_reason(guard, equity):
    g = guard(max_drawdown=0.4, deposit=2000.0)
    equity(1100.0)
    g.check_drawdown(1100.0)
    body = await _call()
    assert body["blocked"] is True
    assert "45" in body["detail"]
    assert body["blocked_at"]


async def test_reports_open_stream_count(guard, equity, monkeypatch):
    guard(max_open_positions=1)
    equity(2000.0)
    import streams
    monkeypatch.setattr(streams.registry, "open_count", lambda: 1)
    assert (await _call())["open_count"] == 1


async def test_missing_equity_gives_null_drawdown_not_an_error(guard, equity):
    # Терминал молчит — баннер должен не сломаться, а просто не показать цифру.
    guard(max_drawdown=0.4, deposit=2000.0)
    equity(None)
    body = await _call()
    assert body["drawdown"] is None
    assert body["equity"] is None


async def test_reading_state_never_changes_it(guard, equity):
    # Просмотр дашборда не должен двигать пик и уж тем более включать стоп.
    g = guard(max_drawdown=0.4, deposit=2000.0)
    equity(900.0)
    await _call()
    assert g.blocked is False
    assert g.peak == 0.0
