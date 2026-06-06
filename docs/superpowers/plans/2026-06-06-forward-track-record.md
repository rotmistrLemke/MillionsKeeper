# Forward Track-Record + Performance Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать внутренний go/no-go по живой торговле: персистить сделки брокера в SQLite, считать live-метрики (по счёту и per-strategy) и оценивать против moderate-порогов.

**Architecture:** Новый пакет `performance/` — `store.py` (SQLite, дедуп по ticket), `metrics.py` (чистые функции), `evaluator.py` (чистая go/no-go оценка). Запись в store — изолированным методом `HistoryAgent._persist_track()` (не трогает существующий `_load_history`). Наружу — `GET /performance`. Атрибуция стратегии через `magic→stream`.

**Tech Stack:** Python 3.11, stdlib `sqlite3`, pytest, FastAPI.

**⚠️ Дисциплина:** TDD (тест → провал → реализация → зелёно → коммит). Денежный путь (`_load_history`, execution) НЕ трогаем — только аддитивная запись. Трейлер каждого коммита: пустая строка, затем `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

- **Create:** `performance/__init__.py`, `performance/metrics.py` (Task 1), `performance/evaluator.py` (Task 2), `performance/store.py` (Task 3).
- **Create:** `tests/performance/__init__.py`, `tests/performance/test_metrics.py` (Task 1), `test_evaluator.py` (Task 2), `test_store.py` (Task 3), `test_history_persist.py` (Task 4).
- **Modify:** `agents/history_agent.py` (Task 4 — метод `_persist_track` + вызов в `run()`), `web/api_routes.py` (Task 4 — `/performance`), `.gitignore` (Task 4).

---

## Task 1: `performance/metrics.py` — чистые метрики

**Files:**
- Create: `performance/__init__.py` (пустой), `performance/metrics.py`
- Create: `tests/performance/__init__.py` (пустой), `tests/performance/test_metrics.py`

- [ ] **Step 1: Создать пустые `performance/__init__.py` и `tests/performance/__init__.py`** (0 байт каждый).

- [ ] **Step 2: Написать тесты `tests/performance/test_metrics.py`**

```python
"""Характеризация чистых метрик performance (forward-track)."""
import math
import pytest
from performance.metrics import compute, per_strategy


def _t(time, profit, commission=0.0, swap=0.0, magic=0):
    return {"time": time, "profit": profit, "commission": commission, "swap": swap, "magic": magic}


def test_empty_returns_zeros():
    m = compute([])
    assert m["trades"] == 0 and m["net_pnl"] == 0.0
    assert m["profit_factor"] == 0.0 and m["sharpe"] is None and m["period_days"] == 0.0


def test_mixed_trades_pinned():
    # nets: +10, -4, +5, -3 → net 8; wins 2 losses 2
    trades = [_t(0, 10), _t(100, -4), _t(200, 6, commission=-1), _t(300, -2, swap=-1)]
    m = compute(trades)
    assert m["net_pnl"] == pytest.approx(8.0)
    assert m["trades"] == 4 and m["wins"] == 2 and m["losses"] == 2
    assert m["win_rate"] == pytest.approx(0.5)
    assert m["gross_profit"] == pytest.approx(15.0) and m["gross_loss"] == pytest.approx(7.0)
    assert m["profit_factor"] == pytest.approx(15.0 / 7.0)
    assert m["avg_win"] == pytest.approx(7.5) and m["avg_loss"] == pytest.approx(-3.5)
    assert m["expectancy"] == pytest.approx(2.0)
    # equity cum: 10,6,11,8 → peak 11, max dd 3 (money), pct 3/11*100
    assert m["max_drawdown_money"] == pytest.approx(3.0)
    assert m["max_drawdown_pct"] == pytest.approx(3.0 / 11.0 * 100.0)
    assert m["longest_loss_streak"] == 1
    assert m["sharpe"] is not None
    assert m["period_days"] == pytest.approx(300.0 / 86400.0)


def test_all_wins_profit_factor_inf():
    m = compute([_t(0, 5), _t(10, 3)])
    assert m["profit_factor"] == math.inf
    assert m["max_drawdown_money"] == 0.0 and m["max_drawdown_pct"] == 0.0


