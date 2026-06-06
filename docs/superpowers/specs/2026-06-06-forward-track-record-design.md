# Forward Track-Record + Performance Stats — Design

**Дата:** 2026-06-06
**Статус:** утверждён (brainstorming)
**Трек:** валидация монетизации — kill-criterion #1 (forward-edge). См. `docs/business/2026-06-06-unit-economics-honest.md`.

## Цель

Дать **внутренний go/no-go** по живой торговле: персистить авторитетные сделки брокера в durable time-series, считать live-метрики (equity, drawdown, profit factor, win-rate, Sharpe и пр.) **по счёту и по каждой стратегии**, и оценивать против настраиваемых порогов. Это инструмент решения «зарабатывает ли бот вживую», а не публичная витрина.

## Не-цели (отдельные слайсы)

- MyFXBook/FXBlue третье-сторонняя верификация и публичный виджет на лендинге.
- Reliability-хардening бота под многомесячный unattended-прогон.
- UI-графики equity (пока только JSON-эндпоинт).
- PostgreSQL (сознательно отложен до прохождения валидации).

## Архитектура

Новый пакет `performance/` с чистыми границами:

```
performance/
├── __init__.py
├── store.py        # SQLite-персистинг (deals + equity_snapshots), дедуп
├── metrics.py      # ЧИСТЫЕ функции: сделки → метрики (+ группировка per-strategy)
└── evaluator.py    # ЧИСТАЯ оценка go/no-go: метрики + пороги → вердикт
```

Зависимости юнитов:
- `store` ← сделки MT5 (приходят из `HistoryAgent`), наружу отдаёт списки/числа.
- `metrics`, `evaluator` — **чистые**, не знают про MT5/SQLite (вход: списки трейдов / числа) → максимально тестируемы, в духе `backtest_engine`.

### `store.py` (SQLite, файл `performance.db` — gitignored)

Две таблицы:
- `deals(ticket INTEGER PRIMARY KEY, time INTEGER, magic INTEGER, symbol TEXT, type INTEGER, entry INTEGER, volume REAL, price REAL, profit REAL, commission REAL, swap REAL)`
- `equity_snapshots(ts INTEGER, balance REAL, equity REAL)`

API:
- `upsert_deals(deals: Iterable[dict]) -> int` — `INSERT OR IGNORE` по `ticket` (сделки перечитываются каждый poll → дедуп обязателен); возвращает число новых строк.
- `record_equity(balance: float, equity: float, ts: int|None=None) -> None`
- `closed_trades(since: int|None=None) -> list[dict]` — закрывающие сделки (realized P&L), отсортированы по `time`.
- `equity_series() -> list[tuple[int, float]]` — (ts, equity) по возрастанию.
- Схема создаётся идемпотентно (`CREATE TABLE IF NOT EXISTS`). Путь к БД — параметр (по умолчанию рядом с модулем), чтобы тесты подставляли tmp/`:memory:`.

**Закрытая сделка:** в MT5 realized P&L на закрывающем deal — фильтр `d.entry == 1 and d.type in (0, 1)` (ровно как `HistoryAgent._load_history`, реюз семантики). Поля `magic`, `commission`, `swap` есть у deal-объекта, но `HistoryAgent` их сейчас НЕ читает — добавляем в извлечение для store. ⚠️ Известное упрощение: `commission` в MT5 нередко разнесена по in/out-сделкам; для go/no-go суммируем по закрывающим сделкам (net_pnl — близкая аппроксимация, не бухгалтерия).

### `metrics.py` (чистые функции)

Вход: `list[Trade]` (dict с полями `time, magic, profit, commission, swap, ...`). Выход — dict метрик:

- `net_pnl` = Σ(profit + commission + swap)
- `trades` = число закрытых сделок
- `wins`/`losses`, `win_rate` = wins/trades
- `gross_profit` = Σ положительных нетто, `gross_loss` = Σ|отрицательных нетто|
- `profit_factor` = gross_profit / gross_loss; если gross_loss == 0 → `float('inf')` при gross_profit>0, иначе 0.0
- `avg_win`, `avg_loss`, `expectancy` = win_rate·avg_win − (1−win_rate)·|avg_loss|
- equity-кривая = кумулятив нетто-P&L по времени; `max_drawdown_money`, `max_drawdown_pct` (от текущего пика; pct = dd_money / peak, peak>0)
- `longest_loss_streak`
- `sharpe` — упрощённый per-trade: mean(нетто)/std(нетто)·√trades (информационно; при std==0 или trades<2 → None)
- `period_days` = (last_time − first_time)/86400; при 0–1 сделке → 0

Функция `per_strategy(trades, magic_to_strategy) -> dict[str, metrics]` — группирует по `magic`→strategy (через переданную карту) и применяет тот же `compute(...)`. Неизвестный magic → ключ `"unmapped"`.

