# PositionMonitorAgent Characterization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запереть поведение `agents/position_monitor_agent.py` характеризационной сеткой (~50 кейсов) без правок прода.

**Architecture:** Агент берёт `trading`/`bus` через конструктор (инъекция фейков). Остальное — модульный `status` + ленивые `streams`/`STRATEGIES`/`strategies.runtime`/`market_data_cache`/`MetaTrader5`/`talib`/`indicators` — подменяются monkeypatch. ATR детерминируется monkeypatch `talib.ATR`. `status` подменяется РЕАЛЬНЫМ `TradingStatusRegistry(seed=...)`. Тесты зовут private-методы напрямую + 1–2 dispatch через `run()`.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio (`asyncio_mode=auto`), numpy/pandas (есть). Без новых зависимостей.

**Характеризационная инверсия TDD:** тест пишется ПОСЛЕ изучения прод-поведения и должен **пройти сразу**. Шаг «запустить»: PASS = заперто; FAIL = находка → не править прод/не подгонять, сообщить (xfail/known-issues).

**ИНВАРИАНТ (урок E1b):** НЕ импортировать `trading` на уровне модуля в `tests/execution/`. Агент `trading` не импортирует — `self.trading` инъектируется фейком.

**Спека:** [docs/superpowers/specs/2026-06-04-position-monitor-characterization-design.md](../specs/2026-06-04-position-monitor-characterization-design.md)

---

## File Structure

- **Modify** `tests/execution/fakes.py` — FakeTrading (+getPositions/+modifySL), FakeMT5 (+copy_rates_from_pos, history_deals_get +position=), FakeCache (+get_rates), FakeRegistry (+by_magic), make_stream (+breakeven_atr/trail_atr/timeframe), make_deal (+comment), новые make_mt5_position/make_rates/make_runtime_strategy/make_rsi.
- **Modify** `tests/execution/conftest.py` — фикстура `position_monitor_agent_factory`.
- **Create** `tests/execution/test_position_monitor.py` — кейсы.
- **Modify** `docs/known-issues.md` — #7 dead-code (calculateStopLoss/calculateMaxMinValue).

---

## Task 1: Расширить харнесс `fakes.py`

**Files:** Modify `tests/execution/fakes.py`

- [ ] **Step 1: Расширить `FakeMT5`**

В `FakeMT5.__init__`, после `self.deals = []`, добавить:
```python
        self.rates = None                    # copy_rates_from_pos (None=по умолчанию make_rates(30))
```
Заменить `history_deals_get` (добавить параметр `position`):
```python
    def history_deals_get(self, date_from=None, date_to=None, position=None):
        return list(self.deals)
```
Добавить метод (рядом с symbol_info):
```python
    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self.rates if self.rates is not None else make_rates(30)
```

- [ ] **Step 2: Расширить `FakeCache`**

В `FakeCache.__init__`, после `self.account_info = ...`, добавить:
```python
        self.rates_df = None                 # get_rates (None → пусто)
```
Добавить метод:
```python
    def get_rates(self, symbol, timeframe, bars=None):
        return self.rates_df
```

- [ ] **Step 3: Расширить `FakeRegistry` методом `by_magic`**

В `FakeRegistry` добавить:
```python
    def by_magic(self, magic):
        for s in self._streams.values():
            if getattr(s, "magic", None) == magic:
                return s
        return None
```

- [ ] **Step 4: Расширить `FakeTrading` (getPositions + modifySL)**

В `FakeTrading.__init__`, после `self._calc_result = 0.5`, добавить:
```python
        self.positions_list = []             # отдаётся getPositions()
        self.modify_calls = []               # записи modifySL
        self._modify_result = True
```
Добавить методы:
```python
    def getPositions(self):
        return list(self.positions_list)

    def set_modify_result(self, val):
        self._modify_result = val

    def modifySL(self, ticket, symbol, new_sl, new_tp=None):
        self.modify_calls.append(dict(ticket=ticket, symbol=symbol, new_sl=new_sl, new_tp=new_tp))
        return self._modify_result
```

- [ ] **Step 5: Расширить `make_stream` и `make_deal`**

