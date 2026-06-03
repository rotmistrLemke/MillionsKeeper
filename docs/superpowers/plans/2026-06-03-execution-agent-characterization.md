# ExecutionAgent Characterization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запереть текущее поведение `agents/execution_agent.py` характеризационной сеткой (~30–35 кейсов) без правок прода.

**Architecture:** `ExecutionAgent` берёт `trading`/`bus` через конструктор (инъекция фейков) и остальные зависимости через модульные/ленивые глобалы (`status`, `streams.registry`, `strategies.STRATEGIES`, `market_data_cache.cache`, `MetaTrader5`, `datetime`) — подменяются через `monkeypatch`. Тесты зовут private-хендлеры (`_handle_signal`/`_handle_close`) и pure-методы напрямую + 1–2 теста на диспетчеризацию через `run()`.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio (`asyncio_mode=auto`). Без новых зависимостей.

**Характеризационная инверсия TDD:** тест пишется ПОСЛЕ изучения прод-поведения и должен **пройти сразу** (он фиксирует, как код ведёт себя сейчас). Шаг «запустить тест» проверяет: PASS = поведение заперто; FAIL = найден баг → конвертируем в `xfail` с желаемым поведением + запись в `docs/known-issues.md`, прод НЕ правим.

**Спека:** [docs/superpowers/specs/2026-06-03-execution-agent-characterization-design.md](../specs/2026-06-03-execution-agent-characterization-design.md)

---

## File Structure

- **Modify** `tests/execution/fakes.py` — добавить `FakeTrading`, `FakeBus`, `FakeRegistry`, `FakeMT5.history_deals_get`/`self.deals`, `profit`/`swap`/`commission` в `make_position`, `make_deal`, `make_stream`, `make_clock`, `make_strategy`. (Общий переиспользуемый харнесс — для E3.)
- **Modify** `tests/execution/conftest.py` — добавить фикстуру `execution_agent_factory`.
- **Create** `tests/execution/test_execution_agent.py` — характеризационные кейсы.
- **Modify** (только при находке) `docs/known-issues.md` — запись о баге.

---

## Task 1: Расширить харнесс `fakes.py`

**Files:**
- Modify: `tests/execution/fakes.py`

- [ ] **Step 1: Добавить `self.deals` и `history_deals_get` в `FakeMT5`**

В `FakeMT5.__init__` (после `self.positions = []`) добавить:

```python
        self.deals = []                      # отдаётся history_deals_get
```

В блок «API, который дёргает trading.py» (рядом с `positions_get`) добавить метод:

```python
    def history_deals_get(self, date_from=None, date_to=None):
        return list(self.deals)
```

- [ ] **Step 2: Расширить `make_position` полями profit/swap/commission**

Заменить функцию `make_position` целиком на:

```python
def make_position(fm, *, ticket=555, type=None, volume=0.1, magic=777, tp=1950.0,
                  profit=0.0, swap=0.0, commission=0.0):
    """Удобный конструктор фейковой позиции MT5."""
    return SimpleNamespace(
        ticket=ticket,
        type=fm.ORDER_TYPE_BUY if type is None else type,
        volume=volume, magic=magic, tp=tp,
        profit=profit, swap=swap, commission=commission,
    )
```

- [ ] **Step 3: Добавить хелперы `make_deal`, `make_stream`, `make_clock`, `make_strategy` и фейки `FakeTrading`/`FakeBus`/`FakeRegistry`**

В конец `tests/execution/fakes.py` добавить:

