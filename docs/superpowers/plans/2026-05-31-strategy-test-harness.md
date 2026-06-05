# Тест-харнесс стратегий — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать CI-ready тест-харнесс для 20 торговых стратегий — контракт-тесты, golden-снимки на реальных данных и поведенческие сценарии — как страховочную сетку перед рефакторингом `settings.py` и `backtest.py`.

**Architecture:** Тесты стратегий импортируются без живого MT5 (модули стратегий зависят только от `talib`+`pandas`). Данные — гибрид: синтетические билдеры OHLC для контракт/поведенческих тестов + один записанный CSV XAUUSD H1 для golden-регрессии. MT5-стаб в `conftest` чинит сбор сломанных legacy-тестов. Стратегии инстанцируются свежими (минуя runtime-singleton).

**Tech Stack:** Python 3.11, pytest (`asyncio_mode=auto`), pandas, TA-Lib.

**Спека:** [docs/superpowers/specs/2026-05-31-strategy-test-harness-design.md](../specs/2026-05-31-strategy-test-harness-design.md)

---

## Структура файлов

| Файл | Создаётся/Меняется | Ответственность |
|------|--------------------|-----------------|
| `tests/conftest.py` | Создать | MT5 sys.modules-стаб; `--update-golden` опция |
| `tests/strategies/__init__.py` | Создать | пакет |
| `tests/strategies/builders.py` | Создать | синтетические OHLC DataFrame'ы |
| `tests/strategies/test_builders.py` | Создать | тесты самих билдеров |
| `tests/strategies/golden_utils.py` | Создать | прогон стратегии → сигнальная серия; сравнение/регенерация |
| `tests/strategies/conftest.py` | Создать | фикстура `real_ohlc`, список `ALL_STRATEGIES` |
| `tests/strategies/test_contract.py` | Создать | контракт BaseStrategy ×20 (A1) |
| `tests/strategies/test_golden.py` | Создать | golden-снимки ×20 (A2) |
| `tests/strategies/test_behavioral.py` | Создать | поведенческие сценарии (A3) |
| `tests/fixtures/xauusd_h1.csv` | Создать (разово) | ~500 реальных баров |
| `tests/golden/*.json` | Создать (генерация) | зафиксированные сигнальные серии |
| `tools/dump_ohlc.py` | Создать | разовый забор баров из MT5 → CSV |

---

## Task 0: MT5-стаб в conftest + починка сбора legacy-тестов

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Написать стаб MT5 и pytest-опцию**

`tests/conftest.py`:
```python
"""Pytest-конфигурация для тестов.

Если установленный MetaTrader5 неполноценен (нет TIMEFRAME_M1) или отсутствует,
подменяем его модулем-заглушкой в sys.modules ДО импорта settings/indicators,
чтобы тесты собирались на любой машине без живого терминала.
"""
import sys
import types


def _install_mt5_stub() -> None:
    try:
        import MetaTrader5 as _mt5
        if hasattr(_mt5, "TIMEFRAME_M1"):
            return  # реальный модуль пригоден
    except Exception:
        pass

    stub = types.ModuleType("MetaTrader5")
    for i, name in enumerate(
        ["TIMEFRAME_M1", "TIMEFRAME_M5", "TIMEFRAME_M15", "TIMEFRAME_M30",
         "TIMEFRAME_H1", "TIMEFRAME_H4", "TIMEFRAME_D1"],
        start=1,
    ):
        setattr(stub, name, i)

    def _noop(*args, **kwargs):
        return None

    # любое неизвестное обращение (функции инициализации и т.п.) → no-op
    stub.__getattr__ = lambda name: _noop  # type: ignore[attr-defined]
    sys.modules["MetaTrader5"] = stub


_install_mt5_stub()


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Перезаписать golden-снимки текущим поведением вместо сравнения.",
    )
```

- [ ] **Step 2: Запустить сбор всех тестов**

Run: `python -m pytest --collect-only -q`
Expected: 0 ошибок сбора (раньше было 3 ошибки `AttributeError: module 'MetaTrader5' has no attribute 'TIMEFRAME_M1'`). Все legacy-тесты собираются.

- [ ] **Step 3: Прогнать существующие legacy-тесты**