Заменить сигнатуру/тело `make_stream` (добавить breakeven_atr/trail_atr/timeframe):
```python
def make_stream(*, id="s1", name="Stream-1", strategy="default", symbol="XAUUSD",
                volume=0.1, sl_atr=0.0, tp_atr=0.0, magic=777, deposit=0.0,
                enabled=True, breakeven_atr=0.0, trail_atr=0.0, timeframe=16385):
    """TradingStream-подобный объект для тестов агентов."""
    return SimpleNamespace(
        id=id, name=name, strategy=strategy, symbol=symbol,
        volume=volume, sl_atr=sl_atr, tp_atr=tp_atr, magic=magic,
        deposit=deposit, enabled=enabled,
        breakeven_atr=breakeven_atr, trail_atr=trail_atr, timeframe=timeframe,
    )
```
Заменить сигнатуру/тело `make_deal` (добавить comment):
```python
def make_deal(*, magic=777, profit=0.0, commission=0.0, swap=0.0, comment=""):
    """Фейковый закрытый deal MT5 (для history_deals_get)."""
    return SimpleNamespace(magic=magic, profit=profit, commission=commission,
                           swap=swap, comment=comment)
```

- [ ] **Step 6: Добавить новые хелперы в конец `fakes.py`**

```python
def make_mt5_position(*, ticket=1001, symbol="XAUUSD", type=0, volume=0.1,
                      price_open=1899.0, sl=0.0, profit=12.34, time=1_700_000_000,
                      magic=777, comment=""):
    """MT5-подобная открытая позиция (для FakeTrading.getPositions). type: 0=BUY,1=SELL."""
    return SimpleNamespace(
        ticket=ticket, symbol=symbol, type=type, volume=volume,
        price_open=price_open, sl=sl, profit=profit, time=time,
        magic=magic, comment=comment,
    )


def make_rates(n=30, *, high=1.05, low=0.95, close=1.0, open_=1.0):
    """numpy structured array баров для copy_rates_from_pos (значения неважны — ATR замокан)."""
    import numpy as np
    arr = np.zeros(n, dtype=[("open", "f8"), ("high", "f8"), ("low", "f8"), ("close", "f8")])
    arr["open"] = open_
    arr["high"] = high
    arr["low"] = low
    arr["close"] = close
    return arr


def make_runtime_strategy(*, exit_signal=False, hedge_exit_signal=False,
                          wants_hedge=False, raise_on_exit=False, raise_on_closed=False):
    """Фейк рантайм-стратегии (под get_runtime_strategy)."""
    class _S:
        def __init__(self):
            self.closed_calls = []
        def compute_indicators(self, df):
            return df
        def compute_flat_indicators(self, df):
            return df
        def get_exit_signal(self, row, pos):
            if raise_on_exit:
                raise RuntimeError("exit boom")
            return exit_signal
        def get_hedge_exit_signal(self, row, pos):
            return hedge_exit_signal
        def wants_hedge(self):
            return wants_hedge
        def on_trade_closed(self, pos, reason):
            if raise_on_closed:
                raise RuntimeError("closed boom")
            self.closed_calls.append((pos, reason))
    return _S()


def make_rsi(value):
    """Фабрика фейк-класса RSI (под indicators.RSI). value=None → нет данных."""
    import pandas as pd
    class _RSI:
        def get_rsi_talib(self, symbol, timeframe):
            if value is None:
                return None
            return {"RSI": pd.Series([value])}
    return _RSI
```

- [ ] **Step 7: Проверить импорт и обратную совместимость**

Run: `python -c "import tests.execution.fakes as f; t=f.FakeTrading(); print(t.getPositions(), t.modifySL(1,'X',1.0), f.FakeMT5().copy_rates_from_pos('X',0,0,30).shape, f.make_mt5_position().symbol, f.make_runtime_strategy().get_exit_signal(None,None))"`
Expected: `[] True (30,) XAUUSD False` без ошибок.

Run (E1/E1b/E2 не сломаны): `python -m pytest tests/execution/test_trading_orders.py tests/execution/test_trading_margin.py tests/execution/test_execution_agent.py -q`
Expected: всё зелёное (как было).

- [ ] **Step 8: Commit**

