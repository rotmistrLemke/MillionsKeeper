# Reliability-C: обогащённый /health + staleness-watchdog — Design

**Дата:** 2026-06-06
**Статус:** утверждён (brainstorming)
**Трек:** reliability (после слайса A+B `2026-06-06-reliability-reconnect-alerts`). Наблюдаемость для unattended-прогона.

## Цель

Дать наблюдаемость зависших агентов: (1) обогащённый `/health` с per-agent liveness для внешнего uptime-монитора и (2) in-process `WatchdogAgent`, который детектит «протухшие» (stale) агенты и алертит в Telegram (реюз слайса B). Чинит латентный баг: registry `last_run` обновляется только при статусе `running`.

## Текущее состояние (факты)

- `core/agent_registry.py`: синглтон `registry`; `AgentInfo` (name/description/status/detail/metrics/last_run/error_count). `update_status` ставит `last_run = now()` **только при `status=="running"`** → агенты, эмитящие IDLE каждый цикл (напр. `ConnectionAgent` в норме), не обновляют `last_run` → ложно «stale».
- `BaseAgent.start()` (строка 67) уже ставит `self.last_run = datetime.now()` после успешной `run()` — но на объекте агента, не в registry.
- `/health` (`web/app.py:55`) возвращает только `{status:"ok", ws_clients}` — registry не используется.
- Слайс B: `TelegramAgent` шлёт алерты на события (дедуп по переходам); `EventBus` push-подписки.

## Не-цели

- Внешний uptime-монитор (это ops/runbook, не код), исторические health-метрики, графики, HTTP 503 на degraded.

## Архитектура

Аддитивно. Боевая логика агентов не меняется.

### 1. Heartbeat (`core/agent_registry.py` + `agents/base_agent.py`)

- `AgentInfo` += два поля: `last_heartbeat: Optional[datetime] = None`, `expected_interval: Optional[float] = None`.
- `registry.register(agent)`: захватывает `expected_interval = getattr(agent, "poll_interval", None)` (поллеры имеют; событийные — None).
- `registry.heartbeat(name)`: `info.last_heartbeat = datetime.now()` (если агент есть).
- `BaseAgent.start()`: после `self.last_run = datetime.now()` (успешная run()) добавить `registry.heartbeat(self.name)` → heartbeat **каждый цикл, независимо от статуса**. Это делает liveness корректным для всех агентов.

### 2. Чистая агрегация (`core/health.py`, новый)

```python
def build_report(infos: list[AgentInfo], now: datetime, stale_k: float = 3.0) -> dict
```
- Для каждого `info`: `stale = (info.expected_interval is not None and info.last_heartbeat is not None
  and (now - info.last_heartbeat).total_seconds() > stale_k * info.expected_interval)`.
  Если `last_heartbeat is None` и `expected_interval is not None` → ещё не запускался: считаем `stale=False` (на старте), либо stale только после первого heartbeat — **решение: `last_heartbeat is None` → stale=False** (не алертить до первого цикла).
- `silent_sec = int((now - last_heartbeat).total_seconds())` если `last_heartbeat` есть, иначе `None`.
- `agents`: список `{name, status, detail, last_heartbeat(iso|None), expected_interval, silent_sec, stale, error_count}`.
- `overall = "degraded"` если любой агент `stale` ИЛИ `status=="error"`, иначе `"ok"`.
- Чистая функция (вход — список `AgentInfo` + now), без обращения к синглтону → тестируема.

### 3. Обогащённый `/health` (`web/app.py`)

Заменить тело `health()`:
```python
from core.agent_registry import registry
from core.health import build_report
from datetime import datetime
report = build_report(list(registry._agents.values()), datetime.now())
return {**report, "ws_clients": ws_manager.connection_count}
```
Верхнеуровневый `status` = `report["overall"]` (`"ok"|"degraded"`) — обратная совместимость для reverse-proxy. **HTTP всегда 200** (degraded не должен ронять бэкенд через proxy; внешний монитор алертит на `status!="ok"`).

(Примечание: `report` содержит `overall`; чтобы сохранить ключ `status`, вернуть `{"status": report["overall"], "overall": report["overall"], "agents": report["agents"], "ws_clients": ...}` — см. план.)

