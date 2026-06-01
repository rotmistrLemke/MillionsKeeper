# Сервис trading_status — план реализации (слайс B1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Инкапсулировать `Dictionary.symbolTradingStatus` за протестированным сервисом `trading_status.status` с доменным API; мигрировать все call-sites с сохранением поведения 1:1; удалить словарь из `settings.py`.

**Architecture:** Новый модуль `trading_status.py` по образцу `streams.py` (класс-registry + синглтон + `RLock`). Именованные статусы `ALLOWED/OPEN/DISABLED`. Сначала создаём сервис с тестами (он сосуществует со старым словарём), затем мигрируем call-sites файл-за-файлом, в конце удаляем словарь из settings. Каждый шаг оставляет приложение работоспособным.

**Tech Stack:** Python 3.11, pytest, threading.RLock.

**Спека:** [docs/superpowers/specs/2026-06-01-trading-status-service-design.md](../specs/2026-06-01-trading-status-service-design.md)

---

## Структура файлов

| Файл | Действие | Ответственность |
|------|----------|-----------------|
| `trading_status.py` | Создать | `TradingStatusRegistry` + константы + синглтон `status` + seed |
| `tests/test_trading_status.py` | Создать | юнит-тесты сервиса |
| `settings.py` | Изменить | удалить `symbolTradingStatus` из `Dictionary` (последним) |
| `main.py`, `streams.py`, `active_state.py` | Изменить | миграция call-sites |
| `agents/signal_agent.py`, `agents/execution_agent.py`, `agents/position_monitor_agent.py`, `agents/market_data_agent.py` | Изменить | миграция call-sites |
| `web/app.py`, `web/api_routes.py` | Изменить | миграция call-sites |

---

## Task 1: Сервис trading_status + тесты (TDD)

**Files:**
- Create: `trading_status.py`
- Test: `tests/test_trading_status.py`

- [ ] **Step 1: Написать тесты (red)**

`tests/test_trading_status.py`:
```python
"""Юнит-тесты TradingStatusRegistry (слайс B1). Без MT5."""
import pytest

from trading_status import TradingStatusRegistry, ALLOWED, OPEN, DISABLED


def _reg():
    # изолированный seed, чтобы тесты не зависели от глобального синглтона
    return TradingStatusRegistry(seed={"XAUUSDrfd": ALLOWED, "EURUSDrfd": DISABLED, "#LCO": ALLOWED})


def test_seed_values():
    r = _reg()
    assert r.status_of("XAUUSDrfd") == ALLOWED
    assert r.status_of("EURUSDrfd") == DISABLED
    assert r.status_of("#LCO") == ALLOWED


def test_has_and_contains():
    r = _reg()
    assert r.has("XAUUSDrfd") is True
    assert ("XAUUSDrfd" in r) is True
    assert r.has("NOPE") is False
    assert ("NOPE" in r) is False


def test_status_of_unknown_is_disabled():
    assert _reg().status_of("UNKNOWN") == DISABLED


def test_is_helpers():
    r = _reg()
    assert r.is_allowed("XAUUSDrfd") is True
    assert r.is_disabled("EURUSDrfd") is True
    assert r.is_open("XAUUSDrfd") is False


def test_mark_open_and_allowed():
    r = _reg()
    r.mark_open("XAUUSDrfd")
    assert r.is_open("XAUUSDrfd") is True
    r.mark_allowed("XAUUSDrfd")
    assert r.is_allowed("XAUUSDrfd") is True


def test_set_status_raw():
    r = _reg()
    r.set_status("EURUSDrfd", ALLOWED)
    assert r.status_of("EURUSDrfd") == ALLOWED
    r.set_status("EURUSDrfd", 99)  # сырое значение принимается без валидации
    assert r.status_of("EURUSDrfd") == 99


def test_activate_only_sets_target_allowed_others_disabled():
    r = _reg()
    r.set_status("EURUSDrfd", ALLOWED)
    r.activate_only("XAUUSDrfd")
    assert r.is_allowed("XAUUSDrfd")
    assert r.is_disabled("EURUSDrfd")
    assert r.is_disabled("#LCO")


def test_activate_only_skips_open_symbols():
    r = _reg()
    r.mark_open("EURUSDrfd")          # символ с открытой позицией
    r.activate_only("XAUUSDrfd")
    assert r.is_allowed("XAUUSDrfd")
    assert r.is_open("EURUSDrfd")      # OPEN не сброшен


def test_sync_enabled():
    r = _reg()
    r.sync_enabled({"XAUUSDrfd", "#LCO"})
    assert r.is_allowed("XAUUSDrfd")
    assert r.is_allowed("#LCO")
    assert r.is_disabled("EURUSDrfd")


def test_sync_enabled_skips_open():
    r = _reg()
    r.mark_open("EURUSDrfd")
    r.sync_enabled({"XAUUSDrfd"})      # EURUSDrfd не в наборе, но OPEN
    assert r.is_open("EURUSDrfd")       # не тронут
    assert r.is_allowed("XAUUSDrfd")


def test_active_symbols_excludes_disabled():
    r = _reg()
    r.set_status("EURUSDrfd", ALLOWED)
    active = set(r.active_symbols())
    assert "XAUUSDrfd" in active
    assert "EURUSDrfd" in active
    assert "#LCO" in active  # ALLOWED по seed
    r.set_status("#LCO", DISABLED)
    assert "#LCO" not in set(r.active_symbols())


def test_symbols_lists_all_keys():
    r = _reg()
    assert set(r.symbols()) == {"XAUUSDrfd", "EURUSDrfd", "#LCO"}


def test_snapshot_is_a_copy():
    r = _reg()
    snap = r.snapshot()
    snap["XAUUSDrfd"] = 999
    assert r.status_of("XAUUSDrfd") == ALLOWED  # внутреннее состояние не изменилось
```