```python
def make_deal(*, magic=777, profit=0.0, commission=0.0, swap=0.0):
    """Фейковый закрытый deal MT5 (для history_deals_get)."""
    return SimpleNamespace(magic=magic, profit=profit, commission=commission, swap=swap)


def make_stream(*, id="s1", name="Stream-1", strategy="default", symbol="XAUUSD",
                volume=0.1, sl_atr=0.0, tp_atr=0.0, magic=777, deposit=0.0,
                enabled=True):
    """TradingStream-подобный объект для тестов execution_agent."""
    return SimpleNamespace(
        id=id, name=name, strategy=strategy, symbol=symbol,
        volume=volume, sl_atr=sl_atr, tp_atr=tp_atr, magic=magic,
        deposit=deposit, enabled=enabled,
    )


def make_clock(fixed_dt):
    """Фабрика фейк-класса datetime: .now() возвращает зафиксированный реальный datetime."""
    class _FakeDateTime:
        @classmethod
        def now(cls, tz=None):
            return fixed_dt
    return _FakeDateTime


def make_strategy(*, hedge=False, trailing=False):
    """Фабрика фейк-класса стратегии для STRATEGIES."""
    class _FakeStrategy:
        def wants_hedge(self):
            return hedge
        def uses_trailing_exit(self):
            return trailing
    return _FakeStrategy


class FakeBus:
    """Шина для тестов агентов: пишет события, поддерживает subscribe (no-op-хранилище)."""
    def __init__(self):
        self.events = []
        self.subscriptions = []

    def subscribe(self, event_type, handler):
        self.subscriptions.append((event_type, handler))

    async def publish(self, ev):
        self.events.append(ev)

    def publish_sync(self, ev):
        self.events.append(ev)


class FakeRegistry:
    """Подмена streams.registry: get(id) / by_symbol(symbol) поверх dict потоков."""
    def __init__(self, streams=None):
        # streams: dict[id -> stream]
        self._streams = dict(streams or {})

    def get(self, stream_id):
        return self._streams.get(stream_id)

    def by_symbol(self, symbol):
        for s in self._streams.values():
            if s.symbol == symbol:
                return s
        return None


class FakeTrading:
    """Спай вместо trading.Trading: записывает вызовы orderOpen/orderClose/calc."""
    def __init__(self):
        self.open_calls = []
        self.close_calls = []
        self.calc_calls = []
        self._open_results = None   # None → дефолтный успешный dict на каждый вызов
        self._close_result = True
        self._calc_result = 0.5

    def set_open_result(self, *results):
        """Последовательность результатов orderOpen (1-й — основная нога, 2-й — хедж)."""
        self._open_results = list(results)

    def set_close_result(self, val):
        self._close_result = val

    def set_calc_result(self, val):
        self._calc_result = val

    def orderOpen(self, symbol, order_type, volume, comment, sl=0.0, tp=0.0, magic=0):
        self.open_calls.append(dict(
            symbol=symbol, order_type=order_type, volume=volume,
            comment=comment, sl=sl, tp=tp, magic=magic,
        ))
        if self._open_results is None:
            return {"order": 12345, "price": 1900.5}
        if self._open_results:
            return self._open_results.pop(0)
        return None

    def orderClose(self, ticket, symbol, tag):
        self.close_calls.append(dict(ticket=ticket, symbol=symbol, tag=tag))
        return self._close_result

    def calculateSafeTradeWithMargin(self, symbol, risk, stop_loss_pips, order_type):
        self.calc_calls.append(dict(
            symbol=symbol, risk=risk, stop_loss_pips=stop_loss_pips, order_type=order_type,
        ))
        return self._calc_result
```

- [ ] **Step 4: Проверить, что харнесс импортируется**

Run: `python -c "import tests.execution.fakes as f; print(f.FakeTrading, f.FakeBus, f.FakeRegistry, f.make_deal, f.make_stream, f.make_clock, f.make_strategy)"`
Expected: печатает все 7 символов без ImportError.

- [ ] **Step 5: Commit**

```bash
git add tests/execution/fakes.py
git commit -m "test(execution): расширить харнесс fakes для E2 (FakeTrading/FakeBus/FakeRegistry/clock/deals)"
```

---

## Task 2: Фикстура `execution_agent_factory`

**Files:**
- Modify: `tests/execution/conftest.py`

- [ ] **Step 1: Добавить фикстуру**

В конец `tests/execution/conftest.py` добавить:

```python
@pytest.fixture
def execution_agent_factory(monkeypatch):
    """Фабрика ExecutionAgent с подменёнными зависимостями.

    Подменяет: agents.execution_agent.status, streams.registry,
    strategies.STRATEGIES, market_data_cache.cache, sys.modules['MetaTrader5'],
    agents.execution_agent.datetime. Прод не трогаем.
    """
    from tests.execution.fakes import (
        FakeMT5, FakeCache, FakeStatus, FakeTrading, FakeBus, FakeRegistry, make_clock,
    )

    def make(*, streams=None, strategies=None, now=None,
             positions=None, deals=None, calc_result=None):
        import agents.execution_agent as ea_mod
        import streams as streams_mod
        import strategies as strat_mod
        import market_data_cache as mdc_mod

        fake_mt5 = FakeMT5()
        if positions is not None:
            fake_mt5.positions = positions
        if deals is not None:
            fake_mt5.deals = deals
        fake_cache = FakeCache()
        fake_status = FakeStatus()
        fake_trading = FakeTrading()
        if calc_result is not None:
            fake_trading.set_calc_result(calc_result)
        fake_registry = FakeRegistry(streams or {})
        strat_map = {} if strategies is None else strategies

        monkeypatch.setattr(ea_mod, "status", fake_status)
        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(strat_mod, "STRATEGIES", strat_map)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
        if now is not None:
            monkeypatch.setattr(ea_mod, "datetime", make_clock(now))

        agent = ea_mod.ExecutionAgent("Execution", FakeBus(), fake_trading)
        return SimpleNamespace(
            agent=agent, bus=agent.bus, trading=fake_trading,
            mt5=fake_mt5, cache=fake_cache, status=fake_status, registry=fake_registry,
        )

    return make
```

