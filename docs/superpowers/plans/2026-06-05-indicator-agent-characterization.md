# E5 — Характеризация indicator_agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запереть текущее поведение всех трёх частей `agents/indicator_agent.py` (run()-dispatch, `_calc_strategy`, `_calc_indicators`) характеризационной сеткой, прод не трогая.

**Architecture:** Переиспользуем харнесс `tests/execution/`. Аддитивно дополняем `fakes.py` (fake рантайм-стратегии + фейк-классы `indicators.py`), добавляем фабрику `indicator_agent_factory` в `conftest.py`, пишем один файл `tests/execution/test_indicator_agent.py`. Монкипатч модульных глобалов — боевой код не меняется.

**Tech Stack:** Python 3.11, pytest, pytest-asyncio (asyncio_mode=auto), pandas.

**⚠️ Характеризация, не TDD:** тесты пишутся под УЖЕ СУЩЕСТВУЮЩЕЕ поведение и должны проходить сразу против прод-кода. Если тест падает — это НАХОДКА: разобраться, привести ассерт к фактическому поведению ИЛИ зафиксировать `xfail` + запись в `docs/known-issues.md`. **Боевой код не правим.**

**⚠️ Инвариант трека:** в `tests/execution/` НЕ импортировать `trading` на уровне модуля. В E5 `trading` не нужен.

---

## File Structure

- **Modify:** `tests/execution/fakes.py` — аддитивные фейки (Task 1).
- **Modify:** `tests/execution/conftest.py` — фабрика `indicator_agent_factory` (Task 2).
- **Create:** `tests/execution/test_indicator_agent.py` — тесты (Tasks 3–6).

---

## Task 1: Аддитивные дополнения харнесса (`fakes.py`)

**Files:**
- Modify: `tests/execution/fakes.py`

- [ ] **Step 1: Расширить `make_bars_df` опциональными колонками**

Найти существующую функцию `make_bars_df` и заменить её целиком на:

```python
def make_bars_df(*, time, n=2, close=1.0, extra_cols=None):
    """pandas DataFrame баров для cache.get_rates (market_data берёт .iloc[-1]['time']).

    time: int (epoch) или pd.Timestamp — обе ветки нормализации в агенте.
    extra_cols: dict[str, value] — доп. колонки (значение тиражируется по n строкам);
                нужно для проверки сбора indicators_raw в IndicatorAgent._calc_strategy.
    """
    import pandas as pd
    data = {"time": [time] * n, "close": [close] * n}
    if extra_cols:
        for col, val in extra_cols.items():
            data[col] = [val] * n
    return pd.DataFrame(data)
```

- [ ] **Step 2: Добавить `make_indicator_strategy` в конец `fakes.py`**

```python
def make_indicator_strategy(*, flat=False, entry_signal=None,
                            indicator_cols=(), flat_cols=()):
    """Фейк рантайм-стратегии под IndicatorAgent._calc_strategy (get_runtime_strategy).

    compute_indicators/compute_flat_indicators возвращают df как есть;
    is_flat/get_entry_signal/indicator_columns/flat_indicator_columns конфигурируемы.
    """
    class _S:
        def compute_indicators(self, df):
            return df
        def compute_flat_indicators(self, df):
            return df
        def is_flat(self, row):
            return flat
        def get_entry_signal(self, row):
            return entry_signal
        def indicator_columns(self):
            return list(indicator_cols)
        def flat_indicator_columns(self):
            return list(flat_cols)
    return _S()
```

- [ ] **Step 3: Добавить фабрики фейк-классов `indicators.py` в конец `fakes.py`**