```bash
git add tests/execution/fakes.py
git commit -m "test(position): расширить харнесс fakes для E3 (getPositions/modifySL/copy_rates/get_rates/by_magic + хелперы)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Фикстура `position_monitor_agent_factory`

**Files:** Modify `tests/execution/conftest.py`

- [ ] **Step 1: Добавить фикстуру**

В конец `tests/execution/conftest.py` добавить:
```python
@pytest.fixture
def position_monitor_agent_factory(monkeypatch):
    """Фабрика PositionMonitorAgent с подменёнными зависимостями.

    status → реальный TradingStatusRegistry(seed); streams.registry/STRATEGIES/
    get_runtime_strategy/cache/sys.modules['MetaTrader5']/talib.ATR — фейки.
    Прод не трогаем. trading не импортируется на уровне модуля.
    """
    from tests.execution.fakes import (
        FakeMT5, FakeCache, FakeTrading, FakeBus, FakeRegistry, make_runtime_strategy,
    )

    def make(*, positions=None, streams=None, strategies=None, runtime_strategy=None,
             status_seed=None, symbol="XAUUSD", rates_df=None, deals=None,
             atr=2.0, modify_result=True):
        import agents.position_monitor_agent as pm_mod
        import streams as streams_mod
        import strategies as strat_mod
        import strategies.runtime as runtime_mod
        import market_data_cache as mdc_mod
        import talib
        from trading_status import TradingStatusRegistry

        fake_mt5 = FakeMT5()
        fake_mt5.symbol_infos[symbol] = SimpleNamespace(point=0.01)
        if deals is not None:
            fake_mt5.deals = deals
        fake_cache = FakeCache()
        fake_cache.rates_df = rates_df
        fake_trading = FakeTrading()
        fake_trading.positions_list = positions or []
        fake_trading._modify_result = modify_result
        fake_registry = FakeRegistry(streams or {})
        real_status = TradingStatusRegistry(
            seed=status_seed if status_seed is not None else {symbol: 0}
        )
        strat_map = {} if strategies is None else strategies
        rstrat = runtime_strategy if runtime_strategy is not None else make_runtime_strategy()

        monkeypatch.setattr(pm_mod, "status", real_status)
        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(strat_mod, "STRATEGIES", strat_map)
        monkeypatch.setattr(runtime_mod, "get_runtime_strategy", lambda name, sym: rstrat)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)
        monkeypatch.setattr(talib, "ATR", lambda h, l, c, timeperiod=14: [atr] * len(c))

        agent = pm_mod.PositionMonitorAgent("PositionMonitor", FakeBus(), fake_trading,
                                            poll_interval=0)
        return SimpleNamespace(
            agent=agent, bus=agent.bus, trading=fake_trading, mt5=fake_mt5,
            cache=fake_cache, status=real_status, registry=fake_registry,
            runtime_strategy=rstrat,
        )

    return make
```

**Примечание:** `import sys`, `from types import SimpleNamespace`, `import pytest` уже есть в `conftest.py`. `talib` установлен (E1/E2 его используют); monkeypatch заменяет атрибут модуля.

- [ ] **Step 2: Smoke-проверка через временный тест**

Создать `tests/execution/test_smoke_pm.py`:
```python
def test_pm_factory_builds(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    assert h.agent.name == "PositionMonitor"
    assert h.agent.trading is h.trading
    assert h.status.status_of("XAUUSD") == 0
```
Run: `python -m pytest tests/execution/test_smoke_pm.py -v`
Expected: PASS.

- [ ] **Step 3: Удалить временный тест**

PowerShell: `Remove-Item tests/execution/test_smoke_pm.py`

- [ ] **Step 4: Commit**

```bash
git add tests/execution/conftest.py
git commit -m "test(position): фикстура position_monitor_agent_factory (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Зона A — `_get_positions_with_pnl` + `_on_new_bar`

**Files:** Create `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

Создать `tests/execution/test_position_monitor.py`:
```python
"""Характеризационные тесты PositionMonitorAgent (слайс E3).

Прод (agents/position_monitor_agent.py) не меняется. Тесты фиксируют текущее
поведение: снапшот позиций + P&L, жизненный цикл (исчезновение/закрытие/сброс
статуса), трейлинг/breakeven SL, exit-сигналы (стратегия/legacy-RSI, хедж).
Зависимости — фикстура position_monitor_agent_factory. trading НЕ импортируется
на уровне модуля (инвариант E1b).

Дефолты: tick bid=1900.0/ask=1900.5; symbol_info point=0.01; ATR=2.0 (замокан).
"""
import pandas as pd
import pytest

from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_deal, make_mt5_position, make_runtime_strategy, make_rsi, make_rates,
)


def _bar_event(symbol="XAUUSD"):
    return Event(type=EventType.NEW_BAR, source="test", payload={"symbol": symbol})


