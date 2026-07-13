from strategies.base import BaseStrategy
from strategies.ema_scalp import EmaScalpStrategy
from strategies.stochastic_scalp import StochasticScalpStrategy
from strategies.ema_pullback import EmaPullbackStrategy
from strategies.ema_cross import EmaCrossStrategy
from strategies.cci_rsi import CciRsiStrategy
from strategies.macd_hist import MacdHistStrategy
from strategies.aroon import AroonStrategy
from strategies.default_hedge import DefaultHedgeStrategy
from strategies.mean_revert_ema import MeanRevertEmaStrategy
from strategies.ema50_pullback import Ema50PullbackStrategy
from strategies.ema_triple_touch import EmaTripleTouchStrategy
from strategies.market_phase import MarketPhaseStrategy
from strategies.combined_a_plus import CombinedAPlusStrategy
from strategies.ema50_rejection import Ema50RejectionStrategy
from strategies.ema50_overstretch import Ema50OverstretchStrategy
from strategies.ema50_overstretch_mtf import Ema50OverstretchMtfStrategy

STRATEGIES = {
    # H1 внутридневные/среднесрочные
    'ema_pullback':          EmaPullbackStrategy,
    'ema_cross':             EmaCrossStrategy,
    'cci_rsi':               CciRsiStrategy,
    'macd_hist':             MacdHistStrategy,
    'aroon':                 AroonStrategy,
    'default_hedge':         DefaultHedgeStrategy,
    # Скальпинговые (предыдущие)
    'sar_adx':               EmaScalpStrategy,
    'triple_ema':            StochasticScalpStrategy,
    # Price-action H4/D1
    'mean_revert_ema':       MeanRevertEmaStrategy,
    'ema50_pullback':        Ema50PullbackStrategy,
    'ema_triple_touch':      EmaTripleTouchStrategy,
    'market_phase':          MarketPhaseStrategy,
    'combined_a_plus':       CombinedAPlusStrategy,
    'ema50_rejection':       Ema50RejectionStrategy,
    'ema50_overstretch':     Ema50OverstretchStrategy,
    'ema50_overstretch_mtf': Ema50OverstretchMtfStrategy,
}