- [ ] **Step 2: Запустить — упадёт (нет модуля)**

Run: `python -m pytest tests/test_trading_status.py -q`
Expected: ошибка импорта `trading_status` / FAIL.

- [ ] **Step 3: Реализовать сервис**

`trading_status.py`:
```python
"""Статус торговли по символу (слайс B1).

Инкапсулирует бывший settings.Dictionary.symbolTradingStatus за доменным API.
Один экземпляр-синглтон `status`, по образцу streams.registry.

Статусы:
  ALLOWED  (0) — разрешено торговать
  OPEN     (1) — позиция открыта, не входить повторно
  DISABLED (3) — выключено
"""
import threading

ALLOWED = 0
OPEN = 1
DISABLED = 3

# Seed-вселенная символов — перенесена дословно из settings.Dictionary.symbolTradingStatus.
_SEED: dict[str, int] = {
    "EURUSDrfd": 3, "NZDUSDrfd": 3, "EURGBPrfd": 3, "USDCHFrfd": 3,
    "USDJPYrfd": 3, "EURCHFrfd": 3, "GBPUSDrfd": 3, "USDCADrfd": 3,
    "EURJPYrfd": 3, "AUDCADrfd": 3, "AUDUSDrfd": 3, "AUDJPYrfd": 3,
    "AUDCHFrfd": 3, "CHFJPYrfd": 3, "EURAUDrfd": 3, "GBPCHFrfd": 3,
    "EURCADrfd": 3, "GBPCADrfd": 3, "XAUUSDrfd": 0, "GBPJPYrfd": 3,
    "XAGUSDrfd": 3, "USDSGDrfd": 3, "#LCO": 0,
}


class TradingStatusRegistry:
    def __init__(self, seed: dict | None = None):
        self._status: dict[str, int] = dict(_SEED if seed is None else seed)
        self._lock = threading.RLock()

    # ── Запросы ──────────────────────────────────────────────────────
    def has(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._status

    def __contains__(self, symbol: str) -> bool:
        return self.has(symbol)

    def status_of(self, symbol: str) -> int:
        with self._lock:
            return self._status.get(symbol, DISABLED)

    def is_allowed(self, symbol: str) -> bool:
        return self.status_of(symbol) == ALLOWED

    def is_open(self, symbol: str) -> bool:
        return self.status_of(symbol) == OPEN

    def is_disabled(self, symbol: str) -> bool:
        return self.status_of(symbol) == DISABLED

    def symbols(self) -> list:
        with self._lock:
            return list(self._status.keys())

    def active_symbols(self) -> list:
        with self._lock:
            return [s for s, v in self._status.items() if v != DISABLED]

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._status)

    # ── Мутации ──────────────────────────────────────────────────────
    def mark_open(self, symbol: str) -> None:
        with self._lock:
            self._status[symbol] = OPEN

    def mark_allowed(self, symbol: str) -> None:
        with self._lock:
            self._status[symbol] = ALLOWED

    def set_status(self, symbol: str, value: int) -> None:
        with self._lock:
            self._status[symbol] = value

    def activate_only(self, symbol: str) -> None:
        """Целевой символ → ALLOWED, прочие → DISABLED. Символы со статусом OPEN не трогаем."""
        with self._lock:
            for s, st in list(self._status.items()):
                if st == OPEN:
                    continue
                self._status[s] = ALLOWED if s == symbol else DISABLED

    def sync_enabled(self, enabled_symbols: set) -> None:
        """Символы из набора → ALLOWED, прочие → DISABLED. OPEN не трогаем."""
        with self._lock:
            for s, st in list(self._status.items()):
                if st == OPEN:
                    continue
                self._status[s] = ALLOWED if s in enabled_symbols else DISABLED


status = TradingStatusRegistry()
```

