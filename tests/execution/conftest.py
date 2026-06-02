"""Фикстура patched_trading: подменяет модульные глобалы trading.py фейками."""
from types import SimpleNamespace

import pytest

from tests.execution.fakes import FakeMT5, FakeCache, FakeStatus


@pytest.fixture
def patched_trading(monkeypatch):
    """Возвращает namespace с Trading() и подменёнными фейками."""
    import trading as trading_mod
    fake_mt5 = FakeMT5()
    fake_cache = FakeCache()
    fake_status = FakeStatus()
    monkeypatch.setattr(trading_mod, "mt5", fake_mt5)
    monkeypatch.setattr(trading_mod, "cache", fake_cache)
    monkeypatch.setattr(trading_mod, "status", fake_status)
    return SimpleNamespace(
        trading=trading_mod.Trading(),
        mt5=fake_mt5, cache=fake_cache, status=fake_status,
    )
