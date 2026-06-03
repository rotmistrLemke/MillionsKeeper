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


def test_maxvol_happy_risk_bound(patched_trading):
    # risk_money=10000*2/100=200; cost=pip_per_lot(1.0)*sl(100)=100; vbr=2.0;
    # vbm=(free 5000 / safety 1.1)/margin 100 = 45.45; max=min(2.0,45.45)=2.0;
    # ratio=5000/100=50 >= 1.1 → 2.0
    vol = patched_trading.trading.calculateMaxVolumeWithMarginCheck(
        "XAUUSD", 2, 100, patched_trading.mt5.ORDER_TYPE_BUY
    )
    assert vol == pytest.approx(2.0)


@pytest.mark.parametrize("active,num_orders,expected", [
    (["A"], 0, 45.45),               # divisor=1 → free=5000 → vbm≈45.45 (margin-bound)
    (["A", "B", "C"], 1, 22.73),     # divisor=3-1=2 → free=2500 → vbm≈22.73
])
def test_maxvol_divisor_scales_free_margin(patched_trading, active, num_orders, expected):
    # risk%=80, sl=1 → vbr=8000 (огромный) → объём ограничен маржой; делитель режет free_margin
    patched_trading.status._active = active
    patched_trading.cache.positions = [SimpleNamespace(magic=1) for _ in range(num_orders)]
    vol = patched_trading.trading.calculateMaxVolumeWithMarginCheck(
        "XAUUSD", 80, 1, patched_trading.mt5.ORDER_TYPE_BUY
    )
    assert vol == pytest.approx(expected, abs=0.01)


def test_maxvol_account_info_none_returns_zero(patched_trading):
    patched_trading.cache.account_info = None
    assert patched_trading.trading.calculateMaxVolumeWithMarginCheck("XAUUSD", 2, 100) == 0


def test_maxvol_nonpositive_balance_returns_zero(patched_trading):
    patched_trading.cache.account_info.balance = 0
    assert patched_trading.trading.calculateMaxVolumeWithMarginCheck("XAUUSD", 2, 100) == 0


def test_maxvol_zero_pip_returns_zero(patched_trading):
    patched_trading.cache.symbol_info.point = 0.0   # pip_per_lot=0 → "<=0" → 0
    assert patched_trading.trading.calculateMaxVolumeWithMarginCheck("XAUUSD", 2, 100) == 0


def test_maxvol_margin_none_returns_zero(patched_trading):
    patched_trading.mt5.margin_per_lot = None       # order_calc_margin None → 0
    assert patched_trading.trading.calculateMaxVolumeWithMarginCheck("XAUUSD", 2, 100) == 0


def test_maxvol_low_margin_ratio_returns_safe_volume(patched_trading):
    # margin 5000: vbm=(5000/1.1)/5000=0.909→0.91; final ratio=5000/5000=1.0<1.1 →
    # safe = free/(margin*safety)=5000/(5000*1.1)=0.909→0.91
    patched_trading.mt5.margin_per_lot = 5000.0
    vol = patched_trading.trading.calculateMaxVolumeWithMarginCheck(
        "XAUUSD", 2, 100, patched_trading.mt5.ORDER_TYPE_BUY
    )
    assert vol == pytest.approx(0.91, abs=0.01)


def test_maxvol_clamps_to_volume_max(patched_trading):
    # vbr=8000 (risk80,sl1), vbm=45.45 → max=45.45, но volume_max=10 → 10.0
    patched_trading.cache.symbol_info.volume_max = 10.0
    vol = patched_trading.trading.calculateMaxVolumeWithMarginCheck(
        "XAUUSD", 80, 1, patched_trading.mt5.ORDER_TYPE_BUY
    )
    assert vol == pytest.approx(10.0)


def test_maxvol_clamps_to_volume_min(patched_trading):
    # vbr=2.0, но volume_min=5.0 → max(2.0,5.0)=5.0
    patched_trading.cache.symbol_info.volume_min = 5.0
    vol = patched_trading.trading.calculateMaxVolumeWithMarginCheck(
        "XAUUSD", 2, 100, patched_trading.mt5.ORDER_TYPE_BUY
    )
    assert vol == pytest.approx(5.0)
