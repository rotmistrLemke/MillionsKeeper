"""A3: поведенческие сценарии — намеренный вход OHLC → ожидаемый сигнал.

Каждый тест строит синтетический сценарий под логику входа конкретной стратегии
и утверждает ожидаемый сигнал на релевантной строке. Стратегии инстанцируются
свежими (не через runtime), чтобы внутреннее состояние не протекало между тестами.
"""
import numpy as np
import pandas as pd

from strategies.ema_cross import EmaCrossStrategy
from strategies.ema_pullback import EmaPullbackStrategy
from strategies.cci_rsi import CciRsiStrategy
from strategies.macd_hist import MacdHistStrategy
from strategies.aroon import AroonStrategy
from strategies.default_hedge import DefaultHedgeStrategy
from strategies.ema_scalp import EmaScalpStrategy
from strategies.stochastic_scalp import StochasticScalpStrategy
from strategies.mean_revert_ema import MeanRevertEmaStrategy
from strategies.ema50_pullback import Ema50PullbackStrategy
from strategies.ema_triple_touch import EmaTripleTouchStrategy
from strategies.market_phase import MarketPhaseStrategy
from strategies.combined_a_plus import CombinedAPlusStrategy
from strategies.ema50_rejection import Ema50RejectionStrategy
from strategies.ema50_overstretch import Ema50OverstretchStrategy
from strategies.ema50_overstretch_mtf import Ema50OverstretchMtfStrategy
from tests.strategies import builders


def _append_bar(df, open_, high, low, close):
    """Возвращает копию df с одним добавленным баром (для крафтинга
    конкретной сигнальной свечи — пин-бар, отскок и т.п.)."""
    crafted = {
        "time": df["time"].iloc[-1] + pd.Timedelta(hours=1),
        "open": open_, "high": high, "low": low, "close": close,
        "tick_volume": 100,
    }
    return pd.concat([df, pd.DataFrame([crafted])], ignore_index=True)


def _any_signal_sequential(strategy, df):
    """Прогоняет get_entry_signal по всем барам (для стейтфул-стратегий и
    мульти-условных фильтров). Возвращает set встретившихся сигналов."""
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    seen = set()
    for i in range(len(df)):
        sig = strategy.get_entry_signal(df.iloc[i])
        if sig:
            seen.add(sig)
    return seen


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


# ── ema_pullback ──────────────────────────────────────────────────────────
# BUY: close>EMA200 + low касается EMA50 + бычий пин/поглощение.

def test_ema_pullback_uptrend_pin_gives_buy():
    base = list(2000 + np.arange(300) * 0.5)  # пологий тренд: EMA50 близко к цене
    df = _append_bar(builders.from_closes(base),
                     open_=2145.0, high=2146.0, low=2136.0, close=2145.5)
    # Крафтовый бар: маленькое бычье тело + длинная нижняя тень до EMA50.
    assert _last_signal(EmaPullbackStrategy(), df) == "BUY"


# ── cci_rsi ───────────────────────────────────────────────────────────────
# BUY: CCI пересёк +100 снизу + RSI>50 + close>EMA200.

def test_cci_rsi_cross_up_gives_buy():
    base = list(2000 + np.arange(285) * 1.0)
    closes = base + [base[-1]] * 14
    closes.append(closes[-1] + 18)     # импульс-бар: CCI пересекает +100
    assert _last_signal(CciRsiStrategy(), builders.from_closes(closes)) == "BUY"


def test_cci_rsi_cross_down_gives_sell():
    base = list(2000 - np.arange(285) * 1.0)
    closes = base + [base[-1]] * 14
    closes.append(closes[-1] - 18)
    assert _last_signal(CciRsiStrategy(), builders.from_closes(closes)) == "SELL"


# cci_rsi не подавляет входы во флэте: на builders.flat() выдаёт 16 сигналов
# (8 BUY + 8 SELL) при последовательном прогоне — flat→None тест неприменим
# (проверка только последнего бара давала ложную уверенность).


# ── macd_hist ─────────────────────────────────────────────────────────────
# BUY при hist > signal, SELL при hist < signal.
# В устойчивом тренде signal далеко от нуля, hist ~ 0 → сигнал контртрендовый.

