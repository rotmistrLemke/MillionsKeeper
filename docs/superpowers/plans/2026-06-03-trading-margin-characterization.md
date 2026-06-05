# Trading Volume/Margin Math Characterization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запереть мат-логику объёма/маржи реального класса `trading.Trading` (calculatePipValue / calculateMaxVolumeWithMarginCheck / checkMarginWithStopLoss / calculateSafeTradeWithMargin) характеризационной сеткой без правок прода.

**Architecture:** Тестируем РЕАЛЬНЫЙ `Trading` через E1-фикстуру `patched_trading` (монкипатч модульных глобалов `trading.mt5`/`cache`/`status` фейками + нейтрализация `time.sleep`). Фейки в `tests/execution/fakes.py` дорастаются аддитивно (E1/E2 не ломаются). order_calc_margin фейка — фикс-скаляр (инъекция зависимости), чтобы арифметика была детерминирована.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio (`asyncio_mode=auto`). Без новых зависимостей.

**Характеризационная инверсия TDD:** тест пишется ПОСЛЕ изучения прод-поведения и должен **пройти сразу**. Шаг «запустить» проверяет: PASS = поведение заперто; FAIL = находка → `xfail` (если известно желаемое) или passing `assert`-документация (если код сломан) + запись в `docs/known-issues.md`. Прод НЕ правим.

**Спека:** [docs/superpowers/specs/2026-06-03-trading-margin-characterization-design.md](../specs/2026-06-03-trading-margin-characterization-design.md)

**Опорные факты прода (проверены):** `TargetType.LONG=0`, `SHORT=1`. `setStopLoss`/`calculateStopLossOld` — мёртвый код (нигде не вызываются), объявлены без `self`. `setStopLoss` при вызове как метод НЕ падает (из-за `0.0==0` ветка проходит), поэтому документируем дефект через `inspect.signature`, а не `assert raises`.

---

## File Structure

