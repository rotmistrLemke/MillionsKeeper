import MetaTrader5 as mt5
import pandas as pd


# ─── Ночная блокировка торговли (23:50–05:00) ────────────────────────────

def _is_night_bar(bar_time: pd.Timestamp) -> bool:
    """True, если бар попадает в окно ночной блокировки 23:50–05:00."""
    h, m = bar_time.hour, bar_time.minute
    if h >= 23 and m >= 50:
        return True
    if h < 5:
        return True
    return False


def _is_daily_or_higher_tf(timeframe) -> bool:
    """D1/W1/MN1 — weekend-фильтр (по часам в баре) для них некорректен:
    дневной бар у брокеров стоит на hour=0, что ложно совпадает с
    is_monday_early и отрезает каждый понедельник."""
    return timeframe in (mt5.TIMEFRAME_D1, mt5.TIMEFRAME_W1, mt5.TIMEFRAME_MN1)
