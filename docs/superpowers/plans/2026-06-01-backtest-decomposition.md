# Декомпозиция backtest.py — план реализации (слайс C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Выделить df-инъектируемое ядро обоих движков backtest.py (тестируемое без MT5), запереть его golden-характеризацией, затем разнести монолит в пакет `backtest_engine/` с тонким facade `backtest.py`. Поведение 1:1.

**Architecture:** Сначала рефакторинг-шов внутри текущего backtest.py (inner-функции `_run_default_on_df`/`_run_strategy_on_df` + обёртки-IO). Затем характеризационные тесты на синтетике из `tests/strategies/builders.py`. Затем перенос кода в пакет: сначала листовые модули, потом движки+отчёт+CLI, в конце backtest.py → facade. Публичный API (`from backtest import run_backtest, run_strategy_backtest, load_rates, BacktestResult`) и CLI (`python backtest.py`) сохраняются.

**Tech Stack:** Python 3.11, pytest, pandas, numpy, TA-Lib.

**Спека:** [docs/superpowers/specs/2026-06-01-backtest-decomposition-design.md](../specs/2026-06-01-backtest-decomposition-design.md)

---

## Структура файлов (целевая)

| Файл | Действие | Ответственность |
|------|----------|-----------------|
| `backtest_engine/__init__.py` | Создать | ре-экспорт публичного API + inner-функций (для тестов) |
| `backtest_engine/filters.py` | Создать | `_is_night_bar`, `_is_daily_or_higher_tf` |
| `backtest_engine/default_strategy.py` | Создать | `calc_ema_series`, `compute_indicators`, `get_ma/macd/rsi/combined_signal` |
| `backtest_engine/result.py` | Создать | `BacktestResult` |
| `backtest_engine/trades.py` | Создать | `_calc_pnl_points`, `_make_default_trade`, `_make_strategy_trade` |
| `backtest_engine/sizing.py` | Создать | `get_pip_value`, `calc_volume` (MT5) |
| `backtest_engine/data.py` | Создать | `load_rates` (MT5) |
| `backtest_engine/engine.py` | Создать | `run_backtest`/`_run_default_on_df`, `run_strategy_backtest`/`_run_strategy_on_df` |
| `backtest_engine/report.py` | Создать | `print_report` |
| `backtest_engine/cli.py` | Создать | `main()` |
| `backtest.py` | Изменить | сначала шов (Task 1), в конце → facade (Task 4) |
| `tests/test_backtest_characterization.py` | Создать | golden-снимок ядра обоих движков |
| `tests/golden/bt_*.json` | Создать (генерация) | baseline характеризации |

---

## Task 1: Шов — выделить df-инъектируемые inner-функции

**Files:**
- Modify: `backtest.py`
- Test: `tests/test_backtest_seam.py`

> Цель: вынести всё тело движка ПОСЛЕ построения `df`/`point`/`symbol_info` в inner-функцию, принимающую готовый `df`, `point`, `symbol_info` и `skip_weekend_filter: bool`. Обёртки (`run_backtest`/`run_strategy_backtest`) делают только IO (load_rates, len-check, DataFrame, symbol_info/point, вычисление `skip_weekend_filter`) и зовут inner. Логика цикла переносится ДОСЛОВНО.

- [ ] **Step 1: Написать smoke-тест (red)**

`tests/test_backtest_seam.py`:
```python
"""C/Task1: inner-функции движка прогоняются на синтетике без MT5."""
from backtest import _run_default_on_df, _run_strategy_on_df, BacktestResult
from strategies.ema_cross import EmaCrossStrategy
from tests.strategies import builders


def test_default_inner_runs_without_mt5():
    df = builders.trend_up(300)
    res = _run_default_on_df(
        df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0,
    )
    assert isinstance(res, BacktestResult)
    assert isinstance(res.trades, list)


def test_strategy_inner_runs_without_mt5():
    df = builders.trend_up(300)
    res = _run_strategy_on_df(
        EmaCrossStrategy(), df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0,
        sl_atr_mult=0.0, tp_atr_mult=0.0, breakeven_atr_mult=0.0, trail_atr_mult=0.0,
    )
    assert isinstance(res, BacktestResult)
    assert isinstance(res.trades, list)
```

- [ ] **Step 2: Запустить — упадёт (inner не существует)**

