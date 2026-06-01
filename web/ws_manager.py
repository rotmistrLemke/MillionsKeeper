import asyncio
import json
import logging
from datetime import datetime
from typing import Set

from fastapi import WebSocket
from core.events import Event, EventType
import auth

logger = logging.getLogger("WSManager")


def _sanitize_for_json(obj):
    """Рекурсивно заменяет float('inf')/-inf/nan на None — стандартный JSON
    их не поддерживает, а JSON.parse в браузере падает."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


class WebSocketManager:
    """
    Управляет WebSocket-соединениями.
    Ретранслирует события с шины EventBus всем авторизованным клиентам.
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        # Авторизованные сокеты — только им уходят события и снапшот.
        self._auth_by_ws: dict[WebSocket, auth.UserRecord] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WS client connected. Total: {len(self._connections)}")
        # Снапшот НЕ отправляем до авторизации — клиент шлёт {cmd:'auth',token}
        # первым сообщением, после чего мы вызываем authenticate().

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        self._auth_by_ws.pop(ws, None)
        logger.info(f"WS client disconnected. Total: {len(self._connections)}")

    async def authenticate(self, ws: WebSocket, token: str) -> bool:
        user = auth.user_from_token(token or "")
        if user is None:
            await self.send_to(ws, "auth_error", {"error": "Недействительный токен"})
            return False
        self._auth_by_ws[ws] = user
        await self.send_to(ws, "auth_ok", {"user": user.to_public()})
        await self._send_snapshot(ws)
        return True

    def user_of(self, ws: WebSocket):
        return self._auth_by_ws.get(ws)

    def is_authenticated(self, ws: WebSocket) -> bool:
        return ws in self._auth_by_ws

    async def broadcast(self, msg_type: str, data: dict):
        if not self._auth_by_ws:
            return
        try:
            # allow_nan=False: Infinity/NaN ломают JSON.parse в браузере, и
            # onmessage молча падает (фрейм виден в Network, но UI «висит»).
            msg = json.dumps({
                "msg_type": msg_type,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }, default=str, allow_nan=False)
        except ValueError as e:
            logger.warning(f"broadcast({msg_type}): неJSON-совместимое значение, sanitize: {e}")
            msg = json.dumps({
                "msg_type": msg_type,
                "timestamp": datetime.now().isoformat(),
                "data": _sanitize_for_json(data),
            }, default=str, allow_nan=False)
        dead = set()
        for ws in list(self._auth_by_ws.keys()):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._auth_by_ws.pop(ws, None)
            self._connections.discard(ws)

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

        # Немедленно отдаём кэш истории (если уже был сделан первый опрос MT5),
        # чтобы UI не ждал следующего 5-минутного тика HistoryAgent.
        try:
            from agents.history_agent import get_latest_snapshot
            snap = get_latest_snapshot()
            if snap:
                await self.send_to(ws, "event_stream", {
                    "type": "history.snapshot",
                    "source": "HistoryAgent",
                    "payload": snap,
                })
        except Exception as e:
            logger.warning(f"history snapshot send failed: {e}")

    @property
    def connection_count(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()


async def event_to_ws_bridge(event: Event):
    """Подписчик EventBus — ретранслирует все события в WebSocket."""
    await ws_manager.broadcast("event_stream", event.to_dict())
