"""Характеризация числовых ядер indicators.py (E6). Прод не трогаем.
Литералы вычислены с реального прогона алгоритмов на фиксированных входах."""
import math
import numpy as np
import pandas as pd
import pytest
from indicators import Alligator, MovingAverage, ADX


D = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


# --- smma (Alligator и MovingAverage идентичны) ---
def test_alligator_smma_period3():
    res = list(Alligator().smma(D, 3))
    # i<3 → nan; i==3 → mean(data[0:3])=2.0; затем (prev*2+x)/3
    assert math.isnan(res[0]) and math.isnan(res[1]) and math.isnan(res[2])
    assert res[3:] == [2.0, 3.0, 4.0]


def test_movingaverage_smma_matches_alligator():
    a = list(Alligator().smma(D, 3))
    m = list(MovingAverage().smma(D, 3))
    # обе реализации идентичны (NaN сравниваем отдельно)
    assert a[3:] == m[3:] == [2.0, 3.0, 4.0]


# --- sma / ema / wma ---
def test_sma_period3():
    res = MovingAverage().sma(D, 3)
    assert list(res[2:]) == [2.0, 3.0, 4.0, 5.0]
    assert math.isnan(res.iloc[0]) and math.isnan(res.iloc[1])


def test_ema_period3_adjust_false():
    res = list(MovingAverage().ema(D, 3))
    assert res == pytest.approx([1.0, 1.5, 2.25, 3.125, 4.0625, 5.03125])


def test_wma_period3():
    res = MovingAverage().wma(D, 3)
    assert list(res[2:]) == pytest.approx([2.3333333333, 3.3333333333,
                                           4.3333333333, 5.3333333333])
    assert math.isnan(res.iloc[0]) and math.isnan(res.iloc[1])


# --- calculate_ma dispatch ---
def test_calculate_ma_dispatch_sma():
    res = MovingAverage().calculate_ma(D, 3, "sma")  # case-insensitive
    assert list(res[2:]) == [2.0, 3.0, 4.0, 5.0]


def test_calculate_ma_dispatch_ema():
    res = list(MovingAverage().calculate_ma(D, 3, "EMA"))
    assert res[-1] == pytest.approx(5.03125)


def test_calculate_ma_dispatch_smma():
    res = list(MovingAverage().calculate_ma(D, 3, "SMMA"))
    assert res[3:] == [2.0, 3.0, 4.0]


def test_calculate_ma_unknown_raises():
    with pytest.raises(ValueError):
        MovingAverage().calculate_ma(D, 3, "HULL")


# --- ADX.ExponentialMA ---
def test_exponential_ma_i_zero_returns_prev():
    assert ADX().ExponentialMA(0, 2, 5.0, [1, 2, 3]) == 5.0


def test_exponential_ma_step():
    # (values[1]-prev)*2/(period+1)+prev = (9-5)*2/3+5
    assert ADX().ExponentialMA(1, 2, 5.0, [1, 9, 3]) == pytest.approx(7.6666666667)


# --- ADX.ADX (полный цикл на фиксированном входе) ---
def test_adx_full_pinned():
    high = [10.0, 11.0, 12.0, 13.0]
    low = [9.0, 10.0, 11.0, 12.0]
    close = [9.5, 10.5, 11.5, 12.5]
    adx, pdi, ndi = ADX().ADX(high, low, close, 2)
    assert adx == pytest.approx([0, 66.6666666667, 88.8888888889, 96.2962962963])
    assert pdi == pytest.approx([0, 44.4444444444, 59.2592592593, 64.1975308642])
    assert ndi == [0.0, 0.0, 0.0, 0.0]  # вся сила вверх → minus DI = 0


def test_adx_tr_zero_branch():
    # high==low==close на всех барах → tr=0 → raw_di=0 → всё 0
    flat = [5.0, 5.0, 5.0]
    adx, pdi, ndi = ADX().ADX(flat, flat, flat, 2)
    assert adx == [0, 0, 0] and pdi == [0, 0, 0] and ndi == [0, 0, 0]
