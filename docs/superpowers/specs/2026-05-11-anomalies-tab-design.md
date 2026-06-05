# Спецификация: вкладка «Аномалии»

**Дата:** 2026-05-11
**Ветка:** feature/scalping-strategies (или новая `feature/anomalies-tab`)
**Статус:** утверждён к реализации

## Цель

Добавить в дашборд вкладку «Аномалии», которая в реальном времени показывает инструменты Market Watch MT5 с аномальным поведением на H1 (резкий отрыв цены от EMA50 или экстремум Stochastic). Карточка появляется при возникновении аномалии и исчезает, когда условие снято. Также — история всех зафиксированных аномалий.

## Правила детекции

Сканер раз в `SCAN_INTERVAL_SEC` (300) проходит по всем символам Market Watch MT5. Для каждого символа берёт H1 OHLC, считает индикаторы на последнем **закрытом** баре и проверяет:

- **EMA distance:** `|close - EMA50| >= 4 * ATR14`
  - `close > EMA50` → тип `EMA_FAR_UP`
  - `close < EMA50` → тип `EMA_FAR_DOWN`
- **Stochastic OB/OS:** %K из `STOCH(fastk=3, slowk=3, slowd=5)`
  - `%K > 93` → `STOCH_OB`
  - `%K < 7` → `STOCH_OS`

Один символ может одновременно иметь несколько типов. Карточка показывается, пока активен хотя бы один тип.

### Конфигурация (`settings.ANOMALY`)

```
EMA_PERIOD = 50
ATR_PERIOD = 14
ATR_MULT   = 4.0
STOCH_FASTK = 3
STOCH_SLOWK = 3
STOCH_SLOWD = 5
STOCH_OB = 93
STOCH_OS = 7
TIMEFRAME = mt5.TIMEFRAME_H1
SCAN_INTERVAL_SEC = 300
BARS_TO_FETCH = 200
MISS_TOLERANCE = 2   # сколько подряд пропусков символа до автозакрытия
```

## Архитектура

### Новые файлы

```
agents/anomaly_scanner_agent.py    # оркестратор: MT5 → detector → store → bus
anomaly/__init__.py
anomaly/detector.py                # чистые функции расчёта по DataFrame
anomaly/store.py                   # SQLite репозиторий
anomaly/schemas.py                 # TypedDict/dataclass для API/WS
web/routes_anomalies.py            # FastAPI router /api/anomalies
data/anomalies.db                  # SQLite (создаётся при старте, в .gitignore)
tests/anomaly/test_detector.py
tests/anomaly/test_store.py
```

### Изменения в существующих файлах

- `core/events.py` — добавить `ANOMALY_OPENED`, `ANOMALY_UPDATED`, `ANOMALY_CLOSED`.
- `main.py` — инстанцировать `AnomalyScannerAgent`, подключить `routes_anomalies.router`.
- `web/ws_manager.py` — пробросить новые типы событий клиентам (если фильтрация по EventType — добавить в whitelist).
- `web/static/index.html` — таб «Аномалии» + секция-контейнер.
- `web/static/app.js` — рендер активных карточек, таблица истории, WS-хендлеры.
- `web/static/style.css` (или `style-bybit.css`) — стили карточек, цветовые акценты.
- `settings.py` — блок `ANOMALY`.

### Поток данных

```
Timer 5 мин ─► AnomalyScannerAgent.scan()
              │
              ├─ MT5 symbols_get() (Market Watch only)
              ├─ для каждого symbol:
              │    copy_rates_from_pos(H1, 200) → DataFrame
              │    detector.evaluate(df) → list[AnomalyType] + snapshot
              ├─ diff против active[symbol]:
              │    новое       → store.open() + emit ANOMALY_OPENED
              │    осталось    → store.update_extremes() + emit ANOMALY_UPDATED (если значения изменились)
              │    исчезло     → store.close() + emit ANOMALY_CLOSED
              └─ EventBus ─► ws_manager ─► фронт

Фронт:
  init: GET /api/anomalies/active  + GET /api/anomalies/history?limit=100
  WS:  обновления карточек и истории в реальном времени
  Фильтры истории: symbol, type, период → GET /api/anomalies/history?...
```

## Границы модулей

