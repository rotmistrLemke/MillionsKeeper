"""Флэт-фильтр должен работать в движке так же, как в живой торговле.

`IndicatorAgent` гасит бар через `strategy.is_flat(row)` до того, как сигнал
вообще посчитан, а движок бэктеста этот фильтр не вызывал вовсе. У четырёх
стратегий (cci_rsi, ema_pullback, sar_adx, triple_ema) фильтр не заглушён и
гасит порядка 44 % баров — модельных входов выходило заметно больше живых,
и сравнение живого трека с бэктестом по ним было бессмысленным.

Неделя 07–11.09.2026 показала это в чистом виде: cci_rsi не сделала ни одной
сделки при 62 отказах FLAT, тогда как модель по ней входы показывала.
"""
from backtest import _run_strategy_on_df
from strategies.base import BaseStrategy
from tests.strategies import builders


class _Spy(BaseStrategy):
    """Минимальная стратегия: флэт задаётся снаружи, входы считаются.

    Наследуемся от BaseStrategy, а не имитируем её: движок опирается на
    весь контракт, и самодельная заглушка расходится с ним незаметно.
    """

    def __init__(self, flat: bool):
        super().__init__()
        self._flat = flat
        self.entry_calls = 0
        self.flat_prepared = False

    def compute_indicators(self, df):
        return df

    def compute_flat_indicators(self, df):
        self.flat_prepared = True
        return df

    def is_flat(self, row) -> bool:
        return self._flat

    def get_entry_signal(self, row):
        self.entry_calls += 1
        return 'BUY'

    def get_exit_signal(self, row, position: dict) -> bool:
        return False

    def get_sl_tp(self, row, signal: str, point: float):
        return 0.0, 0.0


def _run(strategy):
    return _run_strategy_on_df(
        strategy, builders.trend_up(300), point=0.01, symbol_info=None,
        skip_weekend_filter=True, spread_points=0, deposit=0.0, risk_pct=80,
        fixed_volume=0.0, sl_points=0.0, tp_points=0.0,
        breakeven_points=0.0, trail_points=0.0,
    )


def test_flat_bars_produce_no_trades():
    strategy = _Spy(flat=True)
    result = _run(strategy)
    assert result.trades == []


def test_flat_bar_does_not_even_ask_for_a_signal():
    """Живой путь сигнал на флэтовом баре не запрашивает: get_entry_signal
    меняет состояние стратегии (_blocked_side и счётчики касаний). Движок,
    спрашивающий его вхолостую, расходится с живым не только числом сделок."""
    strategy = _Spy(flat=True)
    _run(strategy)
    assert strategy.entry_calls == 0


def test_non_flat_bars_still_trade():
    strategy = _Spy(flat=False)
    result = _run(strategy)
    assert len(result.trades) > 0
    assert strategy.entry_calls > 0


def test_engine_prepares_flat_indicators():
    """Колонки flat_* считает compute_flat_indicators — без вызова
    базовый is_flat вернёт True на каждом баре и погасит всё подряд."""
    strategy = _Spy(flat=False)
    _run(strategy)
    assert strategy.flat_prepared is True


def test_real_strategy_without_flat_columns_is_not_silenced():
    """Регрессия: стратегии, заглушившие фильтр (is_flat → False), не должны
    пострадать от того, что колонок flat_* в их df нет."""
    from strategies.ema_cross import EmaCrossStrategy
    result = _run_strategy_on_df(
        EmaCrossStrategy(), builders.trend_up(300), point=0.01, symbol_info=None,
        skip_weekend_filter=True, spread_points=0, deposit=0.0, risk_pct=80,
        fixed_volume=0.0, sl_points=0.0, tp_points=0.0,
        breakeven_points=0.0, trail_points=0.0,
    )
    assert len(result.trades) > 0