**Примечание:** `import sys`, `from types import SimpleNamespace`, `import pytest` уже есть в `conftest.py` (Task не требует их добавления — проверить).

- [ ] **Step 2: Smoke-проверка фикстуры через временный тест**

Создать временно `tests/execution/test_smoke_factory.py`:

```python
def test_factory_builds_agent(execution_agent_factory):
    from datetime import datetime
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    assert h.agent.name == "Execution"
    assert h.agent.trading is h.trading
```

Run: `pytest tests/execution/test_smoke_factory.py -v`
Expected: PASS.

- [ ] **Step 3: Удалить временный тест**

```bash
rm tests/execution/test_smoke_factory.py
```

- [ ] **Step 4: Commit**

```bash
git add tests/execution/conftest.py
git commit -m "test(execution): фикстура execution_agent_factory (E2)"
```

---

## Task 3: `_reason_to_tag` (pure)

**Files:**
- Create: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тест**

Создать `tests/execution/test_execution_agent.py`:

```python
"""Характеризационные тесты ExecutionAgent (слайс E2).

Прод (agents/execution_agent.py) не меняется. Тесты фиксируют текущее поведение:
gating, ночная блокировка, DD-блок, equity, SL/TP по ATR, хедж, эмит/метрики,
закрытие, _reason_to_tag. Зависимости подменяются фикстурой execution_agent_factory.
"""
import asyncio
from datetime import datetime

import pytest

from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_deal, make_position, make_strategy,
)


def _signal_event(**payload):
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("signal", "BUY")
    payload.setdefault("indicators", {})
    return Event(type=EventType.SIGNAL_GENERATED, source="test", payload=payload)


def _close_event(**payload):
    payload.setdefault("symbol", "XAUUSD")
    payload.setdefault("ticket", 555)
    return Event(type=EventType.ORDER_CLOSE_REQUEST, source="test", payload=payload)


@pytest.mark.parametrize("reason,expected", [
    ("strategy:ema50", "SIGNAL"),
    ("rsi_overbought", "RSI"),
    ("sl", "SL"),
    ("stop_loss", "SL"),
    ("tp", "TP"),
    ("take_profit", "TP"),
    ("manual_close_by_user", "MANUAL"),
    ("something_else_long_reason_text", "something_else_long_"),  # [:20]
    (None, "MANUAL"),
])
def test_reason_to_tag(execution_agent_factory, reason, expected):
    h = execution_agent_factory()
    assert h.agent._reason_to_tag(reason) == expected
```

- [ ] **Step 2: Запустить тест**

Run: `pytest tests/execution/test_execution_agent.py -v`
Expected: 9 PASS (характеризует текущее поведение `_reason_to_tag`). Если какой-то кейс FAIL — это находка: пометить `@pytest.mark.xfail(reason=...)` на конкретном параметре через `pytest.param(..., marks=...)` и записать в `docs/known-issues.md`.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация _reason_to_tag (E2)"
```

---

## Task 4: Gating в `_handle_signal`

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить в `test_execution_agent.py`:

```python
async def test_no_signal_does_not_open(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD")
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="NO_SIGNAL"))
    assert h.trading.open_calls == []


