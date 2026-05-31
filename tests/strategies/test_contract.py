"""A1: контракт BaseStrategy — проверяется для каждой стратегии реестра.

Фикстура `strategy` (из conftest) параметризована по всем 20 стратегиям.
"""
import pytest
import pandas as pd

from tests.strategies import builders


def _computed(strategy, df):
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    return df


def test_entry_signal_returns_valid_value(strategy):
    df = _computed(strategy, builders.trend_up())
    for idx in range(len(df)):
        sig = strategy.get_entry_signal(df.iloc[idx])
        assert sig in ("BUY", "SELL", None), f"{strategy.name}: неверный сигнал {sig!r}"


def test_is_flat_returns_bool(strategy):
    df = _computed(strategy, builders.flat())
    assert isinstance(strategy.is_flat(df.iloc[-1]), bool)


def test_hooks_return_bool(strategy):
    assert isinstance(strategy.wants_hedge(), bool)
    assert isinstance(strategy.closes_on_weekend(), bool)
    assert isinstance(strategy.uses_trailing_exit(), bool)


def test_compute_indicators_preserves_length(strategy):
    df = builders.trend_up()
    n0 = len(df)
    out = strategy.compute_indicators(df)
    assert len(out) == n0


def test_get_sl_tp_ordering_on_valid_row(strategy):
    """На строке с готовыми индикаторами SL/TP, если заданы, корректно упорядочены."""
    if strategy.name == "fibonacci_retracement":
        pytest.xfail(
            "FINDING(verify on real data): fibonacci_retracement BUY TP = imp_high "
            "(shift(1).rolling(n).max()). На монотонном синтетическом аптренде imp_high "
            "всегда < текущей цены, поэтому TP < price. На реальных данных вход происходит "
            "на откате, где imp_high может быть выше — проверить через golden-тест на "
            "реальном CSV, является ли это настоящим риском."
        )
    df = _computed(strategy, builders.trend_up())
    row = df.iloc[-1]  # последняя строка — индикаторы не NaN
    price = row["close"]

    for signal in ("BUY", "SELL"):
        sl, tp = strategy.get_sl_tp(row, signal, point=0.01)
        if sl is not None and not pd.isna(sl):
            if signal == "BUY":
                assert sl < price, f"{strategy.name} BUY: sl {sl} !< price {price}"
            else:
                assert sl > price, f"{strategy.name} SELL: sl {sl} !> price {price}"
        if tp is not None and not pd.isna(tp):
            if signal == "BUY":
                assert tp > price, f"{strategy.name} BUY: tp {tp} !> price {price}"
            else:
                assert tp < price, f"{strategy.name} SELL: tp {tp} !< price {price}"


def test_no_exception_on_short_dataframe(strategy):
    """Короткий df (меньше периодов индикаторов) не приводит к исключению."""
    df = builders.trend_up(n=10)
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    for idx in range(len(df)):
        strategy.get_entry_signal(df.iloc[idx])  # не должно кидать


def test_no_exception_on_nan_rows(strategy):
    """Начальные строки с NaN-индикаторами не ломают get_entry_signal."""
    df = _computed(strategy, builders.trend_up())
    strategy.get_entry_signal(df.iloc[0])  # самые ранние строки — NaN, не должно кидать