def test_pnl_buy_points(position_monitor_agent_factory):
    # BUY: (bid 1900.0 - open 1899.0)/point 0.01 = 100.0
    pos = make_mt5_position(type=0, price_open=1899.0, profit=12.34, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    out = h.agent._get_positions_with_pnl()
    assert len(out) == 1
    assert out[0]["type"] == "BUY"
    assert out[0]["pnl_points"] == pytest.approx(100.0)
    assert out[0]["pnl_money"] == pytest.approx(12.34)
    assert out[0]["stream_id"] == "s1"


def test_pnl_sell_points(position_monitor_agent_factory):
    # SELL: (open 1901.5 - ask 1900.5)/point 0.01 = 100.0
    pos = make_mt5_position(type=1, price_open=1901.5, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    out = h.agent._get_positions_with_pnl()
    assert out[0]["type"] == "SELL"
    assert out[0]["pnl_points"] == pytest.approx(100.0)


def test_pnl_tick_none_zero(position_monitor_agent_factory):
    pos = make_mt5_position(type=0, price_open=1899.0, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    h.mt5.tick = None
    out = h.agent._get_positions_with_pnl()
    assert out[0]["pnl_points"] == 0.0


def test_pnl_stream_none_when_magic_unknown(position_monitor_agent_factory):
    pos = make_mt5_position(magic=999)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    out = h.agent._get_positions_with_pnl()
    assert out[0]["stream_id"] is None
    assert out[0]["stream_name"] is None


async def test_on_new_bar_adds_symbol(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    await h.agent._on_new_bar(_bar_event("XAUUSD"))
    assert "XAUUSD" in h.agent._pending_exit_symbols


async def test_on_new_bar_empty_symbol_ignored(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    await h.agent._on_new_bar(Event(type=EventType.NEW_BAR, source="test", payload={}))
    assert h.agent._pending_exit_symbols == set()
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v`
Expected: 6 PASS. FAIL → находка (сообщить, не подгонять).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация _get_positions_with_pnl + _on_new_bar (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Зона A — `run()` оркестрация + детект исчезновения

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

Добавить:
```python
async def test_run_emits_position_update_and_metrics(position_monitor_agent_factory):
    pos = make_mt5_position(ticket=1001, magic=777)
    h = position_monitor_agent_factory(positions=[pos], streams={"s1": make_stream(magic=777)})
    await h.agent.run()
    updates = [e for e in h.bus.events if e.type == EventType.POSITION_UPDATE]
    assert len(updates) == 1
    assert len(updates[0].payload["positions"]) == 1
    assert h.agent.metrics["open_positions"] == 1
    assert 1001 in h.agent._prev_positions


async def test_run_detects_disappeared_position(position_monitor_agent_factory):
    # 1-й цикл: позиция есть; 2-й: пропала → ORDER_CLOSED
    pos = make_mt5_position(ticket=1001, symbol="XAUUSD", magic=777)
    h = position_monitor_agent_factory(
        positions=[pos], streams={"s1": make_stream(magic=777)},
        status_seed={"XAUUSD": 1},
    )
    await h.agent.run()                       # зафиксировали в _prev_positions
    h.trading.positions_list = []             # позиция исчезла
    await h.agent.run()
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    assert closed[0].payload["ticket"] == 1001


async def test_run_checks_exit_only_for_pending_symbols(position_monitor_agent_factory):
    # exit проверяется только для символов с новой свечой
    pos = make_mt5_position(symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        positions=[pos], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    # без pending — exit не вызывается
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []
    # с pending по символу — вызывается
    await h.agent._on_new_bar(_bar_event("XAUUSD"))
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert h.agent._pending_exit_symbols == set()   # очищено
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "run_"`
Expected: 3 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация run() оркестрации + детект исчезновения (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Зона A — `_on_position_disappeared`

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

`_on_position_disappeared` принимает prev_pos dict (как из `_prev_positions`). Добавить:
```python
def _prev(ticket=1001, symbol="XAUUSD", type="BUY", open_price=1899.0, magic=777):
    return {"ticket": ticket, "symbol": symbol, "type": type, "open_price": open_price, "magic": magic}


async def test_disappeared_emits_order_closed_and_resets_status(position_monitor_agent_factory):
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": make_stream(magic=777)},
        status_seed={"XAUUSD": 1},   # OPEN
        deals=[make_deal(comment="tp hit")],
    )
    await h.agent._on_position_disappeared(_prev())
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1
    assert closed[0].payload["reason"] == "TP"
    assert closed[0].payload["stream_id"] == "s1"
    # статус сброшен OPEN→ALLOWED + TRADING_STATUS_CHANGED
    assert h.status.status_of("XAUUSD") == 0
    changed = [e for e in h.bus.events if e.type == EventType.TRADING_STATUS_CHANGED]
    assert len(changed) == 1
    assert changed[0].payload["status"] == 0


async def test_disappeared_hedge_sibling_keeps_status(position_monitor_agent_factory):
    # есть «сосед» по той же magic+symbol → статус НЕ сбрасывается
    sibling = make_mt5_position(ticket=2002, symbol="XAUUSD", magic=777)
    h = position_monitor_agent_factory(
        positions=[sibling], streams={"s1": make_stream(magic=777)},
        status_seed={"XAUUSD": 1},
    )
    await h.agent._on_position_disappeared(_prev(ticket=1001))
    assert h.status.status_of("XAUUSD") == 1   # остался OPEN
    assert [e for e in h.bus.events if e.type == EventType.TRADING_STATUS_CHANGED] == []


async def test_disappeared_calls_on_trade_closed(position_monitor_agent_factory):
    rstrat = make_runtime_strategy()
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(comment="manual")],
    )
    await h.agent._on_position_disappeared(_prev())
    assert len(rstrat.closed_calls) == 1
    assert rstrat.closed_calls[0][1] == "MANUAL"


async def test_disappeared_on_trade_closed_exception_does_not_crash(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(raise_on_closed=True)
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        status_seed={"XAUUSD": 1}, deals=[make_deal(comment="manual")],
    )
    await h.agent._on_position_disappeared(_prev())   # не должно бросить
    closed = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSED]
    assert len(closed) == 1   # ORDER_CLOSED всё равно был эмитнут до хука
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "disappeared"`
Expected: 4 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация _on_position_disappeared (ORDER_CLOSED/статус/хедж/hook) (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Зона A — `_classify_close_reason`

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

Добавить:
```python
@pytest.mark.parametrize("comment,expected", [
    ("sl 1897.0", "SL"),
    ("stop loss", "SL"),
    ("tp reached", "TP"),
    ("take profit", "TP"),
    ("strategy:ema", "SIGNAL"),
    ("manual close", "MANUAL"),
])
def test_classify_close_reason_from_comment(position_monitor_agent_factory, comment, expected):
    h = position_monitor_agent_factory(deals=[make_deal(comment=comment)])
    assert h.agent._classify_close_reason(1001) == expected


def test_classify_close_reason_no_deals(position_monitor_agent_factory):
    h = position_monitor_agent_factory(deals=[])
    assert h.agent._classify_close_reason(1001) == "MANUAL"


def test_classify_close_reason_exception(position_monitor_agent_factory, monkeypatch):
    h = position_monitor_agent_factory()
    def boom(*a, **k):
        raise RuntimeError("hist boom")
    monkeypatch.setattr(h.mt5, "history_deals_get", boom)
    assert h.agent._classify_close_reason(1001) == "MANUAL"
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "classify"`
Expected: 8 PASS (6 параметров + no_deals + exception). FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация _classify_close_reason (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Зона B — `_apply_trailing_sl`

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

`_apply_trailing_sl` принимает pos dict (как из `_get_positions_with_pnl`). ATR=2.0 (замокан),
tick bid=1900.0/ask=1900.5. Добавить хелпер и тесты:
```python
def _posd(ticket=1001, symbol="XAUUSD", type="BUY", open_price=1899.0, sl=0.0, magic=777):
    return {"ticket": ticket, "symbol": symbol, "type": type, "open_price": open_price,
            "sl": sl, "magic": magic}


def test_trail_no_stream_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={})   # by_magic → None
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_no_be_no_trail_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_rates_none_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.mt5.rates = []                # len 0 < 15
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_atr_zero_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)}, atr=0.0)
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_tick_none_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.mt5.tick = None
    h.agent._apply_trailing_sl(_posd())
    assert h.trading.modify_calls == []


