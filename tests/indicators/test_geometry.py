"""Характеризация геометрии indicators.py (E6). Прод не трогаем."""
import math
import numpy as np
import pandas as pd
import pytest
from indicators import Alligator, MovingAverage, AdaptiveMovingAverage


# --- Alligator.angle (тернарник по degrees КОРРЕКТЕН — НЕ находка) ---
def test_angle_degrees_true(indicators_cache):
    # y=(1900.05-1900.00)/0.01=5; atan2(5,50)→5.71°→int("6")=6
    assert Alligator().angle(1900.05, 1900.00, "X", 100) == 6


def test_angle_degrees_false_returns_radians(indicators_cache):
    # degrees=False → int(f"{angle_rad:.0f}") = int("0") = 0 (ветка реально работает)
    assert Alligator().angle(1900.05, 1900.00, "X", 100, degrees=False) == 0


def test_angle_negative_slope(indicators_cache):
    assert Alligator().angle(1899.00, 1900.00, "X", 100) == -63


# --- Alligator.CountDecimalPlace ---
def test_count_decimal_place_2(indicators_cache):
    indicators_cache.symbol_info.point = 0.01
    assert Alligator().CountDecimalPlace("X") == 2


def test_count_decimal_place_3(indicators_cache):
    indicators_cache.symbol_info.point = 0.001
    assert Alligator().CountDecimalPlace("X") == 3


# --- MovingAverage._get_angles ---
def test_get_angles_too_short_none(indicators_cache):
    res = MovingAverage()._get_angles(pd.Series([1.0]), pd.Series([1.0]), "X", atr_value=1.0)
    assert res is None


def test_get_angles_nan_none(indicators_cache):
    res = MovingAverage()._get_angles(
        pd.Series([1.0, float("nan")]), pd.Series([1.0, 2.0]), "X", atr_value=1.0)
    assert res is None


def test_get_angles_scalar_atr(indicators_cache):
    res = MovingAverage()._get_angles(
        pd.Series([1.0, 3.0]), pd.Series([2.0, 2.5]), "X", atr_value=1.0)
    assert res["current_fast"] == 3.0 and res["current_slow"] == 2.5
    assert res["angle_fast"] == 76 and res["angle_slow"] == 45


def test_get_angles_series_atr(indicators_cache):
    # atr_value как Series → берётся .iloc[-1]
    res = MovingAverage()._get_angles(
        pd.Series([1.0, 3.0]), pd.Series([2.0, 2.5]), "X",
        atr_value=pd.Series([9.9, 1.0]))
    assert res["angle_fast"] == 76  # тот же x=1.0/point


# --- MovingAverage.ma_cross_signal ---
def test_ma_cross_buy(indicators_cache):
    res = MovingAverage().ma_cross_signal(
        pd.Series([1.0, 3.0]), pd.Series([2.0, 2.5]), "X", atr_value=1.0)
    assert res["signal"] == "BUY"
    assert res["strength"] == pytest.approx(0.5)


def test_ma_cross_none_angles_no_signal(indicators_cache):
    res = MovingAverage().ma_cross_signal(
        pd.Series([1.0]), pd.Series([1.0]), "X", atr_value=1.0)
    assert res == {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0,
                   'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}


# --- MovingAverage.ma_critical_angle ---
def test_ma_critical_buy(indicators_cache):
    # angle_fast=76 > 65 → BUY
    res = MovingAverage().ma_critical_angle(
        pd.Series([1.0, 3.0]), pd.Series([2.0, 2.5]), "X", atr_value=1.0)
    assert res["signal"] == "BUY"


def test_ma_critical_sell(indicators_cache):
    # angle_fast=-76 < -65 → SELL
    res = MovingAverage().ma_critical_angle(
        pd.Series([3.0, 1.0]), pd.Series([2.5, 2.0]), "X", atr_value=1.0)
    assert res["signal"] == "SELL"


def test_ma_critical_no_signal(indicators_cache):
    # пологий наклон → angle_fast≈0 → NO_SIGNAL
    res = MovingAverage().ma_critical_angle(
        pd.Series([1.900, 1.901]), pd.Series([1.900, 1.900]), "X", atr_value=1.0)
    assert res["signal"] == "NO_SIGNAL"


# --- AdaptiveMovingAverage.checkFlat + находка #8 ---
def test_checkflat_constant_is_flat(indicators_cache):
    # константный close → KAMA константа → angle 0 → flat True
    df = pd.DataFrame({"close": [1900.0] * 30})
    res = AdaptiveMovingAverage().checkFlat(df, "X", {}, atr_value=3.0)
    assert res == {"value": True, "angle": 0}