async def test_trading_status_nonzero_rejects(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD")
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    h.status._status["XAUUSD"] = 1   # OPEN
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_no_stream_skips(execution_agent_factory):
    h = execution_agent_factory(streams={}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_disabled_stream_skips(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", enabled=False)
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_stream_selected_by_id_when_provided(execution_agent_factory):
    by_id = make_stream(id="s2", symbol="XAUUSD", name="ById")
    by_sym = make_stream(id="s1", symbol="XAUUSD", name="BySym")
    h = execution_agent_factory(
        streams={"s1": by_sym, "s2": by_id}, now=datetime(2026, 6, 3, 12, 0),
    )
    await h.agent._handle_signal(_signal_event(signal="BUY", stream_id="s2"))
    # comment в orderOpen начинается с id потока → подтверждает выбор by-id (s2).
    assert h.trading.open_calls
    assert h.trading.open_calls[0]["comment"].startswith("s2:")
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "no_signal or status_nonzero or no_stream or disabled or selected_by_id"`
Expected: 5 PASS. FAIL → находка (xfail + known-issues).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация gating _handle_signal (E2)"
```

---

## Task 5: Ночная блокировка

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
@pytest.mark.parametrize("dt,blocked", [
    (datetime(2026, 6, 3, 23, 55), True),   # >= 23:50
    (datetime(2026, 6, 3, 0, 30), True),    # < 05:00
    (datetime(2026, 6, 3, 4, 59), True),    # < 05:00
    (datetime(2026, 6, 3, 5, 0), False),    # ровно 05:00 — не блок
    (datetime(2026, 6, 3, 12, 0), False),
    (datetime(2026, 6, 3, 23, 49), False),  # < 23:50
])
def test_is_night_block(execution_agent_factory, dt, blocked):
    h = execution_agent_factory(now=dt)
    result, _reason = h.agent._is_night_block()
    assert result is blocked


async def test_night_block_prevents_open(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD")
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 0, 30))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls == []


async def test_daytime_allows_open(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.1)
    h = execution_agent_factory(streams={"s1": stream}, now=datetime(2026, 6, 3, 12, 0))
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    assert h.trading.open_calls   # дошли до открытия
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "night or daytime"`
Expected: 8 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация ночной блокировки (E2)"
```

---

## Task 6: `_compute_stream_equity`

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
def test_equity_realized_own_magic_only(execution_agent_factory):
    stream = make_stream(magic=777, deposit=1000.0)
    deals = [
        make_deal(magic=777, profit=50.0, commission=-2.0, swap=-1.0),  # +47
        make_deal(magic=999, profit=100.0),                             # чужой — игнор
    ]
    h = execution_agent_factory(deals=deals)
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1000.0 + 47.0)


def test_equity_unrealized_own_magic_only(execution_agent_factory):
    stream = make_stream(magic=777, symbol="XAUUSD", deposit=1000.0)
    h = execution_agent_factory()
    h.mt5.positions = [
        make_position(h.mt5, magic=777, profit=30.0, swap=-5.0),  # +25
        make_position(h.mt5, magic=999, profit=200.0),            # чужой — игнор
    ]
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1000.0 + 25.0)


def test_equity_empty_is_deposit(execution_agent_factory):
    stream = make_stream(magic=777, deposit=1500.0)
    h = execution_agent_factory(deals=[])
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1500.0)


def test_equity_realized_plus_unrealized(execution_agent_factory):
    stream = make_stream(magic=777, symbol="XAUUSD", deposit=1000.0)
    h = execution_agent_factory(deals=[make_deal(magic=777, profit=10.0)])
    h.mt5.positions = [make_position(h.mt5, magic=777, profit=5.0, swap=2.0)]
    eq = h.agent._compute_stream_equity(stream, datetime(2026, 6, 1))
    assert eq == pytest.approx(1000.0 + 10.0 + 7.0)


@pytest.mark.parametrize("now,expected_weekday", [
    (datetime(2026, 6, 1, 15, 0), 0),   # пн
    (datetime(2026, 6, 3, 15, 0), 0),   # ср → monday_start = пн 01.06
    (datetime(2026, 6, 7, 15, 0), 0),   # вс → monday_start = пн 01.06
])
def test_monday_start_normalizes_to_monday_midnight(execution_agent_factory, now, expected_weekday):
    h = execution_agent_factory()
    ms = h.agent._monday_start(now)
    assert ms.weekday() == expected_weekday
    assert (ms.hour, ms.minute, ms.second, ms.microsecond) == (0, 0, 0, 0)
    assert ms.date() == datetime(2026, 6, 1).date()


@pytest.mark.parametrize("now", [
    datetime(2026, 6, 1, 15, 0),   # пн → next = пн 08.06
    datetime(2026, 6, 3, 15, 0),   # ср → next = пн 08.06
    datetime(2026, 6, 7, 15, 0),   # вс → next = пн 08.06
])
def test_next_monday(execution_agent_factory, now):
    h = execution_agent_factory()
    nm = h.agent._next_monday(now)
    assert nm.weekday() == 0
    assert nm.date() == datetime(2026, 6, 8).date()
    assert (nm.hour, nm.minute, nm.second, nm.microsecond) == (0, 0, 0, 0)
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "equity or monday"`
Expected: PASS. FAIL → находка (особенно проверить `_next_monday` в понедельник: `wd>0 else 7` → +7 дней).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация _compute_stream_equity + monday-хелперов (E2)"
```

---

## Task 7: DD-блок `_check_stream_drawdown`

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
def test_dd_no_deposit_skips(execution_agent_factory):
    stream = make_stream(deposit=0.0)
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    allowed, reason = h.agent._check_stream_drawdown(stream)
    assert allowed is True and reason == ""


