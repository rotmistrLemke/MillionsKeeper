# Reliability: MT5-реконнект + Telegram-алерты Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Бот переживает месяцы unattended: авто-реконнект MT5 при разрыве + Telegram-алерты на разрыв/восстановление/ошибки/старт.

**Architecture:** Три аддитивных юнита — `MT5Auth.reconnect()`, `ConnectionAgent` (детект+реконнект с backoff), `TelegramAgent` (алерты на переходы, дедуп, graceful no-op, guard от петли) — плюс проводка в `main.py`. Боевой путь агентов и E4-MarketDataAgent не меняем.

**Tech Stack:** Python 3.11, asyncio, pytest, python-telegram-bot (только в проде; в тестах sender инъектируется).

**⚠️ Дисциплина:** TDD. Трейлер каждого коммита: пустая строка, затем `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Агенты делают `import MetaTrader5 as mt5` ЛЕНИВО внутри `run()` (паттерн MarketDataAgent) — тесты патчат `sys.modules['MetaTrader5']`.

---

## File Structure

- **Modify:** `authenticator.py` (+`reconnect`), `main.py` (проводка 2 агентов), `tests/execution/fakes.py` (+`FakeBus.subscribe`).
- **Create:** `agents/connection_agent.py`, `agents/telegram_agent.py`.
- **Create:** `tests/test_authenticator_reconnect.py`, `tests/execution/test_connection_agent.py`, `tests/execution/test_telegram_agent.py`.

---

## Task 1: `MT5Auth.reconnect()`

**Files:**
- Modify: `authenticator.py`
- Create: `tests/test_authenticator_reconnect.py`

- [ ] **Step 1: Написать тест `tests/test_authenticator_reconnect.py`**

```python
"""MT5Auth.reconnect: повторный initialize+login, не кидает, возвращает bool."""
import types
from types import SimpleNamespace


def _fake_mt5(*, init_ok=True, login_ok=True):
    m = types.ModuleType("MetaTrader5")
    m.initialize = lambda **kw: init_ok
    m.login = lambda **kw: login_ok
    m.last_error = lambda: "fake error"
    m.shutdown = lambda: None
    return m


def _make_auth(monkeypatch, fake):
    import authenticator
    monkeypatch.setattr(authenticator, "mt5", fake)
    # __init__ зовёт initialize_connection() → нужен init_ok=True у fake при создании
    return authenticator.MT5Auth({"login": 1, "password": "x", "server": "S"})


def test_reconnect_success(monkeypatch):
    fake = _fake_mt5(init_ok=True, login_ok=True)
    auth = _make_auth(monkeypatch, fake)
    assert auth.reconnect() is True


def test_reconnect_login_fails(monkeypatch):
    fake = _fake_mt5(init_ok=True, login_ok=False)
    auth = _make_auth(monkeypatch, fake)
    assert auth.reconnect() is False


def test_reconnect_initialize_fails_no_raise(monkeypatch):
    auth = _make_auth(monkeypatch, _fake_mt5(init_ok=True, login_ok=True))
    # теперь initialize начинает падать → initialize_connection кинет ConnectionError,
    # reconnect должен поймать и вернуть False (не пробросить)
    import authenticator
    bad = _fake_mt5(init_ok=False, login_ok=True)
    monkeypatch.setattr(authenticator, "mt5", bad)
    assert auth.reconnect() is False
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/test_authenticator_reconnect.py -q`
Expected: FAIL (`AttributeError: 'MT5Auth' object has no attribute 'reconnect'`).

- [ ] **Step 3: Реализовать — добавить метод `reconnect` в класс `MT5Auth` (`authenticator.py`)**

Вставить новый метод сразу ПОСЛЕ метода `login` (перед `logout`):

```python
    def reconnect(self) -> bool:
        """Повторная инициализация + логин (для ConnectionAgent). Не кидает; True при успехе."""
        try:
            self.initialize_connection()
            return bool(self.login())
        except Exception as e:
            print(f"MT5 reconnect failed: {e}")
            return False
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/test_authenticator_reconnect.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add authenticator.py tests/test_authenticator_reconnect.py
git commit -m "feat(reliability): MT5Auth.reconnect() + тесты"
```
(трейлер)

---

## Task 2: `ConnectionAgent`

**Files:**
- Create: `agents/connection_agent.py`
- Create: `tests/execution/test_connection_agent.py`

- [ ] **Step 1: Написать тест `tests/execution/test_connection_agent.py`**

```python
"""ConnectionAgent: детект разрыва, реконнект с backoff, события MT5_*."""
import sys
import types
from types import SimpleNamespace

