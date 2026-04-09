from strategies.base import BaseStrategy
from strategies.ema_scalp import EmaScalpStrategy
from strategies.bollinger_scalp import BollingerScalpStrategy
from strategies.stochastic_scalp import StochasticScalpStrategy
from strategies.range_breakout import RangeBreakoutStrategy
from strategies.ema_pullback import EmaPullbackStrategy
from strategies.cci_rsi import CciRsiStrategy
from strategies.fibonacci_retracement import FibonacciRetracementStrategy
from strategies.news_breakout import NewsBreakoutStrategy
from strategies.candle_reversal import CandleReversalStrategy

STRATEGIES = {
    # H1 внутридневные/среднесрочные
    'range_breakout':        RangeBreakoutStrategy,
    'ema_pullback':          EmaPullbackStrategy,
    'cci_rsi':               CciRsiStrategy,
    'fibonacci_retracement': FibonacciRetracementStrategy,
    'news_breakout':         NewsBreakoutStrategy,
    'candle_reversal':       CandleReversalStrategy,
    # Скальпинговые (предыдущие)
    'sar_adx':               EmaScalpStrategy,
    'donchian_breakout':     BollingerScalpStrategy,
    'triple_ema':            StochasticScalpStrategy,
}