def test_dd_block_when_drawdown_over_threshold(execution_agent_factory):
    # peak инициализируется как deposit (1000); equity = 1000 + realized(-400) = 600.
    # dd = (1000-600)/1000 = 0.40 > 0.35 → блок.
    stream = make_stream(magic=777, deposit=1000.0)
    h = execution_agent_factory(
        deals=[make_deal(magic=777, profit=-400.0)], now=datetime(2026, 6, 3, 12, 0),
    )
    allowed, reason = h.agent._check_stream_drawdown(stream)
    assert allowed is False
    assert stream.id in h.agent._stream_dd_block_until
    # блокировка выставлена до следующего понедельника (08.06).
    assert h.agent._stream_dd_block_until[stream.id].date() == datetime(2026, 6, 8).date()


def test_dd_allows_when_within_threshold(execution_agent_factory):
    # equity = 1000 - 100 = 900; dd = 0.10 ≤ 0.35 → allowed; peak обновляется при росте.
    stream = make_stream(magic=777, deposit=1000.0)
    h = execution_agent_factory(
        deals=[make_deal(magic=777, profit=-100.0)], now=datetime(2026, 6, 3, 12, 0),
    )
    allowed, reason = h.agent._check_stream_drawdown(stream)
    assert allowed is True and reason == ""


def test_dd_active_block_in_future_rejects(execution_agent_factory):
    stream = make_stream(deposit=1000.0)
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    h.agent._stream_dd_block_until[stream.id] = datetime(2026, 6, 8, 0, 0)
    allowed, reason = h.agent._check_stream_drawdown(stream)
    assert allowed is False
    assert "блокировка до" in reason


def test_dd_expired_block_is_cleared(execution_agent_factory):
    # block_until в прошлом → снимаем (pop until/peak/week_start), затем пересчёт (allowed).
    stream = make_stream(magic=777, deposit=1000.0)
    h = execution_agent_factory(deals=[], now=datetime(2026, 6, 3, 12, 0))
    h.agent._stream_dd_block_until[stream.id] = datetime(2026, 6, 1, 0, 0)
    h.agent._stream_peak[stream.id] = 5000.0
    allowed, reason = h.agent._check_stream_drawdown(stream)
    assert allowed is True
    assert stream.id not in h.agent._stream_dd_block_until


def test_dd_week_roll_resets_peak(execution_agent_factory):
    # week_start старше 7 дней → новый _monday_start, peak сброшен (pop).
    stream = make_stream(magic=777, deposit=1000.0)
    h = execution_agent_factory(deals=[], now=datetime(2026, 6, 3, 12, 0))
    h.agent._stream_week_start[stream.id] = datetime(2026, 5, 20, 0, 0)  # >7 дней назад
    h.agent._stream_peak[stream.id] = 9999.0
    h.agent._check_stream_drawdown(stream)
    new_ws = h.agent._stream_week_start[stream.id]
    assert new_ws.weekday() == 0
    assert new_ws.date() == datetime(2026, 6, 1).date()


def test_dd_equity_exception_allows(execution_agent_factory, monkeypatch):
    stream = make_stream(magic=777, deposit=1000.0)
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    def boom(*a, **k):
        raise RuntimeError("equity fail")
    monkeypatch.setattr(h.agent, "_compute_stream_equity", boom)
    allowed, reason = h.agent._check_stream_drawdown(stream)
    assert allowed is True and reason == ""
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "dd_"`
Expected: 7 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация DD-блока _check_stream_drawdown (E2)"
```

---

## Task 8: `_open_order` — объём и SL/TP по ATR

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить (FakeCache: point=0.01, digits=2; FakeMT5.tick: bid=1900.0, ask=1900.5):