from core.events import EventType
from tests.execution.fakes import FakeBus


class _FakeMT5Conn(types.ModuleType):
    def __init__(self, seq):
        super().__init__("MetaTrader5")
        self._seq = list(seq)

    def terminal_info(self):
        # каждый вызов отдаёт следующий из seq; после конца — None
        return self._seq.pop(0) if self._seq else None


class _FakeAuth:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def reconnect(self):
        self.calls += 1
        return self._results.pop(0) if self._results else True


def _counts(bus, etype):
    return sum(1 for e in bus.events if e.type == etype)


async def test_disconnect_then_reconnect(monkeypatch):
    import agents.connection_agent as ca_mod
    # terminal_info всегда None — восстановление определяется успехом auth.reconnect()
    monkeypatch.setitem(sys.modules, "MetaTrader5", _FakeMT5Conn([None, None, None]))
    auth = _FakeAuth([False, False, True])
    agent = ca_mod.ConnectionAgent("Conn", FakeBus(), auth,
                                   poll_interval=0, base_backoff=0, max_backoff=0)

    await agent.run()  # None → переход down: MT5_DISCONNECTED, reconnect→False
    await agent.run()  # уже down: без нового DISCONNECTED, reconnect→False
    await agent.run()  # reconnect→True: MT5_CONNECTED

    assert _counts(agent.bus, EventType.MT5_DISCONNECTED) == 1
    assert _counts(agent.bus, EventType.MT5_CONNECTED) == 1
    assert agent.metrics["disconnects"] == 1
    assert agent.metrics["reconnect_attempts"] == 3
    assert auth.calls == 3
    assert agent.metrics["connected"] is True


