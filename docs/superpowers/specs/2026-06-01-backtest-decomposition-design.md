# Декомпозиция backtest.py — дизайн (слайс C)

**Дата:** 2026-06-01
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** C — финальный шаг «надёжности ядра» (после A: тест-сетка стратегий, B1: trading_status, B2: удаление GlobalValues).

---

## Цель и контекст

`backtest.py` — монолит ~946 строк: два движка (`run_backtest` для default-стратегии MA+MACD+RSI и `run_strategy_backtest` для модульных стратегий), индикаторы/сигналы default, сайзинг, `BacktestResult`, отчёт, CLI. Файл критичен (на нём пользователь проверяет стратегии перед боевой торговлей), но **не покрыт тестами**, а движки MT5-связаны на входе (`load_rates`, `mt5.symbol_info`) — их нельзя прогнать в CI без живого терминала.

Слайс C: сначала выделить df-инъектируемое ядро (тестируемое без MT5) и **запереть поведение характеризационными golden-тестами**, затем разбить монолит на пакет `backtest_engine/`. Поведение сохраняется 1:1. Оба движка остаются как есть (де-дупликация общего каркаса намеренно отклонена — чтобы не менять поведение default-движка).

**Подход:** характеризация → сплит (а не механический сплит и не агрессивная де-дупликация).

---

## Потребители публичного API (сохранить)

- `agents/backtest_agent.py`: `from backtest import run_backtest, run_strategy_backtest, load_rates`; использует `result.*` свойства и `result.trades`.
- CLI: `python backtest.py [--strategy ...]` (документирован в docstring).

Обе точки входа должны продолжать работать без изменений на стороне потребителей.

---

## Архитектура

### Facade для совместимости
Реализация переезжает в новый пакет `backtest_engine/`. **`backtest.py` остаётся тонким facade**:
```python
from backtest_engine import (
    run_backtest, run_strategy_backtest, load_rates, BacktestResult,
)
from backtest_engine.cli import main

if __name__ == "__main__":
    main()
```
Так сохраняются и `from backtest import ...`, и `python backtest.py`. (Пакет и модуль с одинаковым именем сосуществовать не могут, поэтому пакет назван `backtest_engine`, а `backtest.py` — facade.)

### Тестируемый шов (делается ПЕРВЫМ, внутри текущего backtest.py)
Движки разделяются на «обёртку IO» и «чистое ядро»:
- `run_strategy_backtest(symbol, timeframe, ...)` → `load_rates` + `mt5.symbol_info` → `_run_strategy_on_df(strategy, df, point, symbol_info, ...)`.
- `run_backtest(symbol, timeframe, ...)` → `load_rates` + `mt5.symbol_info` → `_run_default_on_df(df, point, symbol_info, ...)`.

Inner-функции принимают готовый `df` (pandas DataFrame с OHLC+time) и `point` (+ `symbol_info` для сайзинга; при `None`/синтетике сайзинг деградирует к фиксированному объёму, как и сейчас при `deposit=0`). MT5 не вызывается → прогон на `tests/strategies/builders.py` из слайса A.

**Граница inner-функции:** всё, что сейчас в теле движка ПОСЛЕ построения `df`/`point`/`symbol_info`, переезжает в inner. Обёртка делает только: `load_rates`, проверку `len < 100`, `pd.DataFrame`+`to_datetime`, `mt5.symbol_info`/`point`, и вызов inner.

### Целевой пакет
```
backtest_engine/
├── __init__.py          # ре-экспорт: run_backtest, run_strategy_backtest, load_rates, BacktestResult
├── filters.py           # _is_night_bar, _is_daily_or_higher_tf, weekend-block helper, _next_monday, dd-block helper
├── data.py              # load_rates (MT5)
├── default_strategy.py  # calc_ema_series, compute_indicators, get_ma/macd/rsi/combined_signal
├── sizing.py            # get_pip_value, calc_volume (MT5)
├── result.py            # BacktestResult
├── trades.py            # _calc_pnl_points, _make_default_trade, _make_strategy_trade
├── engine.py            # run_backtest + _run_default_on_df; run_strategy_backtest + _run_strategy_on_df
├── report.py            # print_report
└── cli.py               # main()
backtest.py              # facade (ре-экспорт + CLI entry)
```

