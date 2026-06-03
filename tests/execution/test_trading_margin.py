"""Характеризационные тесты мат-логики объёма/маржи trading.Trading (слайс E1b).

Прод (trading.py) не меняется. Тесты фиксируют текущее поведение расчёта лота:
calculatePipValue (вкл. конверсию валют), calculateMaxVolumeWithMarginCheck
(риск/маржа/retry/clamp), checkMarginWithStopLoss, calculateSafeTradeWithMargin.
Реальный класс Trading через фикстуру patched_trading; зависимости — фейки.

Дефолты фейков (tests/execution/fakes.py):
  symbol_info: point=0.01, trade_contract_size=100 → pip_per_lot(vol=1)=1.0;
               currency_profit==currency_margin=="USD"; volume_min=0.01,
               volume_max=100.0, volume_step=0.01.
  account_info: balance=10000, equity=10000, margin_free=5000.
  order_calc_margin → margin_per_lot (фикс, дефолт 100.0).
"""
from types import SimpleNamespace

import pytest

from settings import TargetType


def test_pip_value_none_symbol_info(patched_trading):
    patched_trading.cache.symbol_info = None
    assert patched_trading.trading.calculatePipValue("XAUUSD", 1, 0) == 0


def test_pip_value_same_currency(patched_trading):
    t = patched_trading.trading
    # pip = point*contract*volume = 0.01*100*1 = 1.0; order_type не влияет (same-currency)
    assert t.calculatePipValue("XAUUSD", 1, patched_trading.mt5.ORDER_TYPE_BUY) == pytest.approx(1.0)
    assert t.calculatePipValue("XAUUSD", 1, patched_trading.mt5.ORDER_TYPE_SELL) == pytest.approx(1.0)


def test_pip_value_cross_currency_direct(patched_trading):
    patched_trading.cache.symbol_info.currency_profit = "EUR"
    patched_trading.cache.symbol_info.currency_margin = "USD"
    patched_trading.mt5.symbol_infos["EURUSDrfd"] = object()
    patched_trading.mt5.ticks["EURUSDrfd"] = SimpleNamespace(ask=1.1, bid=1.09)
    # pip = 1.0 *= ask(1.1) = 1.1
    assert patched_trading.trading.calculatePipValue("XAUEUR", 1, patched_trading.mt5.ORDER_TYPE_BUY) == pytest.approx(1.1)


def test_pip_value_cross_currency_inverse(patched_trading):
    patched_trading.cache.symbol_info.currency_profit = "EUR"
    patched_trading.cache.symbol_info.currency_margin = "USD"
    # прямой EURUSDrfd отсутствует (→None), обратный USDEURrfd есть → /= bid
    patched_trading.mt5.symbol_infos["USDEURrfd"] = object()
    patched_trading.mt5.ticks["USDEURrfd"] = SimpleNamespace(ask=0.91, bid=0.9)
    assert patched_trading.trading.calculatePipValue("XAUEUR", 1, patched_trading.mt5.ORDER_TYPE_BUY) == pytest.approx(1.0 / 0.9)


def test_pip_value_cross_currency_both_none(patched_trading):
    patched_trading.cache.symbol_info.currency_profit = "EUR"
    patched_trading.cache.symbol_info.currency_margin = "USD"
    # ни EURUSDrfd, ни USDEURrfd нет → конверсии нет, pip = 1.0
    assert patched_trading.trading.calculatePipValue("XAUEUR", 1, patched_trading.mt5.ORDER_TYPE_BUY) == pytest.approx(1.0)


def test_pip_value_exception_returns_zero(patched_trading):
    # tick None → .ask бросает AttributeError → except → 0
    patched_trading.mt5.tick = None
    assert patched_trading.trading.calculatePipValue("XAUUSD", 1, patched_trading.mt5.ORDER_TYPE_BUY) == 0