### `evaluator.py` (чистая оценка)

```python
@dataclass(frozen=True)
class Thresholds:
    min_period_days: int = 90
    min_trades: int = 50
    min_trades_per_strategy: int = 20
    require_net_pnl_positive: bool = True
    max_drawdown_pct: float = 25.0
    min_profit_factor: float = 1.3
```

`evaluate(metrics, thresholds, *, is_strategy=False) -> Verdict`:
- если `trades < min_trades` (или `min_trades_per_strategy` при is_strategy) ИЛИ `period_days < min_period_days` → `INSUFFICIENT_DATA` (+ чего не хватает).
- иначе собрать провалы: `net_pnl ≤ 0` / `max_drawdown_pct > порога` / `profit_factor < порога`. Пусто → `PASS`, иначе `FAIL` + список причин.

`Verdict` = `{status: "PASS"|"FAIL"|"INSUFFICIENT_DATA", reasons: list[str], metrics: dict}`.

Дефолты — **Moderate** (выбор основателя): 90 дней / 50 сделок (per-strategy 20) / net>0 / DD≤25% / PF≥1.3. Пороги настраиваемы (не хардкод в логике).

### Интеграция

- **`HistoryAgent`** (опрашивает `mt5.history_deals_get` каждые ~300с) дополняется: после сбора сделок → `store.upsert_deals(...)` + `store.record_equity(balance, equity)` (equity из account info, уже доступен). **Денежный путь не трогаем — только запись в store.**
- **Атрибуция стратегии:** `deal.magic` → `streams.registry.by_magic(magic)` → `stream.strategy`. Карта строится из текущего реестра потоков. (Историческое: если поток удалён, magic может не резолвиться → `"unmapped"`.)
- **Эндпоинт `web/api_routes`:** `GET /performance` → `{account: {...metrics, verdict}, by_strategy: {name: {...metrics, verdict}}, generated_at}`. Только чтение из store + чистый расчёт. UI — вне охвата.

## Обработка ошибок / краевые случаи

- Пустой store (нет сделок) → метрики с нулями, вердикт `INSUFFICIENT_DATA`.
- `profit_factor` без убытков → `inf` (evaluator трактует `inf ≥ min` как проход).
- Дроп MT5 / `history_deals_get` → None: `HistoryAgent` уже логирует и пропускает; store не вызывается (нет данных), что безопасно.
- SQLite-запись изолирована try/except с логом — сбой персистинга не должен ронять `HistoryAgent` (мониторинг важнее статистики).

## Тестирование

- **`metrics.py`/`evaluator.py` — характеризационные юнит-тесты** на фикстурных наборах сделок: пинованные метрики; edge — нет сделок / все выигрыши (PF=inf) / все убытки / одна сделка / drawdown по кумулятиву / longest_loss_streak. Вердикты: INSUFFICIENT_DATA при малом N/периоде; PASS/FAIL на граничных порогах (DD=25.0, PF=1.3 и т.п.).
- **`store.py` — тесты на tmp/`:memory:` SQLite:** дедуп `upsert_deals` (один ticket дважды → одна строка, возврат счётчика новых), `closed_trades` (фильтр/сортировка), `record_equity`/`equity_series`.
- **Интеграция HistoryAgent→store** — лёгкий тест: на poll агент зовёт `upsert_deals`/`record_equity` (MT5 мокается существующим стаб-паттерном `tests/conftest.py`). Без живого MT5.
- Все тесты — без живого терминала.

## Файловая структура

- **Create:** `performance/__init__.py`, `performance/store.py`, `performance/metrics.py`, `performance/evaluator.py`.
- **Create:** `tests/performance/__init__.py`, `tests/performance/test_metrics.py`, `tests/performance/test_evaluator.py`, `tests/performance/test_store.py` (+ при необходимости интеграционный).
- **Modify:** `agents/history_agent.py` (добавить запись в store — аддитивно), `web/api_routes.py` (эндпоинт `/performance`).
- **Modify:** `.gitignore` (`performance.db`).
- **Reuse:** семантику классификации deal из `HistoryAgent`; `streams.registry.by_magic`.

## Критерии готовности

- Пакет `performance/` реализован; metrics/evaluator — чистые и покрыты юнит-тестами; store — на tmp SQLite.
- `HistoryAgent` пишет сделки+equity в store (аддитивно, деньги-путь не изменён).
- `GET /performance` отдаёт метрики+вердикт по счёту и per-strategy.
- Полный прогон зелёный (прежние 550 + новые).
- Дефолтные пороги = Moderate, настраиваемы.

## Связанные документы

- `docs/business/2026-06-06-unit-economics-honest.md` — почему forward-edge это kill-criterion #1.
- `agents/history_agent.py` — источник сделок (реюз семантики deal).
- `streams.py` — `registry.by_magic` для атрибуции стратегии.
