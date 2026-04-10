"""
app/main.py — Точка входа MillionsKeeper v2.

Запуск:
    cd backend
    python -m app.main

Web Dashboard: http://localhost:8080
"""
from __future__ import annotations

import asyncio
import logging
import sys

import uvicorn

from app.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Main")


def _build_agents(bus, trading_service, broker):
    """Создаёт и возвращает список всех агентов."""
    from app.agents.market_data_agent    import MarketDataAgent
    from app.agents.indicator_agent      import IndicatorAgent
    from app.agents.signal_agent         import SignalAgent
    from app.agents.execution_agent      import ExecutionAgent
    from app.agents.position_monitor_agent import PositionMonitorAgent
    from app.agents.history_agent        import HistoryAgent
    from app.agents.backtest_agent       import BacktestAgent
    from app.agents.account_agent        import AccountAgent

    active_symbols = [s for s, v in trading_service.get_all_statuses().items() if v != 3]
    logger.info(f"Активных символов: {len(active_symbols)}")

    return [
        MarketDataAgent("MarketData", bus, active_symbols),
        IndicatorAgent("Indicator",   bus),
        SignalAgent("Signal",         bus, trading_service),
        ExecutionAgent("Execution",   bus, trading_service),
        PositionMonitorAgent("PosMon", bus, trading_service),
        HistoryAgent("History",       bus),
        BacktestAgent("Backtest",     bus),
        AccountAgent("Account",       bus, broker),
    ]


async def main():
    import MetaTrader5 as mt5

    # ── MT5 авторизация ───────────────────────────────────────────
    logger.info("Подключение к MT5...")
    if not mt5.initialize():
        logger.error("mt5.initialize() failed")
        sys.exit(1)

    ok = mt5.login(
        login=settings.mt5_login,
        password=settings.mt5_password,
        server=settings.mt5_server,
    )
    if not ok:
        logger.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    logger.info(f"MT5 авторизован: {settings.mt5_server}")

    # ── Зависимости ───────────────────────────────────────────────
    from core.event_bus import bus
    from app.trading.broker import MT5Broker
    from app.trading.risk import RiskCalculator
    from app.trading.service import TradingService

    broker  = MT5Broker()
    risk    = RiskCalculator(broker)
    trading = TradingService(broker, risk)

    # ── Агенты ────────────────────────────────────────────────────
    agents = _build_agents(bus, trading, broker)

    # ── Web Dashboard ─────────────────────────────────────────────
    from web.app import app as web_app  # v2: CORS + Redis + WS bridge + SPA
    config = uvicorn.Config(
        web_app,
        host=settings.web_host,
        port=settings.web_port,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    logger.info(f"Запуск на http://{settings.web_host}:{settings.web_port}")

    try:
        await asyncio.gather(
            bus.run(),
            *[agent.start() for agent in agents],
            server.serve(),
        )
    finally:
        mt5.shutdown()
        logger.info("MT5 отключён")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")