def test_trail_buy_breakeven_sets_entry(position_monitor_agent_factory):
    # bid 1900 - entry 1897 = 3.0 >= be(1.0)*atr(2.0)=2.0 → candidate=entry=1897.0
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=1.0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd(open_price=1897.0, sl=0.0))
    assert len(h.trading.modify_calls) == 1
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1897.0)
    assert 1001 in h.agent._be_done


def test_trail_buy_breakeven_idempotent(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=1.0, trail_atr=0)})
    h.agent._apply_trailing_sl(_posd(open_price=1897.0))   # 1-й раз — двигает
    h.agent._apply_trailing_sl(_posd(open_price=1897.0))   # 2-й — _be_done, trail off → нечего двигать
    assert len(h.trading.modify_calls) == 1


def test_trail_buy_trailing_sets_below_price(position_monitor_agent_factory):
    # cand = bid 1900 - trail(1.0)*atr(2.0) = 1898.0
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, breakeven_atr=0, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=0.0))
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1898.0)


def test_trail_buy_does_not_move_sl_down(position_monitor_agent_factory):
    # cur_sl=1899.0; cand=1898.0 < cur → не двигаем (и порог)
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=1899.0))
    assert h.trading.modify_calls == []


def test_trail_sell_trailing_sets_above_price(position_monitor_agent_factory):
    # SELL: cand = ask 1900.5 + trail(1.0)*atr(2.0) = 1902.5
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(type="SELL", open_price=1902.0, sl=0.0))
    assert h.trading.modify_calls[0]["new_sl"] == pytest.approx(1902.5)