def test_all_losses_profit_factor_zero():
    m = compute([_t(0, -5), _t(10, -3)])
    assert m["profit_factor"] == 0.0
    assert m["net_pnl"] == pytest.approx(-8.0)
    assert m["longest_loss_streak"] == 2


def test_single_trade_sharpe_none():
    m = compute([_t(0, 7)])
    assert m["sharpe"] is None and m["trades"] == 1


def test_per_strategy_groups_by_magic():
    trades = [_t(0, 10, magic=1001), _t(10, -2, magic=1001), _t(20, 5, magic=1002), _t(30, 1, magic=9999)]
    out = per_strategy(trades, {1001: "alpha", 1002: "beta"})
    assert set(out) == {"alpha", "beta", "unmapped"}
    assert out["alpha"]["trades"] == 2 and out["alpha"]["net_pnl"] == pytest.approx(8.0)
    assert out["beta"]["net_pnl"] == pytest.approx(5.0)
    assert out["unmapped"]["net_pnl"] == pytest.approx(1.0)
```

- [ ] **Step 3: Прогон — провал**

Run: `python -m pytest tests/performance/test_metrics.py -q`
Expected: FAIL (ModuleNotFoundError: performance.metrics).

- [ ] **Step 4: Реализовать `performance/metrics.py`**

```python
"""Чистые функции метрик live-трека. Знают только списки сделок (dict с time/profit/commission/swap[/magic])."""
from __future__ import annotations
import math
from typing import Mapping


def _net(trade: Mapping) -> float:
    return (float(trade.get("profit", 0.0)) + float(trade.get("commission", 0.0))
            + float(trade.get("swap", 0.0)))


def compute(trades: list[dict]) -> dict:
    """Метрики по списку ЗАКРЫТЫХ сделок."""
    n = len(trades)
    if n == 0:
        return {
            "net_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "gross_profit": 0.0, "gross_loss": 0.0, "profit_factor": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "expectancy": 0.0,
            "max_drawdown_money": 0.0, "max_drawdown_pct": 0.0,
            "longest_loss_streak": 0, "sharpe": None, "period_days": 0.0,
        }
    ordered = sorted(trades, key=lambda t: t.get("time", 0))
    nets = [_net(t) for t in ordered]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)            # положительное
    net_pnl = sum(nets)
    win_rate = len(wins) / n

    if gross_loss == 0:
        profit_factor = math.inf if gross_profit > 0 else 0.0
    else:
        profit_factor = gross_profit / gross_loss

    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (-gross_loss / len(losses)) if losses else 0.0   # отрицательное
    expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

    peak = cum = max_dd_money = 0.0
    for x in nets:
        cum += x
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd_money:
            max_dd_money = dd
    max_dd_pct = (max_dd_money / peak * 100.0) if peak > 0 else 0.0

    longest = cur = 0
    for x in nets:
        if x < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0

    if n >= 2:
        mean = net_pnl / n
        var = sum((x - mean) ** 2 for x in nets) / (n - 1)
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(n)) if std > 0 else None
    else:
        sharpe = None

    period_days = (ordered[-1].get("time", 0) - ordered[0].get("time", 0)) / 86400.0

    return {
        "net_pnl": net_pnl, "trades": n, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate, "gross_profit": gross_profit, "gross_loss": gross_loss,
        "profit_factor": profit_factor, "avg_win": avg_win, "avg_loss": avg_loss,
        "expectancy": expectancy, "max_drawdown_money": max_dd_money,
        "max_drawdown_pct": max_dd_pct, "longest_loss_streak": longest,
        "sharpe": sharpe, "period_days": period_days,
    }


def per_strategy(trades: list[dict], magic_to_strategy: Mapping[int, str]) -> dict[str, dict]:
    """Группирует сделки по magic→strategy и считает compute() на группу. Неизвестный magic → 'unmapped'."""
    groups: dict[str, list[dict]] = {}
    for t in trades:
        name = magic_to_strategy.get(int(t.get("magic", 0)), "unmapped")
        groups.setdefault(name, []).append(t)
    return {name: compute(ts) for name, ts in groups.items()}
