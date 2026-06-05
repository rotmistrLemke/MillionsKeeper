"""Детерминированные синтетические OHLC DataFrame'ы для тестов стратегий.

Колонки: time, open, high, low, close, tick_volume — как у баров MT5.
Длина по умолчанию 300 баров (хватает на EMA200 и flat-avg период 50).
"""
import numpy as np
import pandas as pd

DEFAULT_N = 300
_BASE_PRICE = 2000.0  # порядок цены XAUUSD


def _assemble(closes: np.ndarray) -> pd.DataFrame:
    """Достраивает консистентный OHLC из серии close.

    open[i] = close[i-1] (open[0] = close[0]); high/low охватывают open и close
    с небольшим запасом, чтобы high >= max(open,close) и low <= min(open,close).
    """
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    opens = np.empty(n, dtype=float)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]

    span = np.abs(closes - opens)
    pad = np.maximum(span * 0.25, 0.5)
    highs = np.maximum(opens, closes) + pad
    lows = np.minimum(opens, closes) - pad

    times = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({
        "time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": np.full(n, 100, dtype=int),
    })


def trend_up(n: int = DEFAULT_N, step: float = 1.0) -> pd.DataFrame:
    """Устойчивый восходящий тренд."""
    closes = _BASE_PRICE + np.arange(n) * step
    return _assemble(closes)


def trend_down(n: int = DEFAULT_N, step: float = 1.0) -> pd.DataFrame:
    """Устойчивый нисходящий тренд."""
    closes = _BASE_PRICE - np.arange(n) * step
    return _assemble(closes)


def flat(n: int = DEFAULT_N, amplitude: float = 0.3) -> pd.DataFrame:
    """Узкий диапазон без тренда — активирует флэт-гард BaseStrategy."""
    rng = np.random.default_rng(42)
    closes = _BASE_PRICE + rng.uniform(-amplitude, amplitude, size=n)
    return _assemble(closes)


def from_closes(closes) -> pd.DataFrame:
    """Кастомная серия close — для точечных поведенческих сценариев."""
    return _assemble(closes)
