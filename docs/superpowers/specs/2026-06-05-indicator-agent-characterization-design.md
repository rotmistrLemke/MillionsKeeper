# E5 — Характеризация `indicator_agent`

**Дата:** 2026-06-05
**Слайс:** E5 (последний агент потока вне характеризационной сетки)
**Тип:** характеризационные тесты (golden-сетка), **прод не трогаем**
**Ветка:** `e5/indicator-agent` (от `main`)

## Цель

Запереть текущее поведение всех трёх частей `agents/indicator_agent.py`
характеризационной сеткой, переиспользуя харнесс `tests/execution/`. Если
всплывают странности — фиксируем как known-issue/xfail, **боевой код не правим**
(как в E1–E4).

После E5 весь поток агентов (market_data → indicator → signal → execution →
position_monitor) полностью под характеризационной сеткой.

## Контекст: что делает агент

`IndicatorAgent` ([agents/indicator_agent.py](../../../agents/indicator_agent.py), 175 строк):
подписан на `NEW_BAR`, кладёт в `asyncio.Queue`. `run()` читает РОВНО ОДНО событие
и завершается (внешний цикл `BaseAgent.start()` зовёт повторно). Три части:

### 1. `run()` — gating + dispatch
- Берёт событие, `symbol`, `bar_tf = int(p.get("timeframe") or 0)`.
- `stream = registry.by_symbol(symbol)`; если `None` или `not stream.enabled` → `return`.
- Если `bar_tf` и `int(stream.timeframe) != bar_tf` → `return`.
- `use_strategy = stream.strategy in STRATEGIES`.
- Считает результат в executor: `_calc_strategy` (если use_strategy) либо
  `_calc_indicators` (default/legacy).
- `result["stream_id"] = stream.id`, метрика `calculated`++, эмит
  `INDICATORS_READY` (проброс `correlation_id`), статус IDLE «Готово».
- Исключение в расчёте: лог + статус ERROR (без `INDICATORS_READY`).

### 2. `_calc_strategy(symbol, strategy_name, tf)` — путь рантайм-стратегии
- `get_runtime_strategy(strategy_name, symbol)`, `cache.get_rates(symbol, tf, bars=500)`.
- `df is None or len(df) < 50` → минимальный dict
  `{symbol, strategy, entry_signal:"NO_SIGNAL", is_flat:True}`.
- Иначе: `compute_indicators` + `compute_flat_indicators`, `row = df.iloc[-1]`,
  `flat = bool(is_flat(row))`, `signal = None if flat else get_entry_signal(row)`.
- `indicators_raw`: по `indicator_columns()+flat_indicator_columns()` собирает
  значения последнего бара, что присутствуют в df, `notna` и приводятся к `float`
  (иначе пропуск).
- Возврат: `entry_signal = signal or "NO_SIGNAL"`, `is_flat`, `indicators_raw`,
  legacy-совместимые поля (`signal_ma`/`signal_critical_angle`/`macd_signal`/
  `rsi_signal` = `"NO_SIGNAL"`), `rsi_value`/`atr_value`/`adx_value`/`ema8`/`ema21`
  через `_get_float` (atr: `atr`→`flat_atr`; adx: `flat_adx`→`0.0`).

### 3. `_calc_indicators(symbol, tf)` — legacy default-путь
- `from indicators import MovingAverage, MACD, RSI, ATR, ADX` (+ `Alligator`).
- `MovingAverage`: `get_ma_for_symbol(symbol, tf, 8/21)`, `ma_cross_signal`,
  `ma_critical_angle`.
- `ATR.calculate_atr`, `MACD.calculate_macd_manual`+`MACD_signal`,
  `RSI.get_rsi_talib`+`RSI_signal`, `Alligator.Df`+`ADX.ADX`.
- Возврат-dict: сигналы извлекаются `.get("signal","NO_SIGNAL")` ТОЛЬКО если
  значение — dict (иначе `"NO_SIGNAL"`); `rsi_value` только при наличии данных и
  `len(RSI) >= 3`; `atr_value` через `.iloc[-1]` если `hasattr(..., 'iloc')`,
  иначе как есть; `ema8/ema21` через `.iloc[-1]`; `adx_val = values[-1]` или `0.0`.

## Архитектура тестов

Паттерн E2–E4: фабрика `indicator_agent_factory` в
[conftest.py](../../../tests/execution/conftest.py), монкипатч модульных глобалов,
прод не меняется. Один файл `tests/execution/test_indicator_agent.py`.

**Инвариант трека:** `trading` НЕ импортируется на уровне модуля. Здесь не нужен.

### Фабрика `indicator_agent_factory`
- Патчит `streams.registry`→`FakeRegistry`, `strategies.STRATEGIES`→dict.
- Агент строится с `FakeBus()`.
- Параметры для гибкости: `streams`, `strategies`, плюс опциональная подмена
  `_calc_strategy`/`_calc_indicators` на инстансе канонед-функцией (для изоляции
  `run()`-dispatch), фейк `cache` (для `_calc_strategy`), подмена
  `strategies.runtime.get_runtime_strategy` (для `_calc_strategy`).