```

- [ ] **Step 5: Прогон — зелёно**

Run: `python -m pytest tests/performance/test_metrics.py -q`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add performance/__init__.py performance/metrics.py tests/performance/__init__.py tests/performance/test_metrics.py
git commit -m "feat(performance): чистые метрики live-трека (metrics.py) + тесты"
```
(трейлер)

---

## Task 2: `performance/evaluator.py` — go/no-go

**Files:**
- Create: `performance/evaluator.py`
- Create: `tests/performance/test_evaluator.py`

- [ ] **Step 1: Написать тесты `tests/performance/test_evaluator.py`**

```python
"""Характеризация go/no-go оценки performance."""
import math
from performance.evaluator import Thresholds, evaluate


def _metrics(*, trades=60, period_days=120.0, net_pnl=500.0, max_drawdown_pct=10.0, profit_factor=1.6):
    return {"trades": trades, "period_days": period_days, "net_pnl": net_pnl,
            "max_drawdown_pct": max_drawdown_pct, "profit_factor": profit_factor}


def test_pass_when_all_thresholds_met():
    v = evaluate(_metrics())
    assert v["status"] == "PASS" and v["reasons"] == []


def test_insufficient_when_too_few_trades():
    v = evaluate(_metrics(trades=10))
    assert v["status"] == "INSUFFICIENT_DATA"
    assert any("trades" in r for r in v["reasons"])


def test_insufficient_when_period_too_short():
    v = evaluate(_metrics(period_days=30.0))
    assert v["status"] == "INSUFFICIENT_DATA"
    assert any("period_days" in r for r in v["reasons"])


def test_fail_negative_pnl():
    v = evaluate(_metrics(net_pnl=-100.0))
    assert v["status"] == "FAIL" and any("net_pnl" in r for r in v["reasons"])


def test_fail_drawdown_exceeds():
    v = evaluate(_metrics(max_drawdown_pct=30.0))
    assert v["status"] == "FAIL" and any("drawdown" in r for r in v["reasons"])


def test_fail_low_profit_factor():
    v = evaluate(_metrics(profit_factor=1.1))
    assert v["status"] == "FAIL" and any("profit_factor" in r for r in v["reasons"])


def test_boundaries_inclusive_pass():
    # ровно на границах moderate: dd 25.0 (не >25), pf 1.3 (не <1.3) → PASS
    v = evaluate(_metrics(max_drawdown_pct=25.0, profit_factor=1.3))
    assert v["status"] == "PASS"


def test_profit_factor_inf_passes():
    v = evaluate(_metrics(profit_factor=math.inf))
    assert v["status"] == "PASS"


def test_strategy_uses_lower_trade_floor():
    # 25 сделок: для счёта (min 50) — мало; для стратегии (min 20) — достаточно
    assert evaluate(_metrics(trades=25))["status"] == "INSUFFICIENT_DATA"
    assert evaluate(_metrics(trades=25), is_strategy=True)["status"] == "PASS"
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/performance/test_evaluator.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Реализовать `performance/evaluator.py`**

```python
"""Чистая go/no-go оценка по метрикам live-трека. Пороги настраиваемы (Moderate по умолчанию)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    min_period_days: int = 90
    min_trades: int = 50
    min_trades_per_strategy: int = 20
    require_net_pnl_positive: bool = True
    max_drawdown_pct: float = 25.0
    min_profit_factor: float = 1.3


_DEFAULT = Thresholds()


def evaluate(metrics: dict, thresholds: Thresholds = _DEFAULT, *, is_strategy: bool = False) -> dict:
    """Вердикт. status: PASS | FAIL | INSUFFICIENT_DATA."""
    min_trades = thresholds.min_trades_per_strategy if is_strategy else thresholds.min_trades

    insufficient = []
    if metrics["trades"] < min_trades:
        insufficient.append(f"trades {metrics['trades']} < {min_trades}")
    if metrics["period_days"] < thresholds.min_period_days:
        insufficient.append(f"period_days {metrics['period_days']:.1f} < {thresholds.min_period_days}")
    if insufficient:
        return {"status": "INSUFFICIENT_DATA", "reasons": insufficient, "metrics": metrics}

    reasons = []
    if thresholds.require_net_pnl_positive and metrics["net_pnl"] <= 0:
        reasons.append(f"net_pnl {metrics['net_pnl']:.2f} <= 0")
    if metrics["max_drawdown_pct"] > thresholds.max_drawdown_pct:
        reasons.append(f"max_drawdown_pct {metrics['max_drawdown_pct']:.1f} > {thresholds.max_drawdown_pct}")
    if metrics["profit_factor"] < thresholds.min_profit_factor:
        reasons.append(f"profit_factor {metrics['profit_factor']:.2f} < {thresholds.min_profit_factor}")

    return {"status": "PASS" if not reasons else "FAIL", "reasons": reasons, "metrics": metrics}
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/performance/test_evaluator.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add performance/evaluator.py tests/performance/test_evaluator.py
git commit -m "feat(performance): go/no-go evaluator (moderate-пороги) + тесты"
```
(трейлер)

---

## Task 3: `performance/store.py` — SQLite-персистинг

**Files:**
- Create: `performance/store.py`
- Create: `tests/performance/test_store.py`

- [ ] **Step 1: Написать тесты `tests/performance/test_store.py`**

```python
"""Характеризация SQLite-хранилища performance."""
from performance.store import PerformanceStore, record_poll


def _deal(ticket, time=1000, magic=1001, profit=5.0):
    return {"ticket": ticket, "time": time, "magic": magic, "symbol": "XAUUSD",
            "type": 0, "entry": 1, "volume": 0.1, "price": 1900.0,
            "profit": profit, "commission": -0.5, "swap": 0.0}


def test_upsert_and_read(tmp_path):
    db = tmp_path / "p.db"
    s = PerformanceStore(db)
    n = s.upsert_deals([_deal(1), _deal(2)])
    assert n == 2
    trades = s.closed_trades()
    assert len(trades) == 2 and trades[0]["ticket"] == 1
    s.close()


def test_upsert_dedup_by_ticket(tmp_path):
    s = PerformanceStore(tmp_path / "p.db")
    s.upsert_deals([_deal(1)])
    n2 = s.upsert_deals([_deal(1, profit=999.0)])  # тот же ticket → игнор
    assert n2 == 0
    trades = s.closed_trades()
    assert len(trades) == 1 and trades[0]["profit"] == 5.0  # старое значение сохранено
    s.close()


def test_equity_snapshots(tmp_path):
    s = PerformanceStore(tmp_path / "p.db")
    s.record_equity(10000.0, 10050.0, ts=100)
    s.record_equity(10050.0, 10020.0, ts=200)
    series = s.equity_series()
    assert series == [(100, 10050.0), (200, 10020.0)]
    s.close()


def test_closed_trades_since_filter(tmp_path):
    s = PerformanceStore(tmp_path / "p.db")
    s.upsert_deals([_deal(1, time=100), _deal(2, time=500)])
    assert len(s.closed_trades(since=300)) == 1
    s.close()


def test_record_poll_helper(tmp_path):
    db = tmp_path / "p.db"
    n = record_poll([_deal(1), _deal(2)], balance=10000.0, equity=10010.0, db_path=db)
    assert n == 2
    s = PerformanceStore(db)
    assert len(s.closed_trades()) == 2 and s.equity_series() == [(s.equity_series()[0][0], 10010.0)]
    s.close()
```

- [ ] **Step 2: Прогон — провал**

Run: `python -m pytest tests/performance/test_store.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Реализовать `performance/store.py`**

```python
"""SQLite-персистинг live-трека: сделки (дедуп по ticket) + equity-снимки.
Один connection на инстанс; для кросс-тредового использования открывать
отдельный инстанс в нужном треде (см. record_poll)."""
from __future__ import annotations
import sqlite3
import time as _time
from pathlib import Path
from typing import Iterable, Optional

_DEFAULT_DB = Path(__file__).parent / "performance.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    ticket     INTEGER PRIMARY KEY,
    time       INTEGER NOT NULL,
    magic      INTEGER NOT NULL DEFAULT 0,
    symbol     TEXT,
    type       INTEGER,
    entry      INTEGER,
    volume     REAL,
    price      REAL,
    profit     REAL,
    commission REAL,
    swap       REAL
);
CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts      INTEGER NOT NULL,
    balance REAL,
    equity  REAL
);
"""

