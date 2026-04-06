import asyncio
import json
import logging
from datetime import datetime
from typing import Set

from fastapi import WebSocket
from core.events import Event, EventType

logger = logging.getLogger("WSManager")


class WebSocketManager:
    """
    Управляет WebSocket-соединениями.
    Ретранслирует события с шины EventBus всем подключённым клиентам.
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WS client connected. Total: {len(self._connections)}")
        # Отправляем начальный снепшот состояния
        await self._send_snapshot(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info(f"WS client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, msg_type: str, data: dict):
        if not self._connections:
            return
        msg = json.dumps({
            "msg_type": msg_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }, default=str)
        dead = set()
        for ws in list(self._connections):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self._connections -= dead

    async def send_to(self, ws: WebSocket, msg_type: str, data: dict):
        try:
            await ws.send_text(json.dumps({
                "msg_type": msg_type,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }, default=str))
        except Exception as e:
            logger.warning(f"Failed to send to ws: {e}")

    async def _send_snapshot(self, ws: WebSocket):
        from core.agent_registry import registry
        from core.event_bus import bus

        recent = [e.to_dict() for e in bus.get_recent_events(limit=50)]
        await self.send_to(ws, "agents_snapshot", {
            "agents": registry.get_all_statuses(),
            "recent_events": recent,
        })

    @property
    def connection_count(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()


async def event_to_ws_bridge(event: Event):
    """Подписчик EventBus — ретранслирует все события в WebSocket."""
    await ws_manager.broadcast("event_stream", event.to_dict())