def test_macd_hist_accelerating_up_gives_sell():
    closes = list(2000 + np.cumsum(np.arange(300) * 0.05))
    assert _last_signal(MacdHistStrategy(), builders.from_closes(closes)) == "SELL"


def test_macd_hist_accelerating_down_gives_buy():
    closes = list(2000 - np.cumsum(np.arange(300) * 0.05))
    assert _last_signal(MacdHistStrategy(), builders.from_closes(closes)) == "BUY"


# ── aroon ─────────────────────────────────────────────────────────────────
# BUY: Aroon Up > Aroon Down (устойчивый аптренд → каждый бар новый хай →
# Up=100, Down→0). SELL зеркально на даунтренде.

def test_aroon_uptrend_gives_buy():
    assert _last_signal(AroonStrategy(), builders.trend_up()) == "BUY"


def test_aroon_downtrend_gives_sell():
    assert _last_signal(AroonStrategy(), builders.trend_down()) == "SELL"


# ── default_hedge ─────────────────────────────────────────────────────────
# BUY: EMA8>EMA21 + MACD бычий + RSI в 55..70 и растёт. Нужен «дышащий» тренд,
# чтобы RSI не уходил в насыщение.

def test_default_hedge_breathing_uptrend_gives_buy():
    rng = np.random.default_rng(3)
    steps = rng.choice([1.5, -0.8], size=300, p=[0.62, 0.38])
    closes = list(2000 + np.cumsum(steps))
    assert _any_signal_sequential(DefaultHedgeStrategy(), builders.from_closes(closes)) == {"BUY"}


def test_default_hedge_breathing_downtrend_gives_sell():
    rng = np.random.default_rng(3)
    steps = rng.choice([-1.5, 0.8], size=300, p=[0.62, 0.38])
    closes = list(2000 + np.cumsum(steps))
    assert _any_signal_sequential(DefaultHedgeStrategy(), builders.from_closes(closes)) == {"SELL"}


# ── sar_adx (ema_scalp) ───────────────────────────────────────────────────

def test_sar_adx_smoke_no_exception():
    # TODO behavioral: SAR-флип и переключение +DI/-DI на развороте не совпадают
    # в один и тот же бар при детерминированном синтетическом тренде — точный
    # одновременный (flip + DI-cross + ADX>25) бар собрать надёжно не удаётся.
    s = EmaScalpStrategy()
    df = s.compute_indicators(builders.trend_up())
    df = s.compute_flat_indicators(df)
    for i in range(len(df)):
        s.get_entry_signal(df.iloc[i])  # не должно бросать


# ── triple_ema (stochastic_scalp) ─────────────────────────────────────────
# BUY: EMA8>EMA21>EMA50 + MACD hist>0 и растёт.

def test_triple_ema_accel_up_gives_buy():
    closes = list(2000 + np.cumsum(np.arange(300) * 0.05))
    assert _last_signal(StochasticScalpStrategy(), builders.from_closes(closes)) == "BUY"


def test_triple_ema_accel_down_gives_sell():
    closes = list(2000 - np.cumsum(np.arange(300) * 0.05))
    assert _last_signal(StochasticScalpStrategy(), builders.from_closes(closes)) == "SELL"


# triple_ema не подавляет входы во флэте: на builders.flat() выдаёт 109 сигналов
# (46 BUY + 63 SELL) при последовательном прогоне — flat→None тест неприменим
# (проверка только последнего бара давала ложную уверенность).


# ── mean_revert_ema ───────────────────────────────────────────────────────
# BUY: EMA10>EMA20 + бар в зоне EMA + бычий пин (не «улетел» от EMA10).

def test_mean_revert_ema_zone_pin_gives_buy():
    base = list(2000 + np.arange(300) * 0.5)
    df = _append_bar(builders.from_closes(base),
                     open_=2147.0, high=2147.5, low=2141.0, close=2147.3)
    assert _last_signal(MeanRevertEmaStrategy(), df) == "BUY"


# ── ema50_pullback ────────────────────────────────────────────────────────
# BUY: close>EMA200 + касание EMA50 + бычий пин/поглощение.