_COLS = ("ticket", "time", "magic", "symbol", "type", "entry",
         "volume", "price", "profit", "commission", "swap")


class PerformanceStore:
    def __init__(self, db_path=_DEFAULT_DB):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def upsert_deals(self, deals: Iterable[dict]) -> int:
        """INSERT OR IGNORE по ticket. Возвращает число НОВЫХ строк."""
        rows = [tuple(d.get(c) if c != "magic" else int(d.get("magic", 0)) for c in _COLS)
                for d in deals]
        if not rows:
            return 0
        before = self._conn.total_changes
        self._conn.executemany(
            f"INSERT OR IGNORE INTO deals ({','.join(_COLS)}) "
            f"VALUES ({','.join('?' * len(_COLS))})", rows)
        self._conn.commit()
        return self._conn.total_changes - before

    def record_equity(self, balance: float, equity: float, ts: Optional[int] = None) -> None:
        self._conn.execute(
            "INSERT INTO equity_snapshots (ts,balance,equity) VALUES (?,?,?)",
            (int(ts if ts is not None else _time.time()), balance, equity))
        self._conn.commit()

    def closed_trades(self, since: Optional[int] = None) -> list[dict]:
        if since is not None:
            cur = self._conn.execute(
                "SELECT * FROM deals WHERE time >= ? ORDER BY time ASC", (int(since),))
        else:
            cur = self._conn.execute("SELECT * FROM deals ORDER BY time ASC")
        return [dict(r) for r in cur.fetchall()]

    def equity_series(self) -> list[tuple[int, float]]:
        cur = self._conn.execute("SELECT ts,equity FROM equity_snapshots ORDER BY ts ASC")
        return [(r["ts"], r["equity"]) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


def record_poll(closed_deals, balance: float, equity: float, db_path=None) -> int:
    """Открыть/записать/закрыть в одном вызове (потокобезопасно: connection в текущем треде).
    db_path резолвится на этапе ВЫЗОВА (не дефолт-параметром), чтобы monkeypatch
    _DEFAULT_DB работал в тестах и чтобы прод читал актуальный путь."""
    if db_path is None:
        db_path = _DEFAULT_DB
    store = PerformanceStore(db_path)
    try:
        n = store.upsert_deals(closed_deals)
        store.record_equity(balance, equity)
        return n
    finally:
        store.close()
```

- [ ] **Step 4: Прогон — зелёно**

Run: `python -m pytest tests/performance/test_store.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add performance/store.py tests/performance/test_store.py
git commit -m "feat(performance): SQLite store (дедуп по ticket, equity-снимки) + тесты"
```
(трейлер)

---

## Task 4: Интеграция — HistoryAgent запись + эндпоинт + .gitignore

**Files:**
- Modify: `agents/history_agent.py`
- Modify: `web/api_routes.py`
- Modify: `.gitignore`
- Create: `tests/performance/test_history_persist.py`

- [ ] **Step 1: Добавить `performance.db` в `.gitignore`**

Дописать строку в конец `.gitignore`:
```
performance.db
```

- [ ] **Step 2: Добавить метод `_persist_track` в `HistoryAgent` и вызов в `run()`**

В `agents/history_agent.py`, в методе `run()`, ПОСЛЕ строки `await self.emit(EventType.HISTORY_SNAPSHOT, snapshot)` и ДО `await self.emit_status(AgentStatus.IDLE, ...)`, вставить (с тем же отступом, внутри `try`):

```python
            await asyncio.get_event_loop().run_in_executor(None, self._persist_track)
```

Затем добавить новый метод в класс (например, сразу после `_load_history`):

```python
    def _persist_track(self) -> None:
        """Аддитивная запись closed-сделок + equity в performance-store.
        Изолировано от _load_history; никогда не роняет агент (всё в try)."""
        try:
            from datetime import datetime, timedelta
            import MetaTrader5 as mt5
            from performance.store import record_poll
            import streams

            now = datetime.now()
            date_from = now - timedelta(days=90)
            date_to = now + timedelta(hours=3)
            deals = mt5.history_deals_get(date_from, date_to)

            records = []
            for d in (deals or []):
                # закрытая сделка: entry==1 (OUT), type buy/sell
                if getattr(d, "entry", None) != 1 or d.type not in (0, 1):
                    continue
                records.append({
                    "ticket": int(d.ticket), "time": int(d.time),
                    "magic": int(getattr(d, "magic", 0) or 0),
                    "symbol": getattr(d, "symbol", None), "type": int(d.type),
                    "entry": int(d.entry), "volume": float(getattr(d, "volume", 0.0)),
                    "price": float(getattr(d, "price", 0.0)), "profit": float(d.profit),
                    "commission": float(getattr(d, "commission", 0.0)),
                    "swap": float(getattr(d, "swap", 0.0)),
                })

            info = mt5.account_info()
            balance = float(getattr(info, "balance", 0.0)) if info else 0.0
            equity = float(getattr(info, "equity", 0.0)) if info else 0.0

            record_poll(records, balance, equity)
        except Exception as e:
            self._logger.warning(f"performance persist failed: {e}")
```

(`streams` импортируется на случай будущего использования карты; здесь magic пишется как есть, атрибуция — в эндпоинте.)

- [ ] **Step 3: Добавить эндпоинт `/performance` в `web/api_routes.py`**

В конец файла (рядом с другими `@router.get`) добавить:

```python
@router.get("/performance")
async def get_performance():
    """Live go/no-go: метрики+вердикт по счёту и per-strategy. Только чтение store."""
    import time as _time
    import math
    from performance.store import PerformanceStore
    from performance import metrics as perf_metrics
    from performance.evaluator import evaluate
    import streams

    store = PerformanceStore()
    try:
        trades = store.closed_trades()
    finally:
        store.close()

    magic_map = {int(s.magic): s.strategy for s in streams.registry.all()}

    def _json_safe(m: dict) -> dict:
        out = {}
        for k, v in m.items():
            if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                out[k] = None
            else:
                out[k] = v
        return out

    acc = perf_metrics.compute(trades)
    acc_v = evaluate(acc)
    by_strat = perf_metrics.per_strategy(trades, magic_map)
    by_strat_out = {
        name: {**_json_safe(m), "verdict": {"status": evaluate(m, is_strategy=True)["status"],
                                            "reasons": evaluate(m, is_strategy=True)["reasons"]}}
        for name, m in by_strat.items()
    }
    return {
        "account": {**_json_safe(acc), "verdict": {"status": acc_v["status"], "reasons": acc_v["reasons"]}},
        "by_strategy": by_strat_out,
        "generated_at": int(_time.time()),
    }
```

(Примечание: `verdict.metrics` не вкладываем в ответ повторно — берём только status/reasons, метрики уже в корне через `_json_safe`. Это избегает дубля и inf в неочищенной копии.)

- [ ] **Step 4: Написать тест `tests/performance/test_history_persist.py`**

```python
"""Интеграция: HistoryAgent._persist_track пишет closed-сделки + equity в store."""
import sys
import types
from types import SimpleNamespace

import pytest

from agents.history_agent import HistoryAgent
from core.event_bus import EventBus
from performance.store import PerformanceStore


class _Deal(SimpleNamespace):
    pass


def test_persist_track_writes_closed_deals(tmp_path, monkeypatch):
    # Фейковый mt5 с двумя closed-сделками (entry=1) и одной открывающей (entry=0).
    deals = [
        _Deal(ticket=1, time=1000, magic=1001, symbol="XAUUSD", type=0, entry=1,
              volume=0.1, price=1900.0, profit=10.0, commission=-0.5, swap=0.0),
        _Deal(ticket=2, time=2000, magic=1002, symbol="EURUSD", type=1, entry=1,
              volume=0.2, price=1.1, profit=-4.0, commission=-0.3, swap=-0.1),
        _Deal(ticket=3, time=900, magic=1001, symbol="XAUUSD", type=0, entry=0,
              volume=0.1, price=1899.0, profit=0.0, commission=0.0, swap=0.0),
    ]
    fake_mt5 = types.ModuleType("MetaTrader5")
    fake_mt5.history_deals_get = lambda a, b: deals
    fake_mt5.account_info = lambda: SimpleNamespace(balance=10000.0, equity=10050.0)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_mt5)

    # Подменяем путь БД store на временный (record_poll использует _DEFAULT_DB).
    import performance.store as store_mod
    db = tmp_path / "perf.db"
    monkeypatch.setattr(store_mod, "_DEFAULT_DB", db)

    agent = HistoryAgent("History", EventBus())
    agent._persist_track()

    s = PerformanceStore(db)
    trades = s.closed_trades()
    s.close()
    assert {t["ticket"] for t in trades} == {1, 2}     # открывающая (entry=0) отфильтрована
    assert len(trades) == 2