Run: `python -m pytest tests/test_backtest_seam.py -q`
Expected: FAIL/ImportError (`_run_default_on_df` не определён).

- [ ] **Step 3: Извлечь `_run_default_on_df` из `run_backtest`**

В `backtest.py` переписать `run_backtest` так, чтобы IO остался в обёртке, а тело цикла — в inner. Обёртка (заменяет текущие строки ~293-303 и далее):
```python
def run_backtest(symbol, timeframe, bars=2000, spread_points=0, deposit=0.0,
                 risk_pct=80, fixed_volume=0.0, date_from=None, date_to=None):
    rates = load_rates(symbol, timeframe, bars, date_from, date_to)
    if rates is None or len(rates) < 100:
        print(f"Недостаточно данных для бэктеста {symbol}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    symbol_info = mt5.symbol_info(symbol)
    point       = symbol_info.point if symbol_info else 0.0001
    return _run_default_on_df(
        df, point=point, symbol_info=symbol_info,
        skip_weekend_filter=_is_daily_or_higher_tf(timeframe),
        spread_points=spread_points, deposit=deposit,
        risk_pct=risk_pct, fixed_volume=fixed_volume,
    )


def _run_default_on_df(df, *, point, symbol_info, skip_weekend_filter,
                       spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0):
    df = compute_indicators(df)
    pip_value_per_lot = 1
    # ── далее ДОСЛОВНО переносится текущее тело run_backtest начиная со строки
    #    `result = BacktestResult(initial_deposit=deposit)` и до `return result`,
    #    БЕЗ изменений логики. Удаляются только уже сделанные в обёртке строки
    #    (load_rates, len-check, skip_weekend_filter=..., df=DataFrame,
    #    to_datetime, symbol_info=..., point=..., compute_indicators — последняя
    #    перенесена в начало inner выше). ──
    ...
```
Перенести тело без правок логики. `skip_weekend_filter` теперь параметр (раньше — локальная переменная из `_is_daily_or_higher_tf`). `point`, `symbol_info`, `deposit`, `risk_pct`, `fixed_volume`, `spread_points` — параметры.

- [ ] **Step 4: Извлечь `_run_strategy_on_df` из `run_strategy_backtest`**

Аналогично. Обёртка:
```python
def run_strategy_backtest(strategy, symbol, timeframe, bars=2000, spread_points=0,
                          deposit=0.0, risk_pct=80, fixed_volume=0.0,
                          date_from=None, date_to=None,
                          sl_atr_mult=0.0, tp_atr_mult=0.0,
                          breakeven_atr_mult=0.0, trail_atr_mult=0.0):
    rates = load_rates(symbol, timeframe, bars, date_from, date_to)
    if rates is None or len(rates) < 100:
        print(f"  Недостаточно данных для {symbol}")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    symbol_info = mt5.symbol_info(symbol)
    point       = symbol_info.point if symbol_info else 0.0001
    return _run_strategy_on_df(
        strategy, df, point=point, symbol_info=symbol_info,
        skip_weekend_filter=_is_daily_or_higher_tf(timeframe),
        spread_points=spread_points, deposit=deposit, risk_pct=risk_pct,
        fixed_volume=fixed_volume, sl_atr_mult=sl_atr_mult, tp_atr_mult=tp_atr_mult,
        breakeven_atr_mult=breakeven_atr_mult, trail_atr_mult=trail_atr_mult,
    )


def _run_strategy_on_df(strategy, df, *, point, symbol_info, skip_weekend_filter,
                        spread_points=0, deposit=0.0, risk_pct=80, fixed_volume=0.0,
                        sl_atr_mult=0.0, tp_atr_mult=0.0,
                        breakeven_atr_mult=0.0, trail_atr_mult=0.0):
    df = strategy.compute_indicators(df)
    # ── далее ДОСЛОВНО переносится тело run_strategy_backtest начиная с блока
    #    `need_atr = (...)` и до `return result`, без изменений логики. ──
    ...
```
ВАЖНО: тело использует вложенные замыкания `_next_monday`, `_update_dd_block`, `_close_hedge` — они переезжают внутрь inner как были (не трогаем). Все обращения к `mt5.*` в теле (`mt5.ORDER_TYPE_BUY/SELL`) достигаются ТОЛЬКО при `deposit>0` — на синтетике с `deposit=0` не вызываются.

