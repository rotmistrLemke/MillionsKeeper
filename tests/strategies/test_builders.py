import pandas as pd
from tests.strategies import builders

REQUIRED_COLS = {"time", "open", "high", "low", "close", "tick_volume"}


def test_trend_up_has_required_columns_and_length():
    df = builders.trend_up(300)
    assert REQUIRED_COLS.issubset(df.columns)
    assert len(df) == 300


def test_ohlc_invariants_hold():
    df = builders.trend_up(50)
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()


def test_trend_up_is_monotonic_in_close():
    df = builders.trend_up(50)
    assert df["close"].is_monotonic_increasing


def test_trend_down_is_monotonic_in_close():
    df = builders.trend_down(50)
    assert df["close"].is_monotonic_decreasing


def test_flat_is_deterministic():
    a = builders.flat(100)
    b = builders.flat(100)
    pd.testing.assert_frame_equal(a, b)


def test_from_closes_round_trips_close():
    df = builders.from_closes([10.0, 11.0, 9.0, 12.0])
    assert list(df["close"]) == [10.0, 11.0, 9.0, 12.0]
    assert df["time"].is_monotonic_increasing