Каждый модуль — одна ответственность. `engine.py` остаётся самым крупным (оба движка), но без сопутствующих чистых функций.

---

## Характеризационные тесты

`tests/test_backtest_characterization.py` (pytest, без MT5):
- Прогон `_run_default_on_df` и `_run_strategy_on_df` на детерминированных синтетических df из `builders` (`trend_up`, `trend_down`, `flat`) с фиксированными `point` (напр. 0.01) и `spread_points`.
- Для модульного движка — пара стратегий (напр. `ema_cross`, `cci_rsi`), `deposit=0`/`fixed_volume` вариант (без MT5-сайзинга).
- Golden-снимок ключевых полей: по каждой сделке `type`, `entry_price`, `exit_price`, `pnl_points`, `exit_reason`, `bars_held`; плюс сводные `total_pnl_points`, `win_rate`, `max_drawdown_points`, `total_trades`.
- Сериализация/сравнение по образцу `tests/strategies/golden_utils.py`; регенерация через `--update-golden` (опция уже есть в `tests/conftest.py`).
- Снимок создаётся на шаге «после шва, до разбиения» и далее не должен меняться при переносе кода в модули.

**Важно:** характеризация фиксирует ТЕКУЩЕЕ поведение (включая возможные странности) — её задача ловить регрессии переноса, а не судить корректность.

---

## Порядок реализации

1. **Шов** — внутри текущего `backtest.py` выделить `_run_default_on_df` и `_run_strategy_on_df`; `run_backtest`/`run_strategy_backtest` становятся обёртками. Поведение 1:1. Прогон существующего набора.
2. **Характеризация** — golden-тесты на inner-функции; сгенерировать baseline, закоммитить.
3. **Пакет** — создать `backtest_engine/`, переносить блоки по одному в порядке зависимостей: `filters` → `default_strategy` → `result` → `trades` → `sizing` → `data` → `engine` → `report` → `cli`. После каждого переноса: прогон характеризации + существующего набора + проверка `from backtest import ...`.
4. **Facade** — заменить тело `backtest.py` на ре-экспорт + CLI entry; финальная проверка.

---

## Тестирование и верификация

- **Характеризационные** golden-тесты (ядро обоих движков) — главный страховочный механизм.
- (Опционально) юнит-тесты на чистые `filters` (`_is_night_bar`, weekend-block) и метрики `BacktestResult` (win_rate, profit_factor с PF=9999/0 краем, max_drawdown_*).
- Существующий набор остаётся зелёным.
- Smoke: `python -c "from backtest import run_backtest, run_strategy_backtest, load_rates, BacktestResult; print('ok')"` и `python backtest.py --help` (CLI парсер строится без MT5; реальный прогон CLI требует MT5 — за пользователем).
- Оба inner-движка прогоняются на синтетике без MT5.

---

## Риски

- **Случайное изменение поведения при переносе** — главный риск. Митигируется: характеризация ДО разбиения + перенос мелкими шагами с прогоном после каждого.
- **Дублирование каркаса** двух движков (weekend/dd_block/pnl/equity) остаётся — намеренно (де-дуп отклонён), чтобы не трогать поведение default-движка. Помечается как кандидат на будущий шаг.
- **CLI** реально прогоняется только с MT5 — ручная проверка за пользователем; автоматически проверяем лишь импорт и `--help`.

---

## Связанные документы

- `docs/superpowers/specs/2026-05-31-strategy-test-harness-design.md` — слайс A (builders, golden_utils, переиспользуются здесь)
- [agents/backtest_agent.py](../../../agents/backtest_agent.py) — основной потребитель публичного API
