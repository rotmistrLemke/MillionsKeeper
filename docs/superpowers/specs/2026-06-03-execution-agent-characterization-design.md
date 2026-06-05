# Характеризационные тесты `ExecutionAgent` — дизайн

**Дата:** 2026-06-03
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** E2 (трек «тесты пути исполнения ордеров», backlog #2; после E1 — `trading.py` ордера. Дальше: E3 — `position_monitor`, E4 — `signal`/`market_data`).

---

## Цель и контекст

[agents/execution_agent.py](../../../agents/execution_agent.py) — агент, который
по событию `SIGNAL_GENERATED` решает, открывать ли позицию (gating по статусу,
ночная блокировка, per-stream DD-блок), считает объём и SL/TP по ATR, открывает
основную и при необходимости хедж-ногу через `trading.py`, эмитит события и ведёт
метрики. По `ORDER_CLOSE_REQUEST` закрывает позицию. Это **слой принятия торговых
решений** над денежным путём `trading.py` (покрыт E1) — и он **не покрыт тестами**.

Слайс E2 запирает текущее поведение `ExecutionAgent` характеризационной сеткой.

**Двойная цель:**
1. **Сетка перед будущими правками** — запереть логику gating / DD / ночи / SL-TP /
   хеджа / эмита событий.
2. **Документирование поведения** — явно зафиксировать ветвления.

**Среда:** тесты проходят без живого MT5 (CI-ready), как и вся существующая сетка.

**Граница слайса:** боевой код `execution_agent.py` в E2 **не меняется**
(решение пользователя, как в E1). Найденные баги оформляются как `xfail` + запись
в [docs/known-issues.md](../../../docs/known-issues.md); их фикс — отдельный слайс.

---

## Ключевые факты, на которых построен дизайн

`ExecutionAgent` берёт зависимости из двух источников:

- **Инъекция через конструктор** (чистые швы): `trading` и `bus`
  ([execution_agent.py:22](../../../agents/execution_agent.py#L22)).
- **Модульные/ленивые глобалы** (подмена через monkeypatch, прод не трогаем):
  - `from trading_status import status` — модульный глобал
    ([execution_agent.py:7](../../../agents/execution_agent.py#L7)).
  - `from datetime import datetime` — модульный глобал; `datetime.now()` зовётся в
    `_is_night_block` и `_check_stream_drawdown`.
  - Ленивые импорты внутри методов: `import streams as streams_mod`
    ([:141](../../../agents/execution_agent.py#L141)),
    `from strategies import STRATEGIES` ([:231](../../../agents/execution_agent.py#L231),
    [:287](../../../agents/execution_agent.py#L287)),
    `from market_data_cache import cache` ([:263](../../../agents/execution_agent.py#L263)),
    `import MetaTrader5 as mt5` ([:57](../../../agents/execution_agent.py#L57),
    [:244](../../../agents/execution_agent.py#L244),
    [:262](../../../agents/execution_agent.py#L262)).

### Стратегия подмены (швы → фейки)

| Зависимость | Источник | Подмена в тесте |
|---|---|---|
| `self.trading` | конструктор | **FakeTrading** (запись `orderOpen`/`orderClose`, настраиваемый результат) |
| `bus` | конструктор | **FakeBus** (как в [tests/anomaly/test_scanner_agent.py](../../../tests/anomaly/test_scanner_agent.py)) |
| `status` | `agents.execution_agent.status` | `monkeypatch.setattr` → **FakeStatus** (из `fakes.py`) |
| `streams.registry` | ленивый import | `monkeypatch.setattr(streams, "registry", FakeRegistry)` |
| `strategies.STRATEGIES` | ленивый import | `monkeypatch.setattr` → dict фейк-стратегий (`wants_hedge`/`uses_trailing_exit`) |
| `market_data_cache.cache` | ленивый import | `monkeypatch.setattr` → **FakeCache** (из `fakes.py`) |
| `MetaTrader5` | ленивый `import ... as mt5` | `monkeypatch.setitem(sys.modules, "MetaTrader5", FakeMT5)` |
| `datetime.now()` | `agents.execution_agent.datetime` | `monkeypatch.setattr(execution_agent, "datetime", FakeDatetime)` — `.now()` → фикс. **реальный** `datetime` |

**Контроль времени:** monkeypatch фейк-класса `datetime`, чьё `now()` возвращает
зафиксированный **реальный** `datetime` (решение пользователя). Так
`timedelta` / `.weekday()` / `.replace()` / `.time()` работают штатно. Без новых
зависимостей, в духе E1-харнесса.

**MT5 для агента vs для trading.py:** в E1 подменялся `trading.mt5` (глобал модуля
trading). В E2 `self.trading` — это **FakeTrading**, поэтому реальный `trading.py`
не участвует. Собственные MT5-вызовы агента (`symbol_info_tick`, `history_deals_get`,
`positions_get`, константы `ORDER_TYPE_*`) идут через ленивый
`import MetaTrader5 as mt5` → подменяем `sys.modules['MetaTrader5']` на `FakeMT5`
(у него уже есть нужные sentinel-константы). Это развязывает E2 от catch-22
импорта trading.py из E1.

**Гранулярность вызова (решение пользователя):** основная масса кейсов — прямые
вызовы `await agent._handle_signal(event)` / `_handle_close(event)` и прямые вызовы
`_open_order` / `_compute_stream_equity` / `_reason_to_tag` / `_check_stream_drawdown`.
Плюс 1–2 теста на диспетчеризацию `_on_signal → _queue → run()`.

**run_in_executor:** `_handle_signal`/`_handle_close` гоняют `_open_order`/`orderClose`
через `run_in_executor(None, ...)`. В тестах исполняется дефолтным пулом потоков;
ленивые импорты внутри читают общий `sys.modules` (monkeypatch виден из потока).
Тайминг детерминирован (`await` ждёт future).

### Поведенческие ветвления (что характеризуем)

- **Gating** (`_handle_signal` [:140](../../../agents/execution_agent.py#L140)):
  `NO_SIGNAL` → IDLE; `status_of != 0` → отброс; поток `None`/`not enabled` → IDLE;
  выбор потока `registry.get(stream_id)` при наличии `stream_id`, иначе `by_symbol`.
- **Ночная блокировка** (`_is_night_block` [:36](../../../agents/execution_agent.py#L36)):
  `t >= 23:50` или `t < 05:00` → блок.
- **DD-блок** (`_check_stream_drawdown` [:79](../../../agents/execution_agent.py#L79)):
  `deposit <= 0` → пропуск; активный `block_until` в будущем → блок; `now >= until` →
  снятие; роллинг недели `> 7 дней` → новый `_monday_start` + сброс peak; `dd > 0.35` →
  блок до `_next_monday`; exception в equity → allowed.
- **equity** (`_compute_stream_equity` [:55](../../../agents/execution_agent.py#L55)):
  `deposit + realized(magic) + unrealized(magic)`; realized = `profit+commission+swap`
  по deal-ам своего magic; unrealized = `profit+swap` по позициям своего magic.
- **_open_order** ([:261](../../../agents/execution_agent.py#L261)): `symbol_info None` →
  None; `fixed_volume > 0` → объём потока; иначе `calculateSafeTradeWithMargin(symbol,
  80/90, sl_pips, type)`; `volume <= 0` → None; SL/TP по `sl_atr`/`tp_atr` × ATR от
  `tick.ask`(BUY)/`tick.bid`(SELL), округление до `digits`; trailing-стратегия → TP=0;
  `atr <= 0` → SL/TP=0.
- **Хедж** (`_strategy_wants_hedge` [:229](../../../agents/execution_agent.py#L229),
  `_open_hedge_order` [:240](../../../agents/execution_agent.py#L240)): при
  `wants_hedge()` открывается противоположная нога (тот же magic, sl=0/tp=0,
  comment `:H`), второй `ORDER_OPENED` с `role="H"`; нога None → лог error без события;
  exception → `ORDER_ERROR` `error="hedge:..."`.
- **Эмит/метрики**: `ORDER_OPENED`/`TRADING_STATUS_CHANGED`/`ORDER_CLOSED`/`ORDER_ERROR`
  payload; `opened_today`/`closed_today`; `status.mark_open` при успехе.
- **_handle_close** ([:342](../../../agents/execution_agent.py#L342)) + `_reason_to_tag`
  ([:326](../../../agents/execution_agent.py#L326)): нормализация reason→tag;
  `orderClose(ticket, symbol, tag)`; `ok` → `ORDER_CLOSED`; exception → `ORDER_ERROR`.

---

## Архитектура и структура файлов

```
tests/execution/
├── fakes.py                  # РАСШИРЯЕМ: +FakeTrading, +FakeRegistry, +history_deals_get,
│                             #            +make_deal/make_stream/make_clock, +profit/swap на позиции
├── conftest.py               # РАСШИРЯЕМ: +фикстура execution_agent_factory
├── test_trading_orders.py    # E1 — НЕ ТРОГАЕМ
└── test_execution_agent.py   # НОВЫЙ: ~30–35 характеризационных кейсов
```

### Расширения харнесса (`tests/execution/fakes.py`, переиспользуемые для E3)

- **`FakeMT5`**: добавить `history_deals_get(date_from, date_to)` → настраиваемый
  список deal-ов (атрибут `self.deals`); `positions_get` уже есть. Константы
  `ORDER_TYPE_BUY/SELL`, `symbol_info_tick` уже есть.
- **`make_position`**: добавить поля `profit`/`swap`/`commission` (для equity).
- **`make_deal(*, magic, profit, commission, swap)`** — новый хелпер deal-а.
- **`make_stream(...)`** — конструктор TradingStream-подобного объекта (реальный
  `streams.TradingStream` или namespace c id/name/strategy/symbol/volume/sl_atr/
  tp_atr/magic/deposit/enabled).
- **`make_clock(fixed_dt)`** — фабрика фейк-класса `datetime` с classmethod `now()`.
- **`FakeTrading`** (новый): `orderOpen(...)`/`orderClose(...)` пишут вызовы в списки,
  возвращают настраиваемый результат (dict `{order, price}` или `None`/`False`);
  настраиваемый `calculateSafeTradeWithMargin(...)`.
- **`FakeRegistry`** (новый): `get(id)` / `by_symbol(symbol)` поверх dict потоков.

### Фикстура (`tests/execution/conftest.py`)

- **`execution_agent_factory`** — подменяет `status`/`streams.registry`/`STRATEGIES`/
  `market_data_cache.cache`/`sys.modules['MetaTrader5']`/`datetime`, конструирует
  `ExecutionAgent("Execution", FakeBus(), FakeTrading())` с заданными потоками,
  стратегиями, временем; возвращает namespace `(agent, bus, trading, mt5, status,
  registry, set_now)`.

### Матрица тестов (`test_execution_agent.py`, ~30–35 кейсов)

- **Gating** (×4): NO_SIGNAL; status_of≠0; поток None/disabled; выбор get vs by_symbol.
- **Ночная блокировка** (×4): в окне (23:55/00:30/04:59) → блок; вне (05:00/12:00) →
  проход; граничные точки `_is_night_block`.
- **DD-блок** (×6): deposit≤0 → пропуск; dd>35% → блок + until=next_monday; dd≤35% →
  allowed + peak; активный until → блок; until истёк → снятие; роллинг недели → сброс;
  exception equity → allowed.
- **_compute_stream_equity** (×4): realized свой/чужой magic; unrealized; пустые →
  deposit; `_monday_start`/`_next_monday` для разных дней.
- **_open_order** (×8): symbol_info None; fixed_volume>0 (без calc); calc-ветка (80/90);
  volume≤0; SL/TP BUY; SL/TP SELL + округление; sl_atr/tp_atr=0; trailing→TP=0; atr≤0.
- **Хедж** (×6): wants_hedge → 2 ноги + role=H + opened_today+=2; нога None → 1 нога +
  лог; exception → ORDER_ERROR hedge; без хеджа → 1 нога; `_open_hedge_order` volume≤0
  → None; `_strategy_wants_hedge` нет/exception → False.
- **Эмит/метрики** (×3): happy BUY (ORDER_OPENED+mark_open+TRADING_STATUS_CHANGED+
  opened_today); _open_order None → нет события/mark_open; exception → ORDER_ERROR.
- **_handle_close / _reason_to_tag** (×4 + параметризация tag): tag-таблица; close
  happy (ORDER_CLOSED + closed_today); orderClose falsy → нет события; exception →
  ORDER_ERROR.
- **Dispatch** (×2): `_on_signal`→queue→`run()`→`_handle_signal`; close-аналог.

---

## Находки (ожидаемые)

- Зоны риска (подтвердятся при написании): передача `float(result["volume"])` в
  хедж-ногу; поведение при `result` без ключа `volume`.
- Любой реально воспроизводимый баг → `xfail`-тест с желаемым поведением + запись
  в [docs/known-issues.md](../../../docs/known-issues.md) (#5). Прод в E2 не правится.

---

## Что НЕ входит в E2

- Мат-логика `trading.calculateSafeTradeWithMargin` и пр. → слайс **E1b** (мокается
  через `FakeTrading`).
- `position_monitor_agent` (трейлинг, exit-сигналы, breakeven) → **E3**.
- `signal_agent` / `market_data_agent` → **E4**.

---

## Критерии готовности

- `pytest -q` зелёный локально и в CI (ожидаемо `~308–313 passed, 2 xfailed`;
  было 276+2, добавляется ~30–35 passed, плюс возможный +1 xfail находки).
- Харнесс `fakes.py` расширен и переиспользуем для E3.
- Боевой `execution_agent.py` не изменён.
- Находки (если есть) зафиксированы в `docs/known-issues.md`.
