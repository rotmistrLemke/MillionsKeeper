import asyncio
from datetime import datetime, timedelta, time as dtime

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event
from settings import Dictionary


class ExecutionAgent(BaseAgent):
    """
    Подписывается на SIGNAL_GENERATED и ORDER_CLOSE_REQUEST.
    Открывает / закрывает позиции через trading.py.
    """
    description = "Открытие и закрытие ордеров"

    # Блокировка потока при просадке > 35% до начала следующей недели.
    DD_BLOCK_THRESHOLD = 0.35
    NIGHT_BLOCK_START = dtime(23, 50)
    NIGHT_BLOCK_END   = dtime(5, 0)

    def __init__(self, name: str, bus: EventBus, trading):
        super().__init__(name, bus)
        self.trading = trading
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["opened_today"] = 0
        self.metrics["closed_today"] = 0
        # Per-stream DD state.
        self._stream_peak: dict[str, float] = {}
        self._stream_dd_block_until: dict[str, datetime] = {}
        self._stream_week_start: dict[str, datetime] = {}
        bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal)
        bus.subscribe(EventType.ORDER_CLOSE_REQUEST, self._on_close_request)

    @classmethod
    def _is_night_block(cls) -> tuple[bool, str]:
        t = datetime.now().time()
        if t >= cls.NIGHT_BLOCK_START or t < cls.NIGHT_BLOCK_END:
            return True, "ночная блокировка торговли (23:50–05:00)"
        return False, ""

    @staticmethod
    def _monday_start(now: datetime) -> datetime:
        start = now - timedelta(days=now.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _next_monday(now: datetime) -> datetime:
        wd = now.weekday()
        days = 7 - wd if wd > 0 else 7
        return (now + timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def _compute_stream_equity(self, stream, week_start: datetime) -> float | None:
        """stream.deposit + realized(magic,с начала недели) + unrealized(magic,открытые)."""
        import MetaTrader5 as mt5
        realized = 0.0
        deals = mt5.history_deals_get(week_start, datetime.now())
        if deals:
            for d in deals:
                if getattr(d, "magic", 0) == stream.magic:
                    realized += (
                        float(d.profit or 0.0)
                        + float(getattr(d, "commission", 0.0) or 0.0)
                        + float(getattr(d, "swap", 0.0) or 0.0)
                    )
        unrealized = 0.0
        positions = mt5.positions_get(symbol=stream.symbol)
        if positions:
            for p in positions:
                if getattr(p, "magic", 0) == stream.magic:
                    unrealized += (
                        float(p.profit or 0.0)
                        + float(getattr(p, "swap", 0.0) or 0.0)
                    )
        return float(stream.deposit) + realized + unrealized

    def _check_stream_drawdown(self, stream) -> tuple[bool, str]:
        """Просадка по выделенному депозиту потока. (allowed, reason)."""
        if float(stream.deposit or 0.0) <= 0:
            return True, ""  # без выделенного депозита DD не контролируем

        now = datetime.now()

        until = self._stream_dd_block_until.get(stream.id)
        if until is not None:
            if now >= until:
                self._stream_dd_block_until.pop(stream.id, None)
                self._stream_peak.pop(stream.id, None)
                self._stream_week_start.pop(stream.id, None)
            else:
                return False, (
                    f"просадка потока > 35% — блокировка до {until:%Y-%m-%d %H:%M}"
                )

        week_start = self._stream_week_start.get(stream.id)
        if week_start is None or (now - week_start) > timedelta(days=7):
            week_start = self._monday_start(now)
            self._stream_week_start[stream.id] = week_start
            self._stream_peak.pop(stream.id, None)

        try:
            equity = self._compute_stream_equity(stream, week_start)
        except Exception as e:
            self._logger.warning(f"stream equity calc failed {stream.id}: {e}")
            return True, ""

        peak = self._stream_peak.get(stream.id, float(stream.deposit))
        if equity > peak:
            peak = equity
        self._stream_peak[stream.id] = peak

        if peak > 0 and equity < peak:
            dd = (peak - equity) / peak
            if dd > self.DD_BLOCK_THRESHOLD:
                block_until = self._next_monday(now)
                self._stream_dd_block_until[stream.id] = block_until
                return False, (
                    f"просадка потока {dd*100:.1f}% > 35% — "
                    f"блокировка до {block_until:%Y-%m-%d %H:%M}"
                )
        return True, ""

    async def _on_signal(self, event: Event):
        await self._queue.put(("signal", event))

    async def _on_close_request(self, event: Event):
        await self._queue.put(("close", event))

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание сигналов")
        kind, event = await self._queue.get()

        if kind == "signal":
            await self._handle_signal(event)
        elif kind == "close":
            await self._handle_close(event)

    async def _handle_signal(self, event: Event):
        import streams as streams_mod
        p = event.payload
        symbol = p["symbol"]
        signal = p["signal"]
        trading_status = Dictionary.symbolTradingStatus.get(symbol, 3)

        if signal == "NO_SIGNAL":
            await self.emit_status(AgentStatus.IDLE, f"{symbol}: NO_SIGNAL")
            return
        if trading_status != 0:
            await self.emit_status(
                AgentStatus.IDLE,
                f"{symbol}: сигнал {signal} отброшен (trading_status={trading_status})"
            )
            return

        stream_id = p.get("stream_id")
        stream = streams_mod.registry.get(stream_id) if stream_id else streams_mod.registry.by_symbol(symbol)
        if stream is None or not stream.enabled:
            await self.emit_status(AgentStatus.IDLE, f"{symbol}: нет активного потока")
            return

        night_blocked, night_reason = self._is_night_block()
        if night_blocked:
            await self.emit_status(AgentStatus.IDLE, f"{symbol}: {night_reason}")
            return

        allowed, reason = self._check_stream_drawdown(stream)
        if not allowed:
            await self.emit_status(AgentStatus.IDLE, f"{symbol} [{stream.name}]: {reason}")
            return

        await self.emit_status(AgentStatus.RUNNING, f"Открытие {signal} {symbol} [{stream.name}]")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._open_order, stream, signal, p.get("indicators", {})
            )
            if result:
                self.metrics["opened_today"] = self.metrics.get("opened_today", 0) + 1
                await self.emit(EventType.ORDER_OPENED, {
                    "symbol": symbol,
                    "type": signal,
                    "volume": result.get("volume"),
                    "price": result.get("price"),
                    "ticket": result.get("ticket"),
                    "stream_id": stream.id,
                    "magic": stream.magic,
                    "indicators": p.get("indicators", {}),
                })
                Dictionary.symbolTradingStatus[symbol] = 1
                await self.emit(EventType.TRADING_STATUS_CHANGED, {
                    "symbol": symbol,
                    "status": 1,
                    "reason": "order_opened",
                    "stream_id": stream.id,
                })
        except Exception as e:
            self._logger.error(f"Open order failed {symbol}: {e}")
            await self.emit(EventType.ORDER_ERROR, {"symbol": symbol, "error": str(e)})

    def _open_order(self, stream, signal: str, indicators: dict) -> dict:
        import MetaTrader5 as mt5
        from market_data_cache import cache

        symbol = stream.symbol
        atr = indicators.get("atr_value", 0)
        symbol_info = cache.get_symbol_info(symbol)
        if symbol_info is None:
            return None

        order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
        stop_loss_pips = 2 * atr / symbol_info.point if atr > 0 else 100

        fixed_volume = float(stream.volume or 0.0)
        if fixed_volume > 0:
            volume = fixed_volume
        else:
            volume = self.trading.calculateSafeTradeWithMargin(
                symbol, 80 if signal == "BUY" else 90, stop_loss_pips, order_type
            )
        if not volume or volume <= 0:
            return None

        # Расчёт SL/TP по множителям ATR из настроек потока (0 = выключено).
        sl_price = 0.0
        tp_price = 0.0
        sl_mult = float(stream.sl_atr or 0.0)
        tp_mult = float(stream.tp_atr or 0.0)
        if (sl_mult > 0 or tp_mult > 0) and atr and atr > 0:
            tick = mt5.symbol_info_tick(symbol)
            entry_price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
            digits = int(getattr(symbol_info, 'digits', 5) or 5)
            if sl_mult > 0:
                sl_price = entry_price - sl_mult * atr if signal == "BUY" else entry_price + sl_mult * atr
                sl_price = round(sl_price, digits)
            if tp_mult > 0:
                tp_price = entry_price + tp_mult * atr if signal == "BUY" else entry_price - tp_mult * atr
                tp_price = round(tp_price, digits)

        comment = f"{stream.id}:{stream.strategy}"
        result = self.trading.orderOpen(
            symbol, order_type, volume, comment,
            sl=sl_price, tp=tp_price, magic=stream.magic,
        )
        if isinstance(result, dict) and result.get("order"):
            return {
                "ticket": result["order"],
                "volume": volume,
                "price": result.get("price"),
            }
        return None

    @staticmethod
    def _reason_to_tag(reason: str) -> str:
        """Нормализует payload.reason → короткий тег для MT5 comment/истории."""
        r = (reason or "").lower()
        if r.startswith("strategy:"):
            return "SIGNAL"
        if r.startswith("rsi"):
            return "RSI"
        if r in ("sl", "stop_loss"):
            return "SL"
        if r in ("tp", "take_profit"):
            return "TP"
        if r.startswith("manual"):
            return "MANUAL"
        return (reason or "MANUAL")[:20]

    async def _handle_close(self, event: Event):
        p = event.payload
        ticket = p.get("ticket")
        symbol = p.get("symbol")
        raw_reason = p.get("reason", "manual")
        tag = self._reason_to_tag(raw_reason)

        await self.emit_status(AgentStatus.RUNNING, f"Закрытие позиции {symbol} ({tag})")
        try:
            ok = await asyncio.get_event_loop().run_in_executor(
                None, self.trading.orderClose, ticket, symbol, tag
            )
            if ok:
                self.metrics["closed_today"] = self.metrics.get("closed_today", 0) + 1
                await self.emit(EventType.ORDER_CLOSED, {
                    "ticket": ticket,
                    "symbol": symbol,
                    "reason": raw_reason,
                    "tag": tag,
                })
        except Exception as e:
            self._logger.error(f"Close order failed {ticket}: {e}")
            await self.emit(EventType.ORDER_ERROR, {"ticket": ticket, "error": str(e)})