async def test_stays_connected_no_events(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", _FakeMT5Conn([object(), object()]))
    auth = _FakeAuth([])
    import agents.connection_agent as ca_mod
    agent = ca_mod.ConnectionAgent("Conn", FakeBus(), auth, poll_interval=0)

    await agent.run()
    await agent.run()
    # был connected на старте и остаётся → ни одного MT5_* и нет попыток реконнекта
    assert _counts(agent.bus, EventType.MT5_DISCONNECTED) == 0
    assert _counts(agent.bus, EventType.MT5_CONNECTED) == 0
    assert auth.calls == 0
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/execution/test_connection_agent.py -q`
Expected: FAIL (ModuleNotFoundError: agents.connection_agent).

- [ ] **Step 3: Реализовать `agents/connection_agent.py`**

```python
"""ConnectionAgent — здоровье MT5-соединения: детект разрыва + авто-реконнект."""
import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType


class ConnectionAgent(BaseAgent):
    """Поллит mt5.terminal_info(); при разрыве реконнектит через MT5Auth с backoff.
    Эмитит MT5_DISCONNECTED/MT5_CONNECTED на ПЕРЕХОДАХ. Боевой путь не трогает."""
    description = "Здоровье MT5: детект разрыва + авто-реконнект"

    def __init__(self, name: str, bus: EventBus, mt5_auth, poll_interval: float = 15.0,
                 base_backoff: float = 5.0, max_backoff: float = 60.0):
        super().__init__(name, bus)
        self.mt5_auth = mt5_auth
        self.poll_interval = poll_interval
        self._base_backoff = base_backoff
        self._max_backoff = max_backoff
        self._backoff = base_backoff
        self._connected = True  # на старте main.py уже залогинен
        self.metrics["connected"] = True
        self.metrics["disconnects"] = 0
        self.metrics["reconnect_attempts"] = 0

    async def run(self):
        import MetaTrader5 as mt5

        if mt5.terminal_info() is not None:
            # соединение есть
            self._backoff = self._base_backoff
            self.metrics["connected"] = True
            self._connected = True
            await self.emit_status(AgentStatus.IDLE, "MT5 ок")
            await asyncio.sleep(self.poll_interval)
            return

        # соединения нет
        if self._connected:
            self._connected = False
            self.metrics["disconnects"] += 1
            await self.emit(EventType.MT5_DISCONNECTED, {})

        self.metrics["connected"] = False
        await self.emit_status(AgentStatus.RUNNING, "Реконнект MT5…")
        self.metrics["reconnect_attempts"] += 1
        ok = self.mt5_auth.reconnect()

        if ok:
            self._connected = True
            self._backoff = self._base_backoff
            self.metrics["connected"] = True
            await self.emit(EventType.MT5_CONNECTED, {})
            await self.emit_status(AgentStatus.IDLE, "MT5 восстановлен")
            await asyncio.sleep(self.poll_interval)
        else:
            await self.emit_status(AgentStatus.ERROR, "MT5 реконнект не удался")
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, self._max_backoff)
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/execution/test_connection_agent.py -q`
Expected: 2 passed. Падение → STOP, report.

- [ ] **Step 5: Commit**

```bash
git add agents/connection_agent.py tests/execution/test_connection_agent.py
git commit -m "feat(reliability): ConnectionAgent (детект разрыва + реконнект с backoff) + тесты"
```
(трейлер)

---

## Task 3: `TelegramAgent`

**Files:**
- Modify: `tests/execution/fakes.py` (+`FakeBus.subscribe`)
- Create: `agents/telegram_agent.py`
- Create: `tests/execution/test_telegram_agent.py`

- [ ] **Step 1: Добавить `subscribe`/`unsubscribe` в `FakeBus` (`tests/execution/fakes.py`)**

Найти класс `FakeBus` и добавить методы (после `publish_sync`):

```python
    def subscribe(self, event_type, handler):
        self.subscriptions = getattr(self, "subscriptions", [])
        self.subscriptions.append((event_type, handler))

    def unsubscribe(self, event_type, handler):
        subs = getattr(self, "subscriptions", [])
        self.subscriptions = [(t, h) for (t, h) in subs if h is not handler]
```

- [ ] **Step 2: Написать тест `tests/execution/test_telegram_agent.py`**

```python
"""TelegramAgent: алерты на переходы, дедуп, guard от петли, graceful no-op."""
from core.events import Event, EventType
from tests.execution.fakes import FakeBus


def _make(monkeypatch, *, token="T", chat_id="C"):
    import agents.telegram_agent as tg_mod
    sent = []

    async def fake_sender(text):
        sent.append(text)

    agent = tg_mod.TelegramAgent("Telegram", FakeBus(), sender=fake_sender,
                                 token=token, chat_id=chat_id)
    return agent, sent


def _ev(etype, payload):
    return Event(type=etype, source="t", payload=payload)


async def test_mt5_disconnect_dedup_then_recovery(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))  # дубль
    assert len(sent) == 1 and "disconnect" in sent[0].lower()
    await agent._on_mt5_connected(_ev(EventType.MT5_CONNECTED, {}))
    assert len(sent) == 2 and "reconnect" in sent[1].lower()


async def test_agent_error_dedup(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_agent_status(_ev(EventType.AGENT_STATUS,
                                     {"agent": "Execution", "status": "error", "detail": "boom"}))
    await agent._on_agent_status(_ev(EventType.AGENT_STATUS,
                                     {"agent": "Execution", "status": "error", "detail": "boom"}))
    assert len(sent) == 1 and "Execution" in sent[0]


async def test_agent_status_self_guard(monkeypatch):
    agent, sent = _make(monkeypatch)
    # событие со СВОИМ именем → игнор (нет петли)
    await agent._on_agent_status(_ev(EventType.AGENT_STATUS,
                                     {"agent": "Telegram", "status": "error", "detail": "x"}))
    assert sent == []


async def test_noop_without_config(monkeypatch):
    agent, sent = _make(monkeypatch, token="", chat_id="")
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))
    assert sent == []  # sender не вызван — агент выключен


