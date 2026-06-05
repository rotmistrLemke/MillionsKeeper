import asyncio

from agents.base_agent import BaseAgent, AgentStatus
from core.event_bus import EventBus
from core.events import EventType, Event


class BacktestAgent(BaseAgent):
    """
    Запускает бэктест по запросу (событие BACKTEST_STARTED).
    Публикует BACKTEST_RESULT с результатами.
    """
    description = "Бэктест стратегии"

    def __init__(self, name: str, bus: EventBus):
        super().__init__(name, bus)
        self._queue: asyncio.Queue = asyncio.Queue()
        self.metrics["runs"] = 0
        bus.subscribe(EventType.BACKTEST_STARTED, self._on_backtest_request)

    async def _on_backtest_request(self, event: Event):
        await self._queue.put(event)

    async def run(self):
        await self.emit_status(AgentStatus.IDLE, "Ожидание запроса")
        event = await self._queue.get()
        p = event.payload
        strategy_name = p.get("strategy", "default")
        symbol = p.get("symbol", "XAUUSDrfd")
        bars = p.get("bars", 2000)
        deposit = p.get("deposit", 0.0)
        spread = p.get("spread", 0)
        # Если не задан явно — берём средний спред по символу из settings,
        # чтобы пользователю не нужно было каждый раз вбивать его в UI.
        if not spread or int(spread) <= 0:
            from settings import Dictionary
            spread = int(Dictionary.symbolDefaultSpread.get(symbol, 0) or 0)
        timeframe = p.get("timeframe", None)
        volume = p.get("volume", 0.0)
        sl_atr = float(p.get("sl_atr", 0.0) or 0.0)
        tp_atr = float(p.get("tp_atr", 0.0) or 0.0)
        breakeven_atr = float(p.get("breakeven_atr", 0.0) or 0.0)
        trail_atr = float(p.get("trail_atr", 0.0) or 0.0)
        date_start = p.get("start")
        date_end = p.get("end")

        detail = f"Бэктест {symbol}"
        if strategy_name != "default":
            detail = f"Бэктест [{strategy_name}] {symbol}"
        if date_start:
            detail += f" с {date_start}"
            if date_end:
                detail += f" по {date_end}"
        else:
            detail += f" {bars} баров"
        await self.emit_status(AgentStatus.RUNNING, detail)
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_backtest, strategy_name, symbol, bars, deposit, spread,
                timeframe, volume, date_start, date_end, sl_atr, tp_atr,
                breakeven_atr, trail_atr,
            )
            self.metrics["runs"] = self.metrics.get("runs", 0) + 1
            await self.emit(EventType.BACKTEST_RESULT, {
                "strategy": strategy_name,
                "symbol": symbol,
                "bars": bars,
                "deposit": deposit,
                "result": result,
            }, correlation_id=event.correlation_id)
            await self.emit_status(AgentStatus.IDLE, f"Готово: {symbol}")
        except Exception as e:
            self._logger.error(f"Backtest failed {symbol}: {e}", exc_info=True)
            await self.emit_status(AgentStatus.ERROR, str(e))
            # Обязательно эмитим RESULT с ошибкой — иначе UI зависает
            # в состоянии «загрузка» до конца сессии.
            await self.emit(EventType.BACKTEST_RESULT, {
                "strategy": strategy_name,
                "symbol": symbol,
                "bars": bars,
                "deposit": deposit,
                "result": {"error": str(e)},
            }, correlation_id=event.correlation_id)

    def _run_backtest(self, strategy_name, symbol, bars, deposit, spread, timeframe,
                      volume=0.0, date_start=None, date_end=None,
                      sl_atr=0.0, tp_atr=0.0,
                      breakeven_atr=0.0, trail_atr=0.0) -> dict:
        from datetime import datetime
        import time as _time
        import MetaTrader5 as mt5
        from backtest import run_backtest, run_strategy_backtest, load_rates

        date_from = datetime.strptime(date_start, '%Y-%m-%d') if date_start else None
        date_to   = datetime.strptime(date_end,   '%Y-%m-%d') if date_end   else None

        tf_map = {
            'M1': mt5.TIMEFRAME_M1,   'M5':  mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15, 'M30': mt5.TIMEFRAME_M30,
            'H1':  mt5.TIMEFRAME_H1,  'H4':  mt5.TIMEFRAME_H4,
            'D1':  mt5.TIMEFRAME_D1,
        }

        # ── Preflight: символ должен быть доступен и выбран в MarketWatch ──
        self._logger.info(f"[bt] preflight {symbol} tf={timeframe}")
        if not mt5.terminal_info():
            return {"error": "MT5 terminal не подключён"}
        info = mt5.symbol_info(symbol)
        if info is None:
            return {"error": f"Символ {symbol} не найден в MT5"}
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                return {"error": f"Не удалось активировать {symbol} в MarketWatch"}

        # ── Pre-load котировок с таймаутом, чтобы зависший mt5.copy_rates_* ──
        # не блокировал executor навсегда. Если данных нет — отдаём явную ошибку.
        tf_default = tf_map.get(timeframe, mt5.TIMEFRAME_H1) if timeframe else None
        if strategy_name != "default":
            from strategies import STRATEGIES
            if strategy_name not in STRATEGIES:
                return {"error": f"Стратегия '{strategy_name}' не найдена"}
            strat = STRATEGIES[strategy_name]()
            tf = tf_map.get(timeframe, tf_map.get(strat.default_timeframe, mt5.TIMEFRAME_H1))
        else:
            tf = tf_default or mt5.TIMEFRAME_H1
            strat = None

        t0 = _time.monotonic()
        self._logger.info(f"[bt] load_rates {symbol} tf={tf} bars={bars} range={date_from}..{date_to}")
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FTimeout
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(load_rates, symbol, tf, bars, date_from, date_to)
            try:
                rates = fut.result(timeout=30.0)
            except FTimeout:
                return {"error": f"Таймаут загрузки котировок {symbol} (mt5.copy_rates_* > 30s)"}
        self._logger.info(
            f"[bt] rates loaded in {_time.monotonic()-t0:.2f}s, "
            f"got {0 if rates is None else len(rates)} bars"
        )
        if rates is None or len(rates) < 100:
            return {"error": f"Недостаточно данных: {0 if rates is None else len(rates)} баров"}

        # ── Запуск самого бэктеста ─────────────────────────────────────────
        t1 = _time.monotonic()
        self._logger.info(f"[bt] running {strategy_name} on {len(rates)} bars")
        if strategy_name == "default":
            result = run_backtest(symbol, tf, bars=bars, spread_points=spread, deposit=deposit,
                                  fixed_volume=volume, date_from=date_from, date_to=date_to)
        else:
            result = run_strategy_backtest(
                strat, symbol, tf, bars=bars, spread_points=spread,
                deposit=deposit, fixed_volume=volume,
                date_from=date_from, date_to=date_to,
                sl_atr_mult=sl_atr, tp_atr_mult=tp_atr,
                breakeven_atr_mult=breakeven_atr,
                trail_atr_mult=trail_atr,
            )
        self._logger.info(f"[bt] done in {_time.monotonic()-t1:.2f}s")

        if result is None:
            return {}
        return {
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "total_pnl_points": result.total_pnl_points,
            "total_pnl_money": result.total_pnl_money,
            "final_balance": result.final_balance,
            "return_pct": result.return_pct,
            "max_drawdown_money": result.max_drawdown_money,
            "max_drawdown_pct": result.max_drawdown_pct,
            "profit_factor": result.profit_factor,
            "avg_win_money": result.avg_win_money,
            "avg_loss_money": result.avg_loss_money,
            "trades": result.trades,
        }
