"""Чистые helper-функции, общие для обоих движков бэктеста (слайс D2).

Вынесено из дублирующихся фрагментов `_run_default_on_df`/`_run_strategy_on_df`.
Только чистые (без состояния) функции — stateful dd-block остаётся замыканием
внутри каждого движка.
"""
import pandas as pd


def next_monday(ts: pd.Timestamp) -> pd.Timestamp:
    """Полночь ближайшего следующего понедельника (для снятия dd-блокировки)."""
    days = 7 - ts.weekday() if ts.weekday() > 0 else 7
    return (ts + pd.Timedelta(days=days)).normalize()


def is_weekend_block(weekday: int, hour: int) -> bool:
    """Окно блокировки вокруг выходных: пт ≥23:00, сб/вс, пн <02:00."""
    is_friday_close = weekday == 4 and hour >= 23
    is_weekend      = weekday in (5, 6)
    is_monday_early = weekday == 0 and hour < 2
    return is_friday_close or is_weekend or is_monday_early
