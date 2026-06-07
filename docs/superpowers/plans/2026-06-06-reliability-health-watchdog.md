# Reliability-C: /health + staleness-watchdog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Наблюдаемость зависших агентов: heartbeat в registry, обогащённый /health, WatchdogAgent эмитит AGENT_STALE → TelegramAgent алертит.

**Architecture:** Аддитивно. `core/health.build_report` (чистая) + heartbeat в `AgentRegistry`/`BaseAgent.start` + `/health` enrich + `WatchdogAgent` + событие `AGENT_STALE` + хендлер в TelegramAgent + проводка main.py. Боевая логика агентов не меняется.

**Tech Stack:** Python 3.11, asyncio, FastAPI, pytest.

**⚠️ Дисциплина:** TDD. Трейлер: пустая строка, затем `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

**⚠️ Поправка к спеке:** `expected_interval` захватывается ЛЕНИВО в `registry.heartbeat(name, expected_interval)` (вызывается из `start()`, где `poll_interval` уже установлен), а НЕ в `register()` (там подкласс ещё не выставил `poll_interval`).

---

## File Structure

- **Create:** `core/health.py`, `agents/watchdog_agent.py`, `tests/test_health_report.py`, `tests/test_agent_registry_heartbeat.py`, `tests/execution/test_watchdog_agent.py`.
- **Modify:** `core/agent_registry.py`, `agents/base_agent.py`, `web/app.py`, `core/events.py`, `agents/telegram_agent.py`, `tests/execution/test_telegram_agent.py`, `main.py`.

---

## Task 1: `core/health.py` — чистая агрегация

**Files:**
- Create: `core/health.py`, `tests/test_health_report.py`

- [ ] **Step 1: Написать тест `tests/test_health_report.py`**

```python
"""build_report: per-agent liveness + overall (чистая)."""
from datetime import datetime, timedelta
from core.agent_registry import AgentInfo
from core.health import build_report


def _info(name, *, status="idle", hb_age=None, interval=None, errors=0):
    i = AgentInfo(name, name)
    i.status = status
    i.expected_interval = interval
    i.error_count = errors
    i.last_heartbeat = None if hb_age is None else datetime(2026, 1, 1) - timedelta(seconds=hb_age)
    return i


NOW = datetime(2026, 1, 1)


def test_fresh_not_stale():
    rep = build_report([_info("A", hb_age=5, interval=10)], NOW)
    a = rep["agents"][0]
    assert a["stale"] is False and rep["overall"] == "ok"
    assert a["silent_sec"] == 5


def test_old_heartbeat_is_stale():
    # hb_age 40 > 3*10 → stale
    rep = build_report([_info("A", hb_age=40, interval=10)], NOW)
    assert rep["agents"][0]["stale"] is True and rep["overall"] == "degraded"


def test_no_interval_never_stale():
    rep = build_report([_info("Telegram", hb_age=99999, interval=None)], NOW)
    assert rep["agents"][0]["stale"] is False and rep["overall"] == "ok"


def test_no_heartbeat_not_stale():
    rep = build_report([_info("A", hb_age=None, interval=10)], NOW)
    a = rep["agents"][0]
    assert a["stale"] is False and a["silent_sec"] is None


def test_error_status_degraded():
    rep = build_report([_info("A", status="error", hb_age=1, interval=10)], NOW)
    assert rep["overall"] == "degraded"


def test_boundary_exactly_k_not_stale():
    # hb_age == 3*10 == 30 → не > порога → не stale (строгое >)
    rep = build_report([_info("A", hb_age=30, interval=10)], NOW)
    assert rep["agents"][0]["stale"] is False
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/test_health_report.py -q` → expect ModuleNotFoundError (core.health).

- [ ] **Step 3: Реализовать `core/health.py`**

```python
"""Чистая агрегация здоровья агентов из реестра. Без обращения к синглтону."""
from datetime import datetime


