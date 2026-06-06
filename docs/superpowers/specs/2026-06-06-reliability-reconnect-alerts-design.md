# Reliability: MT5-реконнект + Telegram-алерты — Design

**Дата:** 2026-06-06
**Статус:** утверждён (brainstorming)
**Трек:** валидация forward-edge — предусловие накопления трека (бот переживает месяцы unattended). Слайс A+B (реконнект + алерты); health/watchdog (C) — отдельно.

## Цель

Чтобы бот мог копить forward-трек месяцами без присмотра: (A) **авто-реконнект MT5** при разрыве и (B) **Telegram-алерты** на разрыв/восстановление/ошибки агентов и старт. Без этого после первого сбоя MT5 бот вечно ретраит с ERROR и трек не набирается, а оператор об этом не знает.

## Текущее состояние (факты)

- `BaseAgent.start()` уже ловит исключения `run()`, эмитит `AGENT_STATUS=error`, спит 5с и продолжает цикл (базовая устойчивость к транзиентным ошибкам).
- `MarketDataAgent` детектит разрыв (`mt5.terminal_info()` → None) и эмитит `MT5_DISCONNECTED` **на каждом poll (~10с) пока соединения нет**, `MT5_CONNECTED` при наличии. E4-поведение пинновано тестами — НЕ трогаем.
- **НИКТО не пере-инициализирует MT5** — реконнекта нет.
- `TelegramAgent` заскаффолжен: есть `EventType.TELEGRAM_SENT`, `TELEGRAM_BOT_TOKEN` в `account.py`. Реализации нет.
- `MT5Auth` (`authenticator.py`) инкапсулирует `initialize_connection()` (+ опц. `MT5_PATH`/креды) и `login()`.
- `EventBus.subscribe(event_type, async_handler)` — push-модель, wildcard `market.*`/`*`.

## Не-цели (отдельные слайсы)

- Обогащённый `/health` + per-agent staleness-watchdog (часть C).
- Email/SMS-каналы, периодический daily-heartbeat.
- Процесс-супервизор (рестарт всего процесса) — уже NSSM в `docs/ops/provisioning-runbook.md`.

## Архитектура

Три аддитивных юнита + проводка. Боевой путь агентов не меняется.

### 1. `MT5Auth.reconnect()` (`authenticator.py`, +метод)

```python
def reconnect(self) -> bool: ...
```
Повторно вызывает `initialize_connection()` + `login()`; ловит исключения (включая `ConnectionError` из initialize_connection); возвращает `True` при успешном логине, иначе `False`. Не кидает.

### 2. `ConnectionAgent` (`agents/connection_agent.py`, новый)

Владелец здоровья соединения. Конструктор принимает `mt5_auth` (инстанс `MT5Auth`) + `poll_interval`.

`run()` (одна итерация, в цикле `BaseAgent.start()`):
- `info = mt5.terminal_info()`; `connected = info is not None`.
- **Переход connected→down:** `self._connected=False`, эмит `MT5_DISCONNECTED`, лог, метрика `disconnects += 1`.
- **Если down:** попытка `mt5_auth.reconnect()`; `reconnect_attempts += 1`; при успехе → `self._connected=True`, эмит `MT5_CONNECTED`, лог; иначе sleep по **экспоненциальному backoff** (5→10→30→60с, cap 60), сбрасывается при восстановлении.
- **Если up (и был up):** обычный `poll_interval`.
- Метрики: `connected` (bool), `disconnects`, `reconnect_attempts`.
- emit-статусы через `emit_status` (RUNNING при попытке реконнекта, IDLE в норме).

Состояние `_connected` инициализируется `True` (на старте main.py уже залогинен). Backoff-состояние — поле агента.

### 3. `TelegramAgent` (`agents/telegram_agent.py`, новый)

Реализация заскаффолженного. Конструктор: `bus`, опц. `sender` (async callable `(text)->None`; дефолт — ptb-backed), читает `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` из env.

- **Подписки** (в `__init__` или setup): `bus.subscribe("market.mt5_disconnected", h)`, `..._connected`, `bus.subscribe("agent.status", h)` (или соответствующий тип `AGENT_STATUS`). Хендлеры — async.
- **Дедуп по переходам:** `_last_state: dict[str,str]` по ключу (`"mt5"`, имя агента). Сообщение только при смене состояния:
  - `MT5_DISCONNECTED`: если `_last_state["mt5"] != "down"` → алерт «⚠️ MT5 disconnected», ставим `"down"`.
  - `MT5_CONNECTED`: если было `"down"` → алерт «✅ MT5 reconnected», ставим `"up"`.
  - `AGENT_STATUS`: при `status=="error"` и `_last_state[agent] != "error"` → алерт «⚠️ Agent <name> error: <detail>», ставим `"error"`; при возврате в idle/running из error → опц. «✅ recovered», ставим `"ok"`.
  - ⚠️ **Guard от петли:** игнорировать `AGENT_STATUS` где `agent == self.name` (TelegramAgent сам эмитит `AGENT_STATUS` через `emit_status` и `TELEGRAM_SENT` — нельзя алертить на себя, иначе обратная связь).