### 4. `WatchdogAgent` (`agents/watchdog_agent.py`, новый)

`BaseAgent`, конструктор `(name, bus, poll_interval=60.0, stale_k=3.0)`.

`run()` (одна итерация):
- `report = build_report(list(registry._agents.values()), datetime.now(), self._stale_k)`.
- `current = {a["name"] for a in report["agents"] if a["stale"]}`.
- для `name in current - self._known_stale` (новые stale): `emit(AGENT_STALE, {"agent": name, "silent_sec": ...})`.
- `self._known_stale = current`; метрика `stale_count = len(current)`.
- `emit_status(IDLE/RUNNING)`, `sleep(poll_interval)`.

⚠️ Watchdog НЕ считает сам себя/Telegram stale (у них либо poll_interval, либо None — Telegram None → исключён; Watchdog имеет poll_interval, но его heartbeat обновляется каждый цикл → не stale).

### 5. Событие + алерт (`core/events.py` + `agents/telegram_agent.py`)

- `core/events.py`: `AGENT_STALE = "agent.stale"`.
- `TelegramAgent`: +подписка на `AGENT_STALE` в `_subscribe()`, +хендлер `_on_agent_stale(ev)` → `_send("⚠️ Agent <name> stale (<silent_sec>s без heartbeat)")`. Дедуп не нужен (Watchdog эмитит один раз на переход), но безвреден.

### 6. Проводка `main.py`

Импорт + `WatchdogAgent("Watchdog", bus, poll_interval=60.0)` в список агентов.

## Краевые случаи

- Агент ещё не делал ни одного heartbeat (`last_heartbeat is None`) → не stale (не алертим на старте).
- Событийные агенты (`expected_interval is None`: Telegram) → никогда не stale.
- Watchdog сам имеет `poll_interval` → heartbeat каждый цикл → не self-stale.
- `/health` всегда 200; `overall` отражает degraded.

## Тестирование

- **`build_report`** (чистая) — фикстурные `AgentInfo`: свежий heartbeat → не stale; heartbeat старше `k×interval` → stale; `expected_interval=None` → не stale; `last_heartbeat=None` → не stale; `status=="error"` → `overall=="degraded"`; всё ок → `overall=="ok"`.
- **`registry.heartbeat`/`register`** — `register` агента с `poll_interval` захватывает `expected_interval`; без него → None; `heartbeat(name)` ставит `last_heartbeat`.
- **`WatchdogAgent`** — фейк registry-инфо со stale-агентом → один `AGENT_STALE` на переход; повторный run() без новых stale → без эмита; уход из stale убирает из `_known_stale`. Харнесс `tests/execution/` (FakeBus); registry монкипатчится списком AgentInfo.
- **`TelegramAgent._on_agent_stale`** — шлёт алерт (инъектируемый sender), эмит `TELEGRAM_SENT`.
- **`/health`** — лёгкий тест: при stale-агенте `status=="degraded"` (через pure-функцию); эндпоинт — smoke-импорт.

## Файловая структура

- **Create:** `core/health.py`, `agents/watchdog_agent.py`, `tests/test_health_report.py`, `tests/execution/test_watchdog_agent.py`, тест в `tests/test_agent_registry_heartbeat.py`, + кейс в `tests/execution/test_telegram_agent.py` (или новый).
- **Modify:** `core/agent_registry.py` (+поля/heartbeat/register), `agents/base_agent.py` (+heartbeat-вызов), `web/app.py` (/health), `core/events.py` (+AGENT_STALE), `agents/telegram_agent.py` (+хендлер/подписка), `main.py` (проводка).

## Критерии готовности

- Heartbeat обновляется каждый цикл; `last_run`-баг (RUNNING-only) обойдён через `last_heartbeat`.
- `/health` отдаёт per-agent liveness + overall; всегда 200.
- `WatchdogAgent` эмитит `AGENT_STALE` на переход; TelegramAgent алертит.
- Полный прогон зелёный (582 + новые); деньги-путь и слайс A+B не сломаны.

## Связанные документы

- `docs/superpowers/specs|plans/2026-06-06-reliability-reconnect-alerts*` — слайс A+B (TelegramAgent, который расширяем).
- `docs/ops/provisioning-runbook.md` — внешний uptime-монитор бьёт `/health` (ops-часть).
