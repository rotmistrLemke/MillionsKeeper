"""
main.py — Точка входа с мульти-агентной архитектурой + Web Dashboard.

Запуск:
    python main.py

Web Dashboard доступен по адресу: http://localhost:8080

Также поддерживается запуск только торгового бота (без агентов):
    python alligatorBot.py
"""
import asyncio
import logging
import sys
import threading
import uvicorn

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Main")


def _get_active_symbols():
    """Возвращает символы со статусом != 3 (не выключены)."""
    from settings import Dictionary
    return [s for s, v in Dictionary.symbolTradingStatus.items() if v != 3]


async def main():
    import MetaTrader5 as mt5
    from settings import GlobalValues

    # ── Авторизация MT5 ──────────────────────────────────────────
    logger.info("Подключение к MT5...")
    import account as acc_module
    from authenticator import MT5Auth
    auth = MT5Auth(acc_module.Account.account)
    auth.login()

    # ── EventBus ─────────────────────────────────────────────────
    from core.event_bus import bus

    # ── Инициализация торгового модуля ───────────────────────────
    from trading import Trading
    trading = Trading()

    # ── Список активных символов ──────────────────────────────────
    symbols = _get_active_symbols()
    timeframe = GlobalValues.time_frame
    logger.info(f"Активных символов: {len(symbols)}")

    # ── Агенты ───────────────────────────────────────────────────
    from agents.market_data_agent   import MarketDataAgent
    from agents.indicator_agent     import IndicatorAgent
    from agents.signal_agent        import SignalAgent
    from agents.execution_agent     import ExecutionAgent
    from agents.position_monitor_agent import PositionMonitorAgent
    from agents.history_agent       import HistoryAgent
    from agents.backtest_agent      import BacktestAgent
    from agents.account_agent       import AccountAgent

    agents = [
        MarketDataAgent("MarketData",  bus, symbols, timeframe, poll_interval=10.0),
        IndicatorAgent("Indicator",    bus, timeframe),
        SignalAgent("Signal",          bus),
        ExecutionAgent("Execution",    bus, trading),
        PositionMonitorAgent("PosMon", bus, trading, poll_interval=5.0),
        HistoryAgent("History",        bus, poll_interval=300.0),
        BacktestAgent("Backtest",      bus),
        AccountAgent("Account",        bus, poll_interval=30.0),
    ]

    # ── Web Dashboard ─────────────────────────────────────────────
    from web.app import app as web_app

    config = uvicorn.Config(
        web_app,
        host="0.0.0.0",
        port=8080,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    # ── Запускаем всё вместе ──────────────────────────────────────
    logger.info("Запуск агентов и Web Dashboard на http://localhost:8080")
    await asyncio.gather(
        bus.run(),
        *[agent.start() for agent in agents],
        server.serve(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")
