"""Facade бэктест-движка TradingHouse. Реализация — в пакете backtest_engine/.

Запуск CLI: python backtest.py [--strategy ...]
"""
from backtest_engine import (
    run_backtest, run_strategy_backtest,
    _run_default_on_df, _run_strategy_on_df,
    load_rates, BacktestResult,
)
from backtest_engine.cli import main

__all__ = [
    "run_backtest", "run_strategy_backtest",
    "_run_default_on_df", "_run_strategy_on_df",
    "load_rates", "BacktestResult", "main",
]

if __name__ == "__main__":
    main()
