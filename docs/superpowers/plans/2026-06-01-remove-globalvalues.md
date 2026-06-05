# Удаление GlobalValues + legacy-панели — план реализации (слайс B2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Удалить рудиментарный `settings.GlobalValues`, модуль `active_state.py`, legacy-команду/эндпоинт «активной стратегии», разовую миграцию streams и мёртвый frontend-код панели. Источник торгового конфига — только `streams`.

**Architecture:** Сначала убираем ссылки в tracked-коде (streams → backend-consumers → удаление active_state.py → frontend dead-code), затем последним шагом удаляем класс `GlobalValues` из (gitignored) `settings.py`. Каждый шаг оставляет приложение импортируемым и набор тестов зелёным.

**Tech Stack:** Python 3.11, pytest; vanilla JS frontend.

**Спека:** [docs/superpowers/specs/2026-06-01-remove-globalvalues-design.md](../specs/2026-06-01-remove-globalvalues-design.md)

**Важная поправка к спеке (обнаружено при планировании):** разметки панели «Активная стратегия» в `index.html` УЖЕ НЕТ. JS-функции (`setActiveStrategy`, `onActiveStrategyChange`, `renderActiveStrategy`, `syncActiveStrategyForm`, `populateActiveSymbols`) никем не вызываются и работают с несуществующими DOM-элементами под null-guard'ами. Поэтому frontend-часть — чистое удаление мёртвого кода (низкий риск), а не демонтаж живой панели.

---

## Структура файлов

| Файл | Действие |
|------|----------|
| `streams.py` | Изменить — убрать `_migrate_from_legacy`, упростить `load()` |
| `tests/test_streams_load.py` | Создать — тест пустой загрузки без миграции |
| `main.py` | Изменить — убрать GlobalValues/active_state/мёртвые аргументы агентов |
| `web/app.py` | Изменить — удалить ветку `set_active_strategy` |
| `web/ws_manager.py` | Изменить — убрать `active_strategy` из снапшота |
| `web/api_routes.py` | Изменить — удалить `GET /active_strategy` |
| `active_state.py` | Удалить файл |
| `web/static/app.js` | Изменить — удалить мёртвые функции/состояние/ws-обработчики |
| `web/static/style.css` | Изменить — удалить мёртвые CSS-правила панели |
| `settings.py` | Изменить локально (gitignored) — удалить класс `GlobalValues` |

---

## Task 1: streams.py — убрать миграцию + тест

**Files:**
- Modify: `streams.py`
- Test: `tests/test_streams_load.py`

- [ ] **Step 1: Написать тест нового поведения (red)**

`tests/test_streams_load.py`:
```python
"""B2: streams.load() без streams.json даёт пустой реестр (миграция удалена)."""
import importlib


def test_load_without_file_yields_empty_registry(tmp_path, monkeypatch):
    import streams
    importlib.reload(streams)
    # Перенаправляем файл потоков на несуществующий путь во временном каталоге.
    monkeypatch.setattr(streams, "_STREAMS_FILE", tmp_path / "nope_streams.json")
    # Чистый реестр на старте.
    streams.registry._streams.clear()
    streams.load()
    assert streams.registry.all() == []
```

- [ ] **Step 2: Запустить — упадёт (load всё ещё зовёт миграцию)**

Run: `python -m pytest tests/test_streams_load.py -q`
Expected: FAIL или ошибка (миграция пытается читать legacy/GlobalValues).

- [ ] **Step 3: Удалить `_migrate_from_legacy` и упростить `load()`**

В [streams.py](../../../streams.py):
- Удалить функцию `_migrate_from_legacy` целиком (≈ строки 256-285).
- Заменить начало `load()`:
```python
def load() -> None:
    """Загружает потоки из streams.json. Если файла нет — стартуем с пустым реестром."""
    if not _STREAMS_FILE.exists():
        return
```
(остальное тело `load()` без изменений: чтение JSON, `_load_raw_locked`, `_sync_trading_status`, лог.)

- [ ] **Step 4: Запустить тест — зелёно**

Run: `python -m pytest tests/test_streams_load.py -q`
Expected: 1 passed.

- [ ] **Step 5: Проверить отсутствие GlobalValues/active_state в streams.py**

Run (Grep или): искать в `streams.py` подстроки `GlobalValues`, `active_state`, `_migrate_from_legacy` — не должно остаться ни одной.

- [ ] **Step 6: Commit**

```bash
git add streams.py tests/test_streams_load.py
git commit -m "refactor(streams): убрать legacy-миграцию из load() + тест пустой загрузки (B2)"
```