def build_report(infos, now: datetime, stale_k: float = 3.0) -> dict:
    """infos: list[AgentInfo]. Возвращает {overall, agents:[...]}."""
    agents = []
    overall = "ok"
    for info in infos:
        lh = info.last_heartbeat
        silent = int((now - lh).total_seconds()) if lh is not None else None
        stale = (info.expected_interval is not None and lh is not None
                 and silent > stale_k * info.expected_interval)
        if stale or info.status == "error":
            overall = "degraded"
        agents.append({
            "name": info.name,
            "status": info.status,
            "detail": info.detail,
            "last_heartbeat": lh.isoformat() if lh is not None else None,
            "expected_interval": info.expected_interval,
            "silent_sec": silent,
            "stale": stale,
            "error_count": info.error_count,
        })
    return {"overall": overall, "agents": agents}
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/test_health_report.py -q` → expect 6 passed.
(Примечание: `AgentInfo.__init__` пока без `last_heartbeat`/`expected_interval` — Task 2 их добавит; но тест ставит их атрибутами вручную, поэтому пройдёт уже сейчас, т.к. Python допускает присвоение новых атрибутов. Если `AgentInfo` слот-ограничен — Task 2 добавит поля; здесь ожидается PASS.)

- [ ] **Step 5: Commit**

```bash
git add core/health.py tests/test_health_report.py
git commit -m "feat(reliability-C): core/health.build_report (чистая агрегация liveness) + тесты"
```
(трейлер)

---

## Task 2: heartbeat в registry + base_agent

**Files:**
- Modify: `core/agent_registry.py`, `agents/base_agent.py`
- Create: `tests/test_agent_registry_heartbeat.py`

- [ ] **Step 1: Написать тест `tests/test_agent_registry_heartbeat.py`**

```python
"""registry.heartbeat: last_heartbeat + ленивый захват expected_interval; start() зовёт heartbeat."""
import asyncio
from types import SimpleNamespace
from core.agent_registry import AgentRegistry
from agents.base_agent import BaseAgent
from tests.execution.fakes import FakeBus


def test_register_adds_heartbeat_fields():
    reg = AgentRegistry()
    info = reg.register(SimpleNamespace(name="A", description="d"))
    assert info.last_heartbeat is None
    assert info.expected_interval is None


def test_heartbeat_sets_time_and_lazy_interval():
    reg = AgentRegistry()
    reg.register(SimpleNamespace(name="A", description="d"))
    reg.heartbeat("A", expected_interval=10.0)
    info = reg.get("A")
    assert info.last_heartbeat is not None
    assert info.expected_interval == 10.0
    # повторный heartbeat без interval не затирает
    reg.heartbeat("A")
    assert reg.get("A").expected_interval == 10.0


def test_heartbeat_unknown_name_noop():
    reg = AgentRegistry()
    reg.heartbeat("missing")  # не должно кидать


async def test_start_calls_heartbeat():
    from core.agent_registry import registry as global_reg

    class Tiny(BaseAgent):
        def __init__(self, name, bus):
            super().__init__(name, bus)
            self.poll_interval = 7.0
            self._n = 0

        async def run(self):
            self._n += 1
            if self._n >= 2:
                raise asyncio.CancelledError  # выходим после первого успешного run()

    agent = Tiny("TinyHB", FakeBus())
    await agent.start()  # run()#1 ок → heartbeat; run()#2 Cancelled → STOPPED
    info = global_reg.get("TinyHB")
    assert info.last_heartbeat is not None
    assert info.expected_interval == 7.0
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/test_agent_registry_heartbeat.py -q` → expect FAIL (`AttributeError`/нет `heartbeat`).

- [ ] **Step 3: Реализовать**

В `core/agent_registry.py`, в `AgentInfo.__init__`, добавить два поля (после `self.last_run`):
```python
        self.last_heartbeat: Optional[datetime] = None
        self.expected_interval: Optional[float] = None
```

В `AgentInfo.to_dict` (опционально, для полноты ответа) добавить в возвращаемый dict:
```python
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "expected_interval": self.expected_interval,
```

В класс `AgentRegistry`, добавить метод (после `update_status`):
```python
    def heartbeat(self, name: str, expected_interval: float = None):
        info = self._agents.get(name)
        if info is None:
            return
        info.last_heartbeat = datetime.now()
        if expected_interval is not None and info.expected_interval is None:
            info.expected_interval = expected_interval
```

В `agents/base_agent.py`, в методе `start()`, после строки `self.last_run = datetime.now()` (внутри `try`, после `await self.run()`) добавить:
```python
                registry.heartbeat(self.name, getattr(self, "poll_interval", None))
```
(`registry` уже импортирован в base_agent: `from core.agent_registry import registry`.)

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/test_agent_registry_heartbeat.py tests/test_health_report.py -q` → expect 4 + 6 = 10 passed.

- [ ] **Step 5: Commit**