- **Modify** `tests/execution/fakes.py` — `FakeMT5` (+`order_calc_margin`, +`symbol_info`, +`ticks`-мапа, +`margin_per_lot`/`symbol_infos`), `FakeCache` (+`get_account_info`, +`account_info`, +поля symbol_info), `FakeStatus` (+`active_symbols`, +`_active`).
- **Modify** `tests/execution/conftest.py` — `patched_trading`: нейтрализация `time.sleep`.
- **Create** `tests/execution/test_trading_margin.py` — характеризационные кейсы.
- **Modify** `docs/known-issues.md` — находки (#double-count + 2× legacy-no-self).

---

## Task 1: Расширить харнесс `fakes.py`

**Files:** Modify `tests/execution/fakes.py`

- [ ] **Step 1: Расширить `FakeMT5`**

В `FakeMT5.__init__`, сразу после `self.positions = []`, добавить:
```python
        self.ticks = {}                      # symbol -> tick override (конверсионные символы)
        self.symbol_infos = {}               # symbol -> info|None для mt5.symbol_info()
        self.margin_per_lot = 100.0          # order_calc_margin (фикс-скаляр; None для fail-теста)
```

Заменить метод `symbol_info_tick` (сейчас `return self.tick`) на учитывающий мапу:
```python
    def symbol_info_tick(self, symbol):
        return self.ticks.get(symbol, self.tick)
```

В блок «API, который дёргает trading.py» (рядом с `positions_get`/`history_deals_get`) добавить:
```python
    def order_calc_margin(self, order_type, symbol, volume, price):
        return self.margin_per_lot

    def symbol_info(self, symbol):
        return self.symbol_infos.get(symbol)
```

- [ ] **Step 2: Расширить `FakeCache`**

Заменить `FakeCache.__init__` целиком на:
```python
    def __init__(self):
        self.symbol_info = SimpleNamespace(
            visible=True, point=0.01, digits=2, trade_stops_level=10,
            trade_contract_size=100.0, currency_profit="USD", currency_margin="USD",
            volume_min=0.01, volume_max=100.0, volume_step=0.01,
        )
        self.positions = []
        self.account_info = SimpleNamespace(
            balance=10000.0, equity=10000.0, margin_free=5000.0,
        )
```

Добавить метод (рядом с `get_positions`):
```python
    def get_account_info(self):
        return self.account_info
```

- [ ] **Step 3: Расширить `FakeStatus`**

В `FakeStatus.__init__`, после `self._status = {}`, добавить:
```python
        self._active = []
```
Добавить метод:
```python
    def active_symbols(self):
        return list(self._active)
```

- [ ] **Step 4: Проверить импорт и обратную совместимость**

Run: `python -c "import tests.execution.fakes as f; m=f.FakeMT5(); print(m.order_calc_margin(0,'X',1,0), m.symbol_info('X'), f.FakeCache().get_account_info().balance, f.FakeStatus().active_symbols())"`
Expected: `100.0 None 10000.0 []` без ошибок.

Run (E1/E2 не сломаны): `python -m pytest tests/execution/test_trading_orders.py tests/execution/test_execution_agent.py -q`
Expected: всё зелёное (как было).

- [ ] **Step 5: Commit**

```bash
git add tests/execution/fakes.py
git commit -m "test(trading): расширить харнесс fakes для E1b (order_calc_margin/symbol_info/account_info/active_symbols)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `patched_trading` — нейтрализовать `time.sleep`

**Files:** Modify `tests/execution/conftest.py`

- [ ] **Step 1: Добавить патч sleep в фикстуру**

В фикстуре `patched_trading` (после `import trading as trading_mod`, перед/после подмены mt5/cache/status) добавить строку, нейтрализующую sleep в retry-цикле:
```python
    monkeypatch.setattr(trading_mod.time, "sleep", lambda *a, **k: None)
```
(`trading.py` делает `import time` на уровне модуля, поэтому `trading_mod.time` — это модуль `time`; патч авто-восстанавливается после теста.)

- [ ] **Step 2: Проверить, что E1 не сломан**

Run: `python -m pytest tests/execution/test_trading_orders.py -q`
Expected: всё зелёное (sleep в orderOpen/orderClose/modifySL не вызывается — патч безвреден).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/conftest.py
git commit -m "test(trading): patched_trading нейтрализует time.sleep для retry-цикла (E1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `calculatePipValue`

**Files:** Create `tests/execution/test_trading_margin.py`

- [ ] **Step 1: Написать тесты**

Создать `tests/execution/test_trading_margin.py`:
```python
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
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_trading_margin.py -v`
Expected: 6 PASS (7 ассертов). FAIL → находка: не править прод/не подгонять; сообщить.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_margin.py
git commit -m "test(trading): характеризация calculatePipValue + конверсия валют (E1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `calculateMaxVolumeWithMarginCheck`

**Files:** Modify `tests/execution/test_trading_margin.py`

- [ ] **Step 1: Написать тесты**

Добавить в `test_trading_margin.py`:
```python
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
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_trading_margin.py -v -k "maxvol"`
Expected: 10 PASS (happy + 2 параметра divisor + 4 fail-пути + safe + 2 clamp). FAIL → находка (сообщить точное computed-vs-expected, не подгонять).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_margin.py
git commit -m "test(trading): характеризация calculateMaxVolumeWithMarginCheck (E1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `checkMarginWithStopLoss` (+ находка double-count)

**Files:** Modify `tests/execution/test_trading_margin.py`

- [ ] **Step 1: Написать тесты**

Добавить:
```python
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
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_trading_margin.py -v -k "check_margin"`
Expected: 4 PASS + 1 XFAIL (`test_check_margin_double_counts_volume`). Если double-count тест НЕ xfail (т.е. xpass) — значит прод иначе, чем предполагалось: сообщить. Если passing-тесты FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_margin.py
git commit -m "test(trading): характеризация checkMarginWithStopLoss + xfail double-count (E1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `calculateSafeTradeWithMargin` (оркестрация)

**Files:** Modify `tests/execution/test_trading_margin.py`

- [ ] **Step 1: Написать тесты**

Оркестрацию (вызов maxVol → checkMargin → step-down цикл) изолируем, подменяя
`calculateMaxVolumeWithMarginCheck`/`checkMarginWithStopLoss` на инстансе через monkeypatch
(сами методы покрыты в Task 4/5). Добавить:
```python
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
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_trading_margin.py -v -k "safetrade"`
Expected: 4 PASS. FAIL → находка (сообщить, не подгонять).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_margin.py
git commit -m "test(trading): характеризация calculateSafeTradeWithMargin (оркестрация) (E1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Legacy-находки (сигнатуры без `self`)

**Files:** Modify `tests/execution/test_trading_margin.py`

- [ ] **Step 1: Написать тесты**

`setStopLoss`/`calculateStopLossOld` объявлены без `self` (мёртвый код). Документируем
структурный дефект через `inspect.signature` (passing-характеризация, без xfail —
дефект объективен). Добавить:
```python
import inspect
from trading import Trading


def test_legacy_setStopLoss_missing_self_param():
    # FINDING #legacy-no-self: setStopLoss объявлен без self → сломан при вызове как метод.
    params = list(inspect.signature(Trading.setStopLoss).parameters)
    assert params and params[0] != "self"


def test_legacy_calculateStopLossOld_missing_self_param():
    # FINDING #legacy-no-self: calculateStopLossOld объявлен без self.
    params = list(inspect.signature(Trading.calculateStopLossOld).parameters)
    assert params and params[0] != "self"
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_trading_margin.py -v -k "legacy"`
Expected: 2 PASS (фиксируют отсутствие `self`). Если FAIL (у метода есть `self`) — прод иной: сообщить.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_margin.py
git commit -m "test(trading): характеризация legacy setStopLoss/calculateStopLossOld без self (E1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Находки в `docs/known-issues.md` + полный прогон

**Files:** Modify `docs/known-issues.md`

- [ ] **Step 1: Прочитать формат known-issues**

Run: `python -m pytest tests/execution/test_trading_margin.py -q`
Зафиксировать число (ожидаемо `~25 passed, 1 xfailed`). Прочитать `docs/known-issues.md` для образца нумерации/формата записей.

- [ ] **Step 2: Добавить записи находок**

В `docs/known-issues.md` добавить (продолжив существующую нумерацию, напр. #5/#6/#7):
- **double-count volume в `checkMarginWithStopLoss`** ([trading.py:410](../trading.py#L410)): `potential_loss = pip_value * stop_loss_pips * volume`, где `pip_value = calculatePipValue(symbol, volume, ...)` уже умножен на `volume` → `potential_loss` квадратичен по `volume` (завышает потенциальный убыток для дробных лотов <1 — занижает, для >1 — завышает). Желаемое: линейная зависимость (использовать pip-per-lot или не домножать на volume повторно). Зафиксировано xfail-тестом `test_check_margin_double_counts_volume`. Прод не правился.
- **legacy без `self`** ([trading.py:188](../trading.py#L188), [trading.py:199](../trading.py#L199)): `calculateStopLossOld(symbol, ...)` и `setStopLoss(ticket, ...)` объявлены как методы класса `Trading`, но без `self` → при вызове `self` попадает в первый параметр (сдвиг аргументов). Мёртвый код (нигде не вызываются). `setStopLoss` дополнительно дёргает `result.retcode` без None-guard. Зафиксировано тестами `test_legacy_*_missing_self_param`. Желаемое: удалить мёртвый код или восстановить сигнатуру. Прод не правился.

- [ ] **Step 3: Commit**

```bash
git add docs/known-issues.md
git commit -m "docs(known-issues): находки E1b — double-count volume + legacy без self

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Верификация — полный прогон + прод не тронут**

Run: `python -m pytest -q`
Expected: всё зелёное, ожидаемо `~367 passed, 3 xfailed` (было 342+2; +~25 passed, +1 xfail).
Run: `git diff --stat trading.py`
Expected: пусто (боевой `trading.py` не изменён).

---

## Self-Review (выполнено при написании плана)

- **Spec coverage:** calculatePipValue вкл. конверсию (Task 3) ✓; calculateMaxVolumeWithMarginCheck happy/divisor/4×fail/safe/2×clamp (Task 4) ✓; checkMarginWithStopLoss + double-count xfail (Task 5) ✓; calculateSafeTradeWithMargin оркестрация (Task 6) ✓; legacy без self (Task 7) ✓; расширение fakes (Task 1) ✓; patched_trading sleep (Task 2) ✓; known-issues + полный прогон (Task 8) ✓.
- **Placeholder scan:** код приведён полностью в каждом шаге; плейсхолдеров нет.
- **Type consistency:** фейк-поля единообразны — `FakeMT5.margin_per_lot`/`symbol_infos`/`ticks`/`tick`, `FakeCache.account_info`/`symbol_info`(c полями trade_contract_size/currency_profit/currency_margin/volume_min/max/step), `FakeStatus._active`/`active_symbols`; фикстура `patched_trading` отдаёт namespace с `trading`/`mt5`/`cache`/`status` (как в E1) — используется единообразно во всех тасках. `TargetType.LONG=0`/`SHORT=1` учтены (legacy через inspect, а не runtime).
- **Замечание исполнителю:** числовые ожидания (45.45/22.73/0.91/49.5 и т.п.) выведены из дефолтов фейков Task 1; если фактический прогон даёт иное — это либо находка (сообщить), либо рассинхрон дефолтов (сверить с Task 1), но НЕ подгонять прод/значение вслепую.
```