```python
def test_open_order_none_when_no_symbol_info(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.1)
    h = execution_agent_factory()
    h.cache.symbol_info = None
    assert h.agent._open_order(stream, "BUY", {"atr_value": 2.0}) is None


def test_open_order_fixed_volume_skips_calc(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.25)
    h = execution_agent_factory()
    result = h.agent._open_order(stream, "BUY", {"atr_value": 2.0})
    assert result["volume"] == 0.25
    assert h.trading.calc_calls == []   # фикс-объём → calc не зван
    assert h.trading.open_calls[0]["volume"] == 0.25


def test_open_order_calc_volume_buy_uses_80(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.0)
    h = execution_agent_factory(calc_result=0.7)
    result = h.agent._open_order(stream, "BUY", {"atr_value": 2.0})
    assert result["volume"] == 0.7
    assert h.trading.calc_calls[0]["risk"] == 80
    # stop_loss_pips = 2*atr/point = 2*2.0/0.01 = 400.0
    assert h.trading.calc_calls[0]["stop_loss_pips"] == pytest.approx(400.0)


def test_open_order_calc_volume_sell_uses_90(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.0)
    h = execution_agent_factory(calc_result=0.7)
    h.agent._open_order(stream, "SELL", {"atr_value": 2.0})
    assert h.trading.calc_calls[0]["risk"] == 90


def test_open_order_none_when_volume_nonpositive(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.0)
    h = execution_agent_factory(calc_result=0.0)
    assert h.agent._open_order(stream, "BUY", {"atr_value": 2.0}) is None
    assert h.trading.open_calls == []


def test_open_order_sltp_buy(execution_agent_factory):
    # BUY: entry=ask=1900.5; sl=1900.5-1.5*2=1897.5; tp=1900.5+3.0*2=1906.5; round digits=2.
    stream = make_stream(symbol="XAUUSD", volume=0.1, sl_atr=1.5, tp_atr=3.0)
    h = execution_agent_factory(strategies={})
    h.agent._open_order(stream, "BUY", {"atr_value": 2.0})
    call = h.trading.open_calls[0]
    assert call["sl"] == pytest.approx(1897.5)
    assert call["tp"] == pytest.approx(1906.5)


def test_open_order_sltp_sell(execution_agent_factory):
    # SELL: entry=bid=1900.0; sl=1900.0+1.5*2=1903.0; tp=1900.0-3.0*2=1894.0.
    stream = make_stream(symbol="XAUUSD", volume=0.1, sl_atr=1.5, tp_atr=3.0)
    h = execution_agent_factory(strategies={})
    h.agent._open_order(stream, "SELL", {"atr_value": 2.0})
    call = h.trading.open_calls[0]
    assert call["sl"] == pytest.approx(1903.0)
    assert call["tp"] == pytest.approx(1894.0)


def test_open_order_no_sltp_when_multipliers_zero(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.1, sl_atr=0.0, tp_atr=0.0)
    h = execution_agent_factory(strategies={})
    h.agent._open_order(stream, "BUY", {"atr_value": 2.0})
    call = h.trading.open_calls[0]
    assert call["sl"] == 0.0 and call["tp"] == 0.0


def test_open_order_trailing_strategy_zeroes_tp(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="trail", volume=0.1,
                         sl_atr=1.5, tp_atr=3.0)
    h = execution_agent_factory(strategies={"trail": make_strategy(trailing=True)})
    h.agent._open_order(stream, "BUY", {"atr_value": 2.0})
    call = h.trading.open_calls[0]
    assert call["sl"] == pytest.approx(1897.5)   # SL остаётся
    assert call["tp"] == 0.0                       # TP принудительно обнулён


def test_open_order_atr_zero_no_sltp(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", volume=0.1, sl_atr=1.5, tp_atr=3.0)
    h = execution_agent_factory(strategies={})
    h.agent._open_order(stream, "BUY", {"atr_value": 0})
    call = h.trading.open_calls[0]
    assert call["sl"] == 0.0 and call["tp"] == 0.0
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "open_order"`
Expected: 10 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация _open_order (volume + SL/TP по ATR) (E2)"
```

---

## Task 9: Хедж-нога

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
def test_strategy_wants_hedge_true(execution_agent_factory):
    stream = make_stream(strategy="hedge")
    h = execution_agent_factory(strategies={"hedge": make_strategy(hedge=True)})
    assert h.agent._strategy_wants_hedge(stream) is True


def test_strategy_wants_hedge_missing_strategy_false(execution_agent_factory):
    stream = make_stream(strategy="ghost")
    h = execution_agent_factory(strategies={})
    assert h.agent._strategy_wants_hedge(stream) is False


def test_strategy_wants_hedge_exception_false(execution_agent_factory):
    class Boom:
        def wants_hedge(self):
            raise RuntimeError("boom")
    stream = make_stream(strategy="boom")
    h = execution_agent_factory(strategies={"boom": Boom})
    assert h.agent._strategy_wants_hedge(stream) is False


def test_open_hedge_order_zero_volume_none(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", magic=777)
    h = execution_agent_factory()
    assert h.agent._open_hedge_order(stream, "SELL", 0.0) is None
    assert h.trading.open_calls == []


def test_open_hedge_order_builds_opposite_leg(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="s", magic=777)
    h = execution_agent_factory()
    res = h.agent._open_hedge_order(stream, "SELL", 0.1)
    assert res["volume"] == 0.1
    call = h.trading.open_calls[0]
    assert call["sl"] == 0.0 and call["tp"] == 0.0
    assert call["comment"].endswith(":H")
    assert call["magic"] == 777


async def test_hedge_emits_second_order_opened(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="hedge", volume=0.1)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"hedge": make_strategy(hedge=True)},
        now=datetime(2026, 6, 3, 12, 0),
    )
    h.trading.set_open_result({"order": 111, "price": 1900.5}, {"order": 222, "price": 1900.0})
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    opened = [e for e in h.bus.events if e.type == EventType.ORDER_OPENED]
    assert len(opened) == 2
    assert opened[1].payload["role"] == "H"
    assert opened[1].payload["type"] == "SELL"
    assert h.agent.metrics["opened_today"] == 2


async def test_hedge_leg_none_keeps_main_only(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="hedge", volume=0.1)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"hedge": make_strategy(hedge=True)},
        now=datetime(2026, 6, 3, 12, 0),
    )
    h.trading.set_open_result({"order": 111, "price": 1900.5}, None)  # хедж не открылся
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    opened = [e for e in h.bus.events if e.type == EventType.ORDER_OPENED]
    assert len(opened) == 1
    assert h.agent.metrics["opened_today"] == 1


async def test_no_hedge_strategy_single_leg(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="plain", volume=0.1)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"plain": make_strategy(hedge=False)},
        now=datetime(2026, 6, 3, 12, 0),
    )
    await h.agent._handle_signal(_signal_event(signal="BUY"))
    opened = [e for e in h.bus.events if e.type == EventType.ORDER_OPENED]
    assert len(opened) == 1
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "hedge"`
Expected: 8 PASS. FAIL → находка (особенно `test_hedge_leg_none_keeps_main_only`: проверить, что main-нога остаётся без пары — это поведение из кода, лог error, без ORDER_ERROR).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация хедж-ноги (E2)"
```

---

## Task 10: Эмит-события и метрики `_handle_signal`

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
async def test_open_happy_emits_order_opened_and_status_changed(execution_agent_factory):
    stream = make_stream(id="s1", symbol="XAUUSD", strategy="plain", volume=0.1, magic=777)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"plain": make_strategy()},
        now=datetime(2026, 6, 3, 12, 0),
    )
    await h.agent._handle_signal(_signal_event(signal="BUY", indicators={"atr_value": 2.0}))

    opened = [e for e in h.bus.events if e.type == EventType.ORDER_OPENED]
    assert len(opened) == 1
    p = opened[0].payload
    assert p["symbol"] == "XAUUSD"
    assert p["type"] == "BUY"
    assert p["volume"] == 0.1
    assert p["stream_id"] == "s1"
    assert p["magic"] == 777

    assert "XAUUSD" in h.status.opened   # status.mark_open вызван

    changed = [e for e in h.bus.events if e.type == EventType.TRADING_STATUS_CHANGED]
    assert len(changed) == 1
    assert changed[0].payload["status"] == 1
    assert changed[0].payload["reason"] == "order_opened"

    assert h.agent.metrics["opened_today"] == 1


async def test_open_returns_none_no_events(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="plain", volume=0.0)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"plain": make_strategy()},
        now=datetime(2026, 6, 3, 12, 0),
        calc_result=0.0,   # volume<=0 → _open_order вернёт None
    )
    await h.agent._handle_signal(_signal_event(signal="BUY", indicators={"atr_value": 2.0}))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_OPENED] == []
    assert h.status.opened == []


async def test_open_exception_emits_order_error(execution_agent_factory, monkeypatch):
    stream = make_stream(symbol="XAUUSD", strategy="plain", volume=0.1)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"plain": make_strategy()},
        now=datetime(2026, 6, 3, 12, 0),
    )
    def boom(*a, **k):
        raise RuntimeError("open fail")
    monkeypatch.setattr(h.agent, "_open_order", boom)
    await h.agent._handle_signal(_signal_event(signal="BUY", indicators={"atr_value": 2.0}))
    errors = [e for e in h.bus.events if e.type == EventType.ORDER_ERROR]
    assert len(errors) == 1
    assert "open fail" in errors[0].payload["error"]
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "open_happy or returns_none_no_events or open_exception"`
Expected: 3 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация эмита/метрик _handle_signal (E2)"
```

---

## Task 11: `_handle_close`

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
async def test_close_happy_emits_order_closed(execution_agent_factory):
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    h.trading.set_close_result(True)
    await h.agent._handle_close(_close_event(ticket=555, symbol="XAUUSD", reason="tp"))
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    p = closed[0].payload
    assert p["ticket"] == 555
    assert p["symbol"] == "XAUUSD"
    assert p["reason"] == "tp"
    assert p["tag"] == "TP"
    assert h.agent.metrics["closed_today"] == 1
    # tag прокинут в orderClose
    assert h.trading.close_calls[0]["tag"] == "TP"


async def test_close_falsy_result_no_event(execution_agent_factory):
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    h.trading.set_close_result(False)
    await h.agent._handle_close(_close_event(ticket=555, symbol="XAUUSD", reason="manual"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED] == []


async def test_close_exception_emits_order_error(execution_agent_factory):
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    def boom(*a, **k):
        raise RuntimeError("close fail")
    h.trading.orderClose = boom
    await h.agent._handle_close(_close_event(ticket=555, symbol="XAUUSD"))
    errors = [e for e in h.bus.events if e.type == EventType.ORDER_ERROR]
    assert len(errors) == 1
    assert errors[0].payload["ticket"] == 555
    assert "close fail" in errors[0].payload["error"]
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "close_happy or close_falsy or close_exception"`
Expected: 3 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация _handle_close (E2)"
```

---

## Task 12: Диспетчеризация через `run()`

**Files:**
- Modify: `tests/execution/test_execution_agent.py`

- [ ] **Step 1: Написать тесты**

Добавить:

```python
async def test_dispatch_signal_through_run(execution_agent_factory):
    stream = make_stream(symbol="XAUUSD", strategy="plain", volume=0.1)
    h = execution_agent_factory(
        streams={"s1": stream},
        strategies={"plain": make_strategy()},
        now=datetime(2026, 6, 3, 12, 0),
    )
    await h.agent._on_signal(_signal_event(signal="BUY", indicators={"atr_value": 2.0}))
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_OPENED]


