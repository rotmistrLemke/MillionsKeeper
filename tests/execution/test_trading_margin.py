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
import inspect
from types import SimpleNamespace

import pytest


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


def test_check_margin_happy(patched_trading):
    # pip_value=calculatePipValue(vol 0.1)=0.01*100*0.1=0.1;
    # potential_loss=0.1*100*0.1=1.0; total=margin(100)+1.0=101; ratio=5000/101≈49.5 ≥1.2
    ok, ratio = patched_trading.trading.checkMarginWithStopLoss(
        "XAUUSD", 0.1, patched_trading.mt5.ORDER_TYPE_BUY, 100
    )
    assert ok is True
    assert ratio == pytest.approx(5000 / 101)


def test_check_margin_account_none(patched_trading):
    patched_trading.cache.account_info = None
    assert patched_trading.trading.checkMarginWithStopLoss("XAUUSD", 0.1, 0, 100) == (False, 0)


def test_check_margin_margin_required_none(patched_trading):
    patched_trading.mt5.margin_per_lot = None
    assert patched_trading.trading.checkMarginWithStopLoss("XAUUSD", 0.1, 0, 100) == (False, 0)


def test_check_margin_exception_returns_false_zero(patched_trading, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("calc boom")
    monkeypatch.setattr(patched_trading.mt5, "order_calc_margin", boom)
    assert patched_trading.trading.checkMarginWithStopLoss("XAUUSD", 0.1, 0, 100) == (False, 0)


@pytest.mark.xfail(reason="находка #double-count: potential_loss = pip_value*sl*volume, "
                          "а pip_value уже умножен на volume → квадрат по volume; "
                          "желаемое — линейная зависимость (см. docs/known-issues.md)")
def test_check_margin_double_counts_volume(patched_trading):
    # free=300, vol=1.5, sl=100, margin=100.
    # АКТУАЛЬНО (квадрат): pip_value=0.01*100*1.5=1.5; loss=1.5*100*1.5=225; total=325;
    #   ratio=300/325≈0.923 < 1.2 → (False).
    # ЖЕЛАЕМО (линейно): loss=pip_per_lot(1.0)*100*1.5=150; total=250; ratio=300/250=1.2 ≥1.2 → True.
    patched_trading.cache.account_info.margin_free = 300.0
    ok, _ratio = patched_trading.trading.checkMarginWithStopLoss(
        "XAUUSD", 1.5, patched_trading.mt5.ORDER_TYPE_BUY, 100
    )
    assert ok is True   # желаемое поведение; сейчас код даёт False → xfail


def test_safetrade_zero_max_returns_zero(patched_trading, monkeypatch):
    monkeypatch.setattr(patched_trading.trading, "calculateMaxVolumeWithMarginCheck",
                        lambda *a, **k: 0)
    assert patched_trading.trading.calculateSafeTradeWithMargin("XAUUSD", 2, 100) == 0


def test_safetrade_margin_ok_returns_max(patched_trading, monkeypatch):
    monkeypatch.setattr(patched_trading.trading, "calculateMaxVolumeWithMarginCheck",
                        lambda *a, **k: 2.0)
    monkeypatch.setattr(patched_trading.trading, "checkMarginWithStopLoss",
                        lambda *a, **k: (True, 5.0))
    assert patched_trading.trading.calculateSafeTradeWithMargin("XAUUSD", 2, 100) == pytest.approx(2.0)


def test_safetrade_steps_down_to_safe_volume(patched_trading, monkeypatch):
    # max=2.0; шаг 0.5; margin_ok только при volume<=1.5 → ожидаем 1.5
    patched_trading.cache.symbol_info.volume_min = 0.5
    patched_trading.cache.symbol_info.volume_step = 0.5
    monkeypatch.setattr(patched_trading.trading, "calculateMaxVolumeWithMarginCheck",
                        lambda *a, **k: 2.0)
    def fake_check(symbol, volume, order_type, sl, margin_safety=1.2):
        return (volume <= 1.5 + 1e-9, 1.0)
    monkeypatch.setattr(patched_trading.trading, "checkMarginWithStopLoss", fake_check)
    assert patched_trading.trading.calculateSafeTradeWithMargin("XAUUSD", 2, 100) == pytest.approx(1.5)


def test_safetrade_exhausts_returns_max(patched_trading, monkeypatch):
    # margin_ok никогда → цикл исчерпан → возврат max_volume
    patched_trading.cache.symbol_info.volume_min = 0.5
    patched_trading.cache.symbol_info.volume_step = 0.5
    monkeypatch.setattr(patched_trading.trading, "calculateMaxVolumeWithMarginCheck",
                        lambda *a, **k: 2.0)
    monkeypatch.setattr(patched_trading.trading, "checkMarginWithStopLoss",
                        lambda *a, **k: (False, 0.5))
    assert patched_trading.trading.calculateSafeTradeWithMargin("XAUUSD", 2, 100) == pytest.approx(2.0)


# Класс Trading берём из инстанса фикстуры (patched_trading лениво и безопасно
# импортирует trading через permissive-стаб MT5). Модульный `from trading import
# Trading` здесь НЕДОПУСТИМ: он форсирует ранний import trading на этапе коллекции
# → trading.py:427 вычисляет mt5.ORDER_TYPE_BUY против неполного MT5-фейка
# legacy-тестов (catch-22 E1) и загрязняет indicators.mt5 (ломает test_macd_atr).
def test_legacy_setStopLoss_missing_self_param(patched_trading):
    # FINDING #legacy-no-self: setStopLoss объявлен без self → сломан при вызове как метод.
    Trading = type(patched_trading.trading)
    params = list(inspect.signature(Trading.setStopLoss).parameters)
    assert params and params[0] != "self"


def test_legacy_calculateStopLossOld_missing_self_param(patched_trading):
    # FINDING #legacy-no-self: calculateStopLossOld объявлен без self.
    Trading = type(patched_trading.trading)
    params = list(inspect.signature(Trading.calculateStopLossOld).parameters)
    assert params and params[0] != "self"
