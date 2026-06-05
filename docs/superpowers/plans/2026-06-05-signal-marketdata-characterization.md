# E4 — Характеризация signal_agent + market_data_agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запереть текущее поведение `agents/signal_agent.py` и `agents/market_data_agent.py` характеризационной сеткой, прод не трогая.

**Architecture:** Переиспользуем харнесс `tests/execution/` (FakeMT5/FakeBus/FakeRegistry/FakeStatus/FakeCache). Аддитивно дополняем `fakes.py`, добавляем 2 фабрики-фикстуры в `conftest.py`, пишем 2 файла тестов. Монкипатч модульных глобалов — боевой код не меняется.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio (asyncio_mode=auto), pandas.

**⚠️ Характеризация, не TDD:** тесты пишутся под УЖЕ СУЩЕСТВУЮЩЕЕ поведение и должны проходить сразу против прод-кода. Если тест падает — это НАХОДКА: разобраться, привести ассерт к фактическому поведению ИЛИ зафиксировать `xfail` + запись в `docs/known-issues.md`. **Боевой код не правим.**

**⚠️ Инвариант трека:** в `tests/execution/` НЕ импортировать `trading` на уровне модуля (catch-22 E1). В E4 `trading` не нужен вовсе.

---

## File Structure

- **Modify:** `tests/execution/fakes.py` — аддитивные дополнения фейков (Task 1).
- **Modify:** `tests/execution/conftest.py` — 2 новые фабрики-фикстуры (Tasks 2, 6).
- **Create:** `tests/execution/test_signal_agent.py` — тесты SignalAgent (Tasks 3–5).
- **Create:** `tests/execution/test_market_data_agent.py` — тесты MarketDataAgent (Tasks 7–10).

---

## Task 1: Аддитивные дополнения харнесса (`fakes.py`)

**Files:**
- Modify: `tests/execution/fakes.py`

- [ ] **Step 1: Добавить `terminal_info()` в FakeMT5**

В `FakeMT5.__init__` (после `self._error = (1, "fake error")`) добавить:

```python
        self.terminal = SimpleNamespace(connected=True)   # terminal_info(); None → disconnected
```

В тело класса `FakeMT5` (рядом с другими методами, например после `last_error`) добавить:

```python
    def terminal_info(self):
        return self.terminal
```

- [ ] **Step 2: Добавить `is_disabled`/`mark_disabled` в FakeStatus**

В `FakeStatus.__init__` добавить поле:

```python
        self._disabled = set()
```

В тело класса `FakeStatus` добавить:

```python
    def mark_disabled(self, symbol):
        self._disabled.add(symbol)

    def is_disabled(self, symbol):
        return symbol in self._disabled
```

- [ ] **Step 3: Добавить `invalidate()`/флаг в FakeCache**

В `FakeCache.__init__` добавить поле:

```python
        self.invalidated = False
```

В тело класса `FakeCache` добавить:

```python
    def invalidate(self):
        self.invalidated = True
```

- [ ] **Step 4: Добавить `enabled()` в FakeRegistry**

В тело класса `FakeRegistry` добавить:

```python
    def enabled(self):
        return [s for s in self._streams.values() if getattr(s, "enabled", True)]
```

- [ ] **Step 5: Добавить хелпер `make_bars_df`**

В конец `fakes.py` добавить:

```python
def make_bars_df(*, time, n=2, close=1.0):
    """pandas DataFrame баров для cache.get_rates (market_data берёт .iloc[-1]['time']).

    time: int (epoch) или pd.Timestamp — обе ветки нормализации в агенте.
    """
    import pandas as pd
    return pd.DataFrame({"time": [time] * n, "close": [close] * n})
```

- [ ] **Step 6: Проверить импортируемость**