def test_trail_threshold_skips_small_move(position_monitor_agent_factory):
    # cur_sl=1897.9; cand=1898.0; |Δ|=0.1 < 0.1*atr(2.0)=0.2 → не двигаем
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=1897.9))
    assert h.trading.modify_calls == []


def test_trail_modifysl_exception_does_not_crash(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777, trail_atr=1.0)})
    def boom(*a, **k):
        raise RuntimeError("modify boom")
    h.trading.modifySL = boom
    h.agent._apply_trailing_sl(_posd(open_price=1899.0, sl=0.0))   # не должно бросить
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "trail"`
Expected: 12 PASS. FAIL → находка (особенно сверить пороги/breakeven-арифметику; не подгонять).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация _apply_trailing_sl (breakeven/trailing/порог) (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Зона C — хедж-хелперы + `_check_rsi_exit` gating/dispatch

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

Добавить:
```python
def test_is_hedge_position(position_monitor_agent_factory):
    h = position_monitor_agent_factory()
    assert h.agent._is_hedge_position({"comment": "s1:strat:H"}) is True
    assert h.agent._is_hedge_position({"comment": "s1:strat"}) is False
    assert h.agent._is_hedge_position({"comment": ""}) is False


def test_find_paired_hedge_ticket(position_monitor_agent_factory):
    main = make_mt5_position(ticket=1001, symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    hedge = make_mt5_position(ticket=2002, symbol="XAUUSD", type=1, magic=777, comment="s1:strat:H")
    h = position_monitor_agent_factory(positions=[main, hedge], streams={"s1": make_stream(magic=777)})
    main_dict = {"ticket": 1001, "symbol": "XAUUSD", "type": "BUY", "magic": 777}
    assert h.agent._find_paired_hedge_ticket(main_dict) == 2002


def test_find_paired_hedge_none_when_absent(position_monitor_agent_factory):
    main = make_mt5_position(ticket=1001, symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    h = position_monitor_agent_factory(positions=[main], streams={"s1": make_stream(magic=777)})
    main_dict = {"ticket": 1001, "symbol": "XAUUSD", "type": "BUY", "magic": 777}
    assert h.agent._find_paired_hedge_ticket(main_dict) is None


async def test_check_rsi_exit_disabled_status_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={"s1": make_stream(magic=777)},
                                       status_seed={"XAUUSD": 3})   # DISABLED
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 777, "ticket": 1001, "type": "BUY"})
    assert h.bus.events == []


async def test_check_rsi_exit_no_stream_skips(position_monitor_agent_factory):
    h = position_monitor_agent_factory(streams={}, status_seed={"XAUUSD": 0})
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 999, "ticket": 1001, "type": "BUY"})
    assert h.bus.events == []


async def test_check_rsi_exit_dispatches_to_strategy(position_monitor_agent_factory):
    # стратегия в STRATEGIES → идёт в _check_strategy_exit (get_exit_signal True → CLOSE)
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}), status_seed={"XAUUSD": 0},
    )
    await h.agent._check_rsi_exit({"symbol": "XAUUSD", "magic": 777, "ticket": 1001,
                                   "type": "BUY", "open_price": 1899.0, "volume": 0.1,
                                   "sl": 0.0, "comment": "s1:strat"})
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "is_hedge or find_paired or check_rsi_exit"`
Expected: 6 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация хедж-хелперов + _check_rsi_exit gating (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Зона C — `_check_strategy_exit`

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

Добавить:
```python
def _main_pos(ticket=1001, comment="s1:strat"):
    return {"ticket": ticket, "symbol": "XAUUSD", "type": "BUY", "open_price": 1899.0,
            "volume": 0.1, "sl": 0.0, "magic": 777, "comment": comment}


async def test_strategy_exit_no_rates_skips(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat, rates_df=None,
    )
    await h.agent._check_strategy_exit(_main_pos(), make_stream(magic=777, strategy="strat"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


async def test_strategy_exit_short_df_skips(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 10}),   # < 50
    )
    await h.agent._check_strategy_exit(_main_pos(), make_stream(magic=777, strategy="strat"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


async def test_strategy_exit_signal_false_no_close(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=False)
    h = position_monitor_agent_factory(
        streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), make_stream(magic=777, strategy="strat"))
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []


async def test_strategy_exit_main_emits_close(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(exit_signal=True, wants_hedge=False)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        positions=[], streams={"s1": stream}, strategies={"strat": object()},
        runtime_strategy=rstrat, rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), stream)
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 1
    assert reqs[0].payload["reason"] == "strategy:strat"


