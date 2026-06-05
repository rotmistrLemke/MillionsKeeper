# Характеризационные тесты пути ордеров `trading.py` — план реализации (E1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Покрыть характеризационной сеткой денежный путь `Trading.orderOpen/orderClose/modifySL` через переиспользуемый FakeMT5-харнесс, не меняя боевой код.

**Architecture:** Боевой `trading.py` уже существует — это **характеризация**, а не TDD-разработка. Каждый тест описывает *предполагаемое текущее* поведение; запускаем — зелёный означает «поведение заперто». Если тест красный, значит наше предположение неверно: смотрим реальное поведение и правим тест под факт (а не код). Единственное исключение — тест-находка: он описывает *желаемое* поведение и помечается `xfail`, т.к. текущий код падает `AttributeError`. Фейки MT5/cache/status подменяют модульные глобалы `trading.py` через `monkeypatch` — без правок прода.

**Tech Stack:** pytest (`asyncio_mode=auto`), `unittest.mock`-free лёгкие фейки (`types.SimpleNamespace`), монкипатч модульных глобалов.

**Спек:** [docs/superpowers/specs/2026-06-02-trading-orders-characterization-design.md](../specs/2026-06-02-trading-orders-characterization-design.md)

---

## Структура файлов

```
tests/
└── execution/
    ├── __init__.py            # пустой, делает пакет
    ├── fakes.py              # FakeMT5/FakeCache/FakeStatus + make_position (переиспользуемо)
    ├── conftest.py            # фикстура patched_trading (импортирует фейки из .fakes)
    └── test_trading_orders.py # характеризационные кейсы orderOpen/orderClose/modifySL
docs/
└── known-issues.md           # +запись о находке orderOpen-none-result
```

**Почему фейки в `fakes.py`, а не в `conftest.py`:** импортировать классы из `conftest`
— анти-паттерн (pytest управляет жизненным циклом conftest). Выносим переиспользуемые
фейки в обычный модуль `tests/execution/fakes.py`; `conftest.py` импортирует их оттуда
для фикстуры, тесты — тоже оттуда. `tests/` уже пакет (`tests/__init__.py` есть), корневой
[conftest.py](../../../conftest.py) кладёт корень проекта в `sys.path`, поэтому
`from tests.execution.fakes import ...` резолвится.

