from anomaly.schemas import AnomalyType, Snapshot, DetectResult


def test_anomaly_type_values():
    assert AnomalyType.EMA_FAR_UP.value == "EMA_FAR_UP"
    assert AnomalyType.EMA_FAR_DOWN.value == "EMA_FAR_DOWN"
    assert AnomalyType.STOCH_OB.value == "STOCH_OB"
    assert AnomalyType.STOCH_OS.value == "STOCH_OS"


def test_snapshot_round_trip():
    s = Snapshot(
        price=1.10, ema50=1.05, atr=0.01, dist_atr=5.0,
        stoch_k=95.0, stoch_d=90.0, bar_time="2026-05-11T09:00:00Z",
    )
    assert s.to_dict()["price"] == 1.10
    assert s.to_dict()["bar_time"] == "2026-05-11T09:00:00Z"


def test_detect_result_empty_when_no_types():
    r = DetectResult(types=[], snapshot=None)
    assert r.is_anomaly is False


def test_detect_result_truthy_when_types_present():
    snap = Snapshot(price=1, ema50=1, atr=1, dist_atr=5, stoch_k=50, stoch_d=50, bar_time="t")
    r = DetectResult(types=[AnomalyType.EMA_FAR_UP], snapshot=snap)
    assert r.is_anomaly is True
