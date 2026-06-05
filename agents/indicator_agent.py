import asyncio
import pandas as pd

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event


class IndicatorAgent(BaseAgent):
    """
    Подписывается на NEW_BAR. Ищет поток по символу:
      - нет потока (или поток выключен)          → пропускаем.
      - таймфрейм потока ≠ таймфрейм события     → пропускаем.
      - стратегия потока ∈ STRATEGIES            → считаем индикаторы и entry-сигнал.
      - иначе (default/legacy)                    → считаем legacy-индикаторы MA+MACD+RSI.
    Публикует INDICATORS_READY с полем stream_id.
    """
    description = "Расчёт индикаторов активной стратегии потока"

    def __init__(self, name: str, bus: EventBus, timeframe=None):
        super().__init__(name, bus)
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["calculated"] = 0
        bus.subscribe(EventType.NEW_BAR, self._on_new_bar)

    async def _on_new_bar(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        import streams as streams_mod
        from strategies import STRATEGIES

        await self.emit_status(AgentStatus.IDLE, "Ожидание NEW_BAR")
        event = await self._queue.get()
        p = event.payload
        symbol = p["symbol"]
        bar_tf = int(p.get("timeframe") or 0)

        stream = streams_mod.registry.by_symbol(symbol)
        if stream is None or not stream.enabled:
            return
        if bar_tf and int(stream.timeframe) != bar_tf:
            return

        use_strategy = stream.strategy in STRATEGIES
        await self.emit_status(
            AgentStatus.RUNNING,
            f"Индикаторы {symbol} ({stream.strategy if use_strategy else 'default'}) [{stream.name}]"
        )
        try:
            if use_strategy:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._calc_strategy, symbol, stream.strategy, int(stream.timeframe)
                )
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._calc_indicators, symbol, int(stream.timeframe)
                )
            result["stream_id"] = stream.id
            self.metrics["calculated"] = self.metrics.get("calculated", 0) + 1
            await self.emit(EventType.INDICATORS_READY, result, correlation_id=event.correlation_id)
            await self.emit_status(AgentStatus.IDLE, f"Готово: {symbol}")
        except Exception as e:
            self._logger.error(f"Indicator calc failed for {symbol}: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

    def _calc_strategy(self, symbol: str, strategy_name: str, tf: int) -> dict:
        from market_data_cache import cache
        from strategies.runtime import get_runtime_strategy

        strategy = get_runtime_strategy(strategy_name, symbol)
        df = cache.get_rates(symbol, tf, bars=500)
        if df is None or len(df) < 50:
            return {
                "symbol": symbol,
                "strategy": strategy_name,
                "entry_signal": "NO_SIGNAL",
                "is_flat": True,
            }

        df = strategy.compute_indicators(df)
        df = strategy.compute_flat_indicators(df)
        row = df.iloc[-1]

        flat = bool(strategy.is_flat(row))
        signal = None if flat else strategy.get_entry_signal(row)

        # Собираем значения индикаторов последнего бара для UI
        ind_cols = list(strategy.indicator_columns()) + list(strategy.flat_indicator_columns())
        ind_vals = {}
        for col in ind_cols:
            if col in df.columns:
                v = df[col].iloc[-1]
                if pd.notna(v):
                    try:
                        ind_vals[col] = float(v)
                    except (TypeError, ValueError):
                        pass

        def _get_float(col):
            if col in df.columns:
                v = df[col].iloc[-1]
                if pd.notna(v):
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None
            return None

        return {
            "symbol": symbol,
            "strategy": strategy_name,
            "entry_signal": signal or "NO_SIGNAL",
            "is_flat": flat,
            "indicators_raw": ind_vals,
            # legacy-совместимые поля для UI / SignalAgent
            "signal_ma": "NO_SIGNAL",
            "signal_critical_angle": "NO_SIGNAL",
            "macd_signal": "NO_SIGNAL",
            "rsi_signal": "NO_SIGNAL",
            "rsi_value":  _get_float('rsi'),
            "atr_value":  _get_float('atr') or _get_float('flat_atr'),
            "adx_value":  _get_float('flat_adx') or 0.0,
            "ema8":       _get_float('ema8'),
            "ema21":      _get_float('ema21'),
        }

    def _calc_indicators(self, symbol: str, tf: int) -> dict:
        from indicators import MovingAverage, MACD, RSI, ATR, ADX

        ma = MovingAverage()
        macd_ind = MACD()
        rsi_ind = RSI()
        atr_ind = ATR()
        adx_ind = ADX()

        fast_ma = ma.get_ma_for_symbol(symbol, tf, 8)
        slow_ma = ma.get_ma_for_symbol(symbol, tf, 21)
        signal_ma = ma.ma_cross_signal(fast_ma, slow_ma, symbol)

        atr_value = atr_ind.calculate_atr(symbol, tf)
        signal_critical = ma.ma_critical_angle(fast_ma, slow_ma, symbol, atr_value)

        hist_line, prev_hist_line, signal_line = macd_ind.calculate_macd_manual(symbol, tf)
        macd_signal = macd_ind.MACD_signal(hist_line, prev_hist_line, signal_line)

        rsi_data = rsi_ind.get_rsi_talib(symbol, tf)
        rsi_signal = {"signal": "NO_SIGNAL"}
        rsi_value = None
        if rsi_data is not None and 'RSI' in rsi_data and len(rsi_data['RSI']) >= 3:
            rsi_val = rsi_data['RSI'].iloc[-1]
            prev_rsi = rsi_data['RSI'].iloc[-2]
            prev2_rsi = rsi_data['RSI'].iloc[-3]
            rsi_value = float(rsi_val)
            rsi_signal = rsi_ind.RSI_signal(rsi_val, prev_rsi, prev2_rsi)

        from indicators import Alligator
        df = Alligator().Df(symbol, tf)
        adx_values, _, _ = adx_ind.ADX(
            df['high'].values, df['low'].values, df['close'].values, 14
        )
        adx_val = float(adx_values[-1]) if adx_values is not None and len(adx_values) > 0 else 0.0

        return {
            "symbol": symbol,
            "signal_ma": signal_ma.get("signal", "NO_SIGNAL") if isinstance(signal_ma, dict) else "NO_SIGNAL",
            "signal_critical_angle": signal_critical.get("signal", "NO_SIGNAL") if isinstance(signal_critical, dict) else "NO_SIGNAL",
            "macd_signal": macd_signal.get("signal", "NO_SIGNAL") if isinstance(macd_signal, dict) else "NO_SIGNAL",
            "rsi_signal": rsi_signal.get("signal", "NO_SIGNAL") if isinstance(rsi_signal, dict) else "NO_SIGNAL",
            "rsi_value": rsi_value,
            "atr_value": float(atr_value.iloc[-1]) if atr_value is not None and hasattr(atr_value, 'iloc') else atr_value,
            "adx_value": adx_val,
            "ema8": float(fast_ma.iloc[-1]) if fast_ma is not None and hasattr(fast_ma, 'iloc') else None,
            "ema21": float(slow_ma.iloc[-1]) if slow_ma is not None and hasattr(slow_ma, 'iloc') else None,
        }