Run: `python -m pytest -q`
Expected: тесты собираются и выполняются (часть может падать по другим причинам — это нормально, важно что нет ошибок *сбора*).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: MT5-стаб в conftest — чинит сбор legacy-тестов без живого терминала"
```

---

## Task 1: Синтетические билдеры OHLC

**Files:**
- Create: `tests/strategies/__init__.py`
- Create: `tests/strategies/builders.py`
- Test: `tests/strategies/test_builders.py`

- [ ] **Step 1: Создать пакет**

`tests/strategies/__init__.py`:
```python
```
(пустой файл)

- [ ] **Step 2: Написать билдеры**

`tests/strategies/builders.py`:
```python
"""Детерминированные синтетические OHLC DataFrame'ы для тестов стратегий.

Колонки: time, open, high, low, close, tick_volume — как у баров MT5.
Длина по умолчанию 300 баров (хватает на EMA200 и flat-avg период 50).
"""
import numpy as np
import pandas as pd

DEFAULT_N = 300
_BASE_PRICE = 2000.0  # порядок цены XAUUSD


def _assemble(closes: np.ndarray) -> pd.DataFrame:
    """Достраивает консистентный OHLC из серии close.

    open[i] = close[i-1] (open[0] = close[0]); high/low охватывают open и close
    с небольшим запасом, чтобы high >= max(open,close) и low <= min(open,close).
    """
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    opens = np.empty(n, dtype=float)
    opens[0] = closes[0]
    opens[1:] = closes[:-1]

    span = np.abs(closes - opens)
    pad = np.maximum(span * 0.25, 0.5)
    highs = np.maximum(opens, closes) + pad
    lows = np.minimum(opens, closes) - pad

    times = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({
        "time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_volume": np.full(n, 100, dtype=int),
    })


def trend_up(n: int = DEFAULT_N, step: float = 1.0) -> pd.DataFrame:
    """Устойчивый восходящий тренд."""
    closes = _BASE_PRICE + np.arange(n) * step
    return _assemble(closes)


def trend_down(n: int = DEFAULT_N, step: float = 1.0) -> pd.DataFrame:
    """Устойчивый нисходящий тренд."""
    closes = _BASE_PRICE - np.arange(n) * step
    return _assemble(closes)


def flat(n: int = DEFAULT_N, amplitude: float = 0.3) -> pd.DataFrame:
    """Узкий диапазон без тренда — активирует флэт-гард BaseStrategy."""
    rng = np.random.default_rng(42)
    closes = _BASE_PRICE + rng.uniform(-amplitude, amplitude, size=n)
    return _assemble(closes)


def from_closes(closes) -> pd.DataFrame:
    """Кастомная серия close — для точечных поведенческих сценариев."""
    return _assemble(closes)
```

- [ ] **Step 3: Написать тесты билдеров**

`tests/strategies/test_builders.py`:
```python
import pandas as pd
from tests.strategies import builders

REQUIRED_COLS = {"time", "open", "high", "low", "close", "tick_volume"}


def test_trend_up_has_required_columns_and_length():
    df = builders.trend_up(300)
    assert REQUIRED_COLS.issubset(df.columns)
    assert len(df) == 300


def test_ohlc_invariants_hold():
    df = builders.trend_up(50)
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()


def test_trend_up_is_monotonic_in_close():
    df = builders.trend_up(50)
    assert df["close"].is_monotonic_increasing


def test_trend_down_is_monotonic_in_close():
    df = builders.trend_down(50)
    assert df["close"].is_monotonic_decreasing


def test_flat_is_deterministic():
    a = builders.flat(100)
    b = builders.flat(100)
    pd.testing.assert_frame_equal(a, b)


def test_from_closes_round_trips_close():
    df = builders.from_closes([10.0, 11.0, 9.0, 12.0])
    assert list(df["close"]) == [10.0, 11.0, 9.0, 12.0]
    assert df["time"].is_monotonic_increasing