```bash
git add core/agent_registry.py agents/base_agent.py tests/test_agent_registry_heartbeat.py
git commit -m "feat(reliability-C): heartbeat в registry (ленивый expected_interval) + вызов в BaseAgent.start"
```
(трейлер)

---

## Task 3: обогащённый `/health`

**Files:**
- Modify: `web/app.py`
- Create: `tests/test_health_endpoint.py`

- [ ] **Step 1: Написать тест `tests/test_health_endpoint.py`**

```python
"""/health: degraded при stale-агенте. Вызываем корутину health() напрямую
(без TestClient/httpx — чтобы не зависеть от наличия httpx)."""
from datetime import datetime, timedelta


async def test_health_degraded_when_stale(monkeypatch):
    from core.agent_registry import registry, AgentInfo
    from web.app import health

    info = AgentInfo("Stuck", "d")
    info.expected_interval = 10.0
    info.last_heartbeat = datetime.now() - timedelta(seconds=100)  # >3*10 → stale
    monkeypatch.setattr(registry, "_agents", {"Stuck": info})

    body = await health()
    assert body["status"] == "degraded" and body["overall"] == "degraded"
    assert body["agents"][0]["name"] == "Stuck" and body["agents"][0]["stale"] is True


async def test_health_ok_when_fresh(monkeypatch):
    from core.agent_registry import registry, AgentInfo
    from web.app import health

    info = AgentInfo("Fresh", "d")
    info.expected_interval = 10.0
    info.last_heartbeat = datetime.now()
    monkeypatch.setattr(registry, "_agents", {"Fresh": info})

    body = await health()
    assert body["status"] == "ok"
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/test_health_endpoint.py -q` → expect FAIL (текущий /health возвращает только `{status:"ok", ws_clients}`; нет `agents`/`overall`).

- [ ] **Step 3: Реализовать — заменить тело `health()` в `web/app.py`**

Найти:
```python
@app.get("/health")
async def health():
    """Health check для reverse-proxy / мониторинга."""
    return {
        "status": "ok",
        "ws_clients": ws_manager.connection_count,
    }
```
Заменить на:
```python
@app.get("/health")
async def health():
    """Health check: overall + per-agent liveness. Всегда 200 (degraded не роняет бэкенд)."""
    from datetime import datetime
    from core.agent_registry import registry
    from core.health import build_report
    report = build_report(list(registry._agents.values()), datetime.now())
    return {
        "status": report["overall"],     # обратная совместимость reverse-proxy
        "overall": report["overall"],
        "agents": report["agents"],
        "ws_clients": ws_manager.connection_count,
    }
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/test_health_endpoint.py -q` → expect 2 passed. Если `fastapi.testclient` требует `httpx` и его нет — STOP, report (но он в зависимостях fastapi/starlette).

- [ ] **Step 5: Commit**

```bash
git add web/app.py tests/test_health_endpoint.py
git commit -m "feat(reliability-C): обогащённый /health (per-agent liveness + overall, всегда 200) + тесты"
```
(трейлер)

---

## Task 4: `AGENT_STALE` + `WatchdogAgent`

**Files:**
- Modify: `core/events.py`
- Create: `agents/watchdog_agent.py`, `tests/execution/test_watchdog_agent.py`

- [ ] **Step 1: Добавить событие в `core/events.py`**

Найти строку `AGENT_STATUS             = "agent.status"` и добавить ПОСЛЕ неё:
```python
    AGENT_STALE              = "agent.stale"
```

- [ ] **Step 2: Написать тест `tests/execution/test_watchdog_agent.py`**