- [ ] **Step 5: Запустить smoke + весь набор**

Run: `python -m pytest tests/test_backtest_seam.py -q` → 2 passed.
Run: `python -m pytest -q` → 224 passed, 20 skipped, 1 xfailed (222 прежних + 2 новых).

- [ ] **Step 6: Commit**

```bash
git add backtest.py tests/test_backtest_seam.py
git commit -m "refactor(backtest): выделить df-инъектируемые inner-функции движков (C, шов)"
```

---

## Task 2: Характеризационные golden-тесты

**Files:**
- Create: `tests/test_backtest_characterization.py`
- Create: `tests/golden/bt_*.json` (генерация)

> Запираем поведение обоих движков ДО переноса в модули. Используем `--update-golden` (опция в `tests/conftest.py`) и `tests/strategies/golden_utils.py` для save/load/path.

- [ ] **Step 1: Написать характеризационный тест**

`tests/test_backtest_characterization.py`:
```python
"""C/Task2: golden-характеризация ядра движков на синтетике (без MT5).
Запирает текущее поведение перед декомпозицией. Регенерация: --update-golden."""
import pytest

from backtest import _run_default_on_df, _run_strategy_on_df
from strategies.ema_cross import EmaCrossStrategy
from strategies.cci_rsi import CciRsiStrategy
from tests.strategies import builders, golden_utils


def _snapshot(res) -> dict:
    return {
        "summary": {
            "total_trades": res.total_trades,
            "win_rate": round(res.win_rate, 6),
            "total_pnl_points": round(res.total_pnl_points, 4),
            "max_drawdown_points": round(res.max_drawdown_points, 4),
        },
        "trades": [
            {
                "type": t["type"],
                "entry_price": round(float(t["entry_price"]), 4),
                "exit_price": round(float(t["exit_price"]), 4),
                "pnl_points": round(float(t["pnl_points"]), 4),
                "exit_reason": t["exit_reason"],
                "bars_held": int(t["bars_held"]),
            }
            for t in res.trades
        ],
    }


def _check(name, res, request):
    snap = _snapshot(res)
    if request.config.getoption("--update-golden"):
        golden_utils.save_golden(name, snap)
        pytest.skip(f"golden обновлён для {name}")
    if not golden_utils.golden_path(name).exists():
        pytest.fail(f"Нет golden {name}. Сгенерируйте: pytest -k characterization --update-golden")
    assert snap == golden_utils.load_golden(name), f"{name}: поведение движка изменилось"


CASES_DEFAULT = ["trend_up", "trend_down", "flat"]


@pytest.mark.parametrize("shape", CASES_DEFAULT)
def test_default_engine_characterization(shape, request):
    df = getattr(builders, shape)(300)
    res = _run_default_on_df(
        df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=2, deposit=0.0, risk_pct=80, fixed_volume=0.0,
    )
    _check(f"bt_default_{shape}", res, request)


STRAT_CASES = [("ema_cross", EmaCrossStrategy), ("cci_rsi", CciRsiStrategy)]


@pytest.mark.parametrize("name,cls", STRAT_CASES)
@pytest.mark.parametrize("shape", CASES_DEFAULT)
def test_strategy_engine_characterization(name, cls, shape, request):
    df = getattr(builders, shape)(300)
    res = _run_strategy_on_df(
        cls(), df, point=0.01, symbol_info=None, skip_weekend_filter=False,
        spread_points=2, deposit=0.0, risk_pct=80, fixed_volume=0.0,
        sl_atr_mult=1.5, tp_atr_mult=2.5, breakeven_atr_mult=0.0, trail_atr_mult=0.0,
    )
    _check(f"bt_{name}_{shape}", res, request)
```

- [ ] **Step 2: Сгенерировать baseline**

Run: `python -m pytest tests/test_backtest_characterization.py --update-golden -q`
Expected: 9 кейсов skipped («golden обновлён»); в `tests/golden/` появились `bt_default_*.json`, `bt_ema_cross_*.json`, `bt_cci_rsi_*.json` (9 файлов).

- [ ] **Step 3: Прогнать на стабильность**

