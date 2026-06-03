# Характеризационные тесты мат-логики объёма/маржи `trading.py` — дизайн

**Дата:** 2026-06-03
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** E1b (трек «тесты пути исполнения ордеров», backlog #2; после E1 — ордера, E2 — `execution_agent`. Дальше: E3 — `position_monitor` (включая SL/excursion-математику), E4 — signal/market_data).

---

## Цель и контекст

[trading.py](../../../trading.py) содержит арифметику расчёта объёма сделки по
риску и марже. Этот объём напрямую определяет размер реальной позиции (денежный
риск), но **не покрыт тестами**. E2 мокал `calculateSafeTradeWithMargin` через
`FakeTrading`; E1b запирает её фактическую математику и зависимые методы.

**Двойная цель:**
1. **Сетка перед правками** — запереть денежную арифметику расчёта лота.
2. **Документирование поведения** — явно зафиксировать ветвления (конверсия валют,
   retry-цикл, clamp/round объёма, margin-ratio).

**Среда:** тесты без живого MT5 (CI-ready), как вся существующая сетка.

**Граница слайса:** боевой `trading.py` в E1b **не меняется** (решение пользователя,
как в E1/E2). Находки → `xfail` (если известно желаемое поведение) или passing-
характеризация `assert raises` (если код объективно сломан) + запись в
[docs/known-issues.md](../../../docs/known-issues.md); фикс — отдельный слайс.

---

## Ключевые факты, на которых построен дизайн

В отличие от E2 (агент берёт `trading` через конструктор → инъекция `FakeTrading`),
E1b тестирует **реальный класс `Trading`**. Поэтому переиспользуем фикстуру
**`patched_trading`** из E1 ([tests/execution/conftest.py](../../../tests/execution/conftest.py)),
которая монкипатчит модульные глобалы `trading.mt5` / `trading.cache` /
`trading.status` фейками — боевой код не меняется.

Зависимости целевых методов (что нужно дорастить в фейках):
- `cache.get_symbol_info` (есть), `cache.get_account_info` (**нет** — добавить),
  `cache.get_positions` (есть).
- `mt5.symbol_info_tick` (есть), `mt5.order_calc_margin` (**нет**), `mt5.symbol_info`
  (**нет** — для конверсии), константы `ORDER_TYPE_BUY/SELL` (есть).
- `status.active_symbols` (**нет** — добавить).
- `time.sleep` — retry-цикл `calculateMaxVolumeWithMarginCheck` спит на fail-путях;
  нейтрализуем через monkeypatch (no-op) в фикстуре.
- `dict.symbolStopLossValue` — НЕ нужен (мутирует только `calculateStopLoss`, вне E1b).

### Целевые методы (4 ядра)

- **`calculatePipValue`** ([trading.py:225](../../../trading.py#L225)):
  `symbol_info None → 0`; BUY читает `tick.ask`, SELL `tick.bid`;
  `pip = point*trade_contract_size*volume`; если `currency_profit != currency_margin` —
  конверсия: прямой `XXXYYYrfd` (есть → `*= ask`), иначе инверсия `YYYXXXrfd`
  (есть → `/= bid`), иначе без конверсии; exception → `0`.
- **`calculateMaxVolumeWithMarginCheck`** ([trading.py:263](../../../trading.py#L263)):
  retry до 3 раз; `divisor = len(active_symbols) - len(orders)`, `≤0 → 1`;
  `free_margin = margin_free/divisor`; `risk_money = balance*risk%/100`;
  `stop_loss_cost = pip_per_lot*sl_pips`; `volume_by_risk = risk_money/stop_loss_cost`;
  `volume_by_margin = (free_margin/margin_safety)/margin_per_lot`;
  `max = min(оба)`, clamp `volume_max`/`volume_min`, round по `volume_step`;
  `margin_ratio = free_margin/final_margin`; `< safety` → возврат пересчитанного
  `max_volume_safe`; fail-пути (`account_info None`/`balance≤0`/`pip≤0`/`margin None`/
  exception) → retry → `0`.
- **`checkMarginWithStopLoss`** ([trading.py:390](../../../trading.py#L390)):
  `account_info None → (False,0)`; `margin_required None → (False,0)`;
  `total = margin_required + potential_loss`; `ratio = free_margin/total`;
  возврат `(ratio≥safety, ratio)`; exception → `(False,0)`.
- **`calculateSafeTradeWithMargin`** ([trading.py:427](../../../trading.py#L427)):
  `max_volume = calculateMaxVolumeWithMarginCheck(...)`; `≤0 → 0`;
  `margin_ok` → возврат `max_volume`; иначе step-down по `volume_step` до `margin_ok`
  → `safe_volume`; не нашли → `max_volume`.

### Находки (ожидаемые)

- **#double-count** — в `checkMarginWithStopLoss`: `potential_loss =
  pip_value*sl_pips*volume`, где `pip_value = calculatePipValue(symbol, volume, ...)`
  уже умножен на `volume` → `potential_loss` квадратичен по `volume`. Известно
  желаемое (линейное) поведение → **`xfail`** + known-issues.
- **#legacy-no-self** — `setStopLoss(ticket, new_sl, oldSl, orderType)`
  ([trading.py:199](../../../trading.py#L199)) и `calculateStopLossOld(symbol, ...)`
  ([trading.py:188](../../../trading.py#L188)) объявлены **без `self`** → вызов как
  метод сдвигает аргументы (instance попадает в первый параметр); `setStopLoss` ещё и
  дёргает `result.retcode` без None-guard. Код объективно сломан → passing-
  характеризация `assert raises` + known-issues.

---

## Архитектура и структура файлов

```
tests/execution/
├── fakes.py                   # РАСШИРЯЕМ (аддитивно — E1/E2 не ломаются)
├── conftest.py                # patched_trading: +нейтрализация time.sleep
├── test_trading_orders.py     # E1 — НЕ ТРОГАЕМ
├── test_execution_agent.py    # E2 — НЕ ТРОГАЕМ
└── test_trading_margin.py     # НОВЫЙ: ~25–30 характеризационных кейсов
```

### Расширения харнесса (`tests/execution/fakes.py`, переиспользуемо)

- **`FakeMT5`**:
  - `order_calc_margin(order_type, symbol, volume, price)` → настраиваемый результат
    (атрибут, в т.ч. `None`).
  - `symbol_info(symbol)` → настраиваемая мапа `symbol → info|None` (для конверсии).
  - Конверсионные тики: мапа `symbol → tick` (с `.ask/.bid`), `symbol_info_tick`
    отдаёт по символу с fallback на дефолтный `self.tick`.
- **`FakeCache`**:
  - `get_account_info()` → `SimpleNamespace(balance, equity, margin_free)` (настраиваемо;
    `None` для fail-теста).
  - на `symbol_info` добавить `trade_contract_size`, `currency_profit`,
    `currency_margin`, `volume_min`, `volume_max`, `volume_step`.
- **`FakeStatus`**: `active_symbols()` → list (настраиваемо).

### Фикстура (`tests/execution/conftest.py`)

- **`patched_trading`** — расширить: добавить `monkeypatch.setattr(trading_mod.time,
  "sleep", lambda *a, **k: None)`. Остальное (подмена mt5/cache/status) уже есть;
  E1-тесты не затрагиваются (sleep в orderOpen/orderClose/modifySL не вызывается).

### Матрица тестов (`test_trading_margin.py`, ~25–30 кейсов)

- **calculatePipValue (×6):** symbol_info None→0; same-currency (pip=point*contract*vol);
  BUY→ask / SELL→bid; cross прямая (*=ask); cross инверсия (/=bid); оба None→без конверсии;
  exception→0.
- **calculateMaxVolumeWithMarginCheck (×8):** happy (min(risk,margin)); divisor (≤0→1,
  free_margin деление); account_info None→0; balance≤0→0; pip≤0→0; margin None→0;
  margin_ratio<safety→safe-объём; clamp volume_max/min + round volume_step.
- **checkMarginWithStopLoss (×4 + находка):** account_info None→(False,0); margin None→
  (False,0); happy ratio; **double-count xfail**; exception→(False,0).
- **calculateSafeTradeWithMargin (×4):** max_volume≤0→0; margin_ok→max_volume; step-down
  до safe_volume; не нашли→max_volume.
- **legacy (×2):** setStopLoss без self → assert raises + known-issues; calculateStopLossOld
  без self → assert raises + known-issues.

---

## Что НЕ входит в E1b

- `calculateStopLoss` (трейлинг-значение + мутация `dict.symbolStopLossValue`) и
  `calculateMaxMinValue` (экскурсия через `copy_rates_from_pos`) → ближе к мониторингу
  позиции, слайс **E3**.
- `orderOpen`/`orderClose`/`modifySL` → покрыты **E1**.
- `execution_agent` → покрыт **E2**.

---

## Критерии готовности

- `pytest -q` зелёный локально и в CI; ожидаемо `~368–375 passed, ~3–4 xfailed`
  (было 342+2; +~25–30 passed, +1 xfail double-count).
- Харнесс `fakes.py` расширен; `patched_trading` нейтрализует `time.sleep`.
- Боевой `trading.py` не изменён.
- Находки (#double-count + 2× #legacy-no-self) зафиксированы в `docs/known-issues.md`.