```python
"""WatchdogAgent: эмит AGENT_STALE на переход в stale, без дублей."""
from datetime import datetime, timedelta
from core.events import EventType
from core.agent_registry import AgentInfo
from tests.execution.fakes import FakeBus


def _stale_info(name, age, interval=10.0):
    i = AgentInfo(name, name)
    i.expected_interval = interval
    i.last_heartbeat = datetime.now() - timedelta(seconds=age)
    return i


def _count(bus, etype):
    return sum(1 for e in bus.events if e.type == etype)


async def test_emits_stale_on_transition_once(monkeypatch):
    import agents.watchdog_agent as wd_mod
    from core.agent_registry import registry

    monkeypatch.setattr(registry, "_agents", {"Stuck": _stale_info("Stuck", 100)})
    agent = wd_mod.WatchdogAgent("Watchdog", FakeBus(), poll_interval=0)

    await agent.run()  # переход → AGENT_STALE
    await agent.run()  # уже известен stale → без нового эмита
    assert _count(agent.bus, EventType.AGENT_STALE) == 1
    ev = next(e for e in agent.bus.events if e.type == EventType.AGENT_STALE)
    assert ev.payload["agent"] == "Stuck"
    assert agent.metrics["stale_count"] == 1


async def test_recovery_clears_known(monkeypatch):
    import agents.watchdog_agent as wd_mod
    from core.agent_registry import registry

    agents_map = {"Stuck": _stale_info("Stuck", 100)}
    monkeypatch.setattr(registry, "_agents", agents_map)
    agent = wd_mod.WatchdogAgent("Watchdog", FakeBus(), poll_interval=0)
    await agent.run()  # stale

    # агент восстановился (свежий heartbeat)
    agents_map["Stuck"].last_heartbeat = datetime.now()
    await agent.run()
    assert agent.metrics["stale_count"] == 0
    # снова протух → новый эмит (переход повторился)
    agents_map["Stuck"].last_heartbeat = datetime.now() - timedelta(seconds=100)
    await agent.run()
    assert _count(agent.bus, EventType.AGENT_STALE) == 2


async def test_no_stale_no_emit(monkeypatch):
    import agents.watchdog_agent as wd_mod
    from core.agent_registry import registry
    fresh = AgentInfo("Fresh", "d")
    fresh.expected_interval = 10.0
    fresh.last_heartbeat = datetime.now()
    monkeypatch.setattr(registry, "_agents", {"Fresh": fresh})
    agent = wd_mod.WatchdogAgent("Watchdog", FakeBus(), poll_interval=0)
    await agent.run()
    assert _count(agent.bus, EventType.AGENT_STALE) == 0
```

- [ ] **Step 3: Прогон — провал**

Run: `python -m pytest tests/execution/test_watchdog_agent.py -q` → expect ModuleNotFoundError.

- [ ] **Step 4: Реализовать `agents/watchdog_agent.py`**

```python
"""WatchdogAgent — детект протухших (stale) агентов и алерт через AGENT_STALE."""
import asyncio
from datetime import datetime

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType
from core.agent_registry import registry
from core.health import build_report


class WatchdogAgent(BaseAgent):
    """Периодически считает build_report; на переходе агента в stale эмитит AGENT_STALE."""
    description = "Watchdog: детект зависших агентов"

    def __init__(self, name: str, bus: EventBus, poll_interval: float = 60.0, stale_k: float = 3.0):
        super().__init__(name, bus)
        self.poll_interval = poll_interval
        self._stale_k = stale_k
        self._known_stale: set[str] = set()
        self.metrics["stale_count"] = 0

    async def run(self):
        report = build_report(list(registry._agents.values()), datetime.now(), self._stale_k)
        by_name = {a["name"]: a for a in report["agents"]}
        current = {name for name, a in by_name.items() if a["stale"]}

        for name in current - self._known_stale:
            await self.emit(EventType.AGENT_STALE, {
                "agent": name,
                "silent_sec": by_name[name].get("silent_sec"),
            })

        self._known_stale = current
        self.metrics["stale_count"] = len(current)
        await self.emit_status(AgentStatus.IDLE, f"stale: {len(current)}")
        await asyncio.sleep(self.poll_interval)
```

- [ ] **Step 5: Прогон — зелёно**

Run: `python -m pytest tests/execution/test_watchdog_agent.py -q` → expect 3 passed. Падение → STOP, report.

- [ ] **Step 6: Commit**

```bash
git add core/events.py agents/watchdog_agent.py tests/execution/test_watchdog_agent.py
git commit -m "feat(reliability-C): AGENT_STALE + WatchdogAgent (детект stale на переходе) + тесты"
```
(трейлер)

---

## Task 5: TelegramAgent `_on_agent_stale`

**Files:**
- Modify: `agents/telegram_agent.py`, `tests/execution/test_telegram_agent.py`

- [ ] **Step 1: APPEND тест в `tests/execution/test_telegram_agent.py`**

Добавить в конец файла (хелперы `_make`/`_ev` уже есть):