async def test_strategy_exit_main_with_hedge_closes_pair(position_monitor_agent_factory):
    # wants_hedge + парный хедж в позициях → 2 CLOSE (основная + pair_close)
    hedge = make_mt5_position(ticket=2002, symbol="XAUUSD", type=1, magic=777, comment="s1:strat:H")
    rstrat = make_runtime_strategy(exit_signal=True, wants_hedge=True)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        positions=[hedge], streams={"s1": stream}, strategies={"strat": object()},
        runtime_strategy=rstrat, rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), stream)
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 2
    reasons = {r.payload["reason"] for r in reqs}
    assert "strategy:strat" in reasons
    assert "strategy:strat:pair_close" in reasons


async def test_strategy_exit_hedge_leg_closes_only_itself(position_monitor_agent_factory):
    # хедж-нога (:H) + wants_hedge → get_hedge_exit_signal True → закрытие только ноги
    rstrat = make_runtime_strategy(hedge_exit_signal=True, wants_hedge=True)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        streams={"s1": stream}, strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(ticket=2002, comment="s1:strat:H"), stream)
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 1
    assert reqs[0].payload["reason"] == "strategy:strat:hedge"


async def test_strategy_exit_exception_does_not_crash(position_monitor_agent_factory):
    rstrat = make_runtime_strategy(raise_on_exit=True)
    stream = make_stream(magic=777, strategy="strat")
    h = position_monitor_agent_factory(
        streams={"s1": stream}, strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._check_strategy_exit(_main_pos(), stream)   # не должно бросить
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST] == []
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "strategy_exit"`
Expected: 7 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация _check_strategy_exit (вкл. хедж-pair) (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Зона C — `_check_legacy_rsi_exit`

**Files:** Modify `tests/execution/test_position_monitor.py`

- [ ] **Step 1: Написать тесты**

`_check_legacy_rsi_exit` делает `from indicators import RSI`; подменяем `indicators.RSI`. Добавить:
```python
async def test_legacy_rsi_buy_exit(position_monitor_agent_factory, monkeypatch):
    # BUY + RSI < 45 → RSI_EXIT_TRIGGERED + ORDER_CLOSE_REQUEST
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(40.0))
    stream = make_stream(magic=777, strategy="nonstrat")   # НЕ в STRATEGIES → legacy
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={},
                                       status_seed={"XAUUSD": 0})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "BUY"}, stream)
    assert [e for e in h.bus.events if e.type == EventType.RSI_EXIT_TRIGGERED]
    reqs = [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
    assert len(reqs) == 1
    assert reqs[0].payload["reason"].startswith("RSI=")


async def test_legacy_rsi_sell_exit(position_monitor_agent_factory, monkeypatch):
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(60.0))   # SELL + >55
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "SELL"}, stream)
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]


async def test_legacy_rsi_no_exit_when_neutral(position_monitor_agent_factory, monkeypatch):
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(50.0))   # BUY: 50 не <45
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "BUY"}, stream)
    assert h.bus.events == []


async def test_legacy_rsi_no_data_skips(position_monitor_agent_factory, monkeypatch):
    import indicators
    monkeypatch.setattr(indicators, "RSI", make_rsi(None))   # get_rsi_talib → None
    stream = make_stream(magic=777, strategy="nonstrat")
    h = position_monitor_agent_factory(streams={"s1": stream}, strategies={})
    await h.agent._check_legacy_rsi_exit({"symbol": "XAUUSD", "ticket": 1001, "type": "BUY"}, stream)
    assert h.bus.events == []