```python
def fake_moving_average(*, cross=None, critical=None, ma_value=1900.0):
    """Фабрика фейк-класса indicators.MovingAverage (инстанцируется без аргументов)."""
    _cross = cross if cross is not None else {"signal": "NO_SIGNAL"}
    _critical = critical if critical is not None else {"signal": "NO_SIGNAL"}
    class _MA:
        def get_ma_for_symbol(self, symbol, timeframe, period,
                              ma_type='EMA', price_type='close', bars=100):
            import pandas as pd
            return pd.Series([ma_value])
        def ma_cross_signal(self, fast_ma, slow_ma, symbol, atr_value=None):
            return _cross
        def ma_critical_angle(self, fast_ma, slow_ma, symbol, atr_value=None):
            return _critical
    return _MA


def fake_macd(*, calc=(1.0, 2.0, 3.0), signal=None):
    """Фабрика фейк-класса indicators.MACD. calc → (hist, prev_hist, signal_line)."""
    _signal = signal if signal is not None else {"signal": "NO_SIGNAL"}
    class _M:
        def calculate_macd_manual(self, symbol, timeframe,
                                  fast_ema=12, slow_ema=26, signal_period=9):
            return calc
        def MACD_signal(self, hist_line, prev_hist_line, signal_line):
            return _signal
    return _M


def fake_rsi_ind(*, rsi_series=None, signal=None):
    """Фабрика фейк-класса indicators.RSI. rsi_series → list|None; None → нет данных."""
    _signal = signal if signal is not None else {"signal": "NO_SIGNAL"}
    class _R:
        def get_rsi_talib(self, symbol, timeframe, period=14, bars=100):
            import pandas as pd
            if rsi_series is None:
                return None
            return {"RSI": pd.Series(rsi_series)}
        def RSI_signal(self, rsi, prev_rsi, prev2_rsi):
            return _signal
    return _R


def fake_atr_ind(*, series=None, scalar=None):
    """Фабрика фейк-класса indicators.ATR. series → list (вернёт Series); иначе scalar."""
    class _A:
        def calculate_atr(self, symbol, timeframe, bars=50):
            import pandas as pd
            if series is not None:
                return pd.Series(series)
            return scalar
    return _A


def fake_adx_ind(*, values=None):
    """Фабрика фейк-класса indicators.ADX. ADX() → (values, None, None)."""
    class _A:
        def ADX(self, high, low, close, adx_period):
            return (values, None, None)
    return _A


def fake_alligator(*, df=None):
    """Фабрика фейк-класса indicators.Alligator. Df() → DataFrame с high/low/close."""
    class _A:
        def Df(self, symbol, timeframe):
            import pandas as pd
            if df is not None:
                return df
            return pd.DataFrame({"high": [1.0], "low": [1.0], "close": [1.0]})
    return _A
```

- [ ] **Step 4: Проверить импортируемость**

Run: `python -c "from tests.execution.fakes import make_indicator_strategy, fake_moving_average, fake_macd, fake_rsi_ind, fake_atr_ind, fake_adx_ind, fake_alligator, make_bars_df; s=make_indicator_strategy(flat=True); assert s.is_flat(None) is True; MA=fake_moving_average(); assert MA().ma_cross_signal(None, None, 'X') == {'signal': 'NO_SIGNAL'}; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Регрессия харнесса**

Run: `python -m pytest tests/execution/ -q`
Expected: все прежние тесты зелёные (дополнения аддитивны). Записать pass-count.

- [ ] **Step 6: Commit**

```bash
git add tests/execution/fakes.py
git commit -m "test(E5): фейки харнесса под indicator_agent (рантайм-стратегия + классы indicators)"
```
Завершить сообщение трейлером (пустая строка, затем): `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Фикстура `indicator_agent_factory`

**Files:**
- Modify: `tests/execution/conftest.py`

- [ ] **Step 1: Добавить фабрику в конец `conftest.py`**

```python
@pytest.fixture
def indicator_agent_factory(monkeypatch):
    """Фабрика IndicatorAgent с подменёнными зависимостями. Прод не трогаем.

    Патчит streams.registry, strategies.STRATEGIES, market_data_cache.cache,
    и (опц.) strategies.runtime.get_runtime_strategy. `trading` не импортируется.

    Драйв run(): положить NEW_BAR-event в agent._queue, затем `await agent.run()`.
    _calc_strategy/_calc_indicators можно подменить на инстансе прямо в тесте
    (для изоляции dispatch). _calc_indicators-тесты сами патчат indicators.* через
    отдельный аргумент monkeypatch.
    """
    from tests.execution.fakes import FakeCache, FakeBus, FakeRegistry

    def make(*, streams=None, strategies=None, rates_df=None, runtime_strategy=None):
        import agents.indicator_agent as ia_mod
        import streams as streams_mod
        import strategies as strat_mod
        import strategies.runtime as runtime_mod
        import market_data_cache as mdc_mod

        fake_cache = FakeCache()
        fake_cache.rates_df = rates_df
        fake_registry = FakeRegistry(streams or {})
        strat_map = {} if strategies is None else strategies

        monkeypatch.setattr(streams_mod, "registry", fake_registry)
        monkeypatch.setattr(strat_mod, "STRATEGIES", strat_map)
        monkeypatch.setattr(mdc_mod, "cache", fake_cache)
        if runtime_strategy is not None:
            monkeypatch.setattr(runtime_mod, "get_runtime_strategy",
                                lambda name, sym: runtime_strategy)

        agent = ia_mod.IndicatorAgent("Indicator", FakeBus())
        return SimpleNamespace(
            agent=agent, bus=agent.bus, registry=fake_registry, cache=fake_cache,
        )

    return make
```

