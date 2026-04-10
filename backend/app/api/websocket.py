"""
api/websocket.py — WebSocket менеджер для realtime событий.

Все события EventBus транслируются подключённым клиентам через _ws_bridge.
Клиент может отправлять команды (get_agents, run_backtest, close_position, ...).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("WSManager")


class WSManager:
    """Хранит активные соединения и рассылает сообщения."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.debug(f"WS connected, total={len(self._connections)}")

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.debug(f"WS disconnected, total={len(self._connections)}")

    async def broadcast(self, msg_type: str, data: Any) -> None:
        if not self._connections:
            return
        payload = json.dumps({"type": msg_type, "payload": data}, default=str)
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)

    async def send_to(self, ws: WebSocket, msg_type: str, data: Any) -> None:
        payload = json.dumps({"type": msg_type, "payload": data}, default=str)
        try:
            await ws.send_text(payload)
        except Exception:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Синглтон
ws_manager = WSManager()


async def ws_event_bridge(event) -> None:
    """
    Подписывается на EventBus («*»).
    Маппинг EventType → WS msg_type для клиента.
    """
    from core.events import EventType

    type_map = {
        EventType.ACCOUNT_UPDATE:   "account_update",
        EventType.POSITION_UPDATE:  "position_update",
        EventType.AGENT_STATUS:     "agent_status",
        EventType.BACKTEST_RESULT:  "backtest_result",
        EventType.ORDER_OPENED:     "agent_event",
        EventType.ORDER_CLOSED:     "agent_event",
        EventType.ORDER_ERROR:      "agent_event",
        EventType.SIGNAL_GENERATED: "agent_event",
    }

    msg_type = type_map.get(event.type)
    if msg_type and ws_manager.connection_count > 0:
        await ws_manager.broadcast(msg_type, event.payload)


async def handle_ws_session(ws: WebSocket) -> None:
    """Полная жизнь одного WS соединения."""
    await ws_manager.connect(ws)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=25.0)
                await _handle_command(ws, raw)
            except asyncio.TimeoutError:
                await ws_manager.send_to(ws, "ping", {})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS session error: {e}")
    finally:
        ws_manager.disconnect(ws)


async def _handle_command(ws: WebSocket, raw: str) -> None:
    try:
        cmd = json.loads(raw)
    except json.JSONDecodeError:
        return

    action = cmd.get("cmd")

    if action == "get_agents":
        try:
            from core.agent_registry import registry
            await ws_manager.send_to(ws, "agents_snapshot", registry.get_all_statuses())
        except Exception:
            pass

    elif action == "run_backtest":
        from core.event_bus import bus
        from core.events import Event, EventType
        await bus.publish(Event(
            type=EventType.BACKTEST_STARTED,
            source="ws_client",
            payload={k: cmd.get(k) for k in ("strategy", "symbol", "bars", "deposit", "spread", "risk", "timeframe")},
        ))

    elif action == "close_position":
        from core.event_bus import bus
        from core.events import Event, EventType
        await bus.publish(Event(
            type=EventType.ORDER_CLOSE_REQUEST,
            source="ws_client",
            payload={"ticket": cmd.get("ticket"), "symbol": cmd.get("symbol", ""), "reason": "manual_ws"},
        ))

    elif action == "ping":
        await ws_manager.send_to(ws, "pong", {})