Run: `python -m pytest tests/test_backtest_characterization.py -q`
Expected: 9 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_backtest_characterization.py tests/golden/bt_*.json
git commit -m "test(backtest): golden-характеризация ядра движков на синтетике (C)"
```

---

## Task 3: Создать пакет и перенести листовые модули

**Files:**
- Create: `backtest_engine/__init__.py`, `filters.py`, `default_strategy.py`, `result.py`, `trades.py`, `sizing.py`, `data.py`
- Modify: `backtest.py`

> Переносим функции/класс ДОСЛОВНО из backtest.py в модули пакета. В backtest.py заменяем определения на импорты из пакета. backtest.py пока сохраняет движки/отчёт/CLI. Характеризация — стабильна на каждом шаге (импорт `from backtest import _run_*_on_df` остаётся рабочим, т.к. backtest.py всё ещё содержит движки и теперь импортирует листовые функции).

- [ ] **Step 1: Создать пакет с листовыми модулями**

Создать `backtest_engine/__init__.py` (пустой пока).
Создать каждый модуль, перенеся ДОСЛОВНО из backtest.py:
- `backtest_engine/filters.py` ← `_is_night_bar`, `_is_daily_or_higher_tf` (+ `import MetaTrader5 as mt5`, `import pandas as pd`).
- `backtest_engine/default_strategy.py` ← `calc_ema_series`, `compute_indicators`, `get_ma_signal`, `get_macd_signal`, `get_rsi_signal`, `get_combined_signal` (+ `import pandas as pd`, `import numpy as np`, `import talib`).
- `backtest_engine/result.py` ← класс `BacktestResult` (+ `import numpy as np`).
- `backtest_engine/trades.py` ← `_calc_pnl_points`, `_make_default_trade`, `_make_strategy_trade`.
- `backtest_engine/sizing.py` ← `get_pip_value`, `calc_volume` (+ `import MetaTrader5 as mt5`).
- `backtest_engine/data.py` ← `load_rates` (+ `import MetaTrader5 as mt5`).

- [ ] **Step 2: Заменить определения в backtest.py на импорты**

В начале `backtest.py` (после строки `from account import Account`) добавить:
```python
from backtest_engine.filters import _is_night_bar, _is_daily_or_higher_tf
from backtest_engine.default_strategy import (
    calc_ema_series, compute_indicators,
    get_ma_signal, get_macd_signal, get_rsi_signal, get_combined_signal,
)
from backtest_engine.result import BacktestResult
from backtest_engine.trades import _calc_pnl_points, _make_default_trade, _make_strategy_trade
from backtest_engine.sizing import get_pip_value, calc_volume
from backtest_engine.data import load_rates
```
И УДАЛИТЬ из backtest.py исходные определения этих функций/класса (теперь они в пакете). Оставить в backtest.py: `run_backtest`/`_run_default_on_df`, `run_strategy_backtest`/`_run_strategy_on_df`, `print_report`, `main`, и константы.

- [ ] **Step 3: Проверка**

Run: `python -c "from backtest import run_backtest, run_strategy_backtest, load_rates, BacktestResult; print('ok')"` → `ok`
Run: `python -m pytest -q` → 224 passed, 20 skipped, 1 xfailed (характеризация без изменений).

- [ ] **Step 4: Commit**

```bash
git add backtest_engine/ backtest.py
git commit -m "refactor(backtest): вынести листовые модули в пакет backtest_engine (C)"
```

---

## Task 4: Перенести движки/отчёт/CLI; backtest.py → facade

**Files:**
- Create: `backtest_engine/engine.py`, `backtest_engine/report.py`, `backtest_engine/cli.py`
- Modify: `backtest_engine/__init__.py`, `backtest.py`

- [ ] **Step 1: Перенести движки в engine.py**

Создать `backtest_engine/engine.py`, перенеся ДОСЛОВНО из backtest.py: `run_backtest`, `_run_default_on_df`, `run_strategy_backtest`, `_run_strategy_on_df`. В шапку engine.py добавить импорты:
```python
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import talib
from backtest_engine.filters import _is_night_bar, _is_daily_or_higher_tf
from backtest_engine.default_strategy import compute_indicators, get_combined_signal, get_macd_signal
from backtest_engine.result import BacktestResult
from backtest_engine.trades import _calc_pnl_points, _make_default_trade, _make_strategy_trade
from backtest_engine.sizing import calc_volume
from backtest_engine.data import load_rates
```
(Проверить по факту, какие из импортов реально используются телом; лишние не добавлять.)

- [ ] **Step 2: Перенести report.py и cli.py**

- `backtest_engine/report.py` ← `print_report` (+ `import numpy as np`).
- `backtest_engine/cli.py` ← `main` (+ его импорты: `argparse`, `MetaTrader5 as mt5`, `from datetime import datetime`, `from authenticator import MT5Auth`, `from account import Account`, `from strategies import STRATEGIES`, и `from backtest_engine.engine import run_backtest, run_strategy_backtest`, `from backtest_engine.report import print_report`).

- [ ] **Step 3: __init__.py — ре-экспорт**

`backtest_engine/__init__.py`:
```python
from backtest_engine.engine import (
    run_backtest, run_strategy_backtest,
    _run_default_on_df, _run_strategy_on_df,
)
from backtest_engine.data import load_rates
from backtest_engine.result import BacktestResult