---

## Task 2: backend-потребители GlobalValues/active_state

**Files:**
- Modify: `main.py`, `web/app.py`, `web/ws_manager.py`, `web/api_routes.py`

> После этой задачи `active_state` и `GlobalValues` больше не импортируются нигде в tracked-коде (кроме самого `active_state.py`, который удаляется в Task 3, и `settings.py` — Task 5).

- [ ] **Step 1: main.py**

В [main.py](../../../main.py):
- Удалить `import active_state` и `active_state.load()` (строки ~64-65, вместе с комментарием «Восстановление последней выбранной стратегии»).
- Удалить `from settings import GlobalValues` (внутри `main()`, ~строка 43) и строку `timeframe = GlobalValues.time_frame` (~77).
- Удалить функцию `_get_active_symbols()` (~35-38) и строку `symbols = _get_active_symbols()` (~76), если `symbols` больше нигде не нужен.
- Лог-строку (~78) заменить на:
```python
    logger.info(f"Потоков: {len(streams.registry.all())}")
```
- Конструкторы агентов упростить (опциональные аргументы):
```python
        MarketDataAgent("MarketData",  bus, poll_interval=10.0),
        IndicatorAgent("Indicator",    bus),
```
(было: `MarketDataAgent("MarketData", bus, symbols, timeframe, poll_interval=10.0)` и `IndicatorAgent("Indicator", bus, timeframe)`.)

- [ ] **Step 2: web/app.py — удалить ветку set_active_strategy**

В [web/app.py](../../../web/app.py) удалить целиком блок `elif action == "set_active_strategy":` со всем телом (≈ строки 190-264, заканчивается закрытием `await ws_manager.broadcast("active_strategy_changed", {...})`). Соседние ветки (`close_position` выше и `chart_subscribe` ниже) сохранить. Убедиться, что в файле не осталось `GlobalValues`, `active_state`, `set_active_strategy`.

- [ ] **Step 3: web/ws_manager.py — убрать active_strategy из снапшота**

В [web/ws_manager.py](../../../web/ws_manager.py) `_send_snapshot`:
- Убрать ключ `"active_strategy": { ... }` из payload `agents_snapshot` (строки ~115-122).
- Поправить импорт строки ~109 `from settings import GlobalValues, TF_REVERSE`: убрать `GlobalValues`; `TF_REVERSE` убрать тоже, если он больше не используется в `_send_snapshot`/файле (проверить — после удаления блока он, скорее всего, не нужен).

Результат payload:
```python
        await self.send_to(ws, "agents_snapshot", {
            "agents": registry.get_all_statuses(),
            "recent_events": recent,
        })
```

- [ ] **Step 4: web/api_routes.py — удалить GET /active_strategy**

В [web/api_routes.py](../../../web/api_routes.py) удалить эндпоинт целиком (≈ 681-693):
```python
@router.get("/active_strategy")
async def get_active_strategy(...):
    ...
```
вместе с комментарием-разделителем `# ──── Active strategy ────`, если он только для него.

- [ ] **Step 5: Проверка импортов/сбора**

Run: `python -c "import main, web.app, web.api_routes, web.ws_manager; print('import ok')"` → `import ok`
Run: `python -m pytest -q` → 222 passed, 20 skipped, 1 xfailed (221 прежних + 1 новый из Task 1).

- [ ] **Step 6: Commit**

```bash
git add main.py web/app.py web/ws_manager.py web/api_routes.py
git commit -m "refactor: убрать backend-потребителей GlobalValues/active_state (B2)"
```

---

## Task 3: удалить active_state.py

**Files:**
- Delete: `active_state.py`

- [ ] **Step 1: Подтвердить отсутствие импортёров**

Run (Grep): искать `active_state` во всех `.py`. Ожидается: ноль ссылок (Task 1 и 2 их убрали).

- [ ] **Step 2: Удалить файл**

```bash
git rm active_state.py
```

- [ ] **Step 3: Проверка**

Run: `python -c "import main; print('ok')"` → `ok`
Run: `python -m pytest -q` → 222 passed, 20 skipped, 1 xfailed.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: удалить модуль active_state (заменён streams) (B2)"
```

---

## Task 4: frontend — удалить мёртвый код панели

**Files:**
- Modify: `web/static/app.js`, `web/static/style.css`

> Все перечисленные JS-функции и состояние — мёртвые (нет DOM-элементов, нет вызовов, кроме ws-обработчиков, которые тоже удаляются). Читать текущий файл перед удалением.

- [ ] **Step 1: app.js — удалить состояние и ws-обработчики**

- Удалить поле `active_strategy: null,` из объекта `state` (~454).
- В обработчике снапшота удалить блок (~544-548):
```javascript
    if (data.active_strategy) {
      state.active_strategy = data.active_strategy;
      renderActiveStrategy();
      syncActiveStrategyForm();
    }
