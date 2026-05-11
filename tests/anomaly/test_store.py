import pytest

from anomaly.schemas import AnomalyType, Snapshot
from anomaly.store import AnomalyStore


def _snap(price=1.0, ema50=1.0, atr=0.1, dist=5.0, k=95.0, d=90.0, t="2026-05-11T09:00:00+00:00"):
    return Snapshot(price=price, ema50=ema50, atr=atr, dist_atr=dist,
                    stoch_k=k, stoch_d=d, bar_time=t)


@pytest.fixture
def store():
    s = AnomalyStore(":memory:")
    s.init_schema()
    return s


def test_open_creates_active_row(store):
    rid = store.open("EURUSDrfd", [AnomalyType.EMA_FAR_UP], _snap(), opened_at="2026-05-11T09:00:00+00:00")
    rows = store.list_active()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "EURUSDrfd"
    assert rows[0]["id"] == rid
    assert rows[0]["closed_at"] is None
    assert "EMA_FAR_UP" in rows[0]["types"]


def test_update_changes_types_and_extends_extremes(store):
    rid = store.open("EURUSDrfd", [AnomalyType.EMA_FAR_UP], _snap(dist=4.2, k=94), opened_at="2026-05-11T09:00:00+00:00")
    store.update(rid, [AnomalyType.EMA_FAR_UP, AnomalyType.STOCH_OB], _snap(dist=5.1, k=97))
    row = store.list_active()[0]
    assert "STOCH_OB" in row["types"]
    assert row["max_abs_dist_atr"] == pytest.approx(5.1)
    assert row["peak_stoch_k"] == pytest.approx(97.0)
    # open-снапшот НЕ меняется
    assert row["open_dist_atr"] == pytest.approx(4.2)


def test_close_sets_closed_at_duration_and_close_snapshot(store):
    rid = store.open("X", [AnomalyType.STOCH_OB], _snap(), opened_at="2026-05-11T09:00:00+00:00")
    store.close(rid, _snap(price=1.5, k=80, d=75), closed_at="2026-05-11T10:30:00+00:00")
    active = store.list_active()
    assert active == []
    history = store.list_history(limit=10)["items"]
    row = history[0]
    assert row["closed_at"] == "2026-05-11T10:30:00+00:00"
    assert row["duration_sec"] == 90 * 60
    assert row["close_price"] == pytest.approx(1.5)


def test_recover_active_returns_only_open(store):
    rid1 = store.open("A", [AnomalyType.EMA_FAR_UP], _snap(), opened_at="2026-05-11T08:00:00+00:00")
    rid2 = store.open("B", [AnomalyType.STOCH_OS], _snap(), opened_at="2026-05-11T08:30:00+00:00")
    store.close(rid1, _snap(), closed_at="2026-05-11T09:00:00+00:00")
    recovered = store.recover_active()
    assert len(recovered) == 1
    assert recovered[0]["symbol"] == "B"
    assert recovered[0]["id"] == rid2


def test_list_history_filters_by_symbol(store):
    store.open("A", [AnomalyType.EMA_FAR_UP], _snap(), opened_at="2026-05-11T08:00:00+00:00")
    store.open("B", [AnomalyType.STOCH_OB], _snap(), opened_at="2026-05-11T08:00:00+00:00")
    res = store.list_history(symbol="A")
    assert all(r["symbol"] == "A" for r in res["items"])
    assert res["total"] == 1


def test_list_history_filters_by_type_substring(store):
    store.open("A", [AnomalyType.EMA_FAR_UP], _snap(), opened_at="2026-05-11T08:00:00+00:00")
    store.open("B", [AnomalyType.STOCH_OB],   _snap(), opened_at="2026-05-11T08:00:00+00:00")
    res = store.list_history(type_="STOCH")
    assert {r["symbol"] for r in res["items"]} == {"B"}


def test_list_history_respects_limit(store):
    for i in range(5):
        store.open(f"S{i}", [AnomalyType.EMA_FAR_UP], _snap(),
                   opened_at=f"2026-05-11T0{i}:00:00+00:00")
    res = store.list_history(limit=3)
    assert len(res["items"]) == 3
    assert res["total"] == 5


def test_open_twice_for_same_symbol_raises(store):
    store.open("X", [AnomalyType.EMA_FAR_UP], _snap(), opened_at="2026-05-11T08:00:00+00:00")
    with pytest.raises(ValueError, match="already active"):
        store.open("X", [AnomalyType.STOCH_OB], _snap(), opened_at="2026-05-11T08:30:00+00:00")