- **`anomaly/detector.py`** — не знает про MT5, БД, EventBus.
  - Вход: `pd.DataFrame` с колонками `open/high/low/close/time` (≥ 60 баров).
  - Выход: `DetectResult { types: list[str], snapshot: {price, ema50, atr, dist_atr, stoch_k, stoch_d, bar_time} }`.
  - Полностью покрывается юнитами на синтетических данных.
- **`anomaly/store.py`** — не знает про EventBus, MT5.
  - Чистый CRUD над SQLite: `open()`, `update()`, `close()`, `recover_active()`, `list_history(filters)`.
  - Принимает путь к БД параметром (для тестов на `:memory:`).
- **`AnomalyScannerAgent`** — оркеструет всё. Не считает индикаторы сам.

## Схема SQLite

`data/anomalies.db`:

```sql
CREATE TABLE IF NOT EXISTS anomalies (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol       TEXT    NOT NULL,
  types        TEXT    NOT NULL,           -- CSV: "EMA_FAR_UP,STOCH_OB"
  opened_at    TEXT    NOT NULL,           -- ISO-8601 UTC
  closed_at    TEXT,                       -- NULL пока активна
  duration_sec INTEGER,                    -- заполняется при close()
  open_price   REAL,
  open_ema50   REAL,
  open_atr     REAL,
  open_dist_atr REAL,
  open_stoch_k REAL,
  open_stoch_d REAL,
  close_price  REAL,
  close_ema50  REAL,
  close_atr    REAL,
  close_dist_atr REAL,
  close_stoch_k REAL,
  close_stoch_d REAL,
  max_abs_dist_atr REAL,
  peak_stoch_k     REAL
);
CREATE INDEX IF NOT EXISTS idx_anomalies_symbol_opened ON anomalies(symbol, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_active ON anomalies(closed_at) WHERE closed_at IS NULL;
```

Один символ может иметь только одну активную запись (`closed_at IS NULL`). При повторном обнаружении тех же типов — обновляем `types`, `max_abs_dist_atr`, `peak_stoch_k`. Новой строки не создаём.

## REST API (`web/routes_anomalies.py`)

Префикс `/api/anomalies`.

| Метод | Путь        | Параметры                                        | Ответ                                |
|-------|-------------|--------------------------------------------------|--------------------------------------|
| GET   | `/active`   | —                                                | `[ActiveAnomaly]` из памяти агента   |
| GET   | `/history`  | `limit=100, symbol?, from?, to?, type?`          | `{items: [HistoryAnomaly], total}`   |
| POST  | `/scan`     | —                                                | `{ok: true, scanned: N}` (ручной запуск, debug) |

### Схемы

```jsonc
// ActiveAnomaly / WS payload
{
  "symbol": "EURUSDrfd",
  "types": ["EMA_FAR_UP", "STOCH_OB"],
  "opened_at": "2026-05-11T09:00:00Z",
  "price": 1.0832,
  "ema50": 1.0784,
  "atr": 0.0011,
  "dist_atr": 4.36,
  "stoch_k": 95.2,
  "stoch_d": 91.7
}

// HistoryAnomaly — то же + closed_at, duration_sec, close_* поля, max_abs_dist_atr, peak_stoch_k
```

## WebSocket

Поверх существующего WS-канала:

```json
{ "type": "anomaly", "event": "opened", "data": { ...ActiveAnomaly } }
{ "type": "anomaly", "event": "updated", "data": { ...ActiveAnomaly } }
{ "type": "anomaly", "event": "closed",  "data": { "symbol": "...", "closed_at": "...", "duration_sec": 3600 } }
```

`updated` шлётся только если изменились `types` или хотя бы одно значение снапшота (с дельтой > 1% по price/EMA или > 0.1 по dist_atr/stoch), чтобы не спамить.

## UI вкладки «Аномалии»

Новый таб в `index.html` рядом с «Лог событий».

Раскладка:
- **Шапка:** счётчик активных, метка последнего скана, кнопка ручного скана (`POST /scan`).
- **Активные:** сетка карточек.
- **История:** таблица с фильтрами `symbol / type / период (24ч/7д/30д/всё)`, пагинация «Показать ещё» (+100).