async def test_telegram_sent_emitted(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_mt5_disconnected(_ev(EventType.MT5_DISCONNECTED, {}))
    assert any(e.type == EventType.TELEGRAM_SENT for e in agent.bus.events)


async def test_startup_ping_once(monkeypatch):
    import asyncio
    agent, sent = _make(monkeypatch)
    # run() делает ping один раз, затем долгий sleep — гоняем с таймаутом
    try:
        await asyncio.wait_for(agent.run(), timeout=0.05)
    except asyncio.TimeoutError:
        pass
    assert any("start" in s.lower() for s in sent)
```

- [ ] **Step 3: Прогон — провал**

Run: `python -m pytest tests/execution/test_telegram_agent.py -q`
Expected: FAIL (ModuleNotFoundError: agents.telegram_agent).

- [ ] **Step 4: Реализовать `agents/telegram_agent.py`**

```python
"""TelegramAgent — алерты о здоровье (MT5 up/down, ошибки агентов, старт).
Дедуп по переходам состояния; graceful no-op без token/chat_id; sender инъектируем."""
import asyncio
import os
import socket

from agents.base_agent import BaseAgent
from core.event_bus import EventBus
from core.events import EventType


def _default_ptb_sender(token: str, chat_id: str):
    async def _send(text: str):
        from telegram import Bot
        await Bot(token).send_message(chat_id=chat_id, text=text)
    return _send


class TelegramAgent(BaseAgent):
    """Подписан на MT5_*/AGENT_STATUS; шлёт Telegram только на смену состояния."""
    description = "Telegram-алерты о здоровье бота"

    def __init__(self, name: str, bus: EventBus, *, sender=None,
                 token: str = None, chat_id: str = None):
        super().__init__(name, bus)
        self._token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        self._sender = sender  # async (text)->None; None → дефолтный ptb
        self._last_state: dict[str, str] = {}
        self._started = False
        self._subscribed = False

    def _enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    async def _send(self, text: str) -> None:
        if not self._enabled():
            return
        sender = self._sender or _default_ptb_sender(self._token, self._chat_id)
        try:
            await sender(text)
        except Exception as e:
            self._logger.warning(f"Telegram send failed: {e}")
            return
        await self.emit(EventType.TELEGRAM_SENT, {"text": text})

    async def _on_mt5_disconnected(self, ev) -> None:
        if self._last_state.get("mt5") != "down":
            self._last_state["mt5"] = "down"
            await self._send("⚠️ MT5 disconnected — пытаюсь реконнект")

    async def _on_mt5_connected(self, ev) -> None:
        if self._last_state.get("mt5") == "down":
            self._last_state["mt5"] = "up"
            await self._send("✅ MT5 reconnected — соединение восстановлено")
        else:
            self._last_state.setdefault("mt5", "up")

    async def _on_agent_status(self, ev) -> None:
        agent = ev.payload.get("agent")
        if agent == self.name:
            return  # guard: не алертим на собственный статус (петля)
        st = ev.payload.get("status")
        if st == "error" and self._last_state.get(agent) != "error":
            self._last_state[agent] = "error"
            await self._send(f"⚠️ Agent {agent} error: {ev.payload.get('detail', '')}")
        elif st in ("idle", "running") and self._last_state.get(agent) == "error":
            self._last_state[agent] = "ok"
            await self._send(f"✅ Agent {agent} recovered")

    def _subscribe(self) -> None:
        if self._subscribed:
            return
        self.bus.subscribe(EventType.MT5_DISCONNECTED, self._on_mt5_disconnected)
        self.bus.subscribe(EventType.MT5_CONNECTED, self._on_mt5_connected)
        self.bus.subscribe(EventType.AGENT_STATUS, self._on_agent_status)
        self._subscribed = True

    async def run(self):
        self._subscribe()
        if not self._started:
            self._started = True
            host = os.environ.get("HOST") or socket.gethostname()
            await self._send(f"🟢 Bot started on {host}")
        await asyncio.sleep(3600)
```

- [ ] **Step 5: Прогон — зелёно**

Run: `python -m pytest tests/execution/test_telegram_agent.py -q`
Expected: 6 passed. Падение → STOP, report.

- [ ] **Step 6: Commit**

```bash
git add agents/telegram_agent.py tests/execution/fakes.py tests/execution/test_telegram_agent.py
git commit -m "feat(reliability): TelegramAgent (алерты на переходы, дедуп, guard, no-op) + тесты"
```
(трейлер)

---

## Task 4: Проводка `main.py` + полный прогон + память

**Files:**
- Modify: `main.py`
- Modify: `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md` (вне git)

- [ ] **Step 1: Импорт двух агентов в `main.py`**

В блоке импортов агентов (после `from agents.account_agent import AccountAgent`) добавить:

```python
    from agents.connection_agent     import ConnectionAgent
    from agents.telegram_agent       import TelegramAgent
```

- [ ] **Step 2: Добавить агенты в список `agents`**

В литерал списка `agents = [ ... ]` добавить две строки (перед `anomaly_agent,`):

```python
        ConnectionAgent("Connection", bus, mt5_auth, poll_interval=15.0),
        TelegramAgent("Telegram",     bus),
```

(`mt5_auth` уже создан выше в `main()` — строка `mt5_auth = MT5Auth(...)`.)

- [ ] **Step 3: Smoke — импорт main без запуска**

Run: `python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('main.py parse OK')"`
Expected: `main.py parse OK`. (Полный `import main` инициализирует MT5/агентов — не запускаем; проверяем синтаксис.)

Также проверить импорт новых агентов:
Run: `python -c "from agents.connection_agent import ConnectionAgent; from agents.telegram_agent import TelegramAgent; print('agents import OK')"`
Expected: `agents import OK`.

- [ ] **Step 4: Полный прогон (регрессия)**

Run: `python -m pytest -q`
Expected: прежние 571 passed + новые (3 + 2 + 6 = 11) = **582 passed, 3 xfailed**. Записать фактические числа. Падение незелёных → STOP, report (особенно tests/execution/ и tests/test_macd_atr.py — порядок импорта).

- [ ] **Step 5: Commit (main.py)**

```bash
git add main.py
git commit -m "feat(reliability): проводка ConnectionAgent + TelegramAgent в main.py"
```
(трейлер)

- [ ] **Step 6: Обновить память** `project_millionskeeper.md`:
- В «Тесты»: добавить `test_connection_agent.py` (2), `test_telegram_agent.py` (6), `test_authenticator_reconnect.py` (3).
- «Текущий прогон»: обновить число passed.
- В запись монетизации/forward-edge: отметить, что **reliability-слайс A+B сделан** (ConnectionAgent авто-реконнект MT5 + TelegramAgent алерты; env `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`); осталось C (health/watchdog) + MyFXBook.
- Пути спеки/плана `docs/superpowers/specs|plans/2026-06-06-reliability-reconnect-alerts*`.

(Память вне git.)

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** `MT5Auth.reconnect` → Task 1; `ConnectionAgent` (детект/backoff/события/метрики) → Task 2; `TelegramAgent` (переходы/дедуп/guard/no-op/startup/TELEGRAM_SENT) → Task 3; проводка main.py + регрессия + память → Task 4. ✅
- **Плейсхолдеры:** нет — весь код приведён целиком; команды и ожидания явные. ✅
- **Согласованность сигнатур:** `MT5Auth.reconnect()->bool`; `ConnectionAgent(name,bus,mt5_auth,poll_interval,base_backoff,max_backoff)` с `.metrics[connected/disconnects/reconnect_attempts]`; `TelegramAgent(name,bus,*,sender,token,chat_id)` с хендлерами `_on_mt5_disconnected/_on_mt5_connected/_on_agent_status` и `_send`; `FakeBus.subscribe`. Имена событий: `MT5_DISCONNECTED`/`MT5_CONNECTED`/`AGENT_STATUS`/`TELEGRAM_SENT` (сверены с core/events.py). ✅
- **Тестируемость:** ленивый `import MetaTrader5` в ConnectionAgent.run() (патч sys.modules); sender инъекция в TelegramAgent (без сети/ptb); backoff 0 в тестах (без реальных пауз). ✅
- **Изоляция:** деньги-путь и E4-MarketDataAgent не изменяются; guard от петли AGENT_STATUS на своё имя. ✅
- **Числа кейсов:** 3 + 2 + 6 = 11. ✅