Run: `python -c "from tests.execution.fakes import FakeMT5, FakeStatus, FakeCache, FakeRegistry, make_bars_df; m=FakeMT5(); assert m.terminal_info().connected; s=FakeStatus(); s.mark_disabled('X'); assert s.is_disabled('X'); c=FakeCache(); c.invalidate(); assert c.invalidated; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Прогон существующих тестов (регрессия харнесса)**

Run: `python -m pytest tests/execution/ -q`
Expected: все прежние тесты зелёные (дополнения аддитивны).

- [ ] **Step 8: Commit**

```bash
git add tests/execution/fakes.py
git commit -m "test(E4): дополнения харнесса под signal/market_data (terminal_info/is_disabled/invalidate/enabled/make_bars_df)"
```

---

## Task 2: Фикстура `signal_agent_factory`

**Files:**
- Modify: `tests/execution/conftest.py`

- [ ] **Step 1: Добавить фабрику в conftest.py**

В конец `tests/execution/conftest.py` добавить:

```python
@pytest.fixture
def signal_agent_factory(monkeypatch):
    """Фабрика SignalAgent с подменённым status. Прод не трогаем.

    Драйв: положить INDICATORS_READY-event в agent._queue, затем `await agent.run()`
    (run читает ровно одно событие из очереди и завершается).
    """
    from tests.execution.fakes import FakeStatus, FakeBus

    def make(*, status_map=None):
        import agents.signal_agent as sa_mod

        fake_status = FakeStatus()
        if status_map:
            fake_status._status.update(status_map)
        monkeypatch.setattr(sa_mod, "status", fake_status)

        agent = sa_mod.SignalAgent("Signal", FakeBus())
        return SimpleNamespace(agent=agent, bus=agent.bus, status=fake_status)

    return make
```

- [ ] **Step 2: Smoke-проверка фабрики**

Создать временный `tests/execution/test_smoke_signal.py`:

```python
import pytest
from core.events import Event, EventType


async def test_smoke_signal_factory(signal_agent_factory):
    h = signal_agent_factory()
    ev = Event(type=EventType.INDICATORS_READY, source="t",
               payload={"symbol": "XAUUSD", "entry_signal": "BUY"})
    h.agent._queue.put_nowait(ev)
    await h.agent.run()
    types = [e.type for e in h.bus.events]
    assert EventType.SIGNAL_GENERATED in types
```

Run: `python -m pytest tests/execution/test_smoke_signal.py -q`
Expected: PASS

- [ ] **Step 3: Удалить smoke-файл**

```bash
git rm -f --ignore-unmatch tests/execution/test_smoke_signal.py 2>/dev/null; rm -f tests/execution/test_smoke_signal.py
```

- [ ] **Step 4: Commit**

```bash
git add tests/execution/conftest.py
git commit -m "test(E4): фикстура signal_agent_factory"
```

---

## Task 3: SignalAgent — приоритет entry_signal

**Files:**
- Create: `tests/execution/test_signal_agent.py`

- [ ] **Step 1: Написать тесты**

Создать `tests/execution/test_signal_agent.py`:

```python
"""Характеризация SignalAgent (E4). Прод не трогаем."""
import pytest
from core.events import Event, EventType


def _run_signal(h):
    """Вернуть payload первого SIGNAL_GENERATED."""
    for e in h.bus.events:
        if e.type == EventType.SIGNAL_GENERATED:
            return e
    return None


async def _feed(h, payload, correlation_id=None):
    ev = Event(type=EventType.INDICATORS_READY, source="t",
               payload=payload, correlation_id=correlation_id)
    h.agent._queue.put_nowait(ev)
    await h.agent.run()


async def test_entry_signal_buy_wins_over_legacy(signal_agent_factory):
    h = signal_agent_factory()
    # legacy сказал бы SELL, но entry_signal=BUY перебивает
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "BUY",
        "signal_ma": "SELL", "signal_critical_angle": "SELL",
        "macd_signal": "SELL", "rsi_signal": "SELL",
    })
    assert _run_signal(h).payload["signal"] == "BUY"
    assert h.agent.metrics["buy_signals"] == 1
    assert h.agent.metrics["sell_signals"] == 0


async def test_entry_signal_sell(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "SELL"})
    assert _run_signal(h).payload["signal"] == "SELL"
    assert h.agent.metrics["sell_signals"] == 1


async def test_entry_no_signal_short_circuits_legacy(signal_agent_factory):
    """entry_signal=NO_SIGNAL перебивает даже полностью-BUY legacy (нюанс)."""
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "NO_SIGNAL",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
    })
    assert _run_signal(h).payload["signal"] == "NO_SIGNAL"
    assert h.agent.metrics["buy_signals"] == 0