def test_ema50_pullback_uptrend_pin_gives_buy():
    base = list(2000 + np.arange(300) * 0.5)
    df = _append_bar(builders.from_closes(base),
                     open_=2145.0, high=2146.0, low=2130.0, close=2145.5)
    assert _last_signal(Ema50PullbackStrategy(), df) == "BUY"


# ── ema_triple_touch ──────────────────────────────────────────────────────

# Логика подсчёта тестов зоны (re-entry-семантика) покрыта юнит-тестом
# tests/strategies/test_ema_triple_touch_gap.py (находка #2 решена).
# Здесь — smoke: полноценный 3-touch сценарий на синтетике собрать сложно.
def test_ema_triple_touch_smoke_no_exception():
    # TODO behavioral: стейтфул-стратегия требует кросс EMA20/50 + ≥3 «теста»
    # зоны с закрытием ВНУТРИ зоны при close по нужную сторону EMA200 —
    # геометрию (close между EMA20 и EMA50 на 3 разнесённых барах) надёжно
    # синтезировать детерминированно затруднительно.
    s = EmaTripleTouchStrategy()
    df = s.compute_indicators(builders.trend_up())
    df = s.compute_flat_indicators(df)
    for i in range(len(df)):
        s.get_entry_signal(df.iloc[i])  # не должно бросать


# ── market_phase ──────────────────────────────────────────────────────────
# TREND_UP (наклон 200MA>thr, close>EMA200): BUY при пробое фрактального
# сопротивления.

def test_market_phase_trend_up_breakout_gives_buy():
    rng = np.random.default_rng(1)
    base = 2000 + np.arange(300) * 1.0 + rng.uniform(-3, 3, 300)
    closes = list(base)
    closes[-1] = closes[-2] + 25  # пробой сопротивления на последнем баре
    assert _last_signal(MarketPhaseStrategy(), builders.from_closes(closes)) == "BUY"


# ── combined_a_plus ───────────────────────────────────────────────────────
# Вход при score≥4/5. Пологий тренд + бычий пин у EMA50 даёт 4 фактора.

def test_combined_a_plus_uptrend_pin_gives_buy():
    base = list(2000 + np.arange(300) * 0.5)
    df = _append_bar(builders.from_closes(base),
                     open_=2145.0, high=2146.0, low=2130.0, close=2145.5)
    assert _last_signal(CombinedAPlusStrategy(), df) == "BUY"


# ── ema50_rejection ───────────────────────────────────────────────────────
# Стейтфул: сильный тренд (EMA50−EMA200≥2ATR) → откат под EMA50 → ретест
# обратно над EMA50 → BUY. Прогоняем последовательно.

def test_ema50_rejection_pullback_retest_gives_buy():
    up = list(2000 + np.arange(280) * 1.0)
    dip = list(np.linspace(up[-1], up[-1] - 25, 10))   # откат под EMA50
    rec = list(np.linspace(dip[-1], dip[-1] + 30, 10))  # ретест над EMA50
    closes = up + dip + rec
    assert _any_signal_sequential(Ema50RejectionStrategy(), builders.from_closes(closes)) == {"BUY"}


# ── ema50_overstretch ─────────────────────────────────────────────────────
# Фейд перерастяжения: EMA50>EMA200 + close≥EMA50+4.5ATR → SELL (зеркально BUY).

def test_ema50_overstretch_spike_up_gives_sell():
    base = list(2000 + np.arange(299) * 0.5)
    base.append(base[-1] + 30)  # резкий вынос вверх → перерастяжение
    assert _last_signal(Ema50OverstretchStrategy(), builders.from_closes(base)) == "SELL"


def test_ema50_overstretch_spike_down_gives_buy():
    base = list(2000 - np.arange(299) * 0.5)
    base.append(base[-1] - 30)
    assert _last_signal(Ema50OverstretchStrategy(), builders.from_closes(base)) == "BUY"


# ── ema50_overstretch_mtf ─────────────────────────────────────────────────
# SELL: перерастяжение вверх от EMA50 + перекуп старшего ТФ (RSI>70 или Stoch>80).

def test_ema50_overstretch_mtf_spike_up_gives_sell():
    base = list(2000 + np.arange(299) * 0.5)
    base.append(base[-1] + 30)
    assert _last_signal(Ema50OverstretchMtfStrategy(), builders.from_closes(base)) == "SELL"