- **Startup-ping:** в `run()` при первом запуске (флаг `_started`) → «🟢 Bot started on <host>» один раз.
- **send:** через `sender`; при отсутствии token/chat_id → `sender` не вызывается (graceful no-op, агент «выключен»). После успешной отправки — эмит `TELEGRAM_SENT`.
- `run()`: агент событийный; основная работа в хендлерах. `run()` делает startup-ping (раз) и затем `await asyncio.sleep(long)` (idle), чтобы вписаться в `BaseAgent.start()`-цикл.
- Дефолтный ptb-sender: `from telegram import Bot; await Bot(token).send_message(chat_id=chat_id, text=text)` — в отдельной функции, не вызывается в тестах (инъекция fake).

### 4. Проводка `main.py`

- Создать `ConnectionAgent("Connection", bus, mt5_auth, poll_interval=...)` (передать существующий `mt5_auth`).
- Создать `TelegramAgent("Telegram", bus)`.
- Добавить оба в список `agents`.

## Краевые случаи / ошибки

- Реконнект не удаётся долго → ConnectionAgent продолжает попытки с backoff (cap 60с), эмитит `MT5_DISCONNECTED` один раз (на переходе); Telegram алертит один раз.
- ptb-отправка падает (сеть/неверный токен) → ловится в хендлере (бус и так ловит исключения хендлеров), лог; не роняет агент.
- Нет token/chat_id → TelegramAgent no-op, без ошибок.
- Дубли `MT5_DISCONNECTED` от MarketDataAgent — гасятся дедупом по переходам.

## Тестирование (без сети/живого MT5)

- **`MT5Auth.reconnect`** — фейк `mt5` (initialize/login успех и провал) → корректный `bool`, не кидает.
- **`ConnectionAgent`** — фейк `mt5.terminal_info` (truthy→None→truthy) + фейк `mt5_auth.reconnect` (False→True): один `MT5_DISCONNECTED` на переходе; backoff-попытки растут; успех → `MT5_CONNECTED`; метрики `disconnects`/`reconnect_attempts`. Харнесс `tests/execution/fakes` (FakeBus/FakeMT5) + новая фикстура.
- **`TelegramAgent`** — инъектируемый fake-sender (список сообщений): два `MT5_DISCONNECTED` → один алерт; `MT5_CONNECTED` → recovery; `AGENT_STATUS(error)` → алерт, повтор → без дубля; recovery агента → опц. алерт; startup → ping; **без token/chat_id → sender не вызван**; эмит `TELEGRAM_SENT` после отправки.
- Все тесты — без живого терминала; ptb не импортируется в тестовом пути (sender инъектируется).

## Файловая структура

- **Modify:** `authenticator.py` (+`reconnect`), `main.py` (проводка 2 агентов), `core/events.py` (если нужен `TELEGRAM_SENT` — уже есть; проверить наличие нужных типов).
- **Create:** `agents/connection_agent.py`, `agents/telegram_agent.py`.
- **Create:** `tests/execution/test_connection_agent.py`, `tests/execution/test_telegram_agent.py` (+ фикстуры в conftest при необходимости), `tests/test_authenticator_reconnect.py` (или в tests/execution).
- **Reuse:** `tests/execution/fakes.py` (FakeBus, FakeMT5 — расширить terminal_info-сценарием при необходимости).

## Критерии готовности

- `MT5Auth.reconnect()` реализован и покрыт тестом.
- `ConnectionAgent` детектит разрыв, реконнектит с backoff, эмитит события, покрыт тестами.
- `TelegramAgent` шлёт алерты на переходы (дедуп), startup-ping, graceful no-op без конфига; покрыт тестами.
- Оба агента в `main.py`.
- Полный прогон зелёный (прежние 571 + новые); деньги-путь и E4-поведение MarketDataAgent не изменены.

## Связанные документы

- `docs/superpowers/specs|plans/2026-06-06-forward-track-record*` — зачем нужен длительный unattended-прогон.
- `docs/ops/provisioning-runbook.md` — NSSM (процесс-супервизор) + env (`MT5_PATH`, токены).
- `agents/market_data_agent.py` — существующий детект `MT5_DISCONNECTED` (не трогаем).
