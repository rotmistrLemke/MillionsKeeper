# Характеризационные тесты пути ордеров `trading.py` — дизайн

**Дата:** 2026-06-02
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** E1 (трек «тесты пути исполнения ордеров», backlog #2; шаг 1 — `trading.py` ордера. Дальше: E1b — мат-логика объёма/маржи, E2 — `execution_agent`, E3 — `position_monitor`).

---

## Цель и контекст

[trading.py](../../../trading.py) — единственное место, где конструируются и
отправляются реальные MT5-ордера (`mt5.order_send`). Открытие/закрытие/модификация
позиций двигают реальные деньги, но **не покрыты тестами вообще** — это главный
непокрытый денежный риск проекта (см. backlog #2 в памяти проекта).

Слайс E1 покрывает характеризационной сеткой три метода класса `Trading`:
`orderOpen`, `orderClose`, `modifySL` — конструкцию `request`-словаря для
`order_send` и обработку результата/retcode.

**Двойная цель:**
1. **Сетка перед будущими правками** — запереть текущее поведение денежного пути.
2. **Документирование поведения** — явно зафиксировать ветвления (условные ключи
   `sl`/`tp`/`magic`, выбор цены bid/ask, усечение comment, граница `trade_stops_level`).

**Среда:** тесты проходят без живого MT5 (CI-ready), как и вся существующая сетка.

**Граница слайса:** боевой код `trading.py` в E1 **не меняется** (решение пользователя).
Найденные баги оформляются как `xfail` + запись в `docs/known-issues.md`; их фикс —
отдельный слайс.

---

## Ключевые факты, на которых построен дизайн

- `trading.py` импортирует зависимости как **модульные глобалы**:
  `import MetaTrader5 as mt5` ([trading.py:1](../../../trading.py#L1)),
  `from market_data_cache import cache` ([trading.py:7](../../../trading.py#L7)),
  `from trading_status import status` ([trading.py:4](../../../trading.py#L4)).
  → подмена через `monkeypatch.setattr(trading, '<name>', fake)` перехватывает вызовы
  без правок прода.
- Вызовы MT5 в трёх целевых методах: `order_send`, `symbol_info_tick`,
  `positions_get`, `last_error`, `symbol_select`, плюс константы
  `TRADE_ACTION_DEAL`/`TRADE_ACTION_SLTP`, `ORDER_TYPE_BUY`/`ORDER_TYPE_SELL`,
  `ORDER_TIME_GTC`, `ORDER_FILLING_FOK`, `TRADE_RETCODE_DONE`.
- `cache.get_symbol_info` → объект с `.visible/.point/.digits/.trade_stops_level`.
- Существующий паттерн тестов агентов ([tests/anomaly/test_scanner_agent.py](../../../tests/anomaly/test_scanner_agent.py)):
  `FakeBus` + инъекция узких семов лямбдами. E1 следует тому же духу (лёгкие фейки,
  без DI-рефактора).
- `tests/conftest.py` уже ставит no-op стаб MT5 в `sys.modules` — он позволяет
  **импортировать** `trading.py`, но недостаточен для ассертов (константы под стабом
  возвращают функции-no-op). Поэтому в E1 нужен полноценный `FakeMT5` с
  различимыми sentinel-константами, подменяющий `trading.mt5` на время теста.

### Поведенческие ветвления (что характеризуем)

- `orderOpen` ([trading.py:14](../../../trading.py#L14)): `price = tick.bid` для обоих
  типов; ключи `sl`/`tp` добавляются только при `> 0`, `magic` — при `int(magic) > 0`;
  `status.mark_open(symbol)` только при `retcode == TRADE_RETCODE_DONE`; `symbol_select`
  при `not symbol_info.visible`. Возврат: `{"order", "price", "symbol", "targetType"}`.
- `orderClose` ([trading.py:72](../../../trading.py#L72)): позиция не найдена → `False`
  без send; `tick is None` → `False`; close-тип противоположен `pos.type`,
  `price = bid` для close-SELL и `ask` для close-BUY; `comment[:31]`; `magic` из позиции;
  `False` при result `None`/retcode≠DONE, иначе `True`.
- `modifySL` ([trading.py:109](../../../trading.py#L109)): позиция/tick/info отсутствуют
  → `False`; граница `trade_stops_level` (BUY: `new_sl >= ref - min_dist`; SELL:
  `new_sl <= ref + min_dist`) → `False` без send; иначе `action=SLTP`, `sl/tp`
  округляются до `digits`, `tp` по умолчанию = `pos.tp` при `new_tp is None`.

---

## Архитектура и структура файлов

```
tests/
└── execution/
    ├── __init__.py
    ├── conftest.py            # FakeMT5 / FakeCache / FakeStatus + фикстура patched_trading
    └── test_trading_orders.py # ~22 характеризационных кейса
```

### Фейки (`tests/execution/conftest.py`)

- **`FakeMT5`** — sentinel-константы; `order_send(request)` записывает копию запроса в
  `self.sent` и возвращает настраиваемый `FakeOrderResult(retcode, order, price)`
  (по умолчанию `retcode=DONE`, `order=12345`, `price=request['price']`); настраиваемые
  `symbol_info_tick` (объект `.bid/.ask/.time`), `positions_get` (по `ticket=`/`symbol=`),
  `last_error`, `symbol_select`. Возможность задать «нет результата» (`order_send → None`).
- **`FakeCache`** — `get_symbol_info(symbol)` → настраиваемый
  `SimpleNamespace(visible, point, digits, trade_stops_level)`; `get_positions`.
- **`FakeStatus`** — спай: `mark_open(symbol)` пишет в список, `status_of` отдаёт значение.
- **`patched_trading`** (фикстура) — через `monkeypatch.setattr` подменяет
  `trading.mt5`/`trading.cache`/`trading.status`, возвращает
  `(Trading(), fake_mt5, fake_status)`.

### Матрица тестов (`test_trading_orders.py`, ~22 кейса)

- **orderOpen:** LONG happy-path (action=DEAL, type=BUY, price=bid, volume, comment=str,
  filling=FOK, time=GTC); SHORT happy-path (type=SELL); `sl`/`tp`/`magic` отсутствуют при 0;
  присутствуют и кастятся при >0; `mark_open` вызван при DONE; `mark_open` НЕ вызван при
  retcode≠DONE; `symbol_select` при `visible=False`.
- **orderClose:** позиция не найдена → False без send; tick None → False; BUY→close SELL,
  price=bid; SELL→close BUY, price=ask; `position`/`magic` из позиции; comment усечён до 31;
  result None → False; retcode≠DONE → False; DONE → True.
- **modifySL:** позиция не найдена → False; граница BUY/SELL → False без send; валидный SL →
  action=SLTP + округление до digits; tp по умолчанию = pos.tp при new_tp=None; new_tp задан →
  использован; retcode≠DONE → False; DONE → True.

---

## Находки (ожидаемые)

- **#orderOpen-none-result:** при `order_send → None` (или `type` не LONG/SHORT) `result`
  остаётся `None`/falsy, после печати `last_error` исполняется
  `return {"order": result.order, ...}` ([trading.py:70](../../../trading.py#L70)) →
  `AttributeError`. Покрывается `xfail`-тестом с желаемым graceful-поведением + запись в
  [docs/known-issues.md](../../../docs/known-issues.md). Прод в E1 не правится.

---

## Что НЕ входит в E1

- Мат-логика объёма/маржи/стопов: `calculateMaxVolumeWithMarginCheck`, `calculatePipValue`,
  `checkMarginWithStopLoss`, `calculateSafeTradeWithMargin`, `calculateStopLoss`,
  `calculateMaxMinValue` → слайс **E1b**.
- `execution_agent` (DD-блок, ночная блокировка, SL/TP по ATR, хедж) → **E2**.
- `position_monitor_agent` (трейлинг, exit-сигналы) → **E3**.
- `signal_agent` / `market_data_agent` → **E4**.

---

## Критерии готовности

- `pytest -q` зелёный локально и в CI (ожидаемо `277 passed, 2 xfailed` — было 255+1,
  добавляется ~22 passed + 1 xfailed находки).
- `FakeMT5`-харнесс переиспользуем для E2/E3.
- Боевой `trading.py` не изменён.
- Находка зафиксирована в `docs/known-issues.md`.
