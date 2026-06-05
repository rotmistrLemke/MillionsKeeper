"""
Стримит обновления текущей (формирующейся) свечи в WS клиентам.
Каждый клиент подписывается на (symbol, timeframe) — бэкенд опрашивает
MT5 раз в N мс и рассылает candle_update.
"""
import asyncio
import logging
from typing import Dict, Tuple

from fastapi import WebSocket

logger = logging.getLogger("ChartStreamer")


class ChartStreamer:
    def __init__(self, interval_ms: int = 500):
        self._subs: Dict[WebSocket, Tuple[str, str]] = {}
        self._task = None
        self._interval = interval_ms / 1000
        self._stopped = False

    def subscribe(self, ws: WebSocket, symbol: str, timeframe: str):
        self._subs[ws] = (symbol, timeframe.upper())

    def unsubscribe(self, ws: WebSocket):
        self._subs.pop(ws, None)

    async def start(self):
        if self._task is not None:
            return
        self._stopped = False
        self._task = asyncio.create_task(self._loop())
        logger.info("ChartStreamer started")

    async def stop(self):
        self._stopped = True
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        try:
            import MetaTrader5 as mt5
        except ImportError:
            logger.error("MetaTrader5 not available")
            return

        from web.ws_manager import ws_manager

        tf_map = {
            "M1":  mt5.TIMEFRAME_M1,
            "M5":  mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1":  mt5.TIMEFRAME_H1,
            "H4":  mt5.TIMEFRAME_H4,
            "D1":  mt5.TIMEFRAME_D1,
        }

        while not self._stopped:
            try:
                if not self._subs:
                    await asyncio.sleep(self._interval)
                    continue

                # Группируем подписчиков по (symbol, timeframe), чтобы
                # вызов MT5 делать один раз на уникальный ключ.
                groups: Dict[Tuple[str, str], list] = {}
                for ws, key in list(self._subs.items()):
                    groups.setdefault(key, []).append(ws)

                for (sym, tf_key), wss in groups.items():
                    tf = tf_map.get(tf_key)
                    if tf is None:
                        continue
                    rates = mt5.copy_rates_from_pos(sym, tf, 0, 1)
                    if rates is None or len(rates) == 0:
                        continue
                    r = rates[-1]
                    tick = mt5.symbol_info_tick(sym)
                    bid = float(tick.bid) if tick else None

                    payload = {
                        "symbol":    sym,
                        "timeframe": tf_key,
                        "candle": {
                            "time":   int(r["time"]),
                            "open":   float(r["open"]),
                            "high":   float(r["high"]),
                            "low":    float(r["low"]),
                            "close":  float(r["close"]),
                            "volume": float(r["tick_volume"]),
                        },
                        "bid": bid,
                    }
                    for ws in wss:
                        await ws_manager.send_to(ws, "candle_update", payload)
            except Exception as e:
                logger.warning(f"chart streamer iter: {e}")
            await asyncio.sleep(self._interval)


chart_streamer = ChartStreamer(interval_ms=500)