- Драйв: `agent._queue.put_nowait(NEW_BAR-event)`, затем `await agent.run()`.
- Возврат namespace: `agent, bus, registry, cache, ...`.

### Дополнения харнесса (`fakes.py`, аддитивно)
- `make_indicator_strategy(*, flat=False, entry_signal=None, indicator_cols=None,
  flat_cols=None)` — фейк рантайм-стратегии: `compute_indicators`/
  `compute_flat_indicators` (возврат df как есть), `is_flat(row)`,
  `get_entry_signal(row)`, `indicator_columns()`, `flat_indicator_columns()`.
- Фейки `indicators.py` (настраиваемые возвраты):
  `FakeMovingAverage` (`get_ma_for_symbol`/`ma_cross_signal`/`ma_critical_angle`),
  `FakeMACD` (`calculate_macd_manual`/`MACD_signal`),
  `FakeRSI` (`get_rsi_talib`/`RSI_signal`),
  `FakeATR` (`calculate_atr`), `FakeADX` (`ADX`), `FakeAlligator` (`Df`).
  Каждый умеет вернуть dict с `signal`, либо non-dict (для isinstance-guard),
  либо series/None.
- Расширить `make_bars_df` опциональными колонками (`extra_cols: dict`) — для
  проверки сбора `indicators_raw` в `_calc_strategy`.

Дополнения аддитивны — E1–E4 не затрагиваются.

## Перечень характеризуемого поведения

### `run()` dispatch (~11 кейсов)
1. Нет потока (`by_symbol` → None) → ранний return, нет `INDICATORS_READY`.
2. Поток `enabled=False` → return.
3. `int(stream.timeframe) != bar_tf` → return.
4. `bar_tf` = 0/None → проверка tf пропущена, расчёт идёт.
5. `strategy ∈ STRATEGIES` → вызван `_calc_strategy` (не `_calc_indicators`).
6. `strategy ∉ STRATEGIES` → вызван `_calc_indicators`.
7. `INDICATORS_READY` payload содержит `stream_id = stream.id`.
8. `correlation_id` проброшен из входного NEW_BAR.
9. Метрика `calculated` инкрементится на успехе.
10. Статусы: IDLE(старт) → RUNNING → IDLE(готово).
11. Исключение в calc → статус ERROR, нет `INDICATORS_READY`, метрика не растёт.

### `_calc_strategy` (~9 кейсов)
12. `cache.get_rates` → None → минимальный dict (entry_signal NO_SIGNAL, is_flat True).
13. df с `len < 50` → тот же минимальный dict.
14. `is_flat` True → `entry_signal == "NO_SIGNAL"`, `is_flat True`, `get_entry_signal` не зовётся.
15. not-flat + `get_entry_signal` → "BUY" → `entry_signal == "BUY"`.
16. not-flat + `get_entry_signal` → None → `entry_signal == "NO_SIGNAL"`.
17. `indicators_raw` собирает колонки из `indicator_columns()+flat_indicator_columns()`,
    присутствующие в df и floatable.
18. `indicators_raw` пропускает колонку, которой нет в df / NaN.
19. legacy-поля = "NO_SIGNAL"; `rsi_value`/`ema8`/`ema21` через `_get_float`.
20. `atr_value` fallback: нет `atr` → берётся `flat_atr`; `adx_value`: нет
    `flat_adx` → `0.0`.

### `_calc_indicators` (~9 кейсов)
21. Сигналы извлекаются `.get("signal")` когда возврат — dict (`signal_ma` и т.д.).
22. non-dict возврат индикатора → соответствующее поле `"NO_SIGNAL"` (isinstance-guard).
23. RSI данные None → `rsi_signal == "NO_SIGNAL"`, `rsi_value is None`.
24. RSI `len < 3` → то же.
25. RSI `len >= 3` → `rsi_value` float, `RSI_signal` вызван, поле из его dict.
26. `atr_value`: объект с `.iloc` → `float(.iloc[-1])`; без `.iloc` → как есть.
27. `ema8`/`ema21` из `fast_ma`/`slow_ma` `.iloc[-1]`; None при отсутствии `.iloc`.
28. `adx_val` = `float(values[-1])`; пустые/None values → `0.0`.
29. Итоговый dict содержит `symbol` и все ожидаемые ключи.

## Ожидаемый исход
Логика детерминированная → ожидаем **0 находок** (возможны мелкие наблюдения в
legacy-парсинге `_calc_indicators`). Находку фиксируем xfail + known-issue, прод
не правим.

## Критерии готовности
- `test_indicator_agent.py` создан, все зелёные.
- Дополнения `fakes.py` аддитивны; полный прогон `pytest` зелёный (455 passed +
  новые, 3 xfailed без регрессий).
- Инвариант: в `tests/execution/` `trading` не импортируется на уровне модуля.
- Память `project_millionskeeper.md` обновлена (слайс E5 закрыт; поток агентов
  полностью под сеткой).

## Вне скоупа
- Любые правки боевого кода.
- Характеризация внутренней математики самого `indicators.py` (smma/angle/ADX-
  расчёты) — здесь фейкаем классы целиком; их математика — отдельный слайс при желании.
- Рефакторинг харнесса сверх перечисленных аддитивных дополнений.
