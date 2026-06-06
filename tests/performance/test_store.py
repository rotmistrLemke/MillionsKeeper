"""Характеризация SQLite-хранилища performance."""
from performance.store import PerformanceStore, record_poll


def _deal(ticket, time=1000, magic=1001, profit=5.0):
    return {"ticket": ticket, "time": time, "magic": magic, "symbol": "XAUUSD",
            "type": 0, "entry": 1, "volume": 0.1, "price": 1900.0,
            "profit": profit, "commission": -0.5, "swap": 0.0}


def test_upsert_and_read(tmp_path):
    db = tmp_path / "p.db"
    s = PerformanceStore(db)
    n = s.upsert_deals([_deal(1), _deal(2)])
    assert n == 2
    trades = s.closed_trades()
    assert len(trades) == 2 and trades[0]["ticket"] == 1
    s.close()


def test_upsert_dedup_by_ticket(tmp_path):
    s = PerformanceStore(tmp_path / "p.db")
    s.upsert_deals([_deal(1)])
    n2 = s.upsert_deals([_deal(1, profit=999.0)])  # тот же ticket → игнор
    assert n2 == 0
    trades = s.closed_trades()
    assert len(trades) == 1 and trades[0]["profit"] == 5.0  # старое значение сохранено
    s.close()


def test_equity_snapshots(tmp_path):
    s = PerformanceStore(tmp_path / "p.db")
    s.record_equity(10000.0, 10050.0, ts=100)
    s.record_equity(10050.0, 10020.0, ts=200)
    series = s.equity_series()
    assert series == [(100, 10050.0), (200, 10020.0)]
    s.close()


def test_closed_trades_since_filter(tmp_path):
    s = PerformanceStore(tmp_path / "p.db")
    s.upsert_deals([_deal(1, time=100), _deal(2, time=500)])
    assert len(s.closed_trades(since=300)) == 1
    s.close()


def test_record_poll_helper(tmp_path):
    db = tmp_path / "p.db"
    n = record_poll([_deal(1), _deal(2)], balance=10000.0, equity=10010.0, db_path=db)
    assert n == 2
    s = PerformanceStore(db)
    assert len(s.closed_trades()) == 2 and s.equity_series() == [(s.equity_series()[0][0], 10010.0)]
    s.close()
