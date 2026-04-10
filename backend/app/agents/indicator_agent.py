"""
agents/indicator_agent.py — Вычисление технических индикаторов.

Подписывается на NEW_BAR (M1 или H1), вычисляет индикаторы активной стратегии.
Публикует INDICATORS_READY с полным набором значений.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd
import talib

from app.agents.base_agent import BaseAgent, AgentStatus
from app.core.config import settings
from core.event_bus import EventBus
from core.events import Event, EventType


class IndicatorAgent(BaseAgent):
    description = "Вычисление TA-Lib индикаторов по M1+H1 барам"

    def __init__(self, name: str, bus: EventBus, bars: int = 300):
        super().__init__(name, bus)
        self.bars = bars
        self._queue: asyncio.Queue = asyncio.Queue()
        bus.subscribe(EventType.NEW_BAR, self._on_new_bar)

    async def _on_new_bar(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание новой свечи")
        event = await self._queue.get()
        p = event.payload
        symbol: str = p["symbol"]
        tf_id: int  = p.get("tf_id", settings.scalp_timeframe)
        tf_name: str = p.get("timeframe", "M1")

        await self.emit_status(AgentStatus.RUNNING, f"{symbol} {tf_name}")

        df = await self._load_bars(symbol, tf_id)
        if df is None or len(df) < 50:
            return

        indicators = self._compute(df)
        indicators["symbol"]    = symbol
        indicators["timeframe"] = tf_name
        indicators["tf_id"]     = tf_id

        await self.emit(EventType.INDICATORS_READY, indicators, correlation_id=event.correlation_id)

    async def _load_bars(self, symbol: str, timeframe: int) -> Optional[pd.DataFrame]:
        rates = await asyncio.get_event_loop().run_in_executor(
            None, lambda: mt5.copy_rates_from_pos(symbol, timeframe, 0, self.bars)
        )
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    @staticmethod
    def _compute(df: pd.DataFrame) -> dict:
        close = df["close"].values.astype(float)
        high  = df["high"].values.astype(float)
        low   = df["low"].values.astype(float)

        ema8  = talib.EMA(close, timeperiod=8)
        ema21 = talib.EMA(close, timeperiod=21)
        macd_line, signal_line, _ = talib.MACD(close, 12, 26, 9)
        rsi   = talib.RSI(close, timeperiod=14)
        atr   = talib.ATR(high, low, close, timeperiod=14)
        adx   = talib.ADX(high, low, close, timeperiod=14)

        def last(arr):
            return float(arr[-1]) if len(arr) > 0 and not pd.isna(arr[-1]) else None

        # EMA сигнал
        e8, e21 = last(ema8), last(ema21)
        if e8 is not None and e21 is not None:
            signal_ma = "BUY" if e8 > e21 else "SELL" if e8 < e21 else "NO_SIGNAL"
        else:
            signal_ma = "NO_SIGNAL"

        # MACD сигнал
        m_cur  = last(macd_line)
        m_prev = float(macd_line[-2]) if len(macd_line) >= 2 and not pd.isna(macd_line[-2]) else None
        m_sig  = last(signal_line)
        if m_cur is not None and m_prev is not None and m_sig is not None:
            if m_cur > 0 and m_cur > m_prev and m_cur > m_sig:
                macd_signal = "BUY"
            elif m_cur < 0 and m_cur < m_prev and m_cur < m_sig:
                macd_signal = "SELL"
            else:
                macd_signal = "NO_SIGNAL"
        else:
            macd_signal = "NO_SIGNAL"

        # RSI сигнал
        r_cur  = last(rsi)
        r_prev = float(rsi[-2]) if len(rsi) >= 2 and not pd.isna(rsi[-2]) else None
        r_prev2 = float(rsi[-3]) if len(rsi) >= 3 and not pd.isna(rsi[-3]) else None
        if r_cur and r_prev and r_prev2:
            if 55 < r_cur < 70 and r_prev > r_prev2:
                rsi_signal = "BUY"
            elif 30 < r_cur < 45 and r_prev < r_prev2:
                rsi_signal = "SELL"
            else:
                rsi_signal = "NO_SIGNAL"
        else:
            rsi_signal = "NO_SIGNAL"

        return {
            "signal_ma":             signal_ma,
            "signal_critical_angle": signal_ma,  # TODO: angle-based check
            "macd_signal":           macd_signal,
            "rsi_signal":            rsi_signal,
            "ema8":                  e8,
            "ema21":                 e21,
            "macd_line":             m_cur,
            "rsi_value":             r_cur,
            "atr_value":             last(atr),
            "adx_value":             last(adx),
        }
