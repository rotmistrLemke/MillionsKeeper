# Характеризационные тесты `PositionMonitorAgent` — дизайн

**Дата:** 2026-06-04
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** E3 (трек «тесты пути исполнения ордеров», backlog #2; после E1 — ордера, E1b — мат-логика объёма/маржи, E2 — `execution_agent`. Дальше: E4 — signal/market_data).

---

## Цель и контекст

[agents/position_monitor_agent.py](../../../agents/position_monitor_agent.py) — агент,
который периодически опрашивает открытые позиции, публикует live P&L, переставляет
breakeven/trailing SL и инициирует выход по сигналу стратегии (или legacy-RSI) на
новой свече. Это **слой сопровождения открытой позиции** — последний непокрытый
денежный кусок (вход и расчёт лота закрыты E1/E1b/E2). Агент двигает реальный SL и
шлёт реальные запросы на закрытие, но **не покрыт тестами**.

Слайс E3 запирает поведение `PositionMonitorAgent` характеризационной сеткой.

**Двойная цель:**
1. **Сетка перед правками** — запереть жизненный цикл позиции, трейлинг/breakeven SL,
   exit-сигналы (включая хедж-логику), сброс торгового статуса.
2. **Документирование поведения** — явно зафиксировать ветвления.

**Среда:** тесты без живого MT5 (CI-ready).

**Граница слайса:** боевой `position_monitor_agent.py` в E3 **не меняется** (как
E1/E1b/E2). Находки → `xfail` (если известно желаемое) или passing-характеризация
(если код сломан) + запись в [docs/known-issues.md](../../../docs/known-issues.md).

---

## Ключевые факты, на которых построен дизайн

`PositionMonitorAgent` берёт `trading`/`bus` через конструктор (инъекция фейков) и
остальное — через модульные/ленивые глобалы (подмена monkeypatch, прод не трогаем):

- `from trading_status import status` — модульный глобал (status_of/is_open/mark_allowed).
- Ленивые импорты внутри методов: `import streams`, `from strategies import STRATEGIES`,
  `from strategies.runtime import get_runtime_strategy`, `from market_data_cache import cache`,
  `import MetaTrader5 as mt5`, `import talib`, `from indicators import RSI`.

**Инвариант (урок E1b):** `position_monitor_agent.py` НЕ импортирует `trading` —
тесты тоже НЕ должны импортировать `trading` на уровне модуля (catch-22 import-time
`mt5.ORDER_TYPE_BUY`). Агент чист: `self.trading` — инъектируемый фейк.

### Стратегия подмены (швы → фейки)

| Зависимость | Источник | Подмена в тесте |
|---|---|---|
| `self.trading` | конструктор | **FakeTrading** (`getPositions` → список MT5-подобных позиций; `modifySL(ticket, symbol, sl)` — спай, настраиваемый возврат) |
| `bus` | конструктор | **FakeBus** |
| `status` | `agents.position_monitor_agent.status` | **реальный** `TradingStatusRegistry(seed=...)` через `monkeypatch.setattr` (семантика сброса статуса критична — фейк рискует разойтись) |
| `streams.registry` | ленивый | **FakeRegistry** (`by_magic` + `by_symbol`) |
| `STRATEGIES` | ленивый | monkeypatch → dict с фейк-стратегией |
| `strategies.runtime.get_runtime_strategy` | ленивый | monkeypatch → возвращает фейк-стратегию (get_exit_signal/get_hedge_exit_signal/on_trade_closed/wants_hedge/compute_indicators/compute_flat_indicators) |
| `market_data_cache.cache` | ленивый | **FakeCache** (`get_rates(symbol, tf, bars=)` → pandas df) |
| `MetaTrader5` | ленивый `import ... as mt5` | `monkeypatch.setitem(sys.modules, ...)` → **FakeMT5** (`copy_rates_from_pos`/`symbol_info`/`symbol_info_tick`/`history_deals_get(position=)`) |
| `talib.ATR` | ленивый `import talib` | `monkeypatch.setattr(talib, "ATR", ...)` → известный ATR (детерминизм + независимость от наличия/версии talib в CI) |

### Поведенческие ветвления (что характеризуем)

- **`_get_positions_with_pnl`** ([:238](../../../agents/position_monitor_agent.py#L238)):
  pnl BUY=`(bid-open)/point`, SELL=`(open-ask)/point`; `tick None`→pnl 0.0; маппинг
  полей; stream по `by_magic` (None если не найден); округление.
- **`run`** ([:38](../../../agents/position_monitor_agent.py#L38)): emit `POSITION_UPDATE`;
  `metrics["open_positions"]`; обновление `_prev_positions`; `_apply_trailing_sl` на
  каждой; exit-проверка только для символов из `_pending_exit_symbols`, затем очистка;
  `asyncio.sleep` (замокать).
- **`_on_new_bar`** ([:33](../../../agents/position_monitor_agent.py#L33)): добавляет
  symbol в pending; пустой symbol игнор.
- **`_on_position_disappeared`** ([:77](../../../agents/position_monitor_agent.py#L77)):
  emit `ORDER_CLOSED`; сброс статуса `is_open→mark_allowed` + `TRADING_STATUS_CHANGED`
  **только** если `is_open и not sibling_open`; hedge-sibling (та же magic+symbol, др.
  ticket → статус НЕ сбрасывается); `strategy.on_trade_closed` (исключение не валит).
- **`_classify_close_reason`** ([:213](../../../agents/position_monitor_agent.py#L213)):
  comment→`SL`/`TP`/`SIGNAL`/`MANUAL`; нет deals→`MANUAL`; exception→`MANUAL`.
- **`_apply_trailing_sl`** ([:132](../../../agents/position_monitor_agent.py#L132)):
  stream None→выход; `be<=0 и trail<=0`→выход; `rates None`/`len<15`/`atr<=0`/`tick None`→выход;
  BUY breakeven (`bid-entry>=be*atr`→candidate=entry, `_be_done`, повторно не двигает);
  BUY trailing (`cand=bid-trail*atr`, двигать если `cand>candidate`); SELL зеркально;
  порог `|candidate-cur_sl|<0.1*atr`→не двигаем; иначе `modifySL` (исключение не валит).
- **`_is_hedge_position`** ([:296](../../../agents/position_monitor_agent.py#L296)):
  comment endswith `:H`.
- **`_find_paired_hedge_ticket`** ([:300](../../../agents/position_monitor_agent.py#L300)):
  противоположная нога той же magic+symbol с `:H`; нет→None.
- **`_check_rsi_exit`** ([:272](../../../agents/position_monitor_agent.py#L272)):
  `status_of==3`→выход; stream None→выход; стратегия в STRATEGIES→`_check_strategy_exit`,
  иначе→`_check_legacy_rsi_exit`.
- **`_check_strategy_exit`** ([:314](../../../agents/position_monitor_agent.py#L314)):
  `get_rates None`/`len<50`→ничего; `get_exit_signal False`→ничего; основная True→
  `ORDER_CLOSE_REQUEST` (`strategy:<name>`); `wants_hedge`+парный хедж→второй
  `ORDER_CLOSE_REQUEST` (`:pair_close`); хедж-нога+wants_hedge→`get_hedge_exit_signal`,
  True→закрытие только ноги (`:hedge`); исключение не валит.
- **`_check_legacy_rsi_exit`** ([:374](../../../agents/position_monitor_agent.py#L374)):
  `RSI<45` BUY / `RSI>55` SELL → `RSI_EXIT_TRIGGERED` + `ORDER_CLOSE_REQUEST`; NaN/нет
  данных→ничего; исключение не валит.

---

## Архитектура и структура файлов

```
tests/execution/
├── fakes.py                       # РАСШИРЯЕМ (аддитивно — E1/E1b/E2 не ломаются)
├── conftest.py                    # +фикстура position_monitor_agent_factory
├── test_trading_orders.py         # E1 — НЕ ТРОГАЕМ
├── test_trading_margin.py         # E1b — НЕ ТРОГАЕМ
├── test_execution_agent.py        # E2 — НЕ ТРОГАЕМ
└── test_position_monitor.py       # НОВЫЙ: ~45–55 характеризационных кейсов
```

### Расширения харнесса (`tests/execution/fakes.py`, переиспользуемо)

- **`FakeTrading`**: `+getPositions()` (отдаёт настраиваемый `self.positions_list` —
  MT5-подобные объекты); `+modifySL(ticket, symbol, sl)` (пишет вызовы в `modify_calls`,
  возвращает настраиваемый `_modify_result`, дефолт True).
- **`FakeMT5`**: `+copy_rates_from_pos(symbol, tf, start, count)` → настраиваемый numpy
  structured array (поля high/low/close/open; содержимое неважно — ATR замокан);
  `history_deals_get` дорастить до приёма `position=`; `symbol_info`/`symbol_info_tick`
  уже есть.
- **`FakeCache`**: `+get_rates(symbol, tf, bars=None)` → настраиваемый pandas df.
- **`FakeRegistry`**: `+by_magic(magic)` (E2 имел только get/by_symbol).
- Хелперы: `make_mt5_position(*, ticket, symbol, type, volume, price_open, sl, profit,
  time, magic, comment)` (MT5-подобная позиция для `getPositions`); `make_rates(n=30)`
  (numpy structured array); `make_runtime_strategy(*, exit_signal=False,
  hedge_exit_signal=False, wants_hedge=False)` (фейк рантайм-стратегии).

### Фикстура (`tests/execution/conftest.py`)

- **`position_monitor_agent_factory`** — монкипатчит `position_monitor_agent.status`
  (реальный `TradingStatusRegistry(seed=...)`), `streams.registry` (FakeRegistry),
  `strategies.STRATEGIES`, `strategies.runtime.get_runtime_strategy`,
  `market_data_cache.cache` (FakeCache), `sys.modules['MetaTrader5']` (FakeMT5),
  `talib.ATR`; конструирует `PositionMonitorAgent("PositionMonitor", FakeBus(),
  FakeTrading(), poll_interval=0)`; возвращает namespace `(agent, bus, trading, mt5,
  cache, status, registry, set_atr, ...)`. `asyncio.sleep` нейтрализуется (poll_interval=0
  + при необходимости monkeypatch).

### Матрица тестов (`test_position_monitor.py`, ~45–55 кейсов)

- **Зона A — снапшот/жизненный цикл (×~14):** pnl BUY/SELL/tick-None; маппинг полей;
  stream по magic/None; `run` emit POSITION_UPDATE + metrics + _prev_positions + sleep;
  `_on_new_bar` (symbol/пустой); детект исчезновения → `_on_position_disappeared`;
  ORDER_CLOSED payload; сброс статуса (is_open→allowed + TRADING_STATUS_CHANGED);
  hedge-sibling держит статус; on_trade_closed вызов + исключение не валит;
  `_classify_close_reason` SL/TP/SIGNAL/MANUAL/нет-deals/exception.
- **Зона B — трейлинг/breakeven (×~12):** stream None; be&trail<=0; rates None/len<15;
  atr<=0; tick None; BUY breakeven (+_be_done повтор); BUY trailing; SELL breakeven;
  SELL trailing; порог 0.1*atr; modifySL зван с верным SL; исключение modifySL не валит.
- **Зона C — exit (×~16):** `_is_hedge_position`; `_find_paired_hedge_ticket` (есть/нет);
  `_check_rsi_exit` gating (status==3/stream None/dispatch strategy vs legacy);
  `_check_strategy_exit` (get_rates None/len<50/exit False/основная True→CLOSE_REQUEST/
  wants_hedge+pair→второй CLOSE/хедж-нога→hedge_exit→:hedge/исключение не валит);
  `_check_legacy_rsi_exit` (BUY<45/SELL>55→RSI_EXIT+CLOSE/NaN/нет данных/исключение).
- **Dispatch (×2):** `_on_new_bar`→pending→`run()`→exit только для new-bar символа.

---

## Находки

- Любой реально воспроизводимый баг → `xfail`/passing-характеризация + known-issues;
  прод не правим.
- **Отдельная запись (решение пользователя):** `docs/known-issues.md` #7 —
  `trading.calculateStopLoss` ([trading.py:159](../../../trading.py#L159)) и
  `calculateMaxMinValue` ([trading.py:468](../../../trading.py#L468)) — **мёртвый код**
  (нигде не вызываются; `calculateStopLoss` мутирует `dict.symbolStopLossValue`),
  кандидаты на удаление. Без тестов в E3.

---

## Что НЕ входит в E3

- `trading.calculateStopLoss`/`calculateMaxMinValue` — мёртвый код, только запись в
  known-issues #7 (без тестов).
- `signal_agent` / `market_data_agent` → слайс **E4**.
- Реальная интеграция с MT5/talib (фейки кодируют предположения о контракте).

---

## Критерии готовности

- `pytest -q` зелёный локально и в CI; ожидаемо `~415–423 passed, 3 xfailed`
  (+возможные находки) (было 368+3; +~45–55).
- Харнесс `fakes.py` расширен и переиспользуем.
- Инвариант соблюдён: тесты НЕ импортируют `trading` на уровне модуля (агент чист).
- Боевой `position_monitor_agent.py` не изменён.
- Находки (если есть) + dead-code #7 в `docs/known-issues.md`.