```

- [ ] **Step 2: Запустить**

Run: `python -m pytest tests/execution/test_position_monitor.py -v -k "legacy_rsi"`
Expected: 4 PASS. FAIL → находка.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_position_monitor.py
git commit -m "test(position): характеризация _check_legacy_rsi_exit (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Dispatch + known-issues #7 + полный прогон

**Files:** Modify `tests/execution/test_position_monitor.py`, `docs/known-issues.md`

- [ ] **Step 1: Написать dispatch-тест**

Добавить в `test_position_monitor.py`:
```python
async def test_dispatch_new_bar_then_run_triggers_exit(position_monitor_agent_factory):
    pos = make_mt5_position(symbol="XAUUSD", type=0, magic=777, comment="s1:strat")
    rstrat = make_runtime_strategy(exit_signal=True)
    h = position_monitor_agent_factory(
        positions=[pos], streams={"s1": make_stream(magic=777, strategy="strat")},
        strategies={"strat": object()}, runtime_strategy=rstrat,
        rates_df=pd.DataFrame({"close": [1.0] * 60}),
    )
    await h.agent._on_new_bar(_bar_event("XAUUSD"))
    await h.agent.run()
    assert [e for e in h.bus.events if e.type == EventType.ORDER_CLOSE_REQUEST]
```

- [ ] **Step 2: Запустить новый тест + полный файл**

Run: `python -m pytest tests/execution/test_position_monitor.py -q`
Expected: все зелёные; зафиксировать число (ожидаемо ~50 passed).

- [ ] **Step 3: Добавить #7 в `docs/known-issues.md`**

Перед `---\n## Связанные документы` добавить:
```markdown
## 7. trading.Trading: мёртвые методы calculateStopLoss/calculateMaxMinValue

- **Где:** [trading.py:159](../trading.py#L159) (`calculateStopLoss`) и [trading.py:468](../trading.py#L468) (`calculateMaxMinValue`).
- **Что:** оба объявлены корректно (с `self`), но НИГДЕ не вызываются (проверено grep по проекту). `calculateStopLoss` мутирует `dict.symbolStopLossValue` (legacy-трейлинг по деньгам), `calculateMaxMinValue` считает экскурсию через `copy_rates_from_pos`. Актуальный трейлинг делает `PositionMonitorAgent._apply_trailing_sl` (ATR-based, через `modifySL`), эти методы — рудимент старой схемы.
- **Желаемое:** удалить мёртвый код (либо подключить, если задумывался).
- **Статус:** ⚠️ ОТКРЫТА (2026-06-04, слайс E3). Без тестов (мёртвый код, решение пользователя — не раздувать E3). Зафиксировано наблюдением при характеризации position_monitor.
```
Также в «Связанные документы» добавить строку:
```markdown
- `docs/superpowers/specs/2026-06-04-position-monitor-characterization-design.md` — слайс E3 (наблюдение #7)
```

- [ ] **Step 4: Commit тестов + known-issues**

```bash
git add tests/execution/test_position_monitor.py docs/known-issues.md
git commit -m "test(position): dispatch run() + known-issues #7 dead-code (E3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: Верификация — полный прогон + прод не тронут**

Run: `python -m pytest -q`
Expected: всё зелёное, ожидаемо `~418 passed, 3 xfailed` (было 368+3; +~50 passed).
Run: `git diff --stat agents/position_monitor_agent.py`
Expected: пусто (боевой агент не изменён).

---

## Self-Review (выполнено при написании плана)

- **Spec coverage:** Зона A — pnl/маппинг/on_new_bar (Task 3), run/детект (Task 4), disappeared/статус/хедж-sibling/hook (Task 5), classify (Task 6) ✓; Зона B — _apply_trailing_sl все ветки (Task 7) ✓; Зона C — хедж-хелперы+gating (Task 8), strategy_exit+pair (Task 9), legacy_rsi (Task 10) ✓; dispatch (Task 11) ✓; харнесс (Task 1) ✓; фикстура (Task 2) ✓; dead-code #7 (Task 11) ✓.
- **Placeholder scan:** код приведён полностью; в Task 6 явно указано убрать walrus-строку (оставлен финальный корректный вариант).
- **Type consistency:** фейк-поля единообразны — FakeTrading.positions_list/modify_calls/modifySL/getPositions; FakeMT5.rates/copy_rates_from_pos/symbol_infos/ticks/tick; FakeCache.rates_df/get_rates; FakeRegistry.by_magic; make_stream(+breakeven_atr/trail_atr/timeframe); make_mt5_position(type int 0/1)/make_runtime_strategy/make_rsi. Фикстура `position_monitor_agent_factory` отдаёт namespace agent/bus/trading/mt5/cache/status/registry/runtime_strategy — используется единообразно.
- **Замечание исполнителю:** числовые ожидания (pnl 100.0; breakeven 1897.0; trailing BUY 1898.0/SELL 1902.5; пороги) выведены из дефолтов фейков (tick 1900.0/1900.5, point 0.01, ATR 2.0). Если фактический прогон даёт иное — находка (сообщить) либо рассинхрон дефолтов (сверить Task 1/2), НЕ подгонять прод/значение.
```
