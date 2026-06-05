# Сервис trading_status — дизайн (слайс B1)

**Дата:** 2026-06-01
**Статус:** дизайн одобрен, готов к плану реализации
**Слайс:** B1 — первый шаг рефакторинга мутируемого глобального состояния `settings.py`.

---

## Цель и контекст

`settings.py` держит мутируемое глобальное состояние. `Dictionary.symbolTradingStatus` — словарь «статус торговли по символу», который мутируется напрямую из множества мест (агенты, web, миграция потоков) сырыми числовыми кодами. Это глобальное изменяемое состояние: трудно тестировать, магические числа разбросаны по коду, логика «активировать только этот символ» продублирована.

B1 инкапсулирует `symbolTradingStatus` за маленьким протестированным сервисом с доменным API. Поведение сохраняется 1:1; новые тесты расширяют сетку слайса A в зону, прилегающую к агентам.

**Модель исполнения (важно для оценки риска):** всё приложение работает в ОДНОМ asyncio event loop ([main.py](../../../main.py): `asyncio.gather(bus.run(), *agents, server.serve())`, uvicorn `loop="asyncio"`). Истинной межпоточной параллельности нет — мутации кооперативны. Поэтому B1 — это про тестируемость и чистоту, а не про починку живой гонки. `RLock` добавляется как дешёвая страховка (согласованно со `streams.StreamRegistry`).

**Среда тестов:** CI-ready, как слайс A (без живого MT5; `trading_status.py` не импортирует MetaTrader5).

---

## Область

**Входит:** инкапсуляция `Dictionary.symbolTradingStatus`.

