import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType

# Кэш последнего снапшота для мгновенной отдачи новому WS-клиенту.
_latest_snapshot: dict | None = None


def get_latest_snapshot() -> dict | None:
    return _latest_snapshot


class HistoryAgent(BaseAgent):
    """
    Периодически читает историю сделок из MT5.
    Публикует HISTORY_SNAPSHOT с агрегированной статистикой.
    """
    description = "История сделок: день/неделя/месяц"

    def __init__(self, name: str, bus: EventBus, poll_interval: float = 300.0):
        super().__init__(name, bus)
        self.poll_interval = poll_interval
        self.metrics["today_pnl"] = 0.0

    async def run(self):
        global _latest_snapshot
        await self.emit_status(AgentStatus.RUNNING, "Загрузка истории")
        try:
            snapshot = await asyncio.get_event_loop().run_in_executor(
                None, self._load_history
            )
            _latest_snapshot = snapshot
            self.metrics["today_pnl"] = snapshot.get("today", {}).get("profit", 0.0)
            await self.emit(EventType.HISTORY_SNAPSHOT, snapshot)
            await asyncio.get_event_loop().run_in_executor(None, self._persist_track)
            await self.emit_status(AgentStatus.IDLE, f"Сегодня: {self.metrics['today_pnl']:+.2f}$")
        except Exception as e:
            self._logger.error(f"History load error: {e}")
            await self.emit_status(AgentStatus.ERROR, str(e))

        await asyncio.sleep(self.poll_interval)

    # MT5 deal.reason → человекочитаемая причина закрытия (когда нет нашего тега).
    _REASON_LABELS = {
        0: "MANUAL",     # закрыто вручную в терминале
        1: "MANUAL",     # mobile — для нас тоже ручное
        2: "MANUAL",     # web terminal
        3: "SIGNAL",     # Expert без нашего комментария — наверняка стратегический выход
        4: "SL",
        5: "TP",
        6: "Stop Out",
        7: "Rollover",
        8: "VMargin",
        9: "Split",
    }

    # Теги, которые бот пишет в deal.comment при закрытии через order_send.
    _BOT_TAGS = {"SL", "TP", "SIGNAL", "RSI", "MANUAL"}

    @staticmethod
    def _strategy_from_comment(comment: str) -> str | None:
        """Разбирает comment входного ордера «s6:default» / «s6:default:H»
        → ключ стратегии («default»). None, если формат не распознан."""
        parts = (comment or "").strip().split(":")
        if len(parts) >= 2 and parts[0].startswith("s") and parts[1]:
            return parts[1]
        return None

    @classmethod
    def _deal_strategy(cls, in_d, out_d) -> tuple[str | None, str | None]:
        """Стратегия/поток закрытой сделки. Приоритет: magic → поток из реестра;
        фолбэк — разбор comment входного ордера. Возвращает (strategy_key, stream_name)."""
        magic = 0
        for d in (in_d, out_d):
            if d is not None:
                magic = int(getattr(d, "magic", 0) or 0)
                if magic:
                    break
        if magic:
            try:
                import streams as streams_mod
                stream = streams_mod.registry.by_magic(magic)
                if stream is not None:
                    return stream.strategy, stream.name
            except Exception:
                pass
        # Фолбэк: comment входного ордера (поток мог быть удалён из реестра).
        if in_d is not None:
            key = cls._strategy_from_comment(getattr(in_d, "comment", "") or "")
            if key:
                return key, None
        return None, None

    @classmethod
    def _deal_reason(cls, d) -> str:
        """Причина закрытия: приоритет у тега бота в comment → MT5 reason-код."""
        comment = (getattr(d, "comment", "") or "").strip()
        # Бот пишет короткие теги (SL/TP/SIGNAL/RSI/MANUAL) при закрытии через order_send.
        upper = comment.upper()
        if upper in cls._BOT_TAGS:
            return upper
        # MT5-код — если наш тег не записан (например, закрытие по SL/TP через
        # встроенные стопы MT5 или ручное из терминала).
        try:
            code = int(getattr(d, "reason", -1))
        except (TypeError, ValueError):
            code = -1
        if code in cls._REASON_LABELS:
            return cls._REASON_LABELS[code]
        return comment or "—"

    def _load_history(self) -> dict:
        """
        Один запрос к MT5 за 3 месяца → локальная нарезка на today/week/month.
        Возвращает также raw unix-таймстемпы (`*_ts`) — фронт использует их
        напрямую, чтобы не страдать от часовых поясов.
        """
        from datetime import datetime, timedelta
        import MetaTrader5 as mt5

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start  = (today_start - timedelta(days=now.weekday()))
        # Окно выборки расширено до ~90 дней, чтобы видеть «хвосты» старых
        # трейдов (linked open→close) для позиций, открытых давно и закрытых
        # недавно. Бакет `month` теперь = последние 90 дней (rolling).
        month_start = today_start - timedelta(days=90)
        date_to     = now + timedelta(hours=3)  # запас под MT5 server time

        deals = mt5.history_deals_get(month_start, date_to)

        today = {"profit": 0.0, "deals": []}
        week  = {"profit": 0.0, "deals": []}
        month = {"profit": 0.0, "deals": []}

        def _fmt(dt: datetime) -> str:
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        if deals:
            # Сначала собираем IN-сделки (entry=0) по position_id, чтобы найти
            # точку входа для каждой закрытой сделки.
            in_map = {}
            for d in deals:
                if getattr(d, "entry", None) == 0 and d.type in (0, 1):
                    in_map[d.position_id] = d

            for d in deals:
                if d.entry != 1 or d.type not in (0, 1):
                    continue
                t_dt = datetime.fromtimestamp(d.time)

                in_d = in_map.get(d.position_id)
                open_time = open_price = position_type = None
                open_time_ts = None
                if in_d is not None:
                    open_time = _fmt(datetime.fromtimestamp(in_d.time))
                    open_time_ts = int(in_d.time)
                    open_price = float(in_d.price)
                    # Реальное направление позиции — из IN-сделки.
                    position_type = "BUY" if in_d.type == 0 else "SELL"

                strategy, stream_name = self._deal_strategy(in_d, d)

                item = {
                    "ticket":        d.ticket,
                    "symbol":        d.symbol,
                    "type":          "BUY" if d.type == 0 else "SELL",
                    "profit":        d.profit,
                    "volume":        d.volume,
                    "time":          _fmt(t_dt),
                    "time_ts":       int(d.time),  # raw unix — для совпадения со шкалой свечей
                    "reason":        self._deal_reason(d),
                    # Поля для отрисовки линии трейда на графике
                    "open_time":     open_time,
                    "open_time_ts":  open_time_ts,
                    "open_price":    open_price,
                    "close_price":   float(d.price) if getattr(d, "price", None) is not None else None,
                    "position_type": position_type,
                    # Пометка потока/стратегии, по которой был выставлен ордер.
                    "strategy":      strategy,
                    "stream_name":   stream_name,
                    "magic":         int(getattr(d, "magic", 0) or 0),
                }
                month["profit"] += d.profit
                month["deals"].append(item)
                if t_dt >= week_start:
                    week["profit"] += d.profit
                    week["deals"].append(item)
                if t_dt >= today_start:
                    today["profit"] += d.profit
                    today["deals"].append(item)

        return {"today": today, "week": week, "month": month}

    def _persist_track(self) -> None:
        """Аддитивная запись closed-сделок + equity в performance-store.
        Изолировано от _load_history; никогда не роняет агент (всё в try)."""
        try:
            from datetime import datetime, timedelta
            import MetaTrader5 as mt5
            from performance.store import record_poll

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
