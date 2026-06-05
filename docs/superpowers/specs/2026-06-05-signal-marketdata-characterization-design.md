# E4 — Характеризация `signal_agent` + `market_data_agent`

**Дата:** 2026-06-05
**Слайс:** E4 (трек «надёжность ядра», backlog #2, последний незакрытый слайс)
**Тип:** характеризационные тесты (golden-сетка), **прод не трогаем**
**Ветка:** `tradingHouse/stage-2`

## Цель

Запереть текущее поведение `agents/signal_agent.py` и `agents/market_data_agent.py`
характеризационной сеткой, переиспользуя харнесс `tests/execution/` (FakeMT5/
FakeBus/FakeRegistry/FakeStatus/FakeCache). Если всплывают странности поведения —
фиксируем как known-issue/xfail, **боевой код не правим** (как в E1–E3).

После E4 весь основной поток агентов (market_data → indicator → signal →
execution → position_monitor) будет под характеризационной сеткой, кроме
indicator_agent (вне скоупа этого слайса).

## Контекст: что делают агенты

### SignalAgent ([agents/signal_agent.py](../../../agents/signal_agent.py), 78 строк)
- Подписан на `INDICATORS_READY`, кладёт событие в `asyncio.Queue`.
- `run()`: читает РОВНО ОДНО событие из очереди и завершается (внешний цикл
  `BaseAgent.start()` зовёт `run()` повторно).
- Логика сигнала:
  - Если `entry_signal ∈ {BUY, SELL, NO_SIGNAL}` — берём его как `combined`
    (IndicatorAgent уже посчитал сигнал стратегии).
  - Иначе — legacy: AND из 4 сигналов (`signal_ma`, `signal_critical_angle`,
    `macd_signal`, `rsi_signal`); все BUY → BUY, все SELL → SELL, иначе NO_SIGNAL.
  - Отсутствующие legacy-ключи дефолтятся в `"NO_SIGNAL"`.
- Метрики `buy_signals`/`sell_signals` инкрементятся ТОЛЬКО при BUY/SELL.
- Эмитит `AGENT_STATUS` (idle → running) и `SIGNAL_GENERATED` с пробросом
  `correlation_id`, `stream_id`, `trading_status` (из `status.status_of`) и
  dict `indicators`.

### MarketDataAgent ([agents/market_data_agent.py](../../../agents/market_data_agent.py), 93 строки)
- `_current_pairs()`: уникальные `(symbol, int(tf))` по `registry.enabled()`,
  пропуская символы с `status.is_disabled(symbol)`.
- `run()`:
  - `cache.invalidate()`, пересчёт пар, очистка `_last_bar_times` по удалённым
    парам (дифф против `_last_seen_pairs`), метрики `symbols`/`pairs`.
  - Эмит `MARKET_CACHE_INVALIDATED`.
  - `mt5.terminal_info()` falsy → `MT5_DISCONNECTED` + статус ERROR + `sleep` +
    `return` (без `NEW_BAR`, без `MT5_CONNECTED`).
  - Иначе → `MT5_CONNECTED`, затем по каждой паре:
    `cache.get_rates(symbol, tf, bars=2)`; None/пусто → continue; иначе берём
    `rates.iloc[-1]['time']`, нормализуем (`pd.Timestamp` → `.timestamp()`,
    иначе `int`); если `prev is None` — записываем без эмита; если `last_time >
    prev` — записываем и эмитим `NEW_BAR`; иначе ничего.
  - Исключение по символу ловится и логируется (агент не падает).
  - Метрики `new_bars`/`last_poll`, статус IDLE, `sleep(poll_interval)`.

## Архитектура тестов

Тот же паттерн, что E2/E3: две фабрики-фикстуры в
[tests/execution/conftest.py](../../../tests/execution/conftest.py),
монкипатч модульных глобалов, прод не меняется. Два файла:
`test_signal_agent.py` и `test_market_data_agent.py`.

### Фабрика `signal_agent_factory`
- Патчит `agents.signal_agent.status` → `FakeStatus`.
- Агент строится с `FakeBus()`.
- Драйв: помещаем `INDICATORS_READY`-event в очередь агента (через
  `await agent._on_indicators_ready(event)` либо прямой `_queue.put_nowait`),
  затем один `await agent.run()`.
- Возвращает namespace: `agent, bus, status`.

### Фабрика `market_data_agent_factory`
- Патчит: `streams.registry` → `FakeRegistry`,
  `agents.market_data_agent.status` → `FakeStatus`,
  `market_data_cache.cache` → `FakeCache`,
  `sys.modules['MetaTrader5']` → `FakeMT5`.
- Агент строится с `poll_interval=0` (иначе тест висит на `asyncio.sleep`).
- Возвращает namespace: `agent, bus, registry, status, cache, mt5`.
- Инвариант трека: `trading` НЕ импортируется на уровне модуля (catch-22 E1).
  Здесь `trading` не нужен вовсе.

### Дополнения харнесса (`tests/execution/fakes.py`)
- `FakeRegistry.enabled()` → список enabled-потоков (`[s for s in values if
  s.enabled]`).
- `FakeStatus.is_disabled(symbol)` + механизм пометки disabled (поле
  `_disabled: set`, например через сеттер `mark_disabled` или прямую инициализацию).
- `FakeCache.invalidate()` → ставит флаг `self.invalidated = True` (для ассерта).
- `FakeMT5.terminal_info()` → возвращает настраиваемое поле (по умолчанию truthy
  sentinel; `None` для disconnected-ветки).
- `make_bars_df(*, time, ...)` → `pd.DataFrame` минимум с колонкой `time`
  (значение — `int` или `pd.Timestamp`), доступной через `.iloc[-1]['time']`.

Дополнения аддитивны — существующие E1/E2/E3-тесты не затрагиваются.

## Перечень характеризуемого поведения

### SignalAgent (~12–15 кейсов)
1. `entry_signal == "BUY"` → combined BUY, `buy_signals` += 1, legacy игнорируется.
2. `entry_signal == "SELL"` → combined SELL, `sell_signals` += 1.
3. `entry_signal == "NO_SIGNAL"` короткозамыкает legacy — combined NO_SIGNAL,
   даже если 4 legacy-сигнала были бы BUY (нюанс, явный тест), счётчики не растут.
4. `entry_signal` отсутствует/None → падаем в legacy.
5. `entry_signal` = мусор (напр. `"buy"` или `"FOO"`) → падаем в legacy.
6. Legacy: все 4 = BUY → BUY (+метрика).
7. Legacy: все 4 = SELL → SELL (+метрика).
8. Legacy: смешанные (3 BUY + 1 NO_SIGNAL) → NO_SIGNAL.
9. Legacy: отсутствующие ключи → дефолт `"NO_SIGNAL"` → NO_SIGNAL.
10. `SIGNAL_GENERATED`: `correlation_id` проброшен из входного event.
11. `SIGNAL_GENERATED`: `trading_status` = `status.status_of(symbol)`,
    `stream_id` проброшен из payload.
12. `SIGNAL_GENERATED`: dict `indicators` содержит ключи `ma/ma_angle/macd/rsi/
    rsi_value/atr_value/adx_value/ema8/ema21`; отсутствующие во входе → None.
13. Эмит порядка: `AGENT_STATUS=idle` → `AGENT_STATUS=running` →
    `SIGNAL_GENERATED` (характеризуем фактический порядок/состав событий на шине).
14. Метрики не растут при NO_SIGNAL (legacy и entry-путь).

### MarketDataAgent (~14–18 кейсов)
1. `_current_pairs`: дедуп `(symbol, tf)` по нескольким потокам с одинаковой парой.
2. `_current_pairs`: пропуск символа с `is_disabled == True`.
3. `_current_pairs`: только `enabled()` потоки (disabled-поток не попадает).
4. `_current_pairs`: `int(timeframe)` нормализация.
5. Метрики `symbols` (уникальные символы) и `pairs` (число пар).
6. Эмит `MARKET_CACHE_INVALIDATED` с `{"pairs": N}` + `cache.invalidate()` вызван.
7. `terminal_info()` None → эмит `MT5_DISCONNECTED`, статус ERROR, ранний return;
   нет `MT5_CONNECTED`, нет `NEW_BAR`.
8. `terminal_info()` truthy → эмит `MT5_CONNECTED`.
9. Новая свеча — первый показ (`prev is None`): `_last_bar_times` записан,
   `NEW_BAR` НЕ эмитится, `new_bars == 0`.
10. Новая свеча — второй запуск с большим `time` → эмит `NEW_BAR`
    (`symbol/bar_time/timeframe`), `new_bars == 1`.
11. Второй запуск с равным `time` → нет `NEW_BAR`.
12. Второй запуск с меньшим `time` → нет `NEW_BAR`.
13. `rates is None` → пара пропущена (continue), нет `NEW_BAR`.
14. `rates` пустой (`len == 0`) → пропуск.
15. Конверсия времени: `pd.Timestamp` → `.timestamp()` (через `make_bars_df`).
16. Конверсия времени: `int` напрямую.
17. Очистка `_last_bar_times`: пара исчезла из потоков между запусками →
    запись удалена (характеризуем через приватное состояние или повторное
    появление пары как «первой»).
18. Исключение в обработке символа (напр. `get_rates` бросает) ловится: агент
    не падает, остальные пары обрабатываются, статус доходит до IDLE.

## Ожидаемый исход
Оба агента почти чистые → ожидаем **0 находок** (как E2/E3). Если найдём
расхождение/баг — фиксируем xfail + known-issue, прод не правим.

## Критерии готовности
- `test_signal_agent.py` + `test_market_data_agent.py` созданы, все зелёные.
- Дополнения `fakes.py` аддитивны; полный прогон `pytest` зелёный
  (423 passed + новые, 3 xfailed без регрессий).
- Инвариант: в `tests/execution/` `trading` не импортируется на уровне модуля.
- Память `project_millionskeeper.md` обновлена (слайс E4 закрыт).

## Вне скоупа
- `indicator_agent` (отдельный слайс при желании).
- Любые правки боевого кода агентов.
- Рефакторинг существующего харнесса сверх перечисленных аддитивных дополнений.
