"""
Общие хелперы для price-action стратегий.

Предусмотрены для повторного использования в стратегиях:
  - Pin-bar детекция (тень ≥ 3 × тела)
  - Engulfing детекция (тело поглощает ≥ 80% предыдущего)
  - Наклон MA (в градусах, через полиномиальную регрессию)
  - Фракталы Билла Вильямса (5-барный паттерн)
"""

import numpy as np
import pandas as pd


# ── Pin-bar ──────────────────────────────────────────────────────────────

def is_bullish_pin_bar(row, tail_body_ratio: float = 3.0) -> bool:
    """Бычий пин-бар: длинная нижняя тень (≥ ratio × тело), тело в верхней трети."""
    o = float(row['open']);  c = float(row['close'])
    h = float(row['high']);  l = float(row['low'])
    body = abs(c - o)
    rng  = h - l
    if rng <= 0:
        return False
    lower_tail = min(o, c) - l
    upper_tail = h - max(o, c)
    # Тело должно быть > 0 чтобы была явная свеча
    if body <= 0:
        return False
    # Нижняя тень ≥ ratio × тела и длиннее верхней
    return lower_tail >= tail_body_ratio * body and lower_tail > upper_tail


def is_bearish_pin_bar(row, tail_body_ratio: float = 3.0) -> bool:
    """Медвежий пин-бар: длинная верхняя тень (≥ ratio × тело)."""
    o = float(row['open']);  c = float(row['close'])
    h = float(row['high']);  l = float(row['low'])
    body = abs(c - o)
    rng  = h - l
    if rng <= 0:
        return False
    lower_tail = min(o, c) - l
    upper_tail = h - max(o, c)
    if body <= 0:
        return False
    return upper_tail >= tail_body_ratio * body and upper_tail > lower_tail


# ── Engulfing ────────────────────────────────────────────────────────────

def _body_low_high(row):
    o = float(row['open']);  c = float(row['close'])
    return (min(o, c), max(o, c))


def is_bullish_engulfing(prev, curr, overlap: float = 0.8) -> bool:
    """Бычье поглощение: медвежья свеча + бычья свеча, тело которой перекрывает
    тело предыдущей минимум на `overlap` (0.8 = 80%)."""
    prev_o = float(prev['open']);  prev_c = float(prev['close'])
    curr_o = float(curr['open']);  curr_c = float(curr['close'])
    # Предыдущая — красная, текущая — зелёная
    if not (prev_c < prev_o and curr_c > curr_o):
        return False
    prev_body = abs(prev_o - prev_c)
    if prev_body <= 0:
        return False
    prev_lo, prev_hi = _body_low_high(prev)
    curr_lo, curr_hi = _body_low_high(curr)
    # Пересечение тел
    inter = max(0.0, min(curr_hi, prev_hi) - max(curr_lo, prev_lo))
    return inter >= overlap * prev_body and curr_hi >= prev_hi and curr_lo <= prev_lo * 1.0  # тело текущей шире


def is_bearish_engulfing(prev, curr, overlap: float = 0.8) -> bool:
    """Медвежье поглощение."""
    prev_o = float(prev['open']);  prev_c = float(prev['close'])
    curr_o = float(curr['open']);  curr_c = float(curr['close'])
    if not (prev_c > prev_o and curr_c < curr_o):
        return False
    prev_body = abs(prev_o - prev_c)
    if prev_body <= 0:
        return False
    prev_lo, prev_hi = _body_low_high(prev)
    curr_lo, curr_hi = _body_low_high(curr)
    inter = max(0.0, min(curr_hi, prev_hi) - max(curr_lo, prev_lo))
    return inter >= overlap * prev_body and curr_hi >= prev_hi and curr_lo <= prev_lo


# ── MA Slope ─────────────────────────────────────────────────────────────

def ma_slope_deg(series: pd.Series, lookback: int = 20) -> float:
    """Угол наклона MA за последние `lookback` баров в градусах.
    Нормализуется на среднее значение серии, чтобы цифры были сопоставимы
    между инструментами разного диапазона цен.
    Возвращает NaN при недостатке данных."""
    if len(series) < lookback:
        return float('nan')
    y = series.iloc[-lookback:].to_numpy(dtype=float)
    if np.any(np.isnan(y)):
        return float('nan')
    mean = float(np.mean(y))
    if mean == 0:
        return float('nan')
    x = np.arange(lookback, dtype=float)
    # slope в % от среднего за один бар → угол
    slope = np.polyfit(x, y, 1)[0] / mean
    return float(np.degrees(np.arctan(slope * 100.0)))


# ── Williams Fractals (5-bar) ────────────────────────────────────────────

def williams_fractals(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    """Добавляет колонки `fractal_up` и `fractal_down` по методу Билла Вильямса.
    n=2 соответствует классическому 5-барному фракталу (по 2 бара слева и справа
    от центрального). Колонки ставятся в True на индексе центрального бара.
    """
    highs = df['high'].to_numpy(dtype=float)
    lows  = df['low'].to_numpy(dtype=float)
    size  = len(df)
    up    = np.zeros(size, dtype=bool)
    down  = np.zeros(size, dtype=bool)
    for i in range(n, size - n):
        window_h = highs[i - n:i + n + 1]
        window_l = lows [i - n:i + n + 1]
        if highs[i] == window_h.max() and np.sum(window_h == highs[i]) == 1:
            up[i] = True
        if lows[i] == window_l.min() and np.sum(window_l == lows[i]) == 1:
            down[i] = True
    df = df.copy()
    df['fractal_up']   = up
    df['fractal_down'] = down
    return df


def last_fractals(df: pd.DataFrame, up: bool, count: int = 3) -> list[float]:
    """Возвращает последние `count` цен верхних (up=True) или нижних (up=False)
    фракталов, порядок от свежего к старому. Колонки fractal_up/fractal_down
    должны быть вычислены заранее."""
    col  = 'fractal_up' if up else 'fractal_down'
    src  = 'high' if up else 'low'
    if col not in df.columns:
        return []
    mask = df[col].to_numpy(dtype=bool)
    vals = df[src].to_numpy(dtype=float)
    idxs = np.where(mask)[0]
    if len(idxs) == 0:
        return []
    # от свежего к старому
    return [float(vals[i]) for i in idxs[::-1][:count]]
