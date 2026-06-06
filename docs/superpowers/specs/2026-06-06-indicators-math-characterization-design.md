# Характеризация математики `indicators.py` — Design

**Дата:** 2026-06-06
**Статус:** утверждён (brainstorming)
**Трек:** надёжность ядра / тест-сетка (продолжение E5; не денежный путь напрямую, но питает indicator→signal).

## Цель

Запереть текущее поведение всех 9 классов `indicators.py` характеризационной сеткой:
числовые ядра, логику торговых сигналов, геометрию углов и тонкие обёртки над
`cache.get_rates`. Прод **не трогаем** — тесты пишутся под уже существующее поведение.

В E4/E5 классы `indicators.*` фейкались целиком; этот слайс покрывает их собственную
математику — последнее белое пятно потока агентов.

## Не-цели

- Не рефакторим и не чиним прод (включая видимые латентные баги — фиксируем как находки).
- Не вводим golden-файловую инфраструктуру (решение: pinned-литералы в тестах).
- Не покрываем интеграцию indicators↔agent (уже покрыто E5).

## Архитектура и харнесс

Новый каталог `tests/indicators/`:

- **`conftest.py`** — фикстура `indicators_cache(monkeypatch)`: монкипатчит **`indicators.cache`**
  на `FakeCache` из `tests.execution.fakes` и возвращает фейк для настройки `point`/`rates_df`.
  ⚠️ Патчить именно `indicators.cache`: `indicators.py` делает `from market_data_cache import cache`
  (строка 8), т.е. создаёт собственный модульный binding — патч `market_data_cache.cache` его НЕ
  затронет.
- Классы инстанцируются напрямую (`Alligator()`, `MACD()`, `MovingAverage()`, …) — ни агента,
  ни event loop. Методы синхронные; глобальный `asyncio_mode=auto` синхронным тестам не мешает.
- `talib` — настоящий (как в `tests/strategies/`); `indicators.mt5` — стаб из глобального
  `tests/conftest.py` (sys.modules). Где метод по умолчанию лезет в `ATR().calculate_atr(...)`
  через `mt5.TIMEFRAME_H1` (это `_get_angles`/`checkFlat` при `atr_value=None`), передаём
  `atr_value` явно, чтобы тестировать изолированно.

**Инвариант:** `trading` не импортируется (indicators его не тянет); execution-харнесс не
раздувается — только импорт фейков (`FakeCache`, `make_bars_df`).

## Раскладка тест-файлов (4 файла, ~50–60 кейсов)

### `test_signals.py` — чистая логика решений (без cache)

Таблицы ветвлений, напрямую определяющие сделки:

- `MACD.MACD_signal` — BUY (`hist>0 ∧ hist>prev ∧ hist>signal`) / SELL (зеркало) / NO_SIGNAL;
  граничные (равенства не дают сигнала).
- `MovingAverage.ma_simple_signal` — `len<2` / NaN → NO_SIGNAL-dict; `fast>slow`→BUY, `<`→SELL,
  `==`→NO_SIGNAL; поля strength/current_fast/current_slow.
- `ADX.ADX_signal` — `adx>25 ∧ pdi>ndi`→BUY / `ndi>pdi`→SELL; `adx≤25`→NO_SIGNAL.
- `RSI.RSI_signal` — `50<rsi<70 ∧ rsi>prev>prev2`→BUY; `30<rsi<50 ∧ rsi<prev<prev2`→SELL;
  границы (70/50/30, не-монотонность)→NO_SIGNAL.
- `RSI.rsi_leave_extremum` — `(prev>70 ∧ rsi<68)` или `(prev<30 ∧ rsi>32)`→True, иначе False.

### `test_kernels.py` — числовые ядра (pinned-литералы с реального прогона)

- `Alligator.smma` / `MovingAverage.smma` (идентичны) — NaN при `i<period`; seed `data[i-period:i].mean()`
  при `i==period`; рекурсия `(prev*(p-1)+x)/p` далее. Малый фиксированный вход, ассерты литералами.
- `MovingAverage.sma/ema/wma` — известные формулы на коротком ряду (pinned/`approx`).
- `MovingAverage.calculate_ma` — диспетч SMA/EMA/WMA/SMMA (case-insensitive) + `ValueError` на
  неизвестном типе.
- `ADX.ExponentialMA` — `i==0`→`prev_value`; иначе EMA-шаг `(v[i]-prev)*2/(p+1)+prev`.
- `ADX.ADX` — DI/ADX-цикл на малом фиксированном массиве high/low/close. Покрыть ветки:
  `tmp_pos>tmp_neg` / `tmp_pos<tmp_neg` / `tmp_pos==tmp_neg` (оба→0), `tr==0`→0. Результат
  `(adx, pdi, ndi)` — pinned-литералы.

### `test_geometry.py` — зависят от `point` (FakeCache `point=0.01`)

