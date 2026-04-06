import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event


class IndicatorAgent(BaseAgent):
    """
    Подписывается на NEW_BAR и рассчитывает все индикаторы для символа.
    Публикует INDICATORS_READY с результатами.
    """
    description = "Расчёт MA, MACD, RSI, ATR, ADX"

    def __init__(self, name: str, bus: EventBus, timeframe):
        super().__init__(name, bus)
        self.timeframe = timeframe
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["calculated"] = 0
        bus.subscribe(EventType.NEW_BAR, self._on_new_bar)

    async def _on_new_bar(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание NEW_BAR")
        event = await self._queue.get()
        symbol = event.payload["symbol"]

        await self.emit_status(AgentStatus.RUNNING, f"Расчёт индикаторов {symbol}")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._calc_indicators, symbol
            )
            self.metrics["calculated"] = self.metrics.get("calculated", 0) + 1
            await self.emit(EventType.INDICATORS_READY, result, correlation_id=event.correlation_id)
            await self.emit_status(AgentStatus.IDLE, f"Готово: {symbol}")
        except Exception as e:
            self._logger.error(f"Indicator calc failed for {symbol}: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

    def _calc_indicators(self, symbol: str) -> dict:
        from indicators import MovingAverage, MACD, RSI, ATR, ADX

        ma = MovingAverage()
        macd_ind = MACD()
        rsi_ind = RSI()
        atr_ind = ATR()
        adx_ind = ADX()

        # MA — как в боте: сначала get_ma_for_symbol, потом cross/angle
        fast_ma = ma.get_ma_for_symbol(symbol, self.timeframe, 8)
        slow_ma = ma.get_ma_for_symbol(symbol, self.timeframe, 21)
        signal_ma = ma.ma_cross_signal(fast_ma, slow_ma, symbol)

        # ATR
        atr_value = atr_ind.calculate_atr(symbol, self.timeframe)

        # MA critical angle (с ATR)
        signal_critical = ma.ma_critical_angle(fast_ma, slow_ma, symbol, atr_value)

        # MACD — calculate_macd_manual возвращает (hist_line, prev_hist_line, signal_line)
        hist_line, prev_hist_line, signal_line = macd_ind.calculate_macd_manual(symbol, self.timeframe)
        macd_signal = macd_ind.MACD_signal(hist_line, prev_hist_line, signal_line)

        # RSI — get_rsi_talib возвращает DataFrame, RSI_signal принимает 3 значения
        rsi_data = rsi_ind.get_rsi_talib(symbol, self.timeframe)
        rsi_signal = {"signal": "NO_SIGNAL"}
        rsi_value = None
        if rsi_data is not None and 'RSI' in rsi_data and len(rsi_data['RSI']) >= 3:
            rsi_val = rsi_data['RSI'].iloc[-1]
            prev_rsi = rsi_data['RSI'].iloc[-2]
            prev2_rsi = rsi_data['RSI'].iloc[-3]
            rsi_value = float(rsi_val)
            rsi_signal = rsi_ind.RSI_signal(rsi_val, prev_rsi, prev2_rsi)

        # ADX
        adx_values = adx_ind.ADX(symbol, self.timeframe)
        adx_val = float(adx_values[-1]) if adx_values is not None and len(adx_values) > 0 else 0.0

        return {
            "symbol": symbol,
            "signal_ma": signal_ma.get("signal", "NO_SIGNAL") if isinstance(signal_ma, dict) else "NO_SIGNAL",
            "signal_critical_angle": signal_critical.get("signal", "NO_SIGNAL") if isinstance(signal_critical, dict) else "NO_SIGNAL",
            "macd_signal": macd_signal.get("signal", "NO_SIGNAL") if isinstance(macd_signal, dict) else "NO_SIGNAL",
            "rsi_signal": rsi_signal.get("signal", "NO_SIGNAL") if isinstance(rsi_signal, dict) else "NO_SIGNAL",
            "rsi_value": rsi_value,
            "atr_value": atr_value,
            "adx_value": adx_val,
            "ema8": float(fast_ma) if fast_ma is not None else None,
            "ema21": float(slow_ma) if slow_ma is not None else None,
        }