__all__ = [
    "run_backtest", "run_strategy_backtest",
    "_run_default_on_df", "_run_strategy_on_df",
    "load_rates", "BacktestResult",
]
```

- [ ] **Step 4: backtest.py → facade**

Заменить ВСЁ содержимое `backtest.py` на:
```python
"""Facade бэктест-движка TradingHouse. Реализация — в пакете backtest_engine/.

Запуск CLI: python backtest.py [--strategy ...]
"""
from backtest_engine import (
    run_backtest, run_strategy_backtest,
    _run_default_on_df, _run_strategy_on_df,
    load_rates, BacktestResult,
)
from backtest_engine.cli import main

__all__ = [
    "run_backtest", "run_strategy_backtest",
    "_run_default_on_df", "_run_strategy_on_df",
    "load_rates", "BacktestResult", "main",
]

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Проверка**

Run: `python -c "from backtest import run_backtest, run_strategy_backtest, load_rates, BacktestResult, _run_default_on_df, _run_strategy_on_df; print('ok')"` → `ok`
Run: `python -c "import agents.backtest_agent; print('agent ok')"` → `agent ok`
Run: `python -m pytest -q` → 224 passed, 20 skipped, 1 xfailed (характеризация НЕ изменилась — поведение сохранено).
Run: `python backtest.py --help` → выводит argparse-помощь без ошибок (CLI парсер строится без подключения к MT5).

- [ ] **Step 6: Commit**

```bash
git add backtest_engine/ backtest.py
git commit -m "refactor(backtest): движки/отчёт/CLI в пакет; backtest.py → facade (C)"
```

---

## Self-Review (автор плана)

- **Покрытие спеки:** шов (inner) → Task 1; характеризация → Task 2; пакет (листовые) → Task 3; движки/отчёт/CLI + facade → Task 4; совместимость API/CLI → Task 4 Step 5. ✔
- **Имена/сигнатуры согласованы:** `_run_default_on_df(df, *, point, symbol_info, skip_weekend_filter, spread_points, deposit, risk_pct, fixed_volume)` и `_run_strategy_on_df(strategy, df, *, point, symbol_info, skip_weekend_filter, spread_points, deposit, risk_pct, fixed_volume, sl_atr_mult, tp_atr_mult, breakeven_atr_mult, trail_atr_mult)` — одинаковы в Task 1 (определение), Task 1/2 (тесты), Task 3/4 (перенос). Имена golden: `bt_default_<shape>`, `bt_<strategy>_<shape>`.
- **Тестируемость без MT5:** inner принимает `skip_weekend_filter: bool` (не `timeframe`), поэтому не зовёт `_is_daily_or_higher_tf` (тот трогает `mt5.TIMEFRAME_W1/MN1`, отсутствующие в conftest-стабе). Сайзинг с `deposit=0`/`symbol_info=None` не вызывает MT5. ✔
- **Стабильность тестового импорта:** тесты импортируют `from backtest import _run_*_on_df` на всех этапах — путь сохраняется (Task 3 оставляет движки в backtest.py; Task 4 facade ре-экспортирует inner). ✔
- **Плейсхолдеры:** тела движков (~150 и ~300 строк) переносятся ДОСЛОВНО — в плане даны точные сигнатуры/обёртки/границы переноса; повторять сотни строк цикла нецелесообразно (это move-рефактор, не написание новой логики). Golden ловит любое отклонение.
