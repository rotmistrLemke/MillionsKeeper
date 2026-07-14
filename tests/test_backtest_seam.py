"""C/Task1: inner-функции движка прогоняются на синтетике без MT5."""
from backtest import _run_default_on_df, _run_strategy_on_df, BacktestResult
from strategies.ema_cross import EmaCrossStrategy
from tests.strategies import builders


def test_default_inner_runs_without_mt5():
    df = builders.trend_up(300)
    res = _run_default_on_df(
        df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0,
    )
    assert isinstance(res, BacktestResult)
    assert isinstance(res.trades, list)


def test_strategy_inner_runs_without_mt5():
    df = builders.trend_up(300)
    res = _run_strategy_on_df(
        EmaCrossStrategy(), df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0,
        sl_points=0.0, tp_points=0.0, breakeven_points=0.0, trail_points=0.0,
    )
    assert isinstance(res, BacktestResult)
    assert isinstance(res.trades, list)
