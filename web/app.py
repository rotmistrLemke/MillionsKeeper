import asyncio
import json
import logging
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from web.ws_manager import ws_manager, event_to_ws_bridge
from web.api_routes import router as api_router
from web.routes_anomalies import router as anomalies_router
from web.chart_streamer import chart_streamer
from core.event_bus import bus

logger = logging.getLogger("WebApp")

app = FastAPI(title="TradingHouse Dashboard", version="1.0.0")


def _csv_env(key: str, default: str = "") -> list[str]:
    raw = os.environ.get(key, default).strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []


# TrustedHost — защита от Host-header injection. По умолчанию принимаем только
# localhost. Для production добавить домен через TRUSTED_HOSTS=mydomain.com,...
_trusted_hosts = _csv_env("TRUSTED_HOSTS", "localhost,127.0.0.1")
if _trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts)

# CORS — по умолчанию пусто (запросы идут с того же домена). Если фронт хостится
# отдельно — указать через CORS_ORIGINS=https://app.example.com,...
_cors_origins = _csv_env("CORS_ORIGINS")
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# REST API
app.include_router(api_router)
app.include_router(anomalies_router)

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health():
    """Health check для reverse-proxy / мониторинга."""
    return {
        "status": "ok",
        "ws_clients": ws_manager.connection_count,
    }


@app.on_event("startup")
async def startup():
    # Подписываем WS-мост на все события шины
    bus.subscribe("*", event_to_ws_bridge)
    await chart_streamer.start()
    logger.info("Web dashboard started")


@app.on_event("shutdown")
async def shutdown():
    await chart_streamer.stop()


@app.get("/")
async def index():
    # Проверку токена делает клиент: если в localStorage нет валидного th_token,
    # app.js сразу редиректит на /login.
    return FileResponse(str(static_dir / "index.html"))