```

- [ ] **Step 5: Прогон новых + регрессия пакета**

Run: `python -m pytest tests/performance/ -q`
Expected: все зелёные (6 metrics + 9 evaluator + 5 store + 1 persist = 21 passed). Падение → STOP, report.

- [ ] **Step 6: Commit**

```bash
git add agents/history_agent.py web/api_routes.py .gitignore tests/performance/test_history_persist.py
git commit -m "feat(performance): запись трека из HistoryAgent + GET /performance (per-strategy go/no-go)"
```
(трейлер)

---

## Task 5: Полный прогон + память

**Files:**
- Modify: `C:\Users\paha4\.claude\projects\i--development-projects-MillionsKeeper\memory\project_millionskeeper.md` (вне git)

- [ ] **Step 1: Полный прогон (регрессия)**

Run: `python -m pytest -q`
Expected: прежние 550 passed + новые 21 = **571 passed, 3 xfailed**. Записать фактические числа. Любое падение незелёных → STOP, report.

- [ ] **Step 2: Обновить память**

В `project_millionskeeper.md`:
- В блок «Тесты»: добавить `tests/performance/` (forward-track, 21 кейс: metrics/evaluator/store/persist).
- «Текущий прогон»: обновить число passed.
- В запись монетизации/валидации: отметить, что **kill-criterion #1 (forward-edge) получил инструмент** — пакет `performance/` (durable SQLite-трек + go/no-go метрики per-strategy, эндпоинт `/performance`); осталось операционное (запустить live + накопить трек) + MyFXBook-верификация (отдельный слайс).
- Указать ключевые пути: спека/план `docs/superpowers/specs|plans/2026-06-06-forward-track-record*`.

(Память вне git — не коммитить.)

- [ ] **Step 3: Commit (если остались незакоммиченные тест/докси-файлы — обычно нет)**

Подтвердить `git status` чистый (всё закоммичено в Tasks 1–4). Память не коммитится.

---

## Self-Review (выполнено автором плана)

- **Покрытие спеки:** store SQLite (дедуп/equity/closed_trades/series) → Task 3; чистые metrics (+per_strategy) → Task 1; evaluator (Thresholds/PASS/FAIL/INSUFFICIENT, moderate) → Task 2; интеграция HistoryAgent (аддитивно, изолированный `_persist_track`) + `/performance` + .gitignore → Task 4; полный прогон + память → Task 5. ✅
- **Плейсхолдеров нет** — весь код приведён целиком; команды и ожидаемые результаты явные. ✅
- **Согласованность имён/сигнатур:** `compute(trades)`, `per_strategy(trades, magic_to_strategy)`, `evaluate(metrics, thresholds=_DEFAULT, *, is_strategy=False)`, `Thresholds(...)`, `PerformanceStore(db_path).upsert_deals/record_equity/closed_trades/equity_series/close`, `record_poll(closed_deals, balance, equity, db_path)` — единообразны между задачами и тестами. ✅
- **Денежный путь не тронут:** `_load_history`/execution не изменяются; `_persist_track` изолирован и всё в try. ✅
- **JSON-safety:** inf/nan санитайзятся в эндпоинте (`_json_safe`) — Starlette JSONResponse не сериализует inf. ✅
- **Тред-affinity SQLite:** запись через `record_poll` (открытие в executor-треде), чтение в эндпоинте — отдельный инстанс; конфликтов нет. ✅
- **Числа кейсов:** 6 + 9 + 5 + 1 = 21. ✅