async def test_dispatch_close_through_run(execution_agent_factory):
    h = execution_agent_factory(now=datetime(2026, 6, 3, 12, 0))
    h.trading.set_close_result(True)
    await h.agent._on_close_request(_close_event(ticket=555, symbol="XAUUSD", reason="sl"))
    await h.agent.run()
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    assert closed[0].payload["tag"] == "SL"
```

- [ ] **Step 2: Запустить**

Run: `pytest tests/execution/test_execution_agent.py -v -k "dispatch"`
Expected: 2 PASS.

**Примечание для исполнителя:** `run()` сначала зовёт `emit_status(IDLE)`, затем снимает один элемент из `_queue`. Так как элемент уже положен через `_on_signal`/`_on_close_request`, `await self._queue.get()` не блокируется. `run_in_executor` исполняется дефолтным пулом — `await` дожидается future.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_execution_agent.py
git commit -m "test(execution): характеризация диспетчеризации run() (E2)"
```

---

## Task 13: Полный прогон + обновление документации

**Files:**
- Modify (только при находках): `docs/known-issues.md`
- Modify: `memory/project_millionskeeper.md` (через память — не в этом репо; обновляется отдельно)

- [ ] **Step 1: Полный прогон сетки**

Run: `pytest -q`
Expected: все зелёные. Ожидаемо `~308–313 passed, 2 xfailed` (было `276 passed, 2 xfailed`; +~30–35, плюс возможные xfail от находок). Зафиксировать фактическое число.