async def test_entry_signal_missing_falls_to_legacy(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",  # entry_signal отсутствует
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
    })
    assert _run_signal(h).payload["signal"] == "BUY"


async def test_entry_signal_garbage_falls_to_legacy(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "FOO",
        "signal_ma": "SELL", "signal_critical_angle": "SELL",
        "macd_signal": "SELL", "rsi_signal": "SELL",
    })
    assert _run_signal(h).payload["signal"] == "SELL"
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_signal_agent.py -q`
Expected: 5 passed. **Если падает — находка** (разобрать, привести ассерт к факту/ xfail).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_signal_agent.py
git commit -m "test(E4): характеризация SignalAgent — приоритет entry_signal над legacy"
```

---

## Task 4: SignalAgent — legacy MA+MACD+RSI

**Files:**
- Modify: `tests/execution/test_signal_agent.py`

- [ ] **Step 1: Дописать тесты legacy-логики**

Добавить в конец `tests/execution/test_signal_agent.py`:

```python
async def test_legacy_all_buy(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
    })
    assert _run_signal(h).payload["signal"] == "BUY"
    assert h.agent.metrics["buy_signals"] == 1


async def test_legacy_all_sell(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",
        "signal_ma": "SELL", "signal_critical_angle": "SELL",
        "macd_signal": "SELL", "rsi_signal": "SELL",
    })
    assert _run_signal(h).payload["signal"] == "SELL"
    assert h.agent.metrics["sell_signals"] == 1


async def test_legacy_mixed_is_no_signal(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "NO_SIGNAL",
    })
    assert _run_signal(h).payload["signal"] == "NO_SIGNAL"
    assert h.agent.metrics["buy_signals"] == 0
    assert h.agent.metrics["sell_signals"] == 0


async def test_legacy_missing_keys_default_no_signal(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD"})  # ни одного legacy-ключа
    assert _run_signal(h).payload["signal"] == "NO_SIGNAL"
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_signal_agent.py -q`
Expected: 9 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_signal_agent.py
git commit -m "test(E4): характеризация SignalAgent — legacy MA+MACD+RSI"
```

---

## Task 5: SignalAgent — эмит/проброс/метрики

**Files:**
- Modify: `tests/execution/test_signal_agent.py`

- [ ] **Step 1: Дописать тесты эмита и проброса**

Добавить в конец `tests/execution/test_signal_agent.py`:

```python
async def test_correlation_id_passthrough(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY"},
                correlation_id="cid-42")
    assert _run_signal(h).correlation_id == "cid-42"


async def test_trading_status_and_stream_id_passthrough(signal_agent_factory):
    h = signal_agent_factory(status_map={"XAUUSD": 1})
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY", "stream_id": "s7"})
    p = _run_signal(h).payload
    assert p["trading_status"] == 1
    assert p["stream_id"] == "s7"


async def test_indicators_dict_keys_present(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {
        "symbol": "XAUUSD", "entry_signal": "BUY",
        "signal_ma": "BUY", "signal_critical_angle": "BUY",
        "macd_signal": "BUY", "rsi_signal": "BUY",
        "rsi_value": 55.0, "atr_value": 2.0, "adx_value": 30.0,
        "ema8": 1900.0, "ema21": 1899.0,
    })
    ind = _run_signal(h).payload["indicators"]
    assert ind == {
        "ma": "BUY", "ma_angle": "BUY", "macd": "BUY", "rsi": "BUY",
        "rsi_value": 55.0, "atr_value": 2.0, "adx_value": 30.0,
        "ema8": 1900.0, "ema21": 1899.0,
    }


async def test_indicators_dict_missing_values_are_none(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY"})
    ind = _run_signal(h).payload["indicators"]
    assert ind["rsi_value"] is None
    assert ind["atr_value"] is None
    assert ind["ema8"] is None
    # legacy-сигналы при отсутствии дефолтятся в "NO_SIGNAL"
    assert ind["ma"] == "NO_SIGNAL"


async def test_emits_agent_status_then_signal(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "BUY"})
    types = [e.type for e in h.bus.events]
    # idle (старт) → running → SIGNAL_GENERATED
    assert types.count(EventType.AGENT_STATUS) == 2
    assert types[-1] == EventType.SIGNAL_GENERATED