- [ ] **Step 2: Smoke-проверка.** Создать `tests/execution/test_smoke_ind.py`:

```python
from tests.execution.fakes import make_stream
from core.events import Event, EventType


async def test_smoke_indicator_factory(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    h.agent._calc_indicators = lambda symbol, tf: {"symbol": symbol, "via": "default"}
    ev = Event(type=EventType.NEW_BAR, source="t",
               payload={"symbol": "XAUUSD", "timeframe": 16385})
    h.agent._queue.put_nowait(ev)
    await h.agent.run()
    ready = [e for e in h.bus.events if e.type == EventType.INDICATORS_READY]
    assert len(ready) == 1
    assert ready[0].payload["via"] == "default"
    assert ready[0].payload["stream_id"] == "s1"
```

Run: `python -m pytest tests/execution/test_smoke_ind.py -q`
Expected: PASS (1 passed). Если падает — STOP, report (находка).

- [ ] **Step 3: Удалить smoke-файл:** `rm -f tests/execution/test_smoke_ind.py` (не коммитить).

- [ ] **Step 4: Commit (только conftest.py)**

```bash
git add tests/execution/conftest.py
git commit -m "test(E5): фикстура indicator_agent_factory"
```
Трейлер как в Task 1. Подтвердить `git status` чистый (нет smoke-файла).

---

## Task 3: run() dispatch — gating

**Files:**
- Create: `tests/execution/test_indicator_agent.py`

- [ ] **Step 1: Создать `tests/execution/test_indicator_agent.py`**

```python
"""Характеризация IndicatorAgent (E5). Прод не трогаем."""
import pytest
from core.events import Event, EventType
from tests.execution.fakes import (
    make_stream, make_bars_df, make_indicator_strategy,
    fake_moving_average, fake_macd, fake_rsi_ind, fake_atr_ind,
    fake_adx_ind, fake_alligator,
)


async def _feed(h, payload, correlation_id=None):
    ev = Event(type=EventType.NEW_BAR, source="t",
               payload=payload, correlation_id=correlation_id)
    h.agent._queue.put_nowait(ev)
    await h.agent.run()


def _ready(h):
    for e in h.bus.events:
        if e.type == EventType.INDICATORS_READY:
            return e
    return None


def _statuses(h):
    return [e.payload["status"] for e in h.bus.events
            if e.type == EventType.AGENT_STATUS]


def _stub_calcs(h, recorder):
    """Подменяет оба calc-метода; пишет, какой позван, и возвращает маркер-dict."""
    def strat(symbol, name, tf):
        recorder.append(("strategy", symbol, name, tf))
        return {"symbol": symbol, "via": "strategy"}
    def default(symbol, tf):
        recorder.append(("default", symbol, tf))
        return {"symbol": symbol, "via": "default"}
    h.agent._calc_strategy = strat
    h.agent._calc_indicators = default


async def test_no_stream_early_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={})  # by_symbol → None
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert rec == []  # ни один calc не позван


async def test_disabled_stream_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", enabled=False, timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert rec == []


async def test_timeframe_mismatch_return(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16408})  # ≠ 16385
    assert _ready(h) is None
    assert rec == []


async def test_bar_tf_zero_skips_tf_check(indicator_agent_factory):
    h = indicator_agent_factory(streams={
        "s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385),
    })
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 0})  # falsy → tf-проверка пропущена
    assert _ready(h) is not None
    assert rec and rec[0][0] == "default"
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_indicator_agent.py -q`
Expected: 4 passed. Падение → STOP, report (находка).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_indicator_agent.py
git commit -m "test(E5): характеризация IndicatorAgent — run() gating"
```
Трейлер как в Task 1.

---

## Task 4: run() dispatch — выбор пути, эмит, метрики, ошибки

**Files:**
- Modify: `tests/execution/test_indicator_agent.py`

- [ ] **Step 1: APPEND тесты**

Хелперы `_feed/_ready/_statuses/_stub_calcs` уже определены (Task 3) — не дублировать. Добавить в конец файла:

```python
async def test_strategy_path_when_in_STRATEGIES(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="mystrat", timeframe=16385)},
        strategies={"mystrat": object()},
    )
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h).payload["via"] == "strategy"
    assert rec[0][0] == "strategy"


