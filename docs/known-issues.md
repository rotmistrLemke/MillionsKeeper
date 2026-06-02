# Известные находки (core reliability, 2026-06-01)

Находки, выявленные при работе над треком «надёжность ядра» (слайсы A–C).
Ни одна не блокирует текущую работу; продакшен-код по ним НЕ менялся —
только зафиксировано. Каждая помечена также в коде/тестах рядом с местом.

---

## 1. fibonacci_retracement: TP для BUY может оказаться за ценой входа

- **Где:** [strategies/fibonacci_retracement.py:116](../strategies/fibonacci_retracement.py#L116) — `get_sl_tp`, ветка BUY: `tp = row['imp_high']`, где `imp_high = high.shift(1).rolling(n).max()` (макс хаёв предыдущих N баров).
- **Что:** на монотонном восходящем тренде `imp_high` всегда ниже текущей цены → TP оказывается «за спиной» цены (`tp < entry`). Поймано контракт-тестом `test_get_sl_tp_ordering_on_valid_row` (помечен `xfail`, слайс A).
- **Нюанс (важно):** дизайн стратегии самосогласован — `get_exit_signal` закрывает BUY при `high >= imp_high`, то есть TP=imp_high совпадает с логикой выхода. На реальных данных вход происходит на откате, где предыдущий swing-high (`imp_high`) выше цены входа → `tp > entry` нормально. Так что на синтетике это артефакт, а не однозначный баг.
- **Статус:** ✅ ЗАКРЫТО (2026-06-01) — артефакт синтетики, не баг. На реальном `tests/fixtures/xauusd_h1.csv` стратегия дала 19 входов, у ВСЕХ TP по правильную сторону (tp_wrong_side=0). На реальных откатах `imp_high`/`imp_low` корректно расположены относительно цены входа. Контракт-тест остаётся `xfail` как пометка, что на монотонной синтетике (нереалистичный вход) TP закономерно за ценой — это ограничение синтетического кейса, а не дефект стратегии.

## 2. ema_triple_touch: параметр min_gap_bars не применяется

- **Где:** [strategies/ema_triple_touch.py:113-123](../strategies/ema_triple_touch.py#L113) — `_update_state`.
- **Что:** комментарий обещает «не считать тест повторно, если прошло меньше `min_gap_bars`», но тело условия — `try: pass except: pass`. Параметр `min_gap_bars` хранится, но фактически не enforce-ится: соседние бары могут засчитываться как отдельные «тесты» зоны, что облегчает срабатывание 3-touch входа сильнее, чем задумано.
- **Статус:** ✅ РЕШЕНО (2026-06-01) — реализована re-entry-семантика: тест зоны засчитывается один раз за «провал» (флаг `_counted_dip`), сбрасывается при закрытии цены ВНЕ зоны. Параметр `min_gap_bars` и мёртвый `try/except` удалены, docstring актуализирован. Покрыто юнит-тестом `tests/strategies/test_ema_triple_touch_gap.py`. На реальном фикстуре убрался 1 ложный вход (было 1 → стало 0), golden перегенерирован.

## 3. backtest_engine: дублирование каркаса двух движков

- **Где:** [backtest_engine/engine.py](../backtest_engine/engine.py) — `_run_default_on_df` и `_run_strategy_on_df`.
- **Что:** оба движка дублируют общий каркас: weekend-фильтр, dd-block (`_next_monday`/`_update_dd_block` как замыкания в каждом), расчёт pnl, ведение equity-кривой, закрытие в конце данных.
- **Статус:** ⚠️ ЧАСТИЧНО (2026-06-01, слайс D2). Вынесены ИДЕНТИЧНЫЕ чистые хелперы в `backtest_engine/_scaffolding.py`: `next_monday()` и `is_weekend_block()` (оба движка теперь их используют). Полное слияние циклов НЕ делалось намеренно: golden default-движка все с 0 сделок (на синтетике он молчит) → его поведение слабо зафиксировано, и слияние было бы рискованным. Stateful `_update_dd_block` остался замыканием в каждом движке.
- **Остаток (опционально):** свести сами циклы к общему каркасу — только после усиления характеризации default-движка (сценарий, где он реально торгует), иначе слияние не защищено тестами.

## 4. orderOpen: AttributeError при order_send → None (денежный путь)

- **Где:** [trading.py:61-70](../trading.py#L61) — `orderOpen`, финальный `return`.
- **Что:** при `mt5.order_send(...) → None` (реальный отказ брокера) или когда `type` не LONG/SHORT, `result` остаётся `None`; код печатает `mt5.last_error()`, но затем безусловно исполняет `return {"order": result.order, ...}` → `AttributeError: 'NoneType' object has no attribute 'order'`. Обработчик падает вместо мягкой деградации на денежном пути.
- **Желаемое:** при отсутствии результата возвращать graceful-значение (например `{"order": None, ...}` или `None`), не кидая исключение.
- **Статус:** ⚠️ ОТКРЫТА (2026-06-02, слайс E1). Зафиксирована xfail-тестом `tests/execution/test_trading_orders.py::TestOrderOpenFindings::test_order_send_none_should_not_crash` (`raises=AttributeError, strict=True`). Прод НЕ правился (E1 только характеризует); фикс — отдельным слайсом.

---

## Связанные документы

- `docs/superpowers/specs/2026-05-31-strategy-test-harness-design.md` — слайс A
- `docs/superpowers/specs/2026-06-01-backtest-decomposition-design.md` — слайс C
- Тесты-маркеры: `tests/strategies/test_contract.py` (fibonacci xfail), `tests/strategies/test_behavioral.py` (ema_triple_touch FINDING-комментарий).