@app.get("/login")
async def login_page():
    return FileResponse(str(static_dir / "login.html"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            # Принимаем команды от клиента
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                await _handle_ws_command(ws, raw)
            except asyncio.TimeoutError:
                # Пинг для поддержания соединения
                await ws.send_text(json.dumps({"msg_type": "ping"}))
    except WebSocketDisconnect:
        chart_streamer.unsubscribe(ws)
        ws_manager.disconnect(ws)
    except Exception as e:
        logger.error(f"WS error: {e}")
        chart_streamer.unsubscribe(ws)
        ws_manager.disconnect(ws)


async def _handle_ws_command(ws: WebSocket, raw: str):
    try:
        cmd = json.loads(raw)
    except json.JSONDecodeError:
        return

    action = cmd.get("cmd")

    # Единственная команда, доступная без авторизации — сама аутентификация.
    if action == "auth":
        await ws_manager.authenticate(ws, cmd.get("token") or "")
        return

    if not ws_manager.is_authenticated(ws):
        await ws_manager.send_to(ws, "auth_required", {
            "error": "Требуется авторизация перед любыми командами"
        })
        return

    # Команды, которые может выполнять только admin.
    ADMIN_ONLY = {"close_position", "set_active_strategy", "set_trading_status"}
    if action in ADMIN_ONLY:
        import auth as auth_mod
        user = ws_manager.user_of(ws)
        if user is None or user.role != auth_mod.ROLE_ADMIN:
            await ws_manager.send_to(ws, "forbidden", {
                "cmd": action,
                "error": "Требуются права администратора"
            })
            return

    if action == "get_agents":
        from core.agent_registry import registry
        await ws_manager.send_to(ws, "agents_snapshot", {
            "agents": registry.get_all_statuses()
        })

    elif action == "get_events":
        events = bus.get_recent_events(
            event_type=cmd.get("event_type"),
            limit=cmd.get("limit", 50)
        )
        await ws_manager.send_to(ws, "events_list", {
            "events": [e.to_dict() for e in events]
        })

    elif action == "run_backtest":
        from core.events import Event, EventType
        await bus.publish(Event(
            type=EventType.BACKTEST_STARTED,
            source="ws_client",
            payload={
                "strategy": cmd.get("strategy", "default"),
                "symbol": cmd.get("symbol", "XAUUSDrfd"),
                "bars": cmd.get("bars", 2000),
                "deposit": cmd.get("deposit", 0.0),
                "spread": cmd.get("spread", 0),
                "volume": cmd.get("volume", 0.0),
                "sl_atr": cmd.get("sl_atr", 0.0),
                "tp_atr": cmd.get("tp_atr", 0.0),
                "breakeven_atr": cmd.get("breakeven_atr", 0.0),
                "trail_atr": cmd.get("trail_atr", 0.0),
                "timeframe": cmd.get("timeframe"),
                "start": cmd.get("start"),
                "end": cmd.get("end"),
            }
        ))

    elif action == "close_position":
        from core.events import Event, EventType
        await bus.publish(Event(
            type=EventType.ORDER_CLOSE_REQUEST,
            source="ws_client",
            payload={
                "ticket": cmd.get("ticket"),
                "symbol": cmd.get("symbol", ""),
                "reason": "manual_ws",
            }
        ))

    elif action == "set_active_strategy":
        from core.events import Event, EventType
        from settings import GlobalValues, TF_MAP
        from trading_status import status
        from strategies.runtime import reset_all as reset_strategy_cache
        strategy = cmd.get("strategy", "default")
        tf_str   = cmd.get("timeframe", "H1")
        tf_enum  = TF_MAP.get(tf_str, GlobalValues.time_frame)
        symbol   = cmd.get("symbol") or GlobalValues.active_symbol
        try:
            volume = float(cmd.get("volume", 0) or 0)
        except (TypeError, ValueError):
            volume = 0.0
        if volume < 0:
            volume = 0.0

        def _parse_mult(key):
            try:
                v = float(cmd.get(key, 0) or 0)
            except (TypeError, ValueError):
                v = 0.0
            return max(0.0, v)

        sl_atr = _parse_mult("sl_atr")
        tp_atr = _parse_mult("tp_atr")

        if not status.has(symbol):
            await ws_manager.send_to(ws, "active_strategy_changed", {
                "error": f"Unknown symbol: {symbol}",
            })
            return

        # Сброс кэша экземпляров — чтобы внутреннее состояние (напр. _blocked_side)
        # не переносилось между применениями стратегии.
        reset_strategy_cache()

        GlobalValues.active_strategy = strategy
        GlobalValues.time_frame      = tf_enum
        GlobalValues.active_symbol   = symbol
        GlobalValues.active_volume   = volume
        GlobalValues.active_sl_atr   = sl_atr
        GlobalValues.active_tp_atr   = tp_atr

        # Активируем только выбранный символ (0 = разрешено, 3 = выключено).
        # Позиции с активным ордером (статус 1) не трогаем — PositionMonitor
        # сбросит их в 0 при закрытии.
        status.activate_only(symbol)

        # Персистим выбор — чтобы сохранялся между перезапусками.
        import active_state
        active_state.save()

        await bus.publish(Event(
            type=EventType.TRADING_STATUS_CHANGED,
            source="ws_client",
            payload={
                "action":    "set_active_strategy",
                "strategy":  strategy,
                "timeframe": tf_str,
                "symbol":    symbol,
                "volume":    volume,
                "sl_atr":    sl_atr,
                "tp_atr":    tp_atr,
            }
        ))
        await ws_manager.broadcast("active_strategy_changed", {
            "strategy":  strategy,
            "timeframe": tf_str,
            "symbol":    symbol,
            "volume":    volume,
            "sl_atr":    sl_atr,
            "tp_atr":    tp_atr,
        })

    elif action == "chart_subscribe":
        symbol = cmd.get("symbol")
        timeframe = cmd.get("timeframe", "H1")
        if symbol:
            chart_streamer.subscribe(ws, symbol, timeframe)

    elif action == "chart_unsubscribe":
        chart_streamer.unsubscribe(ws)

    elif action == "set_trading_status":
        from trading_status import status
        from core.events import Event, EventType
        symbol = cmd.get("symbol")
        status_value = cmd.get("status", 3)
        if status.has(symbol):
            status.set_status(symbol, status_value)
            await bus.publish(Event(
                type=EventType.TRADING_STATUS_CHANGED,
                source="ws_client",
                payload={"symbol": symbol, "status": status_value, "reason": "ws_command"}
            ))