**Точные текущие поведения (из чтения кода, на них опираются ассерты):**
- `orderOpen` ([trading.py:14-70](../../../trading.py#L14)): `price = tick.bid` для LONG и SHORT; ключи `sl`/`tp` только при `> 0`, `magic` только при `int(magic) > 0`; на успехе `status.mark_open(symbol)`; на `retcode != DONE` — без `mark_open`; `symbol_select` при `not symbol_info.visible`. Возврат `{"order","price","symbol","targetType"}`.
- `orderClose` ([trading.py:72-107](../../../trading.py#L72)): нет позиции → `False` без send; `tick is None` → `False`; closing BUY → `price = tick.bid`, closing SELL → `price = tick.ask`; `comment[:31]`.
- `modifySL` ([trading.py:109-142](../../../trading.py#L109)): нет позиции → `False`; граница `trade_stops_level*point` → `False` без send; иначе `action=SLTP`, `sl/tp` округлены до `digits`, `tp` по умолчанию = `pos.tp` при `new_tp=None`.
- `TargetType.LONG = 0`, `TargetType.SHORT = 1` ([settings.py:3-5](../../../settings.py#L3)).
- `trading.py` держит `mt5`/`cache`/`status` как модульные глобалы ([trading.py:1,4,7](../../../trading.py#L1)) → подменяемы `monkeypatch.setattr(trading, name, fake)`.

---

### Task 1: Харнесс фейков + smoke-тест

**Files:**
- Create: `tests/execution/__init__.py`
- Create: `tests/execution/conftest.py`
- Create: `tests/execution/test_trading_orders.py` (только smoke-тест на этом шаге)

- [ ] **Step 1: Создать пустой `tests/execution/__init__.py`**

Пустой файл (делает каталог пакетом, единообразно с `tests/anomaly/`).

- [ ] **Step 2: Написать фейки в `tests/execution/fakes.py`**

```python
"""Фейки MT5/cache/status для характеризационных тестов trading.py.

trading.py держит mt5/cache/status как модульные глобалы, поэтому фикстура
patched_trading (в conftest.py) подменяет их через monkeypatch — боевой код не
меняется. Харнесс переиспользуем для будущих слайсов E2/E3.
"""
from types import SimpleNamespace


class FakeMT5:
    # Различимые sentinel-константы (значения близки к реальным MT5).
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 2
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.sent = []                       # записанные order_send-запросы
        self.tick = SimpleNamespace(bid=1900.0, ask=1900.5, time=1_700_000_000)
        self.positions = []                  # отдаётся positions_get
        self.selected = []                   # записанные symbol_select
        self._result = "default"             # "default" → построить успешный результат
        self._error = (1, "fake error")

    # --- настройка из тестов ---
    def set_result(self, retcode=None, order=12345, price=0.0):
        self._result = SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE if retcode is None else retcode,
            order=order, price=price,
        )

    def set_result_none(self):
        self._result = None

    # --- API, который дёргает trading.py ---
    def order_send(self, request):
        self.sent.append(dict(request))
        if self._result == "default":
            return SimpleNamespace(
                retcode=self.TRADE_RETCODE_DONE, order=12345,
                price=request.get("price", 0.0),
            )
        return self._result

    def symbol_info_tick(self, symbol):
        return self.tick

    def positions_get(self, ticket=None, symbol=None):
        return list(self.positions)

    def last_error(self):
        return self._error

    def symbol_select(self, symbol, enable=True):
        self.selected.append((symbol, enable))
        return True


class FakeCache:
    def __init__(self):
        self.symbol_info = SimpleNamespace(
            visible=True, point=0.01, digits=2, trade_stops_level=10,
        )
        self.positions = []

    def get_symbol_info(self, symbol):
        return self.symbol_info

    def get_positions(self):
        return list(self.positions)


class FakeStatus:
    def __init__(self):
        self.opened = []
        self._status = {}

    def mark_open(self, symbol):
        self.opened.append(symbol)
        self._status[symbol] = 1

    def status_of(self, symbol):
        return self._status.get(symbol, 0)


def make_position(fm, *, ticket=555, type=None, volume=0.1, magic=777, tp=1950.0):
    """Удобный конструктор фейковой позиции MT5."""
    return SimpleNamespace(
        ticket=ticket,
        type=fm.ORDER_TYPE_BUY if type is None else type,
        volume=volume, magic=magic, tp=tp,
    )
```

- [ ] **Step 3: Написать фикстуру в `tests/execution/conftest.py`**

```python
"""Фикстура patched_trading: подменяет модульные глобалы trading.py фейками."""
from types import SimpleNamespace

import pytest

from tests.execution.fakes import FakeMT5, FakeCache, FakeStatus


@pytest.fixture
def patched_trading(monkeypatch):
    """Возвращает namespace с Trading() и подменёнными фейками."""
    import trading as trading_mod
    fake_mt5 = FakeMT5()
    fake_cache = FakeCache()
    fake_status = FakeStatus()
    monkeypatch.setattr(trading_mod, "mt5", fake_mt5)
    monkeypatch.setattr(trading_mod, "cache", fake_cache)
    monkeypatch.setattr(trading_mod, "status", fake_status)
    return SimpleNamespace(
        trading=trading_mod.Trading(),
        mt5=fake_mt5, cache=fake_cache, status=fake_status,
    )
```

- [ ] **Step 4: Smoke-тест в `tests/execution/test_trading_orders.py`**

```python
"""Характеризационные тесты денежного пути trading.py (orderOpen/orderClose/modifySL).

Это характеризация существующего кода: тест фиксирует ТЕКУЩЕЕ поведение.
Если тест красный — сверяемся с кодом и правим ожидание под факт (не код).
"""
from types import SimpleNamespace

import pytest

from settings import TargetType
from tests.execution.fakes import make_position


def test_harness_imports_and_patches(patched_trading):
    t = patched_trading
    assert t.trading is not None
    assert t.mt5.sent == []
    assert t.cache.get_symbol_info("X").visible is True
```

- [ ] **Step 5: Запустить smoke-тест**

Run: `python -m pytest tests/execution/test_trading_orders.py -q`
Expected: PASS (1 passed). Если `trading` не импортируется — проверить, что корневой [conftest.py](../../../conftest.py) активен и ставит стаб MT5.

- [ ] **Step 6: Commit**

```bash
git add tests/execution/__init__.py tests/execution/fakes.py tests/execution/conftest.py tests/execution/test_trading_orders.py
git commit -m "test(execution): FakeMT5-харнесс + smoke-тест (E1, task 1)"
```

---

### Task 2: Характеризация `orderOpen`

**Files:**
- Modify: `tests/execution/test_trading_orders.py` (добавить класс/блок тестов orderOpen)

- [ ] **Step 1: Добавить тесты `orderOpen`**

```python
class TestOrderOpen:
    def test_long_happy_path_builds_buy_deal(self, patched_trading):
        t = patched_trading
        out = t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c1")
        assert len(t.mt5.sent) == 1
        req = t.mt5.sent[0]
        assert req["action"] == t.mt5.TRADE_ACTION_DEAL
        assert req["type"] == t.mt5.ORDER_TYPE_BUY
        assert req["symbol"] == "XAUUSDrfd"
        assert req["volume"] == 0.1
        assert req["price"] == t.mt5.tick.bid          # bid для LONG (текущее поведение)
        assert req["comment"] == "c1"
        assert req["type_filling"] == t.mt5.ORDER_FILLING_FOK
        assert req["type_time"] == t.mt5.ORDER_TIME_GTC
        assert out == {"order": 12345, "price": t.mt5.tick.bid,
                       "symbol": "XAUUSDrfd", "targetType": TargetType.LONG}

    def test_short_happy_path_builds_sell_deal(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("XAUUSDrfd", TargetType.SHORT, 0.2, "c2")
        req = t.mt5.sent[0]
        assert req["type"] == t.mt5.ORDER_TYPE_SELL
        assert req["price"] == t.mt5.tick.bid           # bid и для SHORT (текущее поведение)
        assert req["volume"] == 0.2

    def test_sl_tp_magic_omitted_when_zero(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("S", TargetType.LONG, 0.1, "c", sl=0.0, tp=0.0, magic=0)
        req = t.mt5.sent[0]
        assert "sl" not in req
        assert "tp" not in req
        assert "magic" not in req

    def test_sl_tp_magic_included_and_cast_when_positive(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("S", TargetType.LONG, 0.1, "c",
                            sl=1899.0, tp=1950.0, magic=777)
        req = t.mt5.sent[0]
        assert req["sl"] == 1899.0 and isinstance(req["sl"], float)
        assert req["tp"] == 1950.0 and isinstance(req["tp"], float)
        assert req["magic"] == 777 and isinstance(req["magic"], int)

    def test_mark_open_called_on_done(self, patched_trading):
        t = patched_trading
        t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c")
        assert t.status.opened == ["XAUUSDrfd"]

    def test_mark_open_not_called_when_retcode_not_done(self, patched_trading):
        t = patched_trading
        t.mt5.set_result(retcode=10004, order=999, price=1900.0)  # REQUOTE, не DONE
        t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c")
        assert t.status.opened == []

    def test_symbol_select_when_not_visible(self, patched_trading):
        t = patched_trading
        t.cache.symbol_info.visible = False
        t.trading.orderOpen("XAUUSDrfd", TargetType.LONG, 0.1, "c")
        assert t.mt5.selected == [("XAUUSDrfd", True)]
```

- [ ] **Step 2: Запустить тесты orderOpen**

Run: `python -m pytest tests/execution/test_trading_orders.py::TestOrderOpen -q`
Expected: PASS (7 passed). Если какой-то ассерт красный — это новый факт о поведении: свериться с [trading.py:14-70](../../../trading.py#L14) и поправить ожидание теста под фактическое поведение (код не трогаем).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_orders.py
git commit -m "test(execution): характеризация orderOpen (E1, task 2)"
```

---

### Task 3: Характеризация `orderClose`

**Files:**
- Modify: `tests/execution/test_trading_orders.py`

- [ ] **Step 1: Добавить тесты `orderClose`**

```python
class TestOrderClose:
    def test_no_position_returns_false_without_send(self, patched_trading):
        t = patched_trading
        t.mt5.positions = []
        assert t.trading.orderClose(555, "S", "TP") is False
        assert t.mt5.sent == []

    def test_tick_none_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        t.mt5.tick = None
        assert t.trading.orderClose(555, "S", "TP") is False
        assert t.mt5.sent == []

    def test_closing_buy_uses_sell_at_bid(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY, magic=42)]
        ok = t.trading.orderClose(555, "S", "TP")
        assert ok is True
        req = t.mt5.sent[0]
        assert req["type"] == t.mt5.ORDER_TYPE_SELL
        assert req["price"] == t.mt5.tick.bid
        assert req["position"] == 555
        assert req["magic"] == 42

    def test_closing_sell_uses_buy_at_ask(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_SELL)]
        t.trading.orderClose(555, "S", "TP")
        req = t.mt5.sent[0]
        assert req["type"] == t.mt5.ORDER_TYPE_BUY
        assert req["price"] == t.mt5.tick.ask

    def test_comment_truncated_to_31(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        long_comment = "X" * 50
        t.trading.orderClose(555, "S", long_comment)
        assert t.mt5.sent[0]["comment"] == "X" * 31

    def test_result_none_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        t.mt5.set_result_none()
        assert t.trading.orderClose(555, "S", "TP") is False

    def test_retcode_not_done_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5)]
        t.mt5.set_result(retcode=10004, order=1, price=1900.0)
        assert t.trading.orderClose(555, "S", "TP") is False
```

- [ ] **Step 2: Запустить тесты orderClose**

Run: `python -m pytest tests/execution/test_trading_orders.py::TestOrderClose -q`
Expected: PASS (7 passed). Красный ассерт → свериться с [trading.py:72-107](../../../trading.py#L72), поправить ожидание под факт.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_orders.py
git commit -m "test(execution): характеризация orderClose (E1, task 3)"
```

---

### Task 4: Характеризация `modifySL`

**Files:**
- Modify: `tests/execution/test_trading_orders.py`

- [ ] **Step 1: Добавить тесты `modifySL`**

```python
class TestModifySL:
    def test_no_position_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = []
        assert t.trading.modifySL(555, "S", 1899.0) is False
        assert t.mt5.sent == []

    def test_buy_sl_too_close_blocked_without_send(self, patched_trading):
        # point=0.01, trade_stops_level=10 → min_dist=0.1; bid=1900 → порог 1899.9
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY)]
        assert t.trading.modifySL(555, "S", 1899.95) is False  # >= 1899.9
        assert t.mt5.sent == []

    def test_sell_sl_too_close_blocked_without_send(self, patched_trading):
        # SELL: ref=ask=1900.5; порог = 1900.5 + 0.1 = 1900.6
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_SELL)]
        assert t.trading.modifySL(555, "S", 1900.55) is False  # <= 1900.6
        assert t.mt5.sent == []

    def test_valid_buy_sl_sends_sltp_rounded(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY, tp=1950.0)]
        ok = t.trading.modifySL(555, "S", 1899.0)  # < 1899.9 → разрешено
        assert ok is True
        req = t.mt5.sent[0]
        assert req["action"] == t.mt5.TRADE_ACTION_SLTP
        assert req["position"] == 555
        assert req["sl"] == 1899.0                 # round(1899.0, digits=2)
        assert req["tp"] == 1950.0                 # по умолчанию из pos.tp

    def test_explicit_new_tp_used(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY, tp=1950.0)]
        t.trading.modifySL(555, "S", 1899.0, new_tp=1975.0)
        assert t.mt5.sent[0]["tp"] == 1975.0

    def test_retcode_not_done_returns_false(self, patched_trading):
        t = patched_trading
        t.mt5.positions = [make_position(t.mt5, type=t.mt5.ORDER_TYPE_BUY)]
        t.mt5.set_result(retcode=10004, order=1, price=0.0)
        assert t.trading.modifySL(555, "S", 1899.0) is False
```

- [ ] **Step 2: Запустить тесты modifySL**

Run: `python -m pytest tests/execution/test_trading_orders.py::TestModifySL -q`
Expected: PASS (6 passed). Красный ассерт → свериться с [trading.py:109-142](../../../trading.py#L109), поправить под факт.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_trading_orders.py
git commit -m "test(execution): характеризация modifySL (E1, task 4)"
```

---

### Task 5: Находка — `orderOpen` при `result is None` → `AttributeError`

**Files:**
- Modify: `tests/execution/test_trading_orders.py`
- Modify: `docs/known-issues.md`

- [ ] **Step 1: Добавить xfail-тест желаемого поведения**

```python
class TestOrderOpenFindings:
    @pytest.mark.xfail(
        reason="находка E1: при order_send→None строка trading.py:70 'result.order' "
               "даёт AttributeError; желаемое поведение — graceful-возврат без падения",
        raises=AttributeError, strict=True,
    )
    def test_order_send_none_should_not_crash(self, patched_trading):
        t = patched_trading
        t.mt5.set_result_none()
        # Желаемое: не падать, а вернуть результат с order=None (или None).
        out = t.trading.orderOpen("S", TargetType.LONG, 0.1, "c")
        assert out["order"] is None
```

- [ ] **Step 2: Запустить — убедиться, что xfail фиксируется как ожидаемый**

Run: `python -m pytest tests/execution/test_trading_orders.py::TestOrderOpenFindings -q`
Expected: `1 xfailed` (текущий код кидает `AttributeError`, что и заявлено `raises=AttributeError, strict=True`).

- [ ] **Step 3: Записать находку в `docs/known-issues.md`**

Открыть [docs/known-issues.md](../../../docs/known-issues.md), добавить запись в стиле существующих находок:

```markdown
## E1-1: orderOpen падает AttributeError при order_send → None

**Статус:** ⚠️ ОТКРЫТА (зафиксирована xfail-тестом в tests/execution/test_trading_orders.py)
**Файл:** trading.py:61-70

`orderOpen` при `mt5.order_send(...) → None` (или когда `type` не LONG/SHORT, и
`result` остаётся None) печатает `mt5.last_error()`, но затем безусловно исполняет
`return {"order": result.order, ...}` → `AttributeError: 'NoneType' object has no
attribute 'order'`. Денежный путь: реальный отказ брокера (order_send=None) валит
обработчик вместо мягкой деградации.

**Желаемое:** при отсутствии результата возвращать graceful-значение (например
`{"order": None, ...}` или `None`), не кидая исключение.
**Фикс:** отдельный слайс (E1 по решению не правит боевой trading.py).
```

- [ ] **Step 4: Commit**

```bash
git add tests/execution/test_trading_orders.py docs/known-issues.md
git commit -m "test(execution): находка E1-1 orderOpen result=None → AttributeError (xfail) (E1, task 5)"
```

---

### Task 6: Полный прогон + память + пуш

**Files:** (без новых правок кода)

- [ ] **Step 1: Прогнать всю сетку локально**

Run: `python -m pytest -q`
Expected: `277 passed, 2 xfailed` (было 255 passed, 1 xfailed; +20 passed orderOpen/Close/modifySL +1 xfailed находка). Если число иное — пересчитать по факту и убедиться, что нет неожиданных падений.

- [ ] **Step 2: Обновить память проекта**

В `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md`:
- В разделе «Тесты» обновить число прогона (255 → 277 passed, 1 → 2 xfailed) и добавить `tests/execution/` (FakeMT5-харнесс, характеризация orderOpen/orderClose/modifySL).
- В разделе «Статус работ» добавить `[x] E1 — характеризация пути ордеров trading.py`.
- В backlog #2 пометить, что E1 сделан; следующий шаг E1b/E2.
В `MEMORY.md` обновить однострочник проекта при необходимости.

- [ ] **Step 3: Commit + push**

```bash
git push origin tradingHouse/stage-2
```
(память — вне git, коммитить не нужно; пушим код-коммиты слайса.)

- [ ] **Step 4: Проверить зелёный CI**

После пуша проверить статус Actions для нового sha (через GitHub REST API, как в слайсе CI):
`https://api.github.com/repos/rotmistrLemke/MillionsKeeper/actions/runs?branch=tradingHouse/stage-2&per_page=1`
Expected: `conclusion=success`. Под pandas 3.0.3 новые тесты не используют `freq` — рисков нет.

---

## Self-Review

**Spec coverage:**
- Харнесс FakeMT5/FakeCache/FakeStatus + patched_trading → Task 1. ✓
- Матрица orderOpen (7) → Task 2. ✓
- Матрица orderClose (7) → Task 3. ✓
- Матрица modifySL (6) → Task 4. ✓
- Находка orderOpen-none-result (xfail + known-issues) → Task 5. ✓
- Критерий «277 passed, 2 xfailed», переиспользуемость харнесса, прод не изменён → Task 6. ✓
- НЕ входит (E1b/E2/E3/E4) — план их не трогает. ✓

**Placeholder scan:** все шаги содержат конкретный код/команды/ожидания. Плейсхолдеров нет.

**Type consistency:** `FakeMT5.set_result/set_result_none/sent/selected/tick/positions`, `FakeCache.symbol_info`, `FakeStatus.opened`, `make_position(fm, ...)`, фикстура `patched_trading` → namespace `.trading/.mt5/.cache/.status` — имена согласованы между Task 1 и тестами Task 2-5.
