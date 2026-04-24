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
    Проверяет сигнал выхода и публикует ORDER_CLOSE_REQUEST — ТОЛЬКО
    при открытии новой свечи (событие NEW_BAR).
    """
    description = "Мониторинг открытых позиций, выход по свече"

    def __init__(self, name: str, bus: EventBus, trading, poll_interval: float = 5.0):
        super().__init__(name, bus)
        self.trading = trading
        self.poll_interval = poll_interval
        self.metrics["open_positions"] = 0
        # Словарь {ticket: pos_dict} с прошлого цикла — для детекта закрытий
        self._prev_positions: dict = {}
        # Символы, по которым пришла новая свеча — на них проверяем exit в ближайшем тике.
        self._pending_exit_symbols: set = set()
        # Ticket → флаг «breakeven уже переставлен», чтобы не дёргать order_send повторно.
        self._be_done: set = set()
        bus.subscribe(EventType.NEW_BAR, self._on_new_bar)

    async def _on_new_bar(self, event):
        sym = event.payload.get("symbol")
        if sym:
            self._pending_exit_symbols.add(sym)

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
                    self._be_done.discard(ticket)
            self._prev_positions = {p["ticket"]: p for p in positions}

            # Breakeven + trailing SL — каждый тик поллинга, для любой позиции потока,
            # у которой в настройках задан breakeven_atr или trail_atr.
            for pos in positions:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._apply_trailing_sl, pos
                )

            # Проверяем сигнал выхода ТОЛЬКО для символов с новой свечой.
            if self._pending_exit_symbols:
                targets = self._pending_exit_symbols.copy()
                self._pending_exit_symbols.clear()
                for pos in positions:
                    if pos["symbol"] in targets:
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
        import streams as streams_mod
        from settings import Dictionary
        from strategies import STRATEGIES
        from strategies.runtime import get_runtime_strategy

        symbol = prev_pos["symbol"]
        stream = streams_mod.registry.by_magic(prev_pos.get("magic"))
        if stream is None:
            stream = streams_mod.registry.by_symbol(symbol)

        reason = await asyncio.get_event_loop().run_in_executor(
            None, self._classify_close_reason, prev_pos["ticket"]
        )
        await self.emit(EventType.ORDER_CLOSED, {
            "ticket": prev_pos["ticket"],
            "symbol": symbol,
            "reason": reason,
            "type": prev_pos["type"],
            "open_price": prev_pos["open_price"],
            "stream_id": stream.id if stream else None,
            "magic": prev_pos.get("magic"),
        })

        # Сбрасываем статус торговли обратно в 0, чтобы можно было открыть новую позицию.
        # Без этого после первого трейда символ залипал в status=1 и все сигналы отбрасывались.
        if Dictionary.symbolTradingStatus.get(symbol) == 1:
            Dictionary.symbolTradingStatus[symbol] = 0
            await self.emit(EventType.TRADING_STATUS_CHANGED, {
                "symbol": symbol,
                "status": 0,
                "reason": f"position_closed:{reason}",
                "stream_id": stream.id if stream else None,
            })

        if stream is not None and stream.strategy in STRATEGIES:
            try:
                strategy = get_runtime_strategy(stream.strategy, symbol)
                strategy.on_trade_closed(
                    {"type": prev_pos["type"], "entry_price": prev_pos["open_price"]},
                    reason,
                )
            except Exception as e:
                self._logger.warning(f"on_trade_closed hook failed: {e}")

    def _apply_trailing_sl(self, pos: dict) -> None:
        """Синхронно пересчитывает breakeven + trailing SL для позиции потока
        и вызывает trading.modifySL, если уровень изменился.
        Вызывается в executor, чтобы не блокировать event-loop."""
        import streams as streams_mod
        import MetaTrader5 as mt5

        stream = streams_mod.registry.by_magic(pos.get("magic"))
        if stream is None:
            return
        be_mult   = float(getattr(stream, "breakeven_atr", 0.0) or 0.0)
        trail_mult = float(getattr(stream, "trail_atr", 0.0) or 0.0)
        if be_mult <= 0 and trail_mult <= 0:
            return

        symbol = pos["symbol"]
        # ATR на рабочем TF потока
        rates = mt5.copy_rates_from_pos(symbol, stream.timeframe, 0, 30)
        if rates is None or len(rates) < 15:
            return
        try:
            import talib
            highs = rates['high'].astype(float)
            lows  = rates['low'].astype(float)
            closes = rates['close'].astype(float)
            atr_series = talib.ATR(highs, lows, closes, timeperiod=14)
            atr = float(atr_series[-1])
        except Exception:
            return
        if not atr or atr <= 0:
            return

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return
        # ref_price для высчитывания трейла: best bid/ask в нашу сторону
        # (для BUY трейлим от max-high, для SELL — от min-low; в рантайме
        # аппроксимируем текущей ценой, т.к. high/low бара ещё не закрылся).
        entry = pos["open_price"]
        side  = pos["type"]
        ticket = pos["ticket"]
        cur_sl = float(pos.get("sl") or 0.0)

        candidate_sl = cur_sl if cur_sl > 0 else None

        if side == "BUY":
            if be_mult > 0 and ticket not in self._be_done:
                if tick.bid - entry >= be_mult * atr:
                    if candidate_sl is None or entry > candidate_sl:
                        candidate_sl = entry
                    self._be_done.add(ticket)
            if trail_mult > 0:
                cand = tick.bid - trail_mult * atr
                if candidate_sl is None or cand > candidate_sl:
                    candidate_sl = cand
        else:  # SELL
            if be_mult > 0 and ticket not in self._be_done:
                if entry - tick.ask >= be_mult * atr:
                    if candidate_sl is None or entry < candidate_sl:
                        candidate_sl = entry
                    self._be_done.add(ticket)
            if trail_mult > 0:
                cand = tick.ask + trail_mult * atr
                if candidate_sl is None or cand < candidate_sl:
                    candidate_sl = cand

        if candidate_sl is None:
            return
        # Порог «нужно двигать»: отличие от текущего > 0.1×ATR, чтобы
        # не слать order_send на каждую каплю цены.
        if cur_sl > 0 and abs(candidate_sl - cur_sl) < 0.1 * atr:
            return
        try:
            ok = self.trading.modifySL(ticket, symbol, candidate_sl)
            if ok:
                self._logger.info(
                    f"Trail SL {symbol} #{ticket}: {cur_sl:.5f} → {candidate_sl:.5f}"
                )
        except Exception as e:
            self._logger.warning(f"modifySL failed {symbol}/{ticket}: {e}")

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
        import streams as streams_mod
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

            magic = int(getattr(p, "magic", 0) or 0)
            stream = streams_mod.registry.by_magic(magic)
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
                "magic": magic,
                "stream_id": stream.id if stream else None,
                "stream_name": stream.name if stream else None,
            })
        return result

    async def _check_rsi_exit(self, pos: dict):
        """Проверяет сигнал выхода для позиции по стратегии её потока.
        Поток находим по magic позиции. Ручные позиции (stream=None) пропускаем.
        Если стратегия потока — одна из STRATEGIES, делегируем решение `strategy.get_exit_signal`.
        Иначе — legacy RSI-выход (<45 для BUY, >55 для SELL).
        """
        import streams as streams_mod
        from settings import Dictionary
        from strategies import STRATEGIES

        symbol = pos["symbol"]
        trading_status = Dictionary.symbolTradingStatus.get(symbol, 3)
        if trading_status == 3:
            return

        stream = streams_mod.registry.by_magic(pos.get("magic"))
        if stream is None:
            # Позиция не принадлежит ни одному потоку (ручная/legacy) — не вмешиваемся.
            return

        if stream.strategy in STRATEGIES:
            await self._check_strategy_exit(pos, stream)
        else:
            await self._check_legacy_rsi_exit(pos, stream)

    async def _check_strategy_exit(self, pos: dict, stream):
        from strategies.runtime import get_runtime_strategy
        from market_data_cache import cache

        symbol = pos["symbol"]
        strategy_name = stream.strategy
        try:
            def _run():
                strategy = get_runtime_strategy(strategy_name, symbol)
                df = cache.get_rates(symbol, stream.timeframe, bars=500)
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
                    "stream_id": stream.id,
                    "reason": f"strategy:{strategy_name}",
                })
        except Exception as e:
            self._logger.warning(f"Strategy exit check failed {symbol}/{strategy_name}: {e}")

    async def _check_legacy_rsi_exit(self, pos: dict, stream):
        from indicators import RSI

        symbol = pos["symbol"]
        try:
            rsi_ind = RSI()
            rsi_data = await asyncio.get_event_loop().run_in_executor(
                None, rsi_ind.get_rsi_talib, symbol, stream.timeframe
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
                    "stream_id": stream.id,
                    "rsi_value": rsi_value,
                    "position_type": pos["type"],
                })
                await self.emit(EventType.ORDER_CLOSE_REQUEST, {
                    "ticket": pos["ticket"],
                    "symbol": symbol,
                    "stream_id": stream.id,
                    "reason": f"RSI={rsi_value:.1f}",
                })
        except Exception as e:
            self._logger.warning(f"RSI exit check failed {symbol}: {e}")