```python
async def test_on_agent_stale_alerts(monkeypatch):
    agent, sent = _make(monkeypatch)
    await agent._on_agent_stale(_ev(EventType.AGENT_STALE,
                                    {"agent": "MarketData", "silent_sec": 120}))
    assert len(sent) == 1 and "MarketData" in sent[0] and "stale" in sent[0].lower()
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/execution/test_telegram_agent.py::test_on_agent_stale_alerts -q` → expect FAIL (`AttributeError: _on_agent_stale`).

- [ ] **Step 3: Реализовать — в `agents/telegram_agent.py`**

(a) Добавить хендлер (после `_on_agent_status`):
```python
    async def _on_agent_stale(self, ev) -> None:
        agent = ev.payload.get("agent")
        silent = ev.payload.get("silent_sec")
        await self._send(f"⚠️ Agent {agent} stale ({silent}s без heartbeat)")
```

(b) В `_subscribe()` добавить подписку (после подписки на AGENT_STATUS):
```python
        self.bus.subscribe(EventType.AGENT_STALE, self._on_agent_stale)
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/execution/test_telegram_agent.py -q` → expect 7 passed (6 + 1).

- [ ] **Step 5: Commit**

```bash
git add agents/telegram_agent.py tests/execution/test_telegram_agent.py
git commit -m "feat(reliability-C): TelegramAgent._on_agent_stale — алерт о зависшем агенте + тест"
```
(трейлер)

---

## Task 6: Проводка `main.py` + полный прогон + память

**Files:**
- Modify: `main.py`
- Modify: `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md` (вне git)

- [ ] **Step 1: Импорт в `main.py`** — после `from agents.telegram_agent import TelegramAgent` добавить:
```python
    from agents.watchdog_agent       import WatchdogAgent
```

- [ ] **Step 2: Добавить в список `agents`** — после строки `TelegramAgent("Telegram",     bus),` добавить:
```python
        WatchdogAgent("Watchdog",     bus, poll_interval=60.0),
```

- [ ] **Step 3: Smoke**

Run: `python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('main.py parse OK')"` → `main.py parse OK`.
Run: `python -c "from agents.watchdog_agent import WatchdogAgent; from core.health import build_report; print('OK')"` → `OK`.

- [ ] **Step 4: Полный прогон**

Run: `python -m pytest -q`
Expected: прежние 582 + новые (6 health + 4 registry + 2 endpoint + 3 watchdog + 1 telegram = 16) = **598 passed, 3 xfailed**. Записать фактические числа. Падение незелёных → STOP, report (особенно tests/execution/ и tests/test_macd_atr.py).

- [ ] **Step 5: Commit (main.py)**

```bash
git add main.py
git commit -m "feat(reliability-C): проводка WatchdogAgent в main.py"
```
(трейлер)

- [ ] **Step 6: Обновить память** `project_millionskeeper.md`:
- В «Тесты»: добавить `test_health_report.py` (6), `test_agent_registry_heartbeat.py` (4), `test_health_endpoint.py` (2), `test_watchdog_agent.py` (3), +1 telegram.
- «Текущий прогон»: обновить число passed.
- В reliability-запись: отметить **C сделан** (heartbeat+/health+WatchdogAgent+AGENT_STALE-алерт); reliability-трек закрыт; осталось MyFXBook-верификация.
- Пути спеки/плана `2026-06-06-reliability-health-watchdog*`.

(Память вне git.)

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** build_report → Task 1; heartbeat (registry+base_agent, ленивый interval) → Task 2; /health → Task 3; AGENT_STALE+WatchdogAgent → Task 4; TelegramAgent._on_agent_stale → Task 5; проводка+прогон+память → Task 6. ✅
- **Плейсхолдеры:** нет — весь код приведён; команды/ожидания явные. ✅
- **Поправка ordering:** `expected_interval` ловится лениво в `heartbeat()`, не в `register()` (подкласс ставит poll_interval после super().__init__). ✅
- **Согласованность:** `build_report(infos, now, stale_k=3.0)`; `AgentInfo.last_heartbeat/expected_interval`; `registry.heartbeat(name, expected_interval=None)`; `WatchdogAgent(name,bus,poll_interval,stale_k)` с `_known_stale`/`stale_count`; событие `AGENT_STALE="agent.stale"`; `TelegramAgent._on_agent_stale`. ✅
- **Изоляция:** боевая логика агентов не меняется; /health всегда 200; событийные агенты (interval None) не stale; Watchdog не self-stale (heartbeat каждый цикл). ✅
- **Числа:** 6 + 4 + 2 + 3 + 1 = 16. ✅