- `Alligator.angle` — `atan2(y, pairX/2)`, `degrees`, округление `int(f"{:.0f}")`.
  **Находка #8:** `degrees=False` фактически игнорируется (тернарник пинит градусы из-за порядка
  вычислений/формата) — пинним текущее поведение **проходящим** тестом + комментарий.
- `Alligator.CountDecimalPlace` — `abs(Decimal(str(point)).as_tuple().exponent)`.
- `MovingAverage._get_angles` — `len<2`/NaN→None; `atr_value` Series (`.iloc[-1]`) vs scalar;
  деление на `point`; делегирование `Alligator.angle`.
- `MovingAverage.ma_cross_signal` — пересечение `cur_fast>cur_slow ∧ prev_fast<prev_slow`→BUY
  (зеркало→SELL); `angles is None`→no_signal-dict; поле `strength`.
- `MovingAverage.ma_critical_angle` — порог `angle_fast>65`→BUY / `<-65`→SELL / иначе NO_SIGNAL.
- `AdaptiveMovingAverage.checkFlat` — talib.KAMA(10) + порог угла `>4 ∨ <-4`→`value:False`.
  **Находка #9:** строка 101 `if math.degrees else ...` — `math.degrees` это функция (всегда truthy),
  else-ветка мёртвая → всегда градусная ветка. Пинним проходящим тестом + комментарий.

### `test_data_methods.py` — обёртки над `cache.get_rates` (FakeCache rates + None-guards)

- `ATR.calculate_atr` — `TR=max(h-l, |h-pc|, |l-pc|)`, `rolling(14).mean()`; `df is None`→None.
- `MACD.calculate_macd_manual` — порог длины `slow+signal+10`=45; ручной EMA (`alpha=2/(p+1)`);
  `<45` или None→`(None,None,None)`; pinned `(hist, prev_hist, signal)`.
- `RSI.get_rsi_talib` — talib.RSI в колонку `RSI`; `df is None`/исключение→None.
- `MovingAverage.get_ma_for_symbol` — выбор `price_type` (open/high/low/close→close по умолчанию);
  `df is None`→None; исключение→None.
- `BullsBearsPower.get_bulls_bears_power` — `ewm(span=period).mean()`; bulls=`high-ema`,
  bears=`low-ema`; `df is None`/исключение→`(None,None)`.
- `Alligator` композиция: `Df` (cache passthrough), `MainData` (median + smma 13/8/5 + open),
  `ShiftedData` (shift 3/1/-1), `LastData` (округление по CountDecimalPlace, `.iloc[-2]/[-3]`),
  `SupportData` (делегирует angle), `IsNewBar` (`prev None`→(True,t); `≠`→(True,t); `==`→(False,prev)).

## Дисциплина тестов

- **Характеризация, не TDD:** проходят против прод-кода сразу; прод не правим.
- **Pinned-литералы** для числовых ядер: метод на фиксированном входе → наблюдаемый результат
  в ассерт литералом + комментарий, как получен.
- **Находки:**
  - *Квирк, не падение* (#8 `degrees=False`, #9 `if math.degrees`) → **проходящий** тест текущего
    поведения + комментарий, запись в `docs/known-issues.md`. Прод не трогаем.
  - *Реальное падение/расхождение* → `xfail` + known-issues (как E1/E1b).
- **Float:** числовые — `pytest.approx`; целочисленные углы (`int(...)`) — точное сравнение.
- **Регрессия:** полный прогон после каждого файла; финал — весь набор зелёный + новые ~50–60.

## План находок (фиксируем, не чиним)

1. **#8** `Alligator.angle` `degrees=False` игнорируется.
2. **#9** `AdaptiveMovingAverage.checkFlat` строка 101 `if math.degrees` — else-ветка мёртвая.
3. `ADX.ADX` вложенный `else` (строки 401–403, `tmp_pos==tmp_neg`→оба 0) — поведенчески корректно,
   только комментарий, не баг.

Прочие расхождения при написании разбираем по факту (xfail или пиннинг); прод нетронут.

## Файловая структура

- **Create:** `tests/indicators/__init__.py` — пакет (конвенция: `tests/__init__.py` и
  `tests/execution/__init__.py` уже существуют).
- **Create:** `tests/indicators/conftest.py` — фикстура `indicators_cache`.
- **Create:** `tests/indicators/test_signals.py`
- **Create:** `tests/indicators/test_kernels.py`
- **Create:** `tests/indicators/test_geometry.py`
- **Create:** `tests/indicators/test_data_methods.py`
- **Modify (если находки):** `docs/known-issues.md` (#8, #9).
- **Reuse:** `tests/execution/fakes.py` (`FakeCache`, `make_bars_df`) — без изменений.

## Критерии готовности

- Все 9 классов `indicators.py` имеют характеризационное покрытие.
- Полный прогон зелёный: прежние + ~50–60 новых; xfail только для подтверждённых находок.
- Прод `indicators.py` байт-в-байт не изменён.
- Находки (если есть) зафиксированы в `docs/known-issues.md`.
- Память проекта обновлена (список тестов, прогон, статус-слайс).