async def test_default_path_when_not_in_STRATEGIES(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
        strategies={"mystrat": object()},  # "default" ∉ STRATEGIES
    )
    rec = []
    _stub_calcs(h, rec)
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h).payload["via"] == "default"
    assert rec[0][0] == "default"


async def test_stream_id_injected(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"sX": make_stream(id="sX", symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h).payload["stream_id"] == "sX"


async def test_correlation_id_passthrough(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385}, correlation_id="cid-9")
    assert _ready(h).correlation_id == "cid-9"


async def test_calculated_metric_increments(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert h.agent.metrics["calculated"] == 1


async def test_status_sequence_on_success(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    _stub_calcs(h, [])
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    # IDLE(старт) → RUNNING → IDLE(готово)
    assert _statuses(h) == ["idle", "running", "idle"]


async def test_calc_exception_sets_error_no_ready(indicator_agent_factory):
    h = indicator_agent_factory(
        streams={"s1": make_stream(symbol="XAUUSD", strategy="default", timeframe=16385)},
    )
    def boom(symbol, tf):
        raise RuntimeError("calc boom")
    h.agent._calc_indicators = boom
    await _feed(h, {"symbol": "XAUUSD", "timeframe": 16385})
    assert _ready(h) is None
    assert _statuses(h)[-1] == "error"
    assert h.agent.metrics["calculated"] == 0
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_indicator_agent.py -q`
Expected: 11 passed (4 + 7). Падение → STOP, report.

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_indicator_agent.py
git commit -m "test(E5): характеризация IndicatorAgent — dispatch/эмит/метрики/ошибки"
```
Трейлер как в Task 1.

---

## Task 5: `_calc_strategy` (путь рантайм-стратегии)

**Files:**
- Modify: `tests/execution/test_indicator_agent.py`

- [ ] **Step 1: APPEND тесты** (вызываем метод напрямую)

```python
async def test_calc_strategy_df_none_minimal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=None,
        runtime_strategy=make_indicator_strategy(),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res == {"symbol": "XAUUSD", "strategy": "mystrat",
                   "entry_signal": "NO_SIGNAL", "is_flat": True}


async def test_calc_strategy_df_too_short_minimal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=10),  # < 50
        runtime_strategy=make_indicator_strategy(),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["entry_signal"] == "NO_SIGNAL"
    assert res["is_flat"] is True
    assert "indicators_raw" not in res


async def test_calc_strategy_flat_no_signal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60),
        runtime_strategy=make_indicator_strategy(flat=True, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    # flat=True → signal не запрашивается → NO_SIGNAL
    assert res["entry_signal"] == "NO_SIGNAL"
    assert res["is_flat"] is True


async def test_calc_strategy_not_flat_buy(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["entry_signal"] == "BUY"
    assert res["is_flat"] is False


async def test_calc_strategy_not_flat_none_signal(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal=None),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["entry_signal"] == "NO_SIGNAL"  # signal or "NO_SIGNAL"


async def test_calc_strategy_indicators_raw_collected(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60,
                              extra_cols={"rsi": 55.0, "ema8": 1900.0}),
        runtime_strategy=make_indicator_strategy(
            flat=False, entry_signal="BUY",
            indicator_cols=("rsi", "ema8", "missing_col")),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["indicators_raw"] == {"rsi": 55.0, "ema8": 1900.0}  # missing_col пропущен


async def test_calc_strategy_indicators_raw_skips_nan(indicator_agent_factory):
    import math
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60, extra_cols={"rsi": math.nan}),
        runtime_strategy=make_indicator_strategy(
            flat=False, entry_signal="BUY", indicator_cols=("rsi",)),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["indicators_raw"] == {}  # NaN пропущен
    assert res["rsi_value"] is None     # _get_float тоже None


async def test_calc_strategy_legacy_fields_and_getfloat(indicator_agent_factory):
    h = indicator_agent_factory(
        rates_df=make_bars_df(time=1000, n=60,
                              extra_cols={"rsi": 60.0, "ema8": 1900.0, "ema21": 1899.0}),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["signal_ma"] == "NO_SIGNAL"
    assert res["signal_critical_angle"] == "NO_SIGNAL"
    assert res["macd_signal"] == "NO_SIGNAL"
    assert res["rsi_signal"] == "NO_SIGNAL"
    assert res["rsi_value"] == 60.0
    assert res["ema8"] == 1900.0
    assert res["ema21"] == 1899.0


async def test_calc_strategy_atr_and_adx_fallbacks(indicator_agent_factory):
    h = indicator_agent_factory(
        # нет 'atr' и нет 'flat_adx'; есть 'flat_atr'
        rates_df=make_bars_df(time=1000, n=60, extra_cols={"flat_atr": 3.0}),
        runtime_strategy=make_indicator_strategy(flat=False, entry_signal="BUY"),
    )
    res = h.agent._calc_strategy("XAUUSD", "mystrat", 16385)
    assert res["atr_value"] == 3.0   # _get_float('atr') None → flat_atr
    assert res["adx_value"] == 0.0   # _get_float('flat_adx') None → 0.0
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_indicator_agent.py -q`
Expected: 20 passed (11 + 9). Падение → STOP, report (особенно indicators_raw/NaN/fallback — привести к факту, не ослаблять вслепую).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_indicator_agent.py
git commit -m "test(E5): характеризация IndicatorAgent._calc_strategy"
```
Трейлер как в Task 1.

---

## Task 6: `_calc_indicators` (legacy default-путь)

**Files:**
- Modify: `tests/execution/test_indicator_agent.py`

- [ ] **Step 1: APPEND тесты** (метод напрямую; патчим `indicators.*` через `monkeypatch`)

```python
def _patch_indicators(monkeypatch, *, ma=None, macd=None, rsi=None,
                      atr=None, adx=None, alligator=None):
    """Подменяет классы indicators.* фейками (дефолты — нейтральные)."""
    import indicators
    monkeypatch.setattr(indicators, "MovingAverage", ma or fake_moving_average())
    monkeypatch.setattr(indicators, "MACD", macd or fake_macd())
    monkeypatch.setattr(indicators, "RSI", rsi or fake_rsi_ind())
    monkeypatch.setattr(indicators, "ATR", atr or fake_atr_ind(scalar=None))
    monkeypatch.setattr(indicators, "ADX", adx or fake_adx_ind(values=[20.0]))
    monkeypatch.setattr(indicators, "Alligator", alligator or fake_alligator())


async def test_calc_indicators_dict_signals_extracted(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(
        monkeypatch,
        ma=fake_moving_average(cross={"signal": "BUY"}, critical={"signal": "BUY"}),
        macd=fake_macd(signal={"signal": "SELL"}),
    )
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["signal_ma"] == "BUY"
    assert res["signal_critical_angle"] == "BUY"
    assert res["macd_signal"] == "SELL"


async def test_calc_indicators_non_dict_signal_is_no_signal(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    # cross возвращает не-dict → isinstance-guard → "NO_SIGNAL"
    _patch_indicators(monkeypatch, ma=fake_moving_average(cross="BUY", critical=None))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["signal_ma"] == "NO_SIGNAL"


async def test_calc_indicators_rsi_none(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, rsi=fake_rsi_ind(rsi_series=None))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["rsi_signal"] == "NO_SIGNAL"
    assert res["rsi_value"] is None


async def test_calc_indicators_rsi_too_short(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, rsi=fake_rsi_ind(rsi_series=[50.0, 51.0]))  # len 2 < 3
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["rsi_signal"] == "NO_SIGNAL"
    assert res["rsi_value"] is None


async def test_calc_indicators_rsi_full(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(
        monkeypatch,
        rsi=fake_rsi_ind(rsi_series=[40.0, 45.0, 60.0], signal={"signal": "BUY"}),
    )
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["rsi_value"] == 60.0
    assert res["rsi_signal"] == "BUY"


async def test_calc_indicators_atr_series_vs_scalar(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, atr=fake_atr_ind(series=[1.0, 2.5]))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["atr_value"] == 2.5  # float(.iloc[-1])

    h2 = indicator_agent_factory()
    _patch_indicators(monkeypatch, atr=fake_atr_ind(scalar=7.0))  # без .iloc
    res2 = h2.agent._calc_indicators("XAUUSD", 16385)
    assert res2["atr_value"] == 7.0  # как есть


async def test_calc_indicators_ema_from_ma(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, ma=fake_moving_average(ma_value=1234.0))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["ema8"] == 1234.0
    assert res["ema21"] == 1234.0


async def test_calc_indicators_adx_value_and_empty(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch, adx=fake_adx_ind(values=[33.0]))
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["adx_value"] == 33.0

    h2 = indicator_agent_factory()
    _patch_indicators(monkeypatch, adx=fake_adx_ind(values=[]))  # пусто → 0.0
    res2 = h2.agent._calc_indicators("XAUUSD", 16385)
    assert res2["adx_value"] == 0.0


async def test_calc_indicators_result_has_symbol_and_keys(indicator_agent_factory, monkeypatch):
    h = indicator_agent_factory()
    _patch_indicators(monkeypatch)
    res = h.agent._calc_indicators("XAUUSD", 16385)
    assert res["symbol"] == "XAUUSD"
    for k in ("signal_ma", "signal_critical_angle", "macd_signal", "rsi_signal",
              "rsi_value", "atr_value", "adx_value", "ema8", "ema21"):
        assert k in res
```

- [ ] **Step 2: Прогон**

Run: `python -m pytest tests/execution/test_indicator_agent.py -q`
Expected: 29 passed (20 + 9). Падение → STOP, report (особенно atr/adx — привести к факту).

- [ ] **Step 3: Commit**

```bash
git add tests/execution/test_indicator_agent.py
git commit -m "test(E5): характеризация IndicatorAgent._calc_indicators (legacy)"
```
Трейлер как в Task 1.

---

## Task 7: Полный прогон + обновление памяти

**Files:**
- Modify: `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md`

- [ ] **Step 1: Полный прогон (регрессия)**

Run: `python -m pytest -q`
Expected: все прежние зелёные + новые (~29 тестов indicator). 3 xfailed без новых регрессий. Записать числа.

- [ ] **Step 2: Находки — зафиксировать (если есть)**

Если тест выявил расхождение: занести в `docs/known-issues.md` (#8+), пометить тест `xfail`. **Прод не править.** Закоммитить.

- [ ] **Step 3: Обновить память**

В `project_millionskeeper.md`:
- Список тестов: добавить `test_indicator_agent.py` (E5, N кейсов).
- Обновить «Текущий прогон: ... passed».
- В «Статус работ» добавить `[x] E5 — характеризация indicator_agent ...` (покрытие, цикл, находки/«0 находок», пути спеки/плана).
- Отметить: **весь поток агентов теперь под характеризационной сеткой**.

- [ ] **Step 4: Commit (тесты/докsи; память вне git)**

```bash
git add tests/ docs/
git commit -m "test(E5): полный прогон зелёный + фиксация находок (если есть)"
```

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** run() #1–11 → Tasks 3–4; `_calc_strategy` #12–20 → Task 5; `_calc_indicators` #21–29 → Task 6; харнесс → Task 1; фабрика → Task 2. ✅
- **Плейсхолдеры:** нет — весь тест-код приведён целиком. ✅
- **Согласованность имён:** `indicator_agent_factory`, `make_indicator_strategy`, `fake_moving_average/fake_macd/fake_rsi_ind/fake_atr_ind/fake_adx_ind/fake_alligator`, `make_bars_df(extra_cols=...)`, хелперы `_feed/_ready/_statuses/_stub_calcs/_patch_indicators` — единообразны. ✅
- **Инвариант трека:** `trading` не импортируется. ✅
