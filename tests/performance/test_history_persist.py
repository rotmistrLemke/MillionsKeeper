"""Интеграция: HistoryAgent._persist_track пишет closed-сделки + equity в store."""
import sys
import types
from types import SimpleNamespace

import pytest

from agents.history_agent import HistoryAgent
from core.event_bus import EventBus
from performance.store import PerformanceStore


class _Deal(SimpleNamespace):
    pass


def test_persist_track_writes_closed_deals(tmp_path, monkeypatch):
    # Фейковый mt5 с двумя closed-сделками (entry=1) и одной открывающей (entry=0).
    deals = [
        _Deal(ticket=1, time=1000, magic=1001, symbol="XAUUSD", type=0, entry=1,
              volume=0.1, price=1900.0, profit=10.0, commission=-0.5, swap=0.0),
        _Deal(ticket=2, time=2000, magic=1002, symbol="EURUSD", type=1, entry=1,
              volume=0.2, price=1.1, profit=-4.0, commission=-0.3, swap=-0.1),
        _Deal(ticket=3, time=900, magic=1001, symbol="XAUUSD", type=0, entry=0,
              volume=0.1, price=1899.0, profit=0.0, commission=0.0, swap=0.0),
    ]
    fake_mt5 = types.ModuleType("MetaTrader5")
    fake_mt5.history_deals_get = lambda a, b: deals
    fake_mt5.account_info = lambda: SimpleNamespace(balance=10000.0, equity=10050.0)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)

    # Подменяем путь БД store на временный (record_poll использует _DEFAULT_DB).
    import performance.store as store_mod
    db = tmp_path / "perf.db"
    monkeypatch.setattr(store_mod, "_DEFAULT_DB", db)

    agent = HistoryAgent("History", EventBus())
    agent._persist_track()

    s = PerformanceStore(db)
    trades = s.closed_trades()
    s.close()
    assert {t["ticket"] for t in trades} == {1, 2}     # открывающая (entry=0) отфильтрована
    assert len(trades) == 2