- [ ] **Step 4: Запустить — зелёно**

Run: `python -m pytest tests/test_trading_status.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add trading_status.py tests/test_trading_status.py
git commit -m "feat(trading_status): сервис TradingStatusRegistry + тесты (B1)"
```

---

## Task 2: Миграция core (main, streams, active_state)

**Files:**
- Modify: `main.py`, `streams.py`, `active_state.py`

> На этом шаге `settings.Dictionary.symbolTradingStatus` ещё существует — сервис и словарь сосуществуют. Сервис seed-ится тем же литералом, поэтому стартовые значения совпадают. Удаление словаря — в Task 5.

- [ ] **Step 1: main.py — `_get_active_symbols`**

В [main.py:35-38](../../../main.py#L35) заменить тело:
```python
def _get_active_symbols():
    """Возвращает символы со статусом != 3 (не выключены)."""
    from trading_status import status
    return status.active_symbols()
```
(Удалить ставший ненужным `from settings import Dictionary` внутри функции.)

- [ ] **Step 2: streams.py — `has` и `sync_enabled`**

[streams.py:268-271](../../../streams.py#L268) в `_migrate_from_legacy`:
```python
    from trading_status import status
    symbol = GlobalValues.active_symbol
    if not status.has(symbol):
        logger.warning(f"Миграция отменена: symbol {symbol} неизвестен")
        return
```
(Оставить `from settings import GlobalValues` — он ещё нужен здесь; убрать только `Dictionary` из этого импорта, если он там есть.)

Заменить функцию `_sync_trading_status` целиком ([streams.py:288-297](../../../streams.py#L288)):
```python
def _sync_trading_status() -> None:
    """Приводит статусы к enabled-потокам: enabled-символы → ALLOWED, прочие → DISABLED.
    Символы с открытой позицией (OPEN) не трогаем."""
    from trading_status import status
    status.sync_enabled({s.symbol for s in registry.enabled()})
```

- [ ] **Step 3: active_state.py — `has` и `activate_only`**

[active_state.py:35-36](../../../active_state.py#L35): импорт сверху функции — заменить `from settings import GlobalValues, Dictionary, TF_MAP` на `from settings import GlobalValues, TF_MAP` и добавить `from trading_status import status`. Затем:
```python
    if isinstance(symbol, str) and status.has(symbol):
        GlobalValues.active_symbol = symbol
```
И заменить цикл [active_state.py:47-49](../../../active_state.py#L47):
```python
    # Активируем только сохранённую пару, остальные — выключены.
    status.activate_only(GlobalValues.active_symbol)
```
> Примечание: исходный цикл не пропускал OPEN; `activate_only` пропускает. На старте (когда вызывается `load()`) открытых позиций нет → эквивалентно и безопаснее (см. спеку).

- [ ] **Step 4: Проверить импорт/сбор**

Run: `python -m pytest --collect-only -q`
Expected: 0 ошибок сбора.
Run: `python -c "import main, streams, active_state; print('import ok')"`
Expected: `import ok` (без исключений).

- [ ] **Step 5: Commit**

```bash
git add main.py streams.py active_state.py
git commit -m "refactor(trading_status): миграция core (main/streams/active_state) на сервис (B1)"
```

---

## Task 3: Миграция агентов

**Files:**
- Modify: `agents/signal_agent.py`, `agents/execution_agent.py`, `agents/position_monitor_agent.py`, `agents/market_data_agent.py`

> Для каждого файла: добавить `from trading_status import status`; заменить обращения; если `Dictionary` больше нигде в файле не используется — убрать его импорт.

- [ ] **Step 1: signal_agent.py**

[agents/signal_agent.py:65](../../../agents/signal_agent.py#L65):
```python
            "trading_status": status.status_of(symbol),
```

- [ ] **Step 2: execution_agent.py**

[execution_agent.py:145](../../../agents/execution_agent.py#L145):
```python
        trading_status = status.status_of(symbol)
```
[execution_agent.py:218](../../../agents/execution_agent.py#L218):
```python
                status.mark_open(symbol)
```

- [ ] **Step 3: position_monitor_agent.py**

[position_monitor_agent.py:113-114](../../../agents/position_monitor_agent.py#L113):
```python
        if status.is_open(symbol) and not sibling_open:
            status.mark_allowed(symbol)
```
[position_monitor_agent.py:283](../../../agents/position_monitor_agent.py#L283):
```python
        trading_status = status.status_of(symbol)
```

- [ ] **Step 4: market_data_agent.py**

[market_data_agent.py:31](../../../agents/market_data_agent.py#L31):
```python
            if status.is_disabled(s.symbol):
```

- [ ] **Step 5: Проверить сбор/импорт**

Run: `python -c "import agents.signal_agent, agents.execution_agent, agents.position_monitor_agent, agents.market_data_agent; print('agents import ok')"`
Expected: `agents import ok`.

- [ ] **Step 6: Commit**

```bash
git add agents/signal_agent.py agents/execution_agent.py agents/position_monitor_agent.py agents/market_data_agent.py
git commit -m "refactor(trading_status): миграция агентов на сервис (B1)"
```

---

## Task 4: Миграция web

**Files:**
- Modify: `web/app.py`, `web/api_routes.py`

- [ ] **Step 1: web/app.py — `set_active_strategy`**

[web/app.py:192](../../../web/app.py#L192): заменить `from settings import GlobalValues, Dictionary, TF_MAP` на `from settings import GlobalValues, TF_MAP` + добавить `from trading_status import status`.
[web/app.py:215](../../../web/app.py#L215):
```python
        if not status.has(symbol):
```
Заменить цикл [web/app.py:235-238](../../../web/app.py#L235):
```python
        # Активируем только выбранный символ; позиции со статусом OPEN не трогаем.
        status.activate_only(symbol)
```

- [ ] **Step 2: web/app.py — `set_trading_status`**

[web/app.py:276](../../../web/app.py#L276): заменить `from settings import Dictionary` на `from trading_status import status`.
[web/app.py:280-281](../../../web/app.py#L280):
```python
        if status.has(symbol):
            status.set_status(symbol, status_value)
```
> ВНИМАНИЕ: локальная переменная называется `status` (из `cmd.get("status", 3)`) — она конфликтует с импортом сервиса `status`. Переименовать локальную в `status_value`: на [web/app.py:279](../../../web/app.py#L279) `status_value = cmd.get("status", 3)` и в payload события ниже использовать `status_value`. Проверить весь блок `elif action == "set_trading_status"` на использование старого имени.

- [ ] **Step 3: web/api_routes.py**

[api_routes.py:193](../../../web/api_routes.py#L193):
```python
    from trading_status import status
    return {"symbols": status.symbols()}
```
(Заменить локальный `from settings import Dictionary`/`Dictionary.symbolTradingStatus.keys()` соответственно.)

[api_routes.py:663-666](../../../web/api_routes.py#L663) в `set_trading_status`:
```python
    from trading_status import status
    if not status.has(req.symbol):
        raise HTTPException(status_code=404, detail=f"Символ {req.symbol} не найден")
    status.set_status(req.symbol, req.status)
```

[api_routes.py:677-678](../../../web/api_routes.py#L677) в `get_trading_status`:
```python
    from trading_status import status
    return {"status": status.snapshot()}
```

[api_routes.py:728](../../../web/api_routes.py#L728): заменить `if symbol not in Dictionary.symbolTradingStatus:` на:
```python
    from trading_status import status
    if not status.has(symbol):
```
(Если в этой функции `Dictionary` используется и для другого — оставить его импорт; иначе убрать.)

- [ ] **Step 4: Проверить сбор/импорт**

Run: `python -c "import web.app, web.api_routes; print('web import ok')"`
Expected: `web import ok`.
Run: `python -m pytest -q`
Expected: прежние тесты зелёные (208 passed, 20 skipped, 1 xfailed) + 13 новых trading_status = **221 passed, 20 skipped, 1 xfailed**.

- [ ] **Step 5: Commit**

```bash
git add web/app.py web/api_routes.py
git commit -m "refactor(trading_status): миграция web (app/api_routes) на сервис (B1)"
```

---

## Task 5: Удалить symbolTradingStatus из settings.py

**Files:**
- Modify: `settings.py`

- [ ] **Step 1: Подтвердить отсутствие ссылок**

Run (через инструмент Grep или): `python -m pytest -q` уже зелёный. Затем поиск по проекту строки `symbolTradingStatus` — должны остаться только: определение в `settings.py` и (исторически) ни одного в коде. Любая оставшаяся ссылка вне settings.py — мигрировать перед удалением.

- [ ] **Step 2: Удалить словарь из settings.Dictionary**

Удалить блок `symbolTradingStatus = { ... }` из [settings.py](../../../settings.py#L41) (строки определения внутри класса `Dictionary`). Остальные члены `Dictionary` (`symbolExtremumStatus`, `symbolStopLossValue`, `symbolDefaultSpread`, `indicatorStatus`) НЕ трогать.

- [ ] **Step 3: Финальная проверка**

Run: `python -c "import main; print('ok')"` → `ok`
Run (поиск висячих ссылок): убедиться, что `symbolTradingStatus` больше не встречается нигде в `.py` (кроме, возможно, комментариев). 
Run: `python -m pytest -q`
Expected: **221 passed, 20 skipped, 1 xfailed**, 0 ошибок сбора.

- [ ] **Step 4: Commit**

```bash
git add settings.py
git commit -m "refactor(trading_status): удалить symbolTradingStatus из settings — источник в trading_status (B1)"
```

---

## Self-Review (автор плана)

- **Покрытие спеки:** сервис+константы+seed → Task 1; таблица миграции call-sites спеки → Tasks 2-4 (все 18 строк покрыты: main, streams×2, active_state×2, app×3, api_routes×4, signal, execution×2, position_monitor×2, market_data); удаление словаря → Task 5; тесты → Task 1. ✔
- **Согласованность типов/имён:** методы (`has/status_of/is_*/mark_open/mark_allowed/set_status/activate_only/sync_enabled/active_symbols/symbols/snapshot`) определены в Task 1 и используются в Tasks 2-4 без расхождений. Константы `ALLOWED/OPEN/DISABLED` едины.
- **Ловушка имён:** в `web/app.py` локальная `status` конфликтует с импортом сервиса — Task 4 Step 2 явно требует переименовать локальную в `status_value`. (В `api_routes.set_trading_status` параметр — `req.status`, конфликта нет.)
- **Порядок безопасности:** словарь в settings удаляется ПОСЛЕДНИМ (Task 5), все промежуточные шаги оставляют приложение импортируемым и тесты зелёными.
- **Плейсхолдеры:** seed-литерал приведён полностью (23 символа); код всех методов и тестов приведён целиком. Нет TODO/TBD.