```

- [ ] **Step 4: Прогнать тесты билдеров**

Run: `python -m pytest tests/strategies/test_builders.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/strategies/__init__.py tests/strategies/builders.py tests/strategies/test_builders.py
git commit -m "test(strategies): синтетические OHLC-билдеры + их тесты"
```

---

## Task 2: Разовый забор реального CSV-фикстура

**Files:**
- Create: `tools/dump_ohlc.py`
- Create: `tests/fixtures/xauusd_h1.csv` (результат запуска, локально на машине с MT5)

> **Примечание для исполнителя:** этот шаг требует живого MT5-терминала и выполняется один раз вручную на машине пользователя. CSV коммитится — CI его только читает.

- [ ] **Step 1: Написать скрипт забора**

`tools/dump_ohlc.py`:
```python
"""Разовый забор исторических баров из MT5 в CSV для golden-тестов.

Запуск (локально, при запущенном MT5-терминале):
    python tools/dump_ohlc.py --symbol XAUUSDrfd --timeframe H1 --count 500 \
        --out tests/fixtures/xauusd_h1.csv
"""
import argparse
import sys

import MetaTrader5 as mt5
import pandas as pd

TF = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="XAUUSDrfd")
    p.add_argument("--timeframe", default="H1", choices=list(TF))
    p.add_argument("--count", type=int, default=500)
    p.add_argument("--out", default="tests/fixtures/xauusd_h1.csv")
    args = p.parse_args()

    if not mt5.initialize():
        print(f"mt5.initialize() failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(1)
    try:
        rates = mt5.copy_rates_from_pos(args.symbol, TF[args.timeframe], 0, args.count)
    finally:
        mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("Нет данных от MT5", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    cols = ["time", "open", "high", "low", "close", "tick_volume"]
    df[cols].to_csv(args.out, index=False)
    print(f"Записано {len(df)} баров в {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Создать каталог фикстур и сгенерировать CSV (локально, с MT5)**

Run: `python tools/dump_ohlc.py --symbol XAUUSDrfd --timeframe H1 --count 500 --out tests/fixtures/xauusd_h1.csv`
Expected: `Записано 500 баров в tests/fixtures/xauusd_h1.csv`

- [ ] **Step 3: Проверить формат CSV**

Run: `python -c "import pandas as pd; df=pd.read_csv('tests/fixtures/xauusd_h1.csv'); print(df.columns.tolist()); print(len(df))"`
Expected: `['time', 'open', 'high', 'low', 'close', 'tick_volume']` и `500`.

- [ ] **Step 4: Commit**

```bash
git add tools/dump_ohlc.py tests/fixtures/xauusd_h1.csv
git commit -m "test(fixtures): скрипт забора + реальные бары XAUUSD H1 для golden-тестов"
```

---

## Task 3: golden_utils + общие фикстуры стратегий

**Files:**
- Create: `tests/strategies/golden_utils.py`
- Create: `tests/strategies/conftest.py`

- [ ] **Step 1: Написать golden_utils**

`tests/strategies/golden_utils.py`:
```python
"""Прогон стратегии по OHLC → детерминированная сигнальная серия + сравнение с golden."""
import json
from pathlib import Path

import pandas as pd

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"


def run_signal_series(strategy, df: pd.DataFrame) -> dict:
    """Прогоняет стратегию по df и возвращает сериализуемую сигнальную серию.

    Возвращает dict:
      {"entries": [[idx, "BUY"|"SELL"], ...], "flat_count": int}
    Вход учитывает флэт-гард: если is_flat(row) — вход пропускается.
    """
    work = df.copy()
    work = strategy.compute_indicators(work)
    work = strategy.compute_flat_indicators(work)

    entries = []
    flat_count = 0
    for idx in range(len(work)):
        row = work.iloc[idx]
        if strategy.is_flat(row):
            flat_count += 1
            continue
        sig = strategy.get_entry_signal(row)
        if sig in ("BUY", "SELL"):
            entries.append([idx, sig])
    return {"entries": entries, "flat_count": flat_count}


def golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def load_golden(name: str) -> dict:
    return json.loads(golden_path(name).read_text(encoding="utf-8"))


def save_golden(name: str, data: dict) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_path(name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

- [ ] **Step 2: Написать общие фикстуры**

`tests/strategies/conftest.py`:
```python
"""Фикстуры и параметризация для тестов стратегий."""
from pathlib import Path

import pandas as pd
import pytest

from strategies import STRATEGIES

# (имя, класс) для параметризации по всем стратегиям реестра
ALL_STRATEGIES = list(STRATEGIES.items())
STRATEGY_IDS = [name for name, _ in ALL_STRATEGIES]

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "xauusd_h1.csv"


@pytest.fixture(scope="session")
def real_ohlc() -> pd.DataFrame:
    """~500 реальных баров XAUUSD H1. Каждый тест получает свежую копию через .copy()."""
    if not _FIXTURE.exists():
        pytest.skip(f"Нет фикстуры {_FIXTURE} — запустите tools/dump_ohlc.py")
    df = pd.read_csv(_FIXTURE, parse_dates=["time"])
    return df


@pytest.fixture(params=ALL_STRATEGIES, ids=STRATEGY_IDS)
def strategy(request):
    """Свежий экземпляр стратегии (минуя runtime-singleton, чтобы состояние не протекало)."""
    name, cls = request.param
    return cls()
```

- [ ] **Step 3: Smoke-проверка импортов**

Run: `python -m pytest tests/strategies/ --collect-only -q`
Expected: сбор без ошибок (тесты ещё не написаны — может быть «no tests ran», это нормально).

- [ ] **Step 4: Commit**

```bash
git add tests/strategies/golden_utils.py tests/strategies/conftest.py
git commit -m "test(strategies): golden_utils + фикстуры real_ohlc/strategy"
```

---

## Task 4: Контракт-тесты (A1)

**Files:**
- Create: `tests/strategies/test_contract.py`

- [ ] **Step 1: Написать контракт-тесты**

`tests/strategies/test_contract.py`:
```python
"""A1: контракт BaseStrategy — проверяется для каждой стратегии реестра.

Фикстура `strategy` (из conftest) параметризована по всем 20 стратегиям.
"""
import pandas as pd

from tests.strategies import builders


def _computed(strategy, df):
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    return df


def test_entry_signal_returns_valid_value(strategy):
    df = _computed(strategy, builders.trend_up())
    for idx in range(len(df)):
        sig = strategy.get_entry_signal(df.iloc[idx])
        assert sig in ("BUY", "SELL", None), f"{strategy.name}: неверный сигнал {sig!r}"


def test_is_flat_returns_bool(strategy):
    df = _computed(strategy, builders.flat())
    assert isinstance(strategy.is_flat(df.iloc[-1]), bool)


def test_hooks_return_bool(strategy):
    assert isinstance(strategy.wants_hedge(), bool)
    assert isinstance(strategy.closes_on_weekend(), bool)
    assert isinstance(strategy.uses_trailing_exit(), bool)


def test_compute_indicators_preserves_length(strategy):
    df = builders.trend_up()
    n0 = len(df)
    out = strategy.compute_indicators(df)
    assert len(out) == n0


def test_get_sl_tp_ordering_on_valid_row(strategy):
    """На строке с готовыми индикаторами SL/TP, если заданы, корректно упорядочены."""
    df = _computed(strategy, builders.trend_up())
    row = df.iloc[-1]  # последняя строка — индикаторы не NaN
    price = row["close"]

    for signal in ("BUY", "SELL"):
        sl, tp = strategy.get_sl_tp(row, signal, point=0.01)
        if sl is not None and not pd.isna(sl):
            if signal == "BUY":
                assert sl < price, f"{strategy.name} BUY: sl {sl} !< price {price}"
            else:
                assert sl > price, f"{strategy.name} SELL: sl {sl} !> price {price}"
        if tp is not None and not pd.isna(tp):
            if signal == "BUY":
                assert tp > price, f"{strategy.name} BUY: tp {tp} !> price {price}"
            else:
                assert tp < price, f"{strategy.name} SELL: tp {tp} !< price {price}"


def test_no_exception_on_short_dataframe(strategy):
    """Короткий df (меньше периодов индикаторов) не приводит к исключению."""
    df = builders.trend_up(n=10)
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    for idx in range(len(df)):
        strategy.get_entry_signal(df.iloc[idx])  # не должно кидать


def test_no_exception_on_nan_rows(strategy):
    """Начальные строки с NaN-индикаторами не ломают get_entry_signal."""
    df = _computed(strategy, builders.trend_up())
    strategy.get_entry_signal(df.iloc[0])  # самые ранние строки — NaN, не должно кидать
```

- [ ] **Step 2: Прогнать контракт-тесты**

Run: `python -m pytest tests/strategies/test_contract.py -v`
Expected: 7 тестов × 20 стратегий = 140 параметризованных кейсов, все PASS.

> **Если падает** `test_get_sl_tp_ordering_on_valid_row` для конкретной стратегии: это потенциальная находка (стратегия возвращает SL/TP по неверную сторону) — задокументировать в issue, не «чинить» молча. Если падает `test_no_exception_*` — стратегия не защищена от NaN/коротких данных; зафиксировать как находку.

- [ ] **Step 3: Commit**

```bash
git add tests/strategies/test_contract.py
git commit -m "test(strategies): контракт-тесты BaseStrategy для всех 20 стратегий (A1)"
```

---

## Task 5: Golden-снимки (A2)

**Files:**
- Create: `tests/strategies/test_golden.py`
- Create: `tests/golden/*.json` (генерация на первом прогоне)

- [ ] **Step 1: Написать golden-тест**

`tests/strategies/test_golden.py`:
```python
"""A2: golden-снимки сигнальных серий на реальном CSV XAUUSD H1.

Первый прогон с `--update-golden` создаёт baseline-файлы.
Последующие прогоны строго сравнивают текущее поведение с baseline.
"""
import pytest

from tests.strategies import golden_utils


def test_golden_signal_series(strategy, real_ohlc, request):
    update = request.config.getoption("--update-golden")
    series = golden_utils.run_signal_series(strategy, real_ohlc.copy())

    if update:
        golden_utils.save_golden(strategy.name, series)
        pytest.skip(f"golden обновлён для {strategy.name}")

    if not golden_utils.golden_path(strategy.name).exists():
        pytest.fail(
            f"Нет golden для {strategy.name}. "
            f"Сгенерируйте: pytest tests/strategies/test_golden.py --update-golden"
        )

    expected = golden_utils.load_golden(strategy.name)
    assert series == expected, (
        f"{strategy.name}: сигнальная серия изменилась относительно golden. "
        f"Если изменение намеренное — обновите через --update-golden."
    )
```

- [ ] **Step 2: Сгенерировать baseline golden-файлы**

> Требует наличия `tests/fixtures/xauusd_h1.csv` (Task 2). Без него тест скипнется.

Run: `python -m pytest tests/strategies/test_golden.py --update-golden -q`
Expected: 20 кейсов skipped с сообщением «golden обновлён»; в `tests/golden/` появилось 20 JSON-файлов.

- [ ] **Step 3: Прогнать golden-тесты для проверки стабильности**

Run: `python -m pytest tests/strategies/test_golden.py -v`
Expected: 20 passed (серии совпадают с только что записанным baseline).

- [ ] **Step 4: Commit**

```bash
git add tests/strategies/test_golden.py tests/golden/
git commit -m "test(strategies): golden-снимки сигналов на XAUUSD H1 для всех 20 стратегий (A2)"
```

---

## Task 6: Поведенческий тест-эталон — ema_cross (A3, пример паттерна)

**Files:**
- Create: `tests/strategies/test_behavioral.py`

> Эта задача задаёт **паттерн** поведенческого теста на полностью разобранной стратегии `ema_cross` (логика: EMA50>EMA200 → BUY, EMA50<EMA200 → SELL, `is_flat` всегда False). Task 7 тиражирует паттерн на остальные 19.

- [ ] **Step 1: Написать поведенческие тесты для ema_cross**

`tests/strategies/test_behavioral.py`:
```python
"""A3: поведенческие сценарии — намеренный вход OHLC → ожидаемый сигнал.

Каждый тест строит синтетический сценарий под логику входа конкретной стратегии
и утверждает ожидаемый сигнал на релевантной строке. Стратегии инстанцируются
свежими (не через runtime), чтобы внутреннее состояние не протекало между тестами.
"""
import pandas as pd

from strategies.ema_cross import EmaCrossStrategy
from tests.strategies import builders


def _last_signal(strategy, df):
    df = strategy.compute_indicators(df)
    df = strategy.compute_flat_indicators(df)
    row = df.iloc[-1]
    if strategy.is_flat(row):
        return None
    return strategy.get_entry_signal(row)


def test_ema_cross_uptrend_gives_buy():
    # Устойчивый рост → EMA50 > EMA200 → BUY
    assert _last_signal(EmaCrossStrategy(), builders.trend_up()) == "BUY"


def test_ema_cross_downtrend_gives_sell():
    # Устойчивое падение → EMA50 < EMA200 → SELL
    assert _last_signal(EmaCrossStrategy(), builders.trend_down()) == "SELL"
```

- [ ] **Step 2: Прогнать**

Run: `python -m pytest tests/strategies/test_behavioral.py -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/strategies/test_behavioral.py
git commit -m "test(strategies): поведенческий эталон ema_cross (A3, паттерн)"
```

---

## Task 7: Поведенческие тесты для остальных 19 стратегий (A3)

**Files:**
- Modify: `tests/strategies/test_behavioral.py`

> **Метод (TDD, по одной стратегии за раз):** для каждой стратегии открыть её модуль, прочитать `get_entry_signal`, вывести минимальные условия входа BUY и SELL, построить синтетический сценарий через `builders` (`trend_up`/`trend_down`/`flat`/`from_closes`), написать тест «должен войти» + тест «флэт → None». Прогнать, закоммитить. Затем следующая стратегия.
>
> Каждая стратегия — отдельный микро-цикл из шагов ниже. Список (имена из `STRATEGIES`):
> `sr_bounce, ema_pullback, ema_cross_inverse, cci_rsi, fibonacci_retracement, macd_hist, default_hedge, default_inverse, sar_adx, donchian_breakout, triple_ema, mean_revert_ema, ema50_pullback, ema_triple_touch, market_phase, combined_a_plus, ema50_rejection, ema50_overstretch, ema50_overstretch_mtf`.

**Для КАЖДОЙ стратегии повторить:**

- [ ] **Step A: Прочитать логику входа**

Read: `strategies/<module>.py` — функция `get_entry_signal`. Выписать условия BUY и SELL.

- [ ] **Step B: Написать тесты «должен войти» + «флэт → None»**

Шаблон (подставить реальные условия и подходящий билдер; пример для `ema_cross_inverse` — инверсия ema_cross):
```python
from strategies.ema_cross_inverse import EmaCrossInverseStrategy

def test_ema_cross_inverse_uptrend_gives_sell():
    # инверсная логика: рост → SELL
    assert _last_signal(EmaCrossInverseStrategy(), builders.trend_up()) == "SELL"

def test_ema_cross_inverse_flat_gives_none():
    assert _last_signal(EmaCrossInverseStrategy(), builders.flat()) is None
```
Если простой `trend_up/trend_down/flat` не активирует вход (например, нужен точный кросс CCI через +100, как в `cci_rsi`), построить серию через `builders.from_closes([...])` с явными значениями, дающими нужное условие. Если сконструировать детерминированный вход для стратегии не удаётся за разумное время — написать тест-«не падает» (вызов `get_entry_signal` по всем строкам без исключений) и пометить `# TODO behavioral: <причина>` для возврата.

- [ ] **Step C: Прогнать только эту стратегию**

Run: `python -m pytest tests/strategies/test_behavioral.py -k <strategy_name> -v`
Expected: новые тесты PASS.

- [ ] **Step D: Commit**

```bash
git add tests/strategies/test_behavioral.py
git commit -m "test(strategies): поведенческие тесты <strategy_name> (A3)"
```

- [ ] **Финальный шаг: полный прогон всего харнесса**

Run: `python -m pytest tests/strategies/ -q`
Expected: контракт (140) + golden (20) + поведенческие (≥40) — все PASS (кроме помеченных TODO, если такие появились).

---

## Self-Review (заполняется автором плана)

- **Покрытие спеки:** A1 контракт → Task 4; A2 golden → Task 5; A3 поведенческие → Tasks 6-7; синтетика → Task 1; реальный CSV → Task 2; golden_utils → Task 3; MT5-стаб → Task 0. ✔ все секции спеки покрыты.
- **Плейсхолдеры:** в Task 7 присутствует осознанный шаблон с инструкцией читать каждую стратегию — это не плейсхолдер кода, а метод TDD: точные сценарии входа 19 стратегий нельзя написать без чтения их логики, и попытка выдумать их была бы фабрикацией. Эталон (Task 6) полностью кодирован.
- **Согласованность типов:** `run_signal_series` возвращает `{"entries", "flat_count"}` — используется в Task 5 без расхождений. Фикстура `strategy` (свежий экземпляр) и `real_ohlc` определены в Task 3, применяются в Tasks 4-5. Билдеры `trend_up/trend_down/flat/from_closes` определены в Task 1, используются в Tasks 4/6/7.
```
