"""Характеризация cache-обёрток indicators.py (E6). Прод не трогаем."""
import numpy as np
import pandas as pd
import pytest
from indicators import ATR, MACD, RSI, MovingAverage, BullsBearsPower, Alligator


def _ramp_df(n, base_high=10.0):
    """df с high/low/close (линейные ряды) и time — для cache-обёрток."""
    return pd.DataFrame({
        "time": list(range(n)),
        "open": [base_high - 0.5 + 0.1 * i for i in range(n)],
        "high": [base_high + 0.1 * i for i in range(n)],
        "low": [base_high - 1.0 + 0.1 * i for i in range(n)],
        "close": [base_high - 0.5 + 0.1 * i for i in range(n)],
    })


# --- ATR.calculate_atr ---
def test_atr_df_none_returns_none(indicators_cache):
    indicators_cache.rates_df = None
    assert ATR().calculate_atr("X", 16385) is None


def test_atr_constant_tr(indicators_cache):
    # high-low=1.0 на каждом баре, ряд монотонный → TR=1.0 → rolling(14).mean()=1.0
    indicators_cache.rates_df = _ramp_df(20)
    res = ATR().calculate_atr("X", 16385)
    assert res.iloc[-1] == pytest.approx(1.0)
    assert res.isna().sum() == 13  # первые 13 — NaN (rolling 14)


# --- MACD.calculate_macd_manual ---
def test_macd_manual_too_short_returns_none_triple(indicators_cache):
    indicators_cache.rates_df = _ramp_df(30)  # < 45 (slow26+signal9+10)
    assert MACD().calculate_macd_manual("X", 16385) == (None, None, None)


def test_macd_manual_df_none(indicators_cache):
    indicators_cache.rates_df = None
    assert MACD().calculate_macd_manual("X", 16385) == (None, None, None)


def test_macd_manual_happy_returns_three_floats(indicators_cache):
    indicators_cache.rates_df = _ramp_df(60)
    hist, prev, signal = MACD().calculate_macd_manual("X", 16385)
    assert isinstance(hist, float) and isinstance(prev, float) and isinstance(signal, float)
    # монотонный рост close → MACD-гистограмма положительна
    assert hist > 0


# --- RSI.get_rsi_talib ---
def test_rsi_df_none(indicators_cache):
    indicators_cache.rates_df = None
    assert RSI().get_rsi_talib("X", 16385) is None


def test_rsi_adds_rsi_column(indicators_cache):
    indicators_cache.rates_df = _ramp_df(100)
    out = RSI().get_rsi_talib("X", 16385)
    assert "RSI" in out.columns
    # монотонный рост → RSI стремится к 100 в хвосте
    assert out["RSI"].iloc[-1] > 50


# --- MovingAverage.get_ma_for_symbol ---
def test_get_ma_for_symbol_df_none(indicators_cache):
    indicators_cache.rates_df = None
    assert MovingAverage().get_ma_for_symbol("X", 16385, 5) is None


def test_get_ma_for_symbol_price_type_high(indicators_cache):
    indicators_cache.rates_df = _ramp_df(20)
    res = MovingAverage().get_ma_for_symbol("X", 16385, 3, ma_type="SMA", price_type="high")
    # SMA(3) от high; последний = mean последних 3 high
    expected = float(pd.Series(indicators_cache.rates_df["high"]).rolling(3).mean().iloc[-1])
    assert res.iloc[-1] == pytest.approx(expected)


# --- BullsBearsPower.get_bulls_bears_power ---
def test_bulls_bears_df_none(indicators_cache):
    indicators_cache.rates_df = None
    assert BullsBearsPower().get_bulls_bears_power("X", 16385) == (None, None)


def test_bulls_bears_values(indicators_cache):
    indicators_cache.rates_df = _ramp_df(30)
    bulls, bears = BullsBearsPower().get_bulls_bears_power("X", 16385)
    # bulls = high - ema(close); bears = low - ema(close); high>close>low → bulls>0>...
    assert bulls is not None and bears is not None
    assert bulls > bears  # high-ema > low-ema всегда


# --- Alligator composition + IsNewBar ---
def test_alligator_df_passthrough(indicators_cache):
    indicators_cache.rates_df = _ramp_df(5)
    out = Alligator().Df("X", 16385)
    assert out is indicators_cache.rates_df


def test_is_new_bar_first_time_true():
    df = pd.DataFrame({"time": [100, 101]})
    is_new, t = Alligator().IsNewBar(df, None, 16385)
    assert is_new is True and t == 100


def test_is_new_bar_changed_true():
    df = pd.DataFrame({"time": [200, 201]})
    is_new, t = Alligator().IsNewBar(df, 100, 16385)
    assert is_new is True and t == 200


def test_is_new_bar_same_false():
    df = pd.DataFrame({"time": [100, 101]})
    is_new, t = Alligator().IsNewBar(df, 100, 16385)
    assert is_new is False and t == 100


def test_alligator_main_data_shapes(indicators_cache):
    df = _ramp_df(20)
    median, jaw, teeth, lips, open_price = Alligator().MainData(df)
    # medianPrice = (high+low)/2 поэлементно; open_price = последний open
    assert median.iloc[-1] == pytest.approx((df["high"].iloc[-1] + df["low"].iloc[-1]) / 2)
    assert open_price == df["open"].iloc[-1]
    assert len(jaw) == len(df) and len(teeth) == len(df) and len(lips) == len(df)
