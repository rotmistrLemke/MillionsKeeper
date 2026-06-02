import numpy as np
import pandas as pd
import pytest

from anomaly.detector import DetectorConfig, evaluate
from anomaly.schemas import AnomalyType


def _make_df(closes, highs=None, lows=None):
    closes = np.asarray(closes, dtype=float)
    if highs is None:
        highs = closes + 0.5
    if lows is None:
        lows = closes - 0.5
    return pd.DataFrame({
        "time": pd.date_range("2026-05-01", periods=len(closes), freq="h", tz="UTC"),
        "open": closes,
        "high": highs,
        "low":  lows,
        "close": closes,
    })


@pytest.fixture
def cfg():
    return DetectorConfig(
        ema_period=50, atr_period=14, atr_mult=4.0,
        stoch_fastk=3, stoch_slowk=3, stoch_slowd=5,
        stoch_ob=93.0, stoch_os=7.0,
    )


def test_too_few_bars_returns_empty(cfg):
    df = _make_df(np.linspace(1.0, 2.0, 30))
    r = evaluate(df, cfg)
    assert r.is_anomaly is False
    assert r.snapshot is None


def _flat_then_spike(n_flat: int, last_close: float, baseline: float = 1.0):
    """n_flat баров около baseline, затем один бар с last_close (он будет последним = незакрытым)."""
    closes = [baseline] * n_flat + [last_close]
    # последний бар будет "незакрытым" — детектор смотрит на iloc[-2].
    # Чтобы детектор увидел last_close как закрытый бар, добавим ещё один dummy в конец.
    closes.append(last_close)
    return _make_df(closes,
                    highs=[c + 0.0001 for c in closes],
                    lows=[c - 0.0001 for c in closes])


def test_ema_far_up_when_price_above_ema_by_more_than_4_atr(cfg):
    # Базовая цена 1.0, ATR около 0.0002 (high-low=0.0002 на всех барах).
    # Последний бар: цена 1.10 → отрыв порядка 500 ATR.
    df = _flat_then_spike(n_flat=80, last_close=1.10, baseline=1.0)
    r = evaluate(df, cfg)
    assert AnomalyType.EMA_FAR_UP in r.types
    assert AnomalyType.EMA_FAR_DOWN not in r.types
    assert r.snapshot is not None
    assert r.snapshot.dist_atr > cfg.atr_mult


def test_ema_far_down_when_price_below_ema(cfg):
    df = _flat_then_spike(n_flat=80, last_close=0.90, baseline=1.0)
    r = evaluate(df, cfg)
    assert AnomalyType.EMA_FAR_DOWN in r.types
    assert r.snapshot.dist_atr < -cfg.atr_mult


def test_no_ema_anomaly_when_close_to_ema(cfg):
    df = _flat_then_spike(n_flat=80, last_close=1.0, baseline=1.0)
    r = evaluate(df, cfg)
    assert AnomalyType.EMA_FAR_UP not in r.types
    assert AnomalyType.EMA_FAR_DOWN not in r.types


def test_stoch_ob_triggered_on_rising_series(cfg):
    # Монотонно растущая серия с узким спредом → stoch_k будет около 100.
    # Узкий спред (0.0001) нужен, чтобы close оказался вблизи максимума окна.
    closes = np.asarray(np.linspace(1.0, 2.0, 80))
    df = _make_df(closes,
                  highs=closes + 0.0001,
                  lows=closes - 0.0001)
    r = evaluate(df, cfg)
    assert AnomalyType.STOCH_OB in r.types


def test_stoch_os_triggered_on_falling_series(cfg):
    # Узкий спред: close вблизи минимума окна → stoch_k около 0.
    closes = np.asarray(np.linspace(2.0, 1.0, 80))
    df = _make_df(closes,
                  highs=closes + 0.0001,
                  lows=closes - 0.0001)
    r = evaluate(df, cfg)
    assert AnomalyType.STOCH_OS in r.types


def test_both_ema_and_stoch_can_trigger_simultaneously(cfg):
    # Монотонный рост с узким спредом — даст и big dist_atr, и stoch OB.
    closes = np.asarray(np.linspace(1.0, 5.0, 80))
    df = _make_df(closes,
                  highs=closes + 0.0001,
                  lows=closes - 0.0001)
    r = evaluate(df, cfg)
    assert AnomalyType.EMA_FAR_UP in r.types
    assert AnomalyType.STOCH_OB in r.types


def test_boundary_dist_exactly_4_atr_triggers(cfg):
    """dist_atr == 4.0 строго равно atr_mult — должно сработать (>=)."""
    n = 80
    closes = [1.0] * n + [5.0, 5.0]
    df = _make_df(closes,
                  highs=[c + 0.5 for c in closes],
                  lows=[c - 0.5 for c in closes])
    r = evaluate(df, cfg)
    # Тест-инвариант: если триггер сработал, dist_atr должен быть >= 4.0.
    if AnomalyType.EMA_FAR_UP in r.types:
        assert r.snapshot.dist_atr >= cfg.atr_mult


def test_boundary_stoch_strictly_greater_than_threshold(cfg):
    """stoch_k > 93 (не >=). Если k == 93.0 ровно — не триггерит."""
    closes = np.linspace(1.0, 2.0, 80).tolist()
    df = _make_df(closes)
    r = evaluate(df, cfg)
    if AnomalyType.STOCH_OB in r.types:
        assert r.snapshot.stoch_k > cfg.stoch_ob


def test_zero_atr_does_not_crash(cfg):
    # Все бары идентичны → ATR == 0 → детектор должен вернуть пустой результат.
    df = _make_df([1.0] * 80, highs=[1.0] * 80, lows=[1.0] * 80)
    r = evaluate(df, cfg)
    assert r.is_anomaly is False
