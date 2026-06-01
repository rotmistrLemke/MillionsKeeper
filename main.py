"""
main.py — Точка входа TradingHouse: мульти-агентная архитектура + Web Dashboard.

Запуск:
    python main.py

Конфигурация через env-переменные:
    HOST              — bind address (default 127.0.0.1; для production ставим
                         localhost и публикуем через reverse-proxy)
    PORT              — порт uvicorn (default 8080)
    ADMIN_PASSWORD    — пароль первого admin при первом старте; если не задан,
                         сгенерируется случайный и попадёт в лог один раз
    JWT_SECRET        — секрет подписи токенов (если не задан, читается/создаётся
                         в .jwt_secret)
    TRUSTED_HOSTS     — comma-separated список Host-заголовков, которые сервер
                         принимает (default: localhost,127.0.0.1)
    CORS_ORIGINS      — comma-separated список origin-ов для CORS (default: пусто)
"""
import asyncio
import logging
import os
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


async def main():
    import MetaTrader5 as mt5

    # ── Авторизация MT5 ──────────────────────────────────────────
    # ВАЖНО: имя локальной переменной — `mt5_auth`, а не `auth`. Иначе её
    # затрёт `import auth` ниже, MT5Auth-объект уйдёт в GC, его __del__
    # вызовет mt5.shutdown() и порвёт IPC. Все агенты получат
    # «-10004 No IPC connection».
    logger.info("Подключение к MT5...")
    import account as acc_module
    from authenticator import MT5Auth
    mt5_auth = MT5Auth(acc_module.Account.account)
    mt5_auth.login()

    # ── EventBus ─────────────────────────────────────────────────
    from core.event_bus import bus

    # ── Инициализация торгового модуля ───────────────────────────
    from trading import Trading
    trading = Trading()

    # ── Авторизация: загрузка пользователей ──────────────────────
    import auth
    auth.load()

    # ── Торговые потоки (мульти-поточная торговля) ───────────────
    import streams
    streams.load()

    logger.info(f"Потоков: {len(streams.registry.all())}")

    # ── Агенты ───────────────────────────────────────────────────
    from agents.market_data_agent   import MarketDataAgent
    from agents.indicator_agent     import IndicatorAgent
    from agents.signal_agent        import SignalAgent
    from agents.execution_agent     import ExecutionAgent
    from agents.position_monitor_agent import PositionMonitorAgent
    from agents.history_agent       import HistoryAgent
    from agents.backtest_agent      import BacktestAgent
    from agents.account_agent       import AccountAgent
    from agents.anomaly_scanner_agent import AnomalyScannerAgent
    from anomaly.store import AnomalyStore
    from anomaly.detector import DetectorConfig
    from anomaly.config import AnomalySettings

    anomaly_store = AnomalyStore(AnomalySettings.DB_PATH)
    anomaly_store.init_schema()
    anomaly_agent = AnomalyScannerAgent(
        "AnomalyScanner", bus, anomaly_store,
        DetectorConfig(
            ema_period=AnomalySettings.EMA_PERIOD,
            atr_period=AnomalySettings.ATR_PERIOD,
            atr_mult=AnomalySettings.ATR_MULT,
            stoch_fastk=AnomalySettings.STOCH_FASTK,
            stoch_slowk=AnomalySettings.STOCH_SLOWK,
            stoch_slowd=AnomalySettings.STOCH_SLOWD,
            stoch_ob=AnomalySettings.STOCH_OB,
            stoch_os=AnomalySettings.STOCH_OS,
        ),
        scan_interval_sec=AnomalySettings.SCAN_INTERVAL_SEC,
        miss_tolerance=AnomalySettings.MISS_TOLERANCE,
        timeframe=AnomalySettings.TIMEFRAME,
        bars_to_fetch=AnomalySettings.BARS_TO_FETCH,
        db_path=AnomalySettings.DB_PATH,
    )

    agents = [
        MarketDataAgent("MarketData",  bus, poll_interval=10.0),
        IndicatorAgent("Indicator",    bus),
        SignalAgent("Signal",          bus),
        ExecutionAgent("Execution",    bus, trading),
        PositionMonitorAgent("PosMon", bus, trading, poll_interval=5.0),
        HistoryAgent("History",        bus, poll_interval=300.0),
        BacktestAgent("Backtest",      bus),
        AccountAgent("Account",        bus, poll_interval=30.0),
        anomaly_agent,
    ]

    # ── Web Dashboard ─────────────────────────────────────────────
    from web.app import app as web_app
    from web.routes_anomalies import deps as anomaly_deps
    anomaly_deps.store = anomaly_store
    anomaly_deps.agent = anomaly_agent

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    config = uvicorn.Config(
        web_app,
        host=host,
        port=port,
        log_level="info",
        loop="asyncio",
        access_log=True,  # временно включено для отладки /api/anomalies/*
    )
    server = uvicorn.Server(config)

    # ── Запускаем всё вместе ──────────────────────────────────────
    logger.info(f"Запуск агентов и Web Dashboard на http://{host}:{port}")
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