async def test_no_signal_does_not_increment_metrics(signal_agent_factory):
    h = signal_agent_factory()
    await _feed(h, {"symbol": "XAUUSD", "entry_signal": "NO_SIGNAL"})
    assert h.agent.metrics["buy_signals"] == 0
    assert h.agent.metrics["sell_signals"] == 0
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_signal_agent.py -q`
Expected: 15 passed. **Если `test_indicators_dict_keys_present` падает по порядку/составу — привести ассерт к факту.**

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_signal_agent.py
git commit -m "test(E4): характеризация SignalAgent — эмит/проброс/метрики"
```

---

## Task 6: Фикстура `market_data_agent_factory`

**Files:**
- Modify: `tests/execution/conftest.py`

- [ ] **Step 1: Добавить фабрику в conftest.py**

В конец `tests/execution/conftest.py` добавить:

```python
@pytest.fixture
def market_data_agent_factory(monkeypatch):
    """Фабрика MarketDataAgent с подменёнными зависимостями. Прод не трогаем.

    Патчит streams.registry, agents.market_data_agent.status,
    market_data_cache.cache, sys.modules['MetaTrader5']. poll_interval=0.
    `trading` не импортируется (инвариант трека).
    """
    from tests.execution.fakes import FakeMT5, FakeCache, FakeStatus, FakeBus, FakeRegistry

    def make(*, streams=None, rates_df=None, terminal=True, disabled=None):
        import agents.market_data_agent as md_mod
        import streams as streams_mod
        import market_data_cache as mdc_mod

        fake_mt5 = FakeMT5()
        fake_mt5.terminal = None if terminal is None else fake_mt5.terminal
        fake_cache = FakeCache()
        fake_cache.rates_df = rates_df
        fake_status = FakeStatus()
        for sym in (disabled or []):
            fake_status.mark_disabled(sym)
        fake_registry = FakeRegistry(streams or {})

        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(md_mod, "status", fake_status)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)

        agent = md_mod.MarketDataAgent("MarketData", FakeBus(), poll_interval=0)
        return SimpleNamespace(
            agent=agent, bus=agent.bus, registry=fake_registry,
            status=fake_status, cache=fake_cache, mt5=fake_mt5,
        )

    return make
```

- [ ] **Step 2: Smoke-проверка**

Создать `tests/execution/test_smoke_md.py`:

```python
from tests.execution.fakes import make_stream, make_bars_df
from core.events import EventType


async def test_smoke_md_factory(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    types = [e.type for e in h.bus.events]
    assert EventType.MARKET_CACHE_INVALIDATED in types
    assert EventType.MT5_CONNECTED in types
    assert h.cache.invalidated is True
```

Run: `python -m pytest tests/execution/test_smoke_md.py -q`
Expected: PASS

- [ ] **Step 3: Удалить smoke-файл**

```bash
rm -f tests/execution/test_smoke_md.py
```

- [ ] **Step 4: Commit**

```bash
git add tests/execution/conftest.py
git commit -m "test(E4): фикстура market_data_agent_factory"
```

---

## Task 7: MarketDataAgent — `_current_pairs` и метрики

**Files:**
- Create: `tests/execution/test_market_data_agent.py`

- [ ] **Step 1: Написать тесты**

Создать `tests/execution/test_market_data_agent.py`:

```python
"""Характеризация MarketDataAgent (E4). Прод не трогаем."""
import pytest
from core.events import EventType
from tests.execution.fakes import make_stream, make_bars_df


def _types(h):
    return [e.type for e in h.bus.events]


def _payload(h, etype):
    for e in h.bus.events:
        if e.type == etype:
            return e.payload
    return None


async def test_current_pairs_dedup(market_data_agent_factory):
    h = market_data_agent_factory(streams={
        "s1": make_stream(id="s1", symbol="XAUUSD", timeframe=16385),
        "s2": make_stream(id="s2", symbol="XAUUSD", timeframe=16385),
    }, rates_df=make_bars_df(time=1000))
    await h.agent.run()
    assert h.agent.metrics["pairs"] == 1
    assert h.agent.metrics["symbols"] == 1


async def test_current_pairs_skips_disabled_status(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
        disabled=["XAUUSD"],
    )
    await h.agent.run()
    assert h.agent.metrics["pairs"] == 0


async def test_current_pairs_skips_disabled_stream(market_data_agent_factory):
    h = market_data_agent_factory(streams={
        "s1": make_stream(id="s1", symbol="XAUUSD", enabled=True),
        "s2": make_stream(id="s2", symbol="EURUSD", enabled=False),
    }, rates_df=make_bars_df(time=1000))
    await h.agent.run()
    assert h.agent.metrics["symbols"] == 1
    assert h.agent.metrics["pairs"] == 1


async def test_current_pairs_distinct_symbols(market_data_agent_factory):
    h = market_data_agent_factory(streams={
        "s1": make_stream(id="s1", symbol="XAUUSD", timeframe=16385),
        "s2": make_stream(id="s2", symbol="EURUSD", timeframe=16385),
        "s3": make_stream(id="s3", symbol="XAUUSD", timeframe=16408),
    }, rates_df=make_bars_df(time=1000))
    await h.agent.run()
    assert h.agent.metrics["symbols"] == 2
    assert h.agent.metrics["pairs"] == 3
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_market_data_agent.py -q`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_market_data_agent.py
git commit -m "test(E4): характеризация MarketDataAgent — _current_pairs/метрики"
```

---

## Task 8: MarketDataAgent — connect/disconnect + invalidate

**Files:**
- Modify: `tests/execution/test_market_data_agent.py`

- [ ] **Step 1: Дописать тесты**

Добавить в конец `tests/execution/test_market_data_agent.py`:

```python
async def test_emits_cache_invalidated(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert h.cache.invalidated is True
    assert _payload(h, EventType.MARKET_CACHE_INVALIDATED) == {"pairs": 1}


async def test_terminal_disconnected(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
        terminal=None,
    )
    await h.agent.run()
    types = _types(h)
    assert EventType.MT5_DISCONNECTED in types
    assert EventType.MT5_CONNECTED not in types
    assert EventType.NEW_BAR not in types
    # последний AGENT_STATUS — error
    statuses = [e.payload["status"] for e in h.bus.events
                if e.type == EventType.AGENT_STATUS]
    assert statuses[-1] == "error"


async def test_terminal_connected(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert EventType.MT5_CONNECTED in _types(h)
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_market_data_agent.py -q`
Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_market_data_agent.py
git commit -m "test(E4): характеризация MarketDataAgent — connect/disconnect/invalidate"
```

---

## Task 9: MarketDataAgent — детект новой свечи

**Files:**
- Modify: `tests/execution/test_market_data_agent.py`

- [ ] **Step 1: Дописать тесты**

Добавить в конец `tests/execution/test_market_data_agent.py`:

```python
async def test_first_sight_records_no_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert h.agent.metrics["new_bars"] == 0
    assert EventType.NEW_BAR not in _types(h)
    assert h.agent._last_bar_times[("XAUUSD", 16385)] == 1000


async def test_second_run_greater_time_emits_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()                       # первый показ
    h.cache.rates_df = make_bars_df(time=2000)
    await h.agent.run()                       # новая свеча
    bars = [e for e in h.bus.events if e.type == EventType.NEW_BAR]
    assert len(bars) == 1
    assert bars[0].payload == {"symbol": "XAUUSD", "bar_time": 2000, "timeframe": 16385}


async def test_second_run_equal_time_no_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    await h.agent.run()                       # тот же time
    assert EventType.NEW_BAR not in _types(h)


async def test_second_run_lesser_time_no_new_bar(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=2000),
    )
    await h.agent.run()
    h.cache.rates_df = make_bars_df(time=1000)
    await h.agent.run()                       # время «откатилось»
    assert EventType.NEW_BAR not in _types(h)
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_market_data_agent.py -q`
Expected: 11 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_market_data_agent.py
git commit -m "test(E4): характеризация MarketDataAgent — детект новой свечи"
```

---

## Task 10: MarketDataAgent — rates-edge, конверсия времени, очистка, исключение

**Files:**
- Modify: `tests/execution/test_market_data_agent.py`

- [ ] **Step 1: Дописать тесты**

Добавить в конец `tests/execution/test_market_data_agent.py`:

```python
async def test_rates_none_skipped(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=None,
    )
    await h.agent.run()
    assert h.agent.metrics["new_bars"] == 0
    assert EventType.NEW_BAR not in _types(h)


async def test_rates_empty_skipped(market_data_agent_factory):
    import pandas as pd
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=pd.DataFrame({"time": []}),
    )
    await h.agent.run()
    assert h.agent.metrics["new_bars"] == 0


async def test_time_pd_timestamp_normalized(market_data_agent_factory):
    import pandas as pd
    ts = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=ts),
    )
    await h.agent.run()
    assert h.agent._last_bar_times[("XAUUSD", 16385)] == int(ts.timestamp())


