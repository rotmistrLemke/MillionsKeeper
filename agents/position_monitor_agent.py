import asyncio
import time
import pandas as pd

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType


class PositionMonitorAgent(BaseAgent):
    """
    Периодически опрашивает открытые позиции.
    Публикует POSITION_UPDATE с live P&L.
    Проверяет RSI-выход и публикует ORDER_CLOSE_REQUEST.
    """
    description = "Мониторинг открытых позиций, RSI-выход"

    def __init__(self, name: str, bus: EventBus, trading, poll_interval: float = 5.0):
        super().__init__(name, bus)
        self.trading = trading
        self.poll_interval = poll_interval
        self.metrics["open_positions"] = 0
        # Словарь {ticket: pos_dict} с прошлого цикла — для детекта закрытий
        self._prev_positions: dict = {}

    async def run(self):
        await self.emit_status(AgentStatus.RUNNING, "Проверка позиций")
        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None, self._get_positions_with_pnl
            )
            self.metrics["open_positions"] = len(positions)
            await self.emit(EventType.POSITION_UPDATE, {"positions": positions})

            # Детект позиций, которые пропали с прошлого цикла (SL/TP/внеш. закрытие)
            current_tickets = {p["ticket"] for p in positions}
            for ticket, prev_pos in list(self._prev_positions.items()):
                if ticket not in current_tickets:
                    await self._on_position_disappeared(prev_pos)
            self._prev_positions = {p["ticket"]: p for p in positions}

            # Проверяем сигнал выхода
            for pos in positions:
                await self._check_rsi_exit(pos)

        except Exception as e:
            self._logger.error(f"Position monitor error: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

        await self.emit_status(AgentStatus.IDLE, f"Позиций: {self.metrics['open_positions']}")
        await asyncio.sleep(self.poll_interval)

    async def _on_position_disappeared(self, prev_pos: dict):
        """Позиция исчезла из списка открытых — закрыта SL/TP или вручную извне.
        Пытаемся определить причину по истории MT5 и вызвать strategy.on_trade_closed.
        """
        from settings import GlobalValues, Dictionary
        from strategies import STRATEGIES
        from strategies.runtime import get_runtime_strategy

        symbol = prev_pos["symbol"]

        reason = await asyncio.get_event_loop().run_in_executor(
            None, self._classify_close_reason, prev_pos["ticket"]
        )
        await self.emit(EventType.ORDER_CLOSED, {
            "ticket": prev_pos["ticket"],
            "symbol": symbol,
            "reason": reason,
            "type": prev_pos["type"],
            "open_price": prev_pos["open_price"],
        })

        # Сбрасываем статус торговли обратно в 0, чтобы можно было открыть новую позицию.
        # Без этого после первого трейда символ залипал в status=1 и все сигналы отбрасывались.
        if Dictionary.symbolTradingStatus.get(symbol) == 1:
            Dictionary.symbolTradingStatus[symbol] = 0
            await self.emit(EventType.TRADING_STATUS_CHANGED, {
                "symbol": symbol,
                "status": 0,
                "reason": f"position_closed:{reason}",
            })

        active = GlobalValues.active_strategy
        if active in STRATEGIES:
            try:
                strategy = get_runtime_strategy(active, symbol)
                strategy.on_trade_closed(
                    {"type": prev_pos["type"], "entry_price": prev_pos["open_price"]},
                    reason,
                )
            except Exception as e:
                self._logger.warning(f"on_trade_closed hook failed: {e}")

    def _classify_close_reason(self, ticket: int) -> str:
        """Определяет причину закрытия по MT5 history_deals.
        Возвращает 'SL' | 'TP' | 'SIGNAL' | 'MANUAL'.
        """
        try:
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta
            end = datetime.now() + timedelta(minutes=1)
            start = end - timedelta(days=7)
            deals = mt5.history_deals_get(start, end, position=ticket)
            if not deals:
                return "MANUAL"
            # Последняя сделка по позиции — закрывающая
            closing = deals[-1]
            comment = (closing.comment or "").lower()
            if "sl" in comment or "stop loss" in comment:
                return "SL"
            if "tp" in comment or "take profit" in comment:
                return "TP"
            if "signal" in comment or "strategy" in comment:
                return "SIGNAL"
            return "MANUAL"
        except Exception:
            return "MANUAL"

    def _get_positions_with_pnl(self) -> list:
        import MetaTrader5 as mt5
        positions = self.trading.getPositions()
        result = []
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            if tick:
                if p.type == mt5.ORDER_TYPE_BUY:
                    pnl = (tick.bid - p.price_open) / mt5.symbol_info(p.symbol).point
                else:
                    pnl = (p.price_open - tick.ask) / mt5.symbol_info(p.symbol).point
            else:
                pnl = 0.0

            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "open_price": p.price_open,
                "sl": p.sl,
                "pnl_points": round(pnl, 1),
                "pnl_money": round(p.profit, 2),
                "open_time": int(p.time),
            })
        return result

    async def _check_rsi_exit(self, pos: dict):
        """Проверяет сигнал выхода.
        Если `GlobalValues.active_strategy` — одна из стратегий в STRATEGIES,
        делегирует решение `strategy.get_exit_signal(row, position_dict)`.
        Иначе (default) — legacy RSI-выход (<45 для BUY, >55 для SELL).
        """
        from settings import Dictionary, GlobalValues
        from strategies import STRATEGIES

        symbol = pos["symbol"]
        trading_status = Dictionary.symbolTradingStatus.get(symbol, 3)
        if trading_status == 3:
            return

        active = GlobalValues.active_strategy
        if active in STRATEGIES:
            await self._check_strategy_exit(pos, active)
        else:
            await self._check_legacy_rsi_exit(pos)

    async def _check_strategy_exit(self, pos: dict, strategy_name: str):
        from settings import GlobalValues
        from strategies.runtime import get_runtime_strategy
        from market_data_cache import cache

        symbol = pos["symbol"]
        try:
            def _run():
                strategy = get_runtime_strategy(strategy_name, symbol)
                df = cache.get_rates(symbol, GlobalValues.time_frame, bars=500)
                if df is None or len(df) < 50:
                    return None
                df = strategy.compute_indicators(df)
                df = strategy.compute_flat_indicators(df)
                row = df.iloc[-1]
                position_dict = {
                    "type": pos["type"],
                    "entry_price": pos["open_price"],
                    "volume": pos["volume"],
                    "sl": pos.get("sl"),
                }
                return bool(strategy.get_exit_signal(row, position_dict))

            should_close = await asyncio.get_event_loop().run_in_executor(None, _run)
            if should_close:
                await self.emit(EventType.ORDER_CLOSE_REQUEST, {
                    "ticket": pos["ticket"],
                    "symbol": symbol,
                    "reason": f"strategy:{strategy_name}",
                })
        except Exception as e:
            self._logger.warning(f"Strategy exit check failed {symbol}/{strategy_name}: {e}")

    async def _check_legacy_rsi_exit(self, pos: dict):
        from settings import GlobalValues
        from indicators import RSI

        symbol = pos["symbol"]
        try:
            rsi_ind = RSI()
            rsi_data = await asyncio.get_event_loop().run_in_executor(
                None, rsi_ind.get_rsi_talib, symbol, GlobalValues.time_frame
            )
            if rsi_data is None or 'RSI' not in rsi_data or len(rsi_data['RSI']) < 1:
                return
            rsi_value = float(rsi_data['RSI'].iloc[-1])
            if pd.isna(rsi_value):
                return

            should_close = (
                (pos["type"] == "BUY" and rsi_value < 45) or
                (pos["type"] == "SELL" and rsi_value > 55)
            )
            if should_close:
                await self.emit(EventType.RSI_EXIT_TRIGGERED, {
                    "symbol": symbol,
                    "ticket": pos["ticket"],
                    "rsi_value": rsi_value,
                    "position_type": pos["type"],
                })
                await self.emit(EventType.ORDER_CLOSE_REQUEST, {
                    "ticket": pos["ticket"],
                    "symbol": symbol,
                    "reason": f"RSI={rsi_value:.1f}",
                })
        except Exception as e:
            self._logger.warning(f"RSI exit check failed {symbol}: {e}")
