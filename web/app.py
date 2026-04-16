import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from web.ws_manager import ws_manager, event_to_ws_bridge
from web.api_routes import router as api_router
from web.chart_streamer import chart_streamer
from core.event_bus import bus

logger = logging.getLogger("WebApp")

app = FastAPI(title="MillionsKeeper Dashboard", version="1.0.0")

# REST API
app.include_router(api_router)

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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
    return FileResponse(str(static_dir / "index.html"))


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
        await bus.publish(Event(
            type=EventType.TRADING_STATUS_CHANGED,
            source="ws_client",
            payload={"action": "set_active_strategy", "strategy": cmd.get("strategy", "default")}
        ))

    elif action == "chart_subscribe":
        symbol = cmd.get("symbol")
        timeframe = cmd.get("timeframe", "H1")
        if symbol:
            chart_streamer.subscribe(ws, symbol, timeframe)

    elif action == "chart_unsubscribe":
        chart_streamer.unsubscribe(ws)

    elif action == "set_trading_status":
        from settings import Dictionary
        from core.events import Event, EventType
        symbol = cmd.get("symbol")
        status = cmd.get("status", 3)
        if symbol in Dictionary.symbolTradingStatus:
            Dictionary.symbolTradingStatus[symbol] = status
            await bus.publish(Event(
                type=EventType.TRADING_STATUS_CHANGED,
                source="ws_client",
                payload={"symbol": symbol, "status": status, "reason": "ws_command"}
            ))
