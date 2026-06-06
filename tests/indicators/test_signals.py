"""Характеризация логики сигналов indicators.py (E6). Прод не трогаем."""
import pandas as pd
from indicators import MACD, MovingAverage, ADX, RSI


# --- MACD.MACD_signal ---
def test_macd_signal_buy():
    res = MACD().MACD_signal(2.0, 1.0, 0.0)
    assert res["signal"] == "BUY"
    assert res["hist_line"] == 2.0 and res["prev_hist_line"] == 1.0 and res["signal_line"] == 0.0


def test_macd_signal_sell():
    assert MACD().MACD_signal(-2.0, -1.0, 0.0)["signal"] == "SELL"


def test_macd_signal_no_signal_zero_hist():
    assert MACD().MACD_signal(0.0, -1.0, -1.0)["signal"] == "NO_SIGNAL"


def test_macd_signal_no_signal_not_rising():
    # hist>0 но hist<prev → NO_SIGNAL
    assert MACD().MACD_signal(1.0, 2.0, 0.0)["signal"] == "NO_SIGNAL"


# --- MovingAverage.ma_simple_signal ---
def test_ma_simple_buy():
    res = MovingAverage().ma_simple_signal(pd.Series([1.0, 3.0]), pd.Series([1.0, 2.0]))
    assert res["signal"] == "BUY"
    assert res["strength"] == 1.0
    assert res["current_fast"] == 3.0 and res["current_slow"] == 2.0


def test_ma_simple_sell():
    assert MovingAverage().ma_simple_signal(
        pd.Series([3.0, 1.0]), pd.Series([1.0, 2.0]))["signal"] == "SELL"


def test_ma_simple_equal_no_signal():
    assert MovingAverage().ma_simple_signal(
        pd.Series([2.0, 2.0]), pd.Series([1.0, 2.0]))["signal"] == "NO_SIGNAL"


def test_ma_simple_too_short():
    res = MovingAverage().ma_simple_signal(pd.Series([1.0]), pd.Series([1.0]))
    assert res == {'signal': 'NO_SIGNAL', 'strength': 0, 'current_fast': 0,
                   'current_slow': 0, 'angle_fast': 0, 'angle_slow': 0}


def test_ma_simple_nan_no_signal():
    res = MovingAverage().ma_simple_signal(
        pd.Series([1.0, float("nan")]), pd.Series([1.0, 2.0]))
    assert res["signal"] == "NO_SIGNAL"
    assert res["strength"] == 0


# --- ADX.ADX_signal ---
def test_adx_signal_buy():
    assert ADX().ADX_signal(30, 20, 10) == {"signal": "BUY"}


def test_adx_signal_sell():
    assert ADX().ADX_signal(30, 10, 20) == {"signal": "SELL"}


def test_adx_signal_weak_trend():
    assert ADX().ADX_signal(20, 30, 10) == {"signal": "NO_SIGNAL"}


def test_adx_signal_equal_di():
    assert ADX().ADX_signal(30, 15, 15) == {"signal": "NO_SIGNAL"}


# --- RSI.RSI_signal ---
def test_rsi_signal_buy():
    res = RSI().RSI_signal(60.0, 55.0, 50.0)
    assert res["signal"] == "BUY"
    assert res["rsi"] == 60.0 and res["prev_rsi"] == 55.0 and res["prev2_rsi"] == 50.0


def test_rsi_signal_sell():
    assert RSI().RSI_signal(40.0, 45.0, 50.0)["signal"] == "SELL"


def test_rsi_signal_above_window_no_signal():
    assert RSI().RSI_signal(80.0, 70.0, 60.0)["signal"] == "NO_SIGNAL"


def test_rsi_signal_boundary_50_no_signal():
    # rsi==50 не входит в (50,70) → NO_SIGNAL
    assert RSI().RSI_signal(50.0, 45.0, 40.0)["signal"] == "NO_SIGNAL"


# --- RSI.rsi_leave_extremum ---
def test_rsi_leave_overbought_true():
    assert RSI().rsi_leave_extremum(67.0, 75.0) is True


def test_rsi_leave_oversold_true():
    assert RSI().rsi_leave_extremum(33.0, 25.0) is True


def test_rsi_leave_still_overbought_false():
    assert RSI().rsi_leave_extremum(69.0, 75.0) is False


def test_rsi_leave_neutral_false():
    assert RSI().rsi_leave_extremum(55.0, 50.0) is False