```
- Удалить целиком ветку (~552-559):
```javascript
  if (msg_type === 'active_strategy_changed') {
    if (data && !data.error) {
      state.active_strategy = data;
      renderActiveStrategy();
      syncActiveStrategyForm();
    }
    return;
  }
```

- [ ] **Step 2: app.js — удалить мёртвые функции**

Удалить целиком определения функций: `onActiveStrategyChange` (~1249), `setActiveStrategy` (~1254), `renderActiveStrategy` (~1266), `syncActiveStrategyForm` (~1291), `populateActiveSymbols` (~1311). Перед удалением убедиться (grep), что у каждой нет других вызовов в `app.js`/`index.html` (ожидается — нет).

- [ ] **Step 3: style.css — удалить мёртвые правила**

Удалить CSS-правила, относящиеся к панели: селекторы с `active-strategy`, `#asp-`, и связанные (grep `active-strategy|asp-` по `style.css`). Удалять только правила этой панели; не трогать общие классы.

- [ ] **Step 4: Проверка чистоты frontend**

Run (Grep): `active_strategy`, `active-strategy`, `asp-strategy`, `setActiveStrategy`, `renderActiveStrategy`, `syncActiveStrategyForm`, `populateActiveSymbols`, `onActiveStrategyChange` по `web/static/` — ноль совпадений.

- [ ] **Step 5: Commit**

```bash
git add web/static/app.js web/static/style.css
git commit -m "refactor(ui): удалить мёртвый код панели «Активная стратегия» (B2)"
```

---

## Task 5: удалить GlobalValues из settings.py (локально)

**Files:**
- Modify: `settings.py` (gitignored — правка локальная, НЕ коммитится)

> `settings.py` под `.gitignore` (`settings*`), как и в B1. Удаление не попадёт в git, но необходимо, чтобы приложение не держало мёртвый класс. Коммита в этой задаче НЕТ.

- [ ] **Step 1: Подтвердить отсутствие ссылок в коде**

Run (Grep): `GlobalValues` по всем `.py`. Ожидается: только определение в `settings.py` (и, возможно, docstring в `strategies/default_inverse.py` — это текст, не код; при желании поправить формулировку).

- [ ] **Step 2: Удалить класс GlobalValues**

В [settings.py](../../../settings.py) удалить весь класс `class GlobalValues: ...`. Оставить `TargetType`, `TF_MAP`, `TF_REVERSE`, `IndicatorType`, `Dictionary`.

- [ ] **Step 3: Финальная проверка**

Run: `python -c "import main; print('ok')"` → `ok`
Run: `python -m pytest -q` → 222 passed, 20 skipped, 1 xfailed, 0 ошибок сбора.
Run (Grep): `GlobalValues` по `.py` — только (если есть) docstring-упоминание, нет кода.

> Коммита нет (файл gitignored). Сообщить пользователю, что локальная правка settings.py выполнена.

---

## Self-Review (автор плана)

- **Покрытие спеки:** streams-миграция → Task 1; main/app/ws_manager/api_routes → Task 2; active_state.py → Task 3; frontend → Task 4; settings.GlobalValues → Task 5. Тест нового поведения → Task 1. ✔
- **Поправка к спеке:** спека предполагала удаление разметки панели из index.html — её там нет; план это фиксирует (frontend = удаление мёртвого JS/CSS). Функция называется `setActiveStrategy` (не `applySetStrategy`).
- **Порядок безопасности:** ссылки удаляются до определений: Task 1-2 убирают импортёров `active_state` → Task 3 удаляет файл; Task 1-4 убирают код-ссылки на `GlobalValues` → Task 5 удаляет класс последним. Каждый промежуточный шаг оставляет `import main` рабочим и набор зелёным.
- **Плейсхолдеры:** конкретные блоки кода и команды приведены; номера строк помечены «≈», т.к. сдвигаются при правках — исполнитель удаляет по совпадению текста/имён.
- **Верификация фронтенда:** автотестов нет; ручная проверка страницы (app + MT5) — за пользователем (отмечено в спеке).
