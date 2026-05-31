"""A3: поведенческие сценарии — намеренный вход OHLC → ожидаемый сигнал.

Каждый тест строит синтетический сценарий под логику входа конкретной стратегии
и утверждает ожидаемый сигнал на релевантной строке. Стратегии инстанцируются
свежими (не через runtime), чтобы внутреннее состояние не протекало между тестами.
"""
import pandas as pd

from strategies.ema_cross import EmaCrossStrategy
from tests.strategies import builders


def _last_signal(strategy, df):
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    row = df.iloc[-1]
    if strategy.is_flat(row):
        return None
    return strategy.get_entry_signal(row)


def test_ema_cross_uptrend_gives_buy():
    # Устойчивый рост → EMA50 > EMA200 → BUY
    assert _last_signal(EmaCrossStrategy(), builders.trend_up()) == "BUY"


def test_ema_cross_downtrend_gives_sell():
    # Устойчивое падение → EMA50 < EMA200 → SELL
    assert _last_signal(EmaCrossStrategy(), builders.trend_down()) == "SELL"
