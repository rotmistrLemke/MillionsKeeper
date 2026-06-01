"""CLI бэктест-движка TradingHouse: разбор аргументов, запуск, вывод отчёта."""

import argparse
import MetaTrader5 as mt5
from datetime import datetime
from authenticator import MT5Auth
from account import Account
from strategies import STRATEGIES
from backtest_engine.engine import run_backtest, run_strategy_backtest
from backtest_engine.report import print_report


def main():
    from strategies import STRATEGIES

    all_strategies = ['default'] + list(STRATEGIES.keys())

    parser = argparse.ArgumentParser(description='Бэктест торговых стратегий TradingHouse')
    parser.add_argument('--strategy', default='default',
                        choices=all_strategies + ['all'],
                        help='Стратегия: default, all или имя из strategies/')
    parser.add_argument('--symbol',    default='XAUUSDrfd')
    parser.add_argument('--bars',      type=int,   default=2000)
    parser.add_argument('--spread',    type=int,   default=0)
    parser.add_argument('--deposit',   type=float, default=0)
    parser.add_argument('--risk',      type=float, default=80)
    parser.add_argument('--volume',    type=float, default=0)
    parser.add_argument('--timeframe', default=None,
                        choices=['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'])
    parser.add_argument('--start',     default=None, help='YYYY-MM-DD')
    parser.add_argument('--end',       default=None, help='YYYY-MM-DD')
    args = parser.parse_args()

    tf_map = {
        'M1':  mt5.TIMEFRAME_M1,  'M5':  mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
        'H1':  mt5.TIMEFRAME_H1,  'H4':  mt5.TIMEFRAME_H4,
        'D1':  mt5.TIMEFRAME_D1,
    }

    date_from = datetime.strptime(args.start, '%Y-%m-%d') if args.start else None
    date_to   = datetime.strptime(args.end,   '%Y-%m-%d') if args.end   else None

    account = Account.account
    auth = MT5Auth(account)
    auth.login()

    # Определяем список стратегий для запуска
    if args.strategy == 'all':
        strategies_to_run = list(STRATEGIES.keys())
    elif args.strategy == 'default':
        strategies_to_run = ['default']
    else:
        strategies_to_run = [args.strategy]

    date_str = ''
    if date_from: date_str += f', с {args.start}'
    if date_to:   date_str += f' по {args.end}'

    for strat_name in strategies_to_run:
        if strat_name == 'default':
            tf_name  = args.timeframe or 'H1'
            timeframe = tf_map[tf_name]
            desc     = 'MA + MACD + RSI (основная)'
            print(f"\nЗапуск {desc}: {args.symbol}, {tf_name}, {args.bars} баров{date_str}...")
            result = run_backtest(
                args.symbol, timeframe, bars=args.bars, spread_points=args.spread,
                deposit=args.deposit, risk_pct=args.risk, fixed_volume=args.volume,
                date_from=date_from, date_to=date_to
            )
        else:
            strat    = STRATEGIES[strat_name]()
            tf_name  = args.timeframe or strat.default_timeframe
            timeframe = tf_map[tf_name]
            desc     = strat.description
            print(f"\nЗапуск {desc}: {args.symbol}, {tf_name}, {args.bars} баров{date_str}...")
            result = run_strategy_backtest(
                strat, args.symbol, timeframe, bars=args.bars, spread_points=args.spread,
                deposit=args.deposit, risk_pct=args.risk, fixed_volume=args.volume,
                date_from=date_from, date_to=date_to
            )

        print_report(desc, args.symbol, tf_name, result, deposit=args.deposit)
