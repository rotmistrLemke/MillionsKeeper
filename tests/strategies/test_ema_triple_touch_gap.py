"""Находка #2: ema_triple_touch — re-entry-семантика подсчёта тестов зоны.

Тест зоны засчитывается ОДИН раз за «провал» в зону: соседние бары с закрытием
внутри зоны не должны считаться отдельными тестами. Новый тест засчитывается
только после того, как цена закрылась ВНЕ зоны (провал завершён) и снова вошла.
"""
import pandas as pd

from strategies.ema_triple_touch import EmaTripleTouchStrategy


def _row(*, close, high, low, zone_hi, zone_lo, ema200=100.0,
         cross_up=False, cross_down=False):
    return pd.Series({
        "ema200": ema200,
        "cross20_50_up": cross_up,
        "cross20_50_down": cross_down,
        "zone_hi": zone_hi,
        "zone_lo": zone_lo,
        "close": close,
        "high": high,
        "low": low,
        "time": None,
    })


def test_consecutive_inside_bars_count_as_one_test():
    s = EmaTripleTouchStrategy()
    # UP-кросс баром, закрытым ВЫШЕ зоны → тест не засчитан, сторона UP.
    s._update_state(_row(close=120, high=121, low=119, zone_hi=110, zone_lo=108, cross_up=True))
    assert s._cross_side == "UP"
    assert s._touch_count == 0

    # Три подряд бара с закрытием ВНУТРИ зоны — это один «провал» → 1 тест.
    for _ in range(3):
        s._update_state(_row(close=109, high=111, low=107, zone_hi=110, zone_lo=108))
    assert s._touch_count == 1

    # Бар с закрытием ВНЕ зоны — провал завершён.
    s._update_state(_row(close=120, high=121, low=119, zone_hi=110, zone_lo=108))
    assert s._touch_count == 1

    # Повторный заход в зону → второй тест.
    s._update_state(_row(close=109, high=111, low=107, zone_hi=110, zone_lo=108))
    assert s._touch_count == 2


def test_cross_resets_touch_count():
    s = EmaTripleTouchStrategy()
    s._update_state(_row(close=120, high=121, low=119, zone_hi=110, zone_lo=108, cross_up=True))
    s._update_state(_row(close=109, high=111, low=107, zone_hi=110, zone_lo=108))
    assert s._touch_count == 1
    # Обратный кросс — счётчик и сторона сбрасываются.
    s._update_state(_row(close=90, high=91, low=89, zone_hi=95, zone_lo=93, cross_down=True))
    assert s._cross_side == "DOWN"
    assert s._touch_count == 0
