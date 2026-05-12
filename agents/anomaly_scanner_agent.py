import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from agents.base_agent import BaseAgent, AgentStatus
from anomaly.detector import DetectorConfig, evaluate
from anomaly.schemas import AnomalyType, DetectResult, Snapshot
from anomaly.store import AnomalyStore
from core.events import EventType


def _types_to_str(types) -> List[str]:
    return sorted({t.value for t in types})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnomalyScannerAgent(BaseAgent):
    """Сканер аномалий по всем символам Market Watch на H1."""
    description = "Сканер аномалий EMA50/ATR + Stoch на H1"

    def __init__(self, name: str, bus, store: AnomalyStore,
                 detector_cfg: DetectorConfig,
                 scan_interval_sec: int,
                 miss_tolerance: int,
                 timeframe: int,
                 bars_to_fetch: int,
                 db_path: str):
        super().__init__(name, bus)
        self.store = store
        self.cfg = detector_cfg
        self.scan_interval_sec = scan_interval_sec
        self.miss_tolerance = miss_tolerance
        self.timeframe = timeframe
        self.bars_to_fetch = bars_to_fetch
        self.db_path = db_path

        self.active: Dict[str, dict] = {}
        self.metrics.update({
            "scans": 0, "active_count": 0,
            "opened_total": 0, "closed_total": 0,
            "last_scan_sec": 0.0, "last_scan_at": None,
        })

    # ---- lifecycle ----

    def load_active_from_store(self):
        rows = self.store.recover_active()
        for r in rows:
            types = {AnomalyType(t) for t in r["types"].split(",") if t}
            snap = Snapshot(
                price=r["open_price"], ema50=r["open_ema50"], atr=r["open_atr"],
                dist_atr=r["open_dist_atr"], stoch_k=r["open_stoch_k"],
                stoch_d=r["open_stoch_d"], bar_time=r["opened_at"],
            )
            self.active[r["symbol"]] = {
                "id": r["id"], "types": types, "snapshot": snap,
                "opened_at": r["opened_at"], "misses": 0,
            }
        self.metrics["active_count"] = len(self.active)

    async def run(self):
        if self.metrics["scans"] == 0 and not self.active:
            self.load_active_from_store()
        await self.scan_once()
        await asyncio.sleep(self.scan_interval_sec)

    # ---- one scan iteration ----

    async def scan_once(self):
        started = datetime.now(timezone.utc)
        await self.emit_status(AgentStatus.RUNNING, "scan started")

        symbols = list(self._list_symbols())
        self._logger.info(f"scan_once: {len(symbols)} symbols, active={len(self.active)}")
        seen: set = set()
        for symbol in symbols:
            seen.add(symbol)
            try:
                df = self._fetch_df(symbol)
                result = self._evaluate(df, symbol)
            except Exception as e:
                self._logger.warning(f"scan {symbol} failed: {e}")
                continue

            await self._apply_result(symbol, result)

        missing = [s for s in self.active.keys() if s not in seen]
        for symbol in missing:
            await self._handle_missing(symbol)

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        self.metrics["scans"] += 1
        self.metrics["active_count"] = len(self.active)
        self.metrics["last_scan_sec"] = elapsed
        self.metrics["last_scan_at"] = _now_iso()
        self._logger.info(f"scan_once: done in {elapsed:.2f}s, active={len(self.active)}, opened_total={self.metrics['opened_total']}, closed_total={self.metrics['closed_total']}")
        await self.emit_status(AgentStatus.IDLE, f"scan done in {elapsed:.2f}s")

    async def _apply_result(self, symbol: str, result: DetectResult):
        was_active = symbol in self.active
        if not result.is_anomaly:
            if was_active:
                await self._close(symbol, result.snapshot)
            return

        new_types = set(result.types)
        if not was_active:
            opened_at = _now_iso()
            self.active[symbol] = {
                "id": -1, "types": new_types, "snapshot": result.snapshot,
                "opened_at": opened_at, "misses": 0,
            }
            rid = self.store.open(symbol, list(new_types), result.snapshot,
                                  opened_at=opened_at)
            self.active[symbol]["id"] = rid
            self.metrics["opened_total"] += 1
            await self.emit(EventType.ANOMALY_OPENED, self._payload(symbol))
        else:
            rec = self.active[symbol]
            rec["misses"] = 0
            old_types = rec["types"]
            changed = (new_types != old_types) or self._values_changed(rec["snapshot"], result.snapshot)
            rec["types"] = new_types
            rec["snapshot"] = result.snapshot
            self.store.update(rec["id"], list(new_types), result.snapshot)
            if changed:
                await self.emit(EventType.ANOMALY_UPDATED, self._payload(symbol))

    async def _handle_missing(self, symbol: str):
        rec = self.active.get(symbol)
        if rec is None:
            return
        rec["misses"] += 1
        if rec["misses"] >= self.miss_tolerance:
            await self._close(symbol, rec["snapshot"])

    async def _close(self, symbol: str, close_snap: Optional[Snapshot]):
        rec = self.active.pop(symbol, None)
        if rec is None:
            return
        snap = close_snap or rec["snapshot"]
        closed_at = _now_iso()
        self.store.close(rec["id"], snap, closed_at=closed_at)
        self.metrics["closed_total"] += 1
        await self.emit(EventType.ANOMALY_CLOSED, {
            "symbol": symbol,
            "closed_at": closed_at,
        })

    # ---- helpers (overridable in tests) ----

    def _values_changed(self, old: Snapshot, new: Snapshot) -> bool:
        if old is None or new is None:
            return True
        return (
            abs(old.dist_atr - new.dist_atr) >= 0.1
            or abs(old.stoch_k - new.stoch_k) >= 1.0
        )

    def _payload(self, symbol: str) -> dict:
        rec = self.active[symbol]
        snap = rec["snapshot"]
        return {
            "symbol": symbol,
            "types": _types_to_str(rec["types"]),
            "opened_at": rec["opened_at"],
            **(snap.to_dict() if snap else {}),
        }

    def _list_symbols(self):
        import MetaTrader5 as mt5
        infos = mt5.symbols_get() or ()
        return [s.name for s in infos if getattr(s, "visible", True)]

    def _fetch_df(self, symbol: str) -> pd.DataFrame:
        import MetaTrader5 as mt5
        rates = mt5.copy_rates_from_pos(symbol, self.timeframe, 0, self.bars_to_fetch)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"no rates for {symbol}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df

    def _evaluate(self, df: pd.DataFrame, symbol: str) -> DetectResult:
        return evaluate(df, self.cfg)