Карточка содержит: symbol, стрелка направления (↑/↓ или OB/OS), список типов, текущие значения (price, dist_atr, stoch_k/d), время начала. Цвет:
- зелёный — `EMA_FAR_UP` или `STOCH_OB`
- красный — `EMA_FAR_DOWN` или `STOCH_OS`
- оранжевый — оба направления (редкий случай)

Поведение:
- При открытии вкладки — fetch `/active` + `/history?limit=100`.
- WS `opened` → добавить карточку с fade-in; добавить строку в историю (closed_at пустой).
- WS `updated` → обновить значения in-place (без перерисовки контейнера).
- WS `closed` → fade-out карточку; в истории обновить `closed_at`/`duration`.
- Бейдж в заголовке таба: `Аномалии (N)`, N = число активных. Обновляется по WS.

Без новых JS-зависимостей. Стили — в существующих CSS.

## Жизненный цикл агента

- Старт в `main.py` среди прочих агентов.
- На старте: `store.recover_active()` поднимает в `self.active` строки с `closed_at IS NULL` (восстановление после рестарта).
- Цикл: `await asyncio.sleep(SCAN_INTERVAL_SEC)` → `scan()`.
- `scan()` обёрнут в `try/except` — одна ошибка не валит цикл; `emit_status(ERROR, msg)` + лог.
- Per-symbol ошибки (нет баров, MT5 вернул `None`) — пропускаем символ, не трогаем его `active`-запись. Увеличиваем счётчик `misses[symbol]`; при `misses[symbol] >= MISS_TOLERANCE` — закрываем как `closed`.
- При успехе сканирования символа `misses[symbol]` сбрасывается.
- При закрытии записываем close-снапшот и `duration_sec = closed_at - opened_at`.

### Метрики (status-канал)

`metrics`:
- `scans` — счётчик запусков `scan()`
- `active_count` — текущее число активных
- `opened_total`, `closed_total`
- `last_scan_sec` — длительность последнего скана
- `last_scan_at` — ISO-время

## Тесты

`tests/anomaly/test_detector.py`:
- бар с `(close - ema50) = 5*atr` → `EMA_FAR_UP`
- бар с `(close - ema50) = -5*atr` → `EMA_FAR_DOWN`
- `stoch_k = 95` → `STOCH_OB`; `stoch_k = 5` → `STOCH_OS`
- одновременное срабатывание двух условий → оба тега в списке
- граничные значения: `dist = 4.0 * atr` (включительно), `stoch_k = 93.0` (строго `>`, не срабатывает), `stoch_k = 93.01` (срабатывает) — фиксируем точную семантику тестом
- DataFrame короче 50 баров → пустой список типов, без исключения

`tests/anomaly/test_store.py` (SQLite `:memory:`):
- `open()` создаёт строку с `closed_at=NULL`
- `update()` обновляет `types`, расширяет `max_abs_dist_atr` / `peak_stoch_k`, не меняет open-снапшот
- `close()` заполняет `closed_at`, `duration_sec`, close-снапшот
- `recover_active()` возвращает только незакрытые
- `list_history()` корректно фильтрует по `symbol`, `from`, `to`, `type` (подстрока в CSV), уважает `limit`
- повторный `open()` для уже активного символа — ошибка (защита от дублей)

Интеграционный тест агента — вне MVP (требует мока MT5).

## Что вне MVP

- `/api/anomalies/stats` — добавим, когда понадобится.
- Sparkline на карточках.
- Кнопки действий («Открыть график», «Создать стрим») — потом.
- Push-нотификации (звук/Telegram).
- Настройка порогов через UI — пока только через `settings.py`.
- Интеграционный тест агента с моком MT5.

## Acceptance criteria

1. Запуск бота создаёт `data/anomalies.db`, агент стартует, в логах появляется первый скан.
2. На вкладке «Аномалии» видны карточки тех символов, у которых сработал хотя бы один триггер.
3. После того как условие снято, карточка пропадает в течение одного скан-цикла (≤ 5 мин + сетевой лаг).
4. В таблице истории появляется строка на каждую новую аномалию; при закрытии заполняются `closed_at` и `duration`.
5. Рестарт бота не теряет активные аномалии (recover_active).
6. Ошибка по одному символу не валит сканер: остальные символы обрабатываются, в `events log` виден `WARNING`.
7. Юнит-тесты `tests/anomaly/` зелёные.