async def test_time_int_normalized(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1234567890),
    )
    await h.agent.run()
    assert h.agent._last_bar_times[("XAUUSD", 16385)] == 1234567890


async def test_removed_pair_cleared_between_runs(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(id="s1", symbol="XAUUSD", timeframe=16385)},
        rates_df=make_bars_df(time=1000),
    )
    await h.agent.run()
    assert ("XAUUSD", 16385) in h.agent._last_bar_times
    # пара исчезла из потоков
    h.registry._streams.clear()
    await h.agent.run()
    assert ("XAUUSD", 16385) not in h.agent._last_bar_times


async def test_symbol_exception_caught(market_data_agent_factory):
    h = market_data_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD")},
        rates_df=make_bars_df(time=1000),
    )
    def boom(*a, **k):
        raise RuntimeError("rates boom")
    h.cache.get_rates = boom
    # не должно бросить наружу; статус доходит до IDLE
    await h.agent.run()
    statuses = [e.payload["status"] for e in h.bus.events
                if e.type == EventType.AGENT_STATUS]
    assert statuses[-1] == "idle"
    assert h.agent.metrics["new_bars"] == 0
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_market_data_agent.py -q`
Expected: 17 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_market_data_agent.py
git commit -m "test(E4): характеризация MarketDataAgent — rates-edge/время/очистка/исключение"
```

---

## Task 11: Полный прогон + обновление памяти

**Files:**
- Modify: `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md`

- [ ] **Step 1: Полный прогон всего набора (регрессия)**

Run: `python -m pytest -q`
Expected: все прежние тесты зелёные + новые (~32 теста signal+market_data). 3 xfailed без новых регрессий. Записать фактические числа.

- [ ] **Step 2: Если есть находки — зафиксировать**

Если какой-либо тест выявил расхождение поведения: занести в `docs/known-issues.md` (номер #8+), пометить тест `@pytest.mark.xfail(reason=...)`. **Прод не править.**

- [ ] **Step 3: Обновить память**

В `project_millionskeeper.md`:
- Строка-список тестов (раздел «Тесты»): добавить `test_signal_agent.py` + `test_market_data_agent.py` (E4, N кейсов).
- Обновить «Текущий прогон: ... passed».
- В «Статус работ» добавить пункт `[x] E4 — характеризация signal/market_data ...` с описанием покрытия, цикла, находок (или «0 находок»), путями спеки/плана.
- В backlog #2 отметить E4 закрытым; обновить «осталось».

- [ ] **Step 4: Commit**

```bash
git add docs/ tests/
git commit -m "test(E4): полный прогон зелёный + фиксация находок (если есть)"
```

(память — отдельным шагом вне git, файлы памяти вне репо.)

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** SignalAgent #1–14 → Tasks 3–5; MarketDataAgent #1–18 → Tasks 7–10; харнесс-дополнения → Task 1; фабрики → Tasks 2,6. ✅
- **Плейсхолдеры:** нет — весь тест-код приведён целиком. ✅
- **Согласованность имён:** `signal_agent_factory`/`market_data_agent_factory`, `make_bars_df(time=...)`, `terminal`, `is_disabled`/`mark_disabled`, `invalidated`, `enabled()` — единообразны во всех тасках. ✅
- **Инвариант трека:** `trading` нигде не импортируется. ✅