- [ ] **Step 2: Если были находки — записать в `docs/known-issues.md`**

Для каждой находки добавить запись `#5`+ по образцу существующих (симптом, место в коде `agents/execution_agent.py:NNN`, желаемое поведение, ссылка на xfail-тест). Если находок нет — пропустить шаг.

- [ ] **Step 3: Commit (если были изменения в known-issues)**

```bash
git add docs/known-issues.md
git commit -m "docs(known-issues): находки E2 характеризации ExecutionAgent"
```

- [ ] **Step 4: Верификация — повторный полный прогон**

Run: `pytest -q`
Expected: то же зелёное число, что в Step 1. Боевой `agents/execution_agent.py` НЕ изменён (`git diff --stat agents/execution_agent.py` пуст).

---

## Self-Review (выполнено при написании плана)

- **Spec coverage:** gating (Task 4) ✓, ночь (Task 5) ✓, equity (Task 6) ✓, DD + recovery/сброс окна (Task 7) ✓, SL/TP+volume+trailing (Task 8) ✓, хедж (Task 9) ✓, эмит+метрики (Task 10) ✓, close+_reason_to_tag (Task 3+11) ✓, dispatch (Task 12) ✓, расширение fakes (Task 1) ✓, фикстура (Task 2) ✓, полный прогон+находки (Task 13) ✓.
- **Placeholder scan:** код приведён полностью в каждом шаге; плейсхолдеров нет.
- **Type consistency:** `make_stream`/`make_deal`/`make_position`/`make_strategy`/`make_clock`/`FakeTrading`/`FakeBus`/`FakeRegistry` определены в Task 1 и используются согласованно; `FakeTrading.set_open_result`/`set_close_result`/`set_calc_result`/`open_calls`/`close_calls`/`calc_calls` — единые имена во всех тасках; фикстура `execution_agent_factory` возвращает namespace с полями `agent/bus/trading/mt5/cache/status/registry`, используемыми единообразно.
