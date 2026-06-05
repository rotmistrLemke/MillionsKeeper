# Удаление GlobalValues + legacy-панели «Активная стратегия» — дизайн (слайс B2)

**Дата:** 2026-06-01
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** B2 — завершение рефакторинга глобального состояния `settings.py` (после B1).

---

## Цель и контекст

`settings.GlobalValues` хранит «единый активный конфиг» торговли (`active_strategy`, `active_symbol`, `time_frame`, `active_volume`, `active_sl_atr`, `active_tp_atr`). Это **legacy**: боевой путь уже полностью перешёл на `streams.StreamRegistry` (мульти-поточная торговля). GlobalValues стал рудиментарным параллельным «источником правды», а связанная с ним UI-панель «Активная стратегия» вводит в заблуждение — задаёт конфиг, который не управляет реальной торговлей.

B2 удаляет GlobalValues и legacy-панель целиком. Streams — единственный источник торгового конфига.

### Доказательство рудиментарности (проверено в коде)

- **ExecutionAgent** берёт конфиг из потока: `stream = registry.get/by_symbol`, `stream.strategy`, `stream.volume`, `stream.sl_atr` ([execution_agent.py](../../../agents/execution_agent.py)). GlobalValues не читает.
- **MarketDataAgent** строит пары из `streams.registry.enabled()` через `_current_pairs()`; конструкторные аргументы `symbols`/`timeframe` (из `GlobalValues`) **не сохраняются и не используются** ([market_data_agent.py:18-34](../../../agents/market_data_agent.py#L18)).
- **IndicatorAgent** использует `stream.timeframe`/`stream.strategy`; аргумент `timeframe` конструктора **игнорируется** ([indicator_agent.py:20](../../../agents/indicator_agent.py#L20)).
- Единственный «живой» побочный эффект legacy-команды `set_active_strategy` — `activate_only(symbol)` (через trading_status) — дублирует `streams._sync_trading_status`.
- Панель «Потоки» строго мощнее legacy-панели (символ + стратегия + TF + объём + SL/TP на поток), то есть функциональность не теряется.

---

## Область

**Удаляется:**
- класс `settings.GlobalValues` (локально — `settings.py` gitignored);
- модуль `active_state.py` целиком;
- legacy-команда `set_active_strategy` (ws) и эндпоинт `GET /active_strategy`;
- блок `active_strategy` в ws-снапшоте;
- разовая миграция `streams._migrate_from_legacy`;
- UI-панель «Активная стратегия» (HTML + JS).

**Не трогаем:**
- `streams.py` StreamRegistry (кроме удаления миграции);
- `trading_status` (B1);
- `TF_MAP`/`TF_REVERSE`/`TargetType` в settings (используются streams);
- эндпоинт `/api/symbols` (от trading_status, нужен форме потоков);
- обработчик `set_trading_status`.

---

## Изменения по файлам

### Backend (под контролем версий)

**main.py**
- Убрать `from settings import GlobalValues`.
- Убрать `timeframe = GlobalValues.time_frame` ([main.py:77](../../../main.py#L77)).
- Убрать `import active_state` и `active_state.load()` ([main.py:64-65](../../../main.py#L64)).
- В конструкторах `MarketDataAgent("MarketData", bus, symbols, timeframe, ...)` и `IndicatorAgent("Indicator", bus, timeframe)` убрать ныне мёртвые аргументы `symbols`/`timeframe`. Сигнатуры агентов: `MarketDataAgent.__init__(self, name, bus, symbols=None, timeframe=None, poll_interval=10.0)` и `IndicatorAgent.__init__(self, name, bus, timeframe=None)` — параметры опциональны, поэтому вызовы упрощаются до `MarketDataAgent("MarketData", bus, poll_interval=10.0)` и `IndicatorAgent("Indicator", bus)`. `_get_active_symbols()` (использовался только для мёртвого аргумента) — удалить, если больше нигде не нужен (проверить).
- Лог-строка `logger.info(f"Активных символов: {len(symbols)} | потоков: ...")` ([main.py:78](../../../main.py#L78)) ссылается на `symbols` — упростить до счёта по потокам (например, `len(streams.registry.all())`), убрав `len(symbols)`.

**web/app.py**
- Удалить целиком ветку `elif action == "set_active_strategy":` (~190-264), включая её `reset_strategy_cache()`, запись GlobalValues, `active_state.save()` и broadcast `active_strategy_changed`.
- Оставить `set_trading_status` и прочие действия без изменений.

**web/ws_manager.py**
- В `_send_snapshot` убрать ключ `active_strategy` из payload и связанный `from settings import GlobalValues, TF_REVERSE` (если `TF_REVERSE` больше не нужен в файле — убрать; иначе оставить).

**web/api_routes.py**
- Удалить эндпоинт `GET /active_strategy` (~683-693).

**streams.py**
- Удалить функцию `_migrate_from_legacy` (~256-285).
- В `load()` ([streams.py:228-242](../../../streams.py#L228)): при отсутствии `streams.json` — просто `return` (пустой реестр), без вызова миграции. Обновить docstring.

**active_state.py** — удалить файл целиком (импортёров не остаётся).

### Frontend (под контролем версий)

**web/static/index.html** — удалить разметку панели «Активная стратегия»: элементы `#active-strategy`, `#active-timeframe`, `#active-symbol`, `#active-volume`, `#active-sl-atr`, `#active-tp-atr`, `#btn-set-strategy` и дисплей-элементы `#asp-strategy/#asp-symbol/#asp-timeframe/#asp-volume/#asp-sl/#asp-tp` вместе с их секцией-контейнером.

**web/static/app.js** — удалить:
- функции `applySetStrategy` (~1255), `renderActiveStrategy` (~1266), `syncActiveStrategyForm` (~1291), `populateActiveSymbols` (~1311);
- поле `active_strategy` в объекте `state` (~454);
- обработку снапшота `if (data.active_strategy) { ... }` (~544-547) и ветку `active_strategy_changed` (~552-556);
- все вызовы удалённых функций в init/render и обработчик кнопки `#btn-set-strategy`.

### settings.py (untracked, локальная правка)
Удалить класс `GlobalValues`. Оставить `TargetType`, `TF_MAP`, `TF_REVERSE`, `Dictionary` (с прочими членами). Правка локальная и не коммитится (файл gitignored), но необходима, чтобы приложение не импортировало удалённый класс.

---

## Изменение поведения

- `streams.load()` без `streams.json` → пустой реестр (раньше создавал «Поток 1» из legacy `active_state.json`). Приемлемо: рабочие деплои уже имеют `streams.json`.
- UI лишается панели «Активная стратегия»; управление конфигом — только через панель «Потоки».
- `GET /active_strategy` и ws-ключ `active_strategy` исчезают из API/контракта.

---

## Тестирование и верификация

Web/frontend без автотестов, MT5 в CI отсутствует → верификация слабее, чем в A/B1. Подстраховка:

1. **Юнит-тест** (`tests/test_streams_load.py`): `streams.load()` при отсутствующем `streams.json` (через monkeypatch пути на временный каталог) → `registry.all() == []`, исключений нет. Заменяет удалённую миграцию проверкой нового поведения.
2. **Smoke-импорт**: `python -c "import main, streams, web.app, web.api_routes, web.ws_manager"` без ошибок; `import active_state` падает (модуль удалён) — ожидаемо.
3. **Существующий набор** остаётся зелёным (221 passed, 20 skipped, 1 xfailed).
4. **Grep-чистота**: ни одной ссылки на `GlobalValues`, `active_state`, `set_active_strategy`, `/active_strategy`, и на удалённые JS-функции/`state.active_strategy` в `.py`/`.js`/`.html` (кроме, возможно, комментариев).
5. **Ручная проверка страницы** — за пользователем (нужен запущенный app с MT5): дашборд открывается, панель «Потоки» работает, отсутствие панели «Активная стратегия» не ломает раскладку и консоль без JS-ошибок.

---

## Риски

- **Frontend** — главный риск: удалить панель, не задев общую инициализацию страницы и обработчик ws-снапшота. Митигируется грепом всех вызовов удаляемых функций + ревью + ручной проверкой.
- **Потеря побочных эффектов** legacy-команды (`reset_strategy_cache`, `activate_only`) — дублировали streams-логику; на боевой путь не влияют.
- **Откат**: всё в коммитах B2; при проблеме на фронте откатывается отдельным revert.

---

## Связанные документы

- `docs/superpowers/specs/2026-06-01-trading-status-service-design.md` — B1 (предыдущий шаг)
- [streams.py](../../../streams.py) — единственный источник торгового конфига после B2
