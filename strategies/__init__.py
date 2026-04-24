from strategies.base import BaseStrategy
from strategies.ema_scalp import EmaScalpStrategy
from strategies.bollinger_scalp import BollingerScalpStrategy
from strategies.stochastic_scalp import StochasticScalpStrategy
from strategies.sr_bounce import SrBounceStrategy
from strategies.ema_pullback import EmaPullbackStrategy
from strategies.ema_cross import EmaCrossStrategy
from strategies.ema_cross_inverse import EmaCrossInverseStrategy
from strategies.cci_rsi import CciRsiStrategy
from strategies.fibonacci_retracement import FibonacciRetracementStrategy
from strategies.macd_hist import MacdHistStrategy
from strategies.candle_reversal import CandleReversalStrategy
from strategies.default_hedge import DefaultHedgeStrategy
from strategies.default_inverse import DefaultInverseStrategy
from strategies.mean_revert_ema import MeanRevertEmaStrategy
from strategies.ema50_pullback import Ema50PullbackStrategy
from strategies.ema_triple_touch import EmaTripleTouchStrategy
from strategies.market_phase import MarketPhaseStrategy
from strategies.combined_a_plus import CombinedAPlusStrategy
from strategies.ema50_rejection import Ema50RejectionStrategy
from strategies.ema50_overstretch import Ema50OverstretchStrategy

STRATEGIES = {
    # H1 внутридневные/среднесрочные
    'sr_bounce':             SrBounceStrategy,
    'ema_pullback':          EmaPullbackStrategy,
    'ema_cross':             EmaCrossStrategy,
    'ema_cross_inverse':     EmaCrossInverseStrategy,
    'cci_rsi':               CciRsiStrategy,
    'fibonacci_retracement': FibonacciRetracementStrategy,
    'macd_hist':             MacdHistStrategy,
    'candle_reversal':       CandleReversalStrategy,
    'default_hedge':         DefaultHedgeStrategy,
    'default_inverse':       DefaultInverseStrategy,
    # Скальпинговые (предыдущие)
    'sar_adx':               EmaScalpStrategy,
    'donchian_breakout':     BollingerScalpStrategy,
    'triple_ema':            StochasticScalpStrategy,
    # Price-action H4/D1
    'mean_revert_ema':       MeanRevertEmaStrategy,
    'ema50_pullback':        Ema50PullbackStrategy,
    'ema_triple_touch':      EmaTripleTouchStrategy,
    'market_phase':          MarketPhaseStrategy,
    'combined_a_plus':       CombinedAPlusStrategy,
    'ema50_rejection':       Ema50RejectionStrategy,
    'ema50_overstretch':     Ema50OverstretchStrategy,
}