**Не входит:**
- `symbolStopLossValue` — мутируется в [trading.py:182](../../../trading.py#L182), но это отдельная семантика (стоп-лосс на символ). Кандидат на отдельный шаг.
- `symbolExtremumStatus`, `indicatorStatus` — объявлены в `settings.Dictionary`, но нигде не используются (мёртвый конфиг). Не трогаем.
- `symbolDefaultSpread` — read-only конфиг, остаётся в `settings.Dictionary`.
- `GlobalValues` — слайс B2 (отдельно).

---

## Семантика статусов

Сейчас — магические числа. Вводим именованные константы (значения сохраняются):

```python
ALLOWED  = 0   # разрешено торговать
OPEN     = 1   # позиция открыта — не входить повторно
DISABLED = 3   # выключено
```

---

## Архитектура

### Новый модуль `trading_status.py`

По образцу `streams.py`: модуль-владелец + синглтон-экземпляр.

```python
import threading

ALLOWED, OPEN, DISABLED = 0, 1, 3

# Seed-вселенная символов со стартовыми статусами — переезжает ДОСЛОВНО
# из бывшего settings.Dictionary.symbolTradingStatus.
_SEED: dict[str, int] = {
    "EURUSDrfd": 3, "NZDUSDrfd": 3, ...  # все символы, XAUUSDrfd: 0, #LCO: 0
}


class TradingStatusRegistry:
    def __init__(self, seed: dict[str, int] | None = None):
        self._status: dict[str, int] = dict(seed if seed is not None else _SEED)
        self._lock = threading.RLock()

    # ── Запросы ──
    def has(self, symbol: str) -> bool: ...
    def __contains__(self, symbol: str) -> bool: ...        # alias has()
    def status_of(self, symbol: str) -> int: ...            # .get(sym, DISABLED)
    def is_disabled(self, symbol: str) -> bool: ...         # status_of == DISABLED
    def is_open(self, symbol: str) -> bool: ...             # status_of == OPEN
    def is_allowed(self, symbol: str) -> bool: ...          # status_of == ALLOWED
    def symbols(self) -> list[str]: ...                     # list(keys)
    def active_symbols(self) -> list[str]: ...              # status != DISABLED
    def snapshot(self) -> dict[str, int]: ...               # КОПИЯ внутреннего dict

    # ── Мутации ──
    def mark_open(self, symbol: str) -> None: ...           # [sym] = OPEN
    def mark_allowed(self, symbol: str) -> None: ...        # [sym] = ALLOWED
    def set_status(self, symbol: str, value: int) -> None:  # сырой set (ws/api команды)
    def activate_only(self, symbol: str) -> None:           # sym→ALLOWED, прочие→DISABLED, пропуск OPEN
    def sync_enabled(self, enabled_symbols: set[str]) -> None:  # in set→ALLOWED иначе→DISABLED, пропуск OPEN


status = TradingStatusRegistry()
```

Все методы берут `self._lock`. `snapshot()` возвращает копию (не живую ссылку) — текущий `api_routes` возвращает сам dict наружу, что нежелательно; копия безопаснее и поведение по содержимому идентично.

### Изменение `settings.py`
Удаляем `symbolTradingStatus` из `Dictionary`. Остальные члены `Dictionary` (`symbolDefaultSpread`, `symbolStopLossValue`, неиспользуемые `symbolExtremumStatus`/`indicatorStatus`) остаются.

---

## Миграция call-sites (поведение 1:1)

| Файл:строка | Сейчас | Становится |
|---|---|---|
| [main.py:38](../../../main.py#L38) | `[s for s,v in symbolTradingStatus.items() if v!=3]` | `trading_status.status.active_symbols()` |
| [streams.py:269](../../../streams.py#L269) | `symbol not in symbolTradingStatus` | `not status.has(symbol)` |
| [streams.py:294-297](../../../streams.py#L294) | цикл `_sync_trading_status` (пропуск cur==1) | `status.sync_enabled(enabled_symbols)` |
| [active_state.py:35](../../../active_state.py#L35) | `symbol in symbolTradingStatus` | `status.has(symbol)` |
| [active_state.py:48-49](../../../active_state.py#L48) | цикл «0 для active иначе 3» (без пропуска OPEN) | `status.activate_only(active_symbol)` — см. примечание ниже |
| [web/app.py:215](../../../web/app.py#L215) | `symbol not in symbolTradingStatus` | `not status.has(symbol)` |
| [web/app.py:235-238](../../../web/app.py#L235) | цикл «0 для symbol иначе 3, пропуск 1» | `status.activate_only(symbol)` |
| [web/app.py:280-281](../../../web/app.py#L280) | `if symbol in: [symbol]=status` | `if status.has(symbol): status.set_status(symbol, st)` |
| [web/api_routes.py:193](../../../web/api_routes.py#L193) | `list(symbolTradingStatus.keys())` | `status.symbols()` |
| [web/api_routes.py:664-666](../../../web/api_routes.py#L664) | `not in` + `[sym]=req.status` | `status.has(...)` + `status.set_status(...)` |
| [web/api_routes.py:678](../../../web/api_routes.py#L678) | `{"status": symbolTradingStatus}` | `{"status": status.snapshot()}` |
| [web/api_routes.py:728](../../../web/api_routes.py#L728) | `symbol not in symbolTradingStatus` | `not status.has(symbol)` |
| [agents/signal_agent.py:65](../../../agents/signal_agent.py#L65) | `.get(symbol, 3)` | `status.status_of(symbol)` |
| [agents/position_monitor_agent.py:113-114](../../../agents/position_monitor_agent.py#L113) | `.get(sym)==1 ... [sym]=0` | `status.is_open(sym) ... status.mark_allowed(sym)` |
| [agents/position_monitor_agent.py:283](../../../agents/position_monitor_agent.py#L283) | `.get(symbol, 3)` | `status.status_of(symbol)` |
| [agents/market_data_agent.py:31](../../../agents/market_data_agent.py#L31) | `.get(s.symbol,3)==3` | `status.is_disabled(s.symbol)` |
| [agents/execution_agent.py:145](../../../agents/execution_agent.py#L145) | `.get(symbol, 3)` | `status.status_of(symbol)` |
| [agents/execution_agent.py:218](../../../agents/execution_agent.py#L218) | `[symbol]=1` | `status.mark_open(symbol)` |

Импорт во всех местах: `from trading_status import status` (или `import trading_status`).

---

## Тесты

`tests/test_trading_status.py` (pytest, без MT5):
- **seed:** свежий `TradingStatusRegistry()` имеет `status_of("XAUUSDrfd")==ALLOWED`, `status_of("EURUSDrfd")==DISABLED`, `status_of("#LCO")==ALLOWED`.
- **has / __contains__:** известный символ → True; неизвестный → False.
- **status_of default:** неизвестный символ → `DISABLED`.
- **mark_open / mark_allowed:** меняют статус символа; `is_open`/`is_allowed` отражают.
- **set_status:** ставит произвольное значение (в т.ч. сырое).
- **activate_only:** целевой → ALLOWED, остальные → DISABLED; символ со статусом OPEN остаётся OPEN (не сбрасывается).
- **sync_enabled:** символы из множества → ALLOWED, прочие → DISABLED; OPEN-символы не трогаются.
- **active_symbols:** возвращает все, кроме DISABLED.
- **snapshot:** возвращает копию — мутация результата не меняет внутреннее состояние.
- Тесты используют ИЗОЛИРОВАННЫЙ экземпляр `TradingStatusRegistry(seed={...})`, а не глобальный синглтон, чтобы не было протекания состояния между тестами.

---

## Краевые случаи и обработка ошибок

- `set_status` принимает сырое значение без валидации — сохраняет текущее поведение ws/api команд (`status = cmd.get("status", 3)`), где значение приходит извне.
- `status_of` возвращает `int` — сохраняет payload-совместимость (`signal_agent` кладёт результат в событие под ключом `trading_status`).
- Правило «не трогаем OPEN(1)» строго сохранено в `activate_only` и `sync_enabled` — это защищает символы с открытой позицией от сброса.
- Seed копируется дословно из старого литерала → стартовое поведение приложения не меняется.
- **Примечание про active_state:** [active_state.py:48-49](../../../active_state.py#L48) сейчас ставит `0/3` для всех символов БЕЗ пропуска `OPEN(1)`, тогда как `activate_only` пропускает OPEN. Это не строго 1:1, НО `active_state.load()` вызывается на старте ([main.py:65](../../../main.py#L65)), до открытия любых позиций, когда OPEN ни у кого нет → на практике эквивалентно и строго безопаснее (защищает открытые позиции, если порядок вызова когда-нибудь изменится).

---

## Связанные документы

- [streams.py](../../../streams.py) — образец паттерна (registry + singleton + RLock + `_sync_trading_status`, который B1 заменяет на `status.sync_enabled`)
- `docs/superpowers/specs/2026-05-31-strategy-test-harness-design.md` — слайс A (тест-сетка)
- Слайс B2 (будущий) — миграция `GlobalValues` → `streams`
