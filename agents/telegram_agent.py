"""TelegramAgent — алерты о здоровье (MT5 up/down, ошибки агентов, старт).
Дедуп по переходам состояния; graceful no-op без token/chat_id; sender инъектируем."""
import asyncio
import os
import socket

from agents.base_agent import BaseAgent
from core.event_bus import EventBus
from core.events import EventType


def _default_ptb_sender(token: str, chat_id: str):
    async def _send(text: str):
        from telegram import Bot
        await Bot(token).send_message(chat_id=chat_id, text=text)
    return _send


class TelegramAgent(BaseAgent):
    """Подписан на MT5_*/AGENT_STATUS; шлёт Telegram только на смену состояния."""
    description = "Telegram-алерты о здоровье бота"

    def __init__(self, name: str, bus: EventBus, *, sender=None,
                 token: str = None, chat_id: str = None):
        super().__init__(name, bus)
        self._token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        self._sender = sender  # async (text)->None; None → дефолтный ptb
        self._last_state: dict[str, str] = {}
        self._started = False
        self._subscribed = False

    def _enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    async def _send(self, text: str) -> None:
        if not self._enabled():
            return
        sender = self._sender or _default_ptb_sender(self._token, self._chat_id)
        try:
            await sender(text)
        except Exception as e:
            self._logger.warning(f"Telegram send failed: {e}")
            return
        await self.emit(EventType.TELEGRAM_SENT, {"text": text})

    async def _on_mt5_disconnected(self, ev) -> None:
        if self._last_state.get("mt5") != "down":
            self._last_state["mt5"] = "down"
            await self._send("⚠️ MT5 disconnected — пытаюсь реконнект")

    async def _on_mt5_connected(self, ev) -> None:
        if self._last_state.get("mt5") == "down":
            self._last_state["mt5"] = "up"
            await self._send("✅ MT5 reconnected — соединение восстановлено")
        else:
            self._last_state.setdefault("mt5", "up")

    async def _on_agent_status(self, ev) -> None:
        agent = ev.payload.get("agent")
        if agent == self.name:
            return  # guard: не алертим на собственный статус (петля)
        st = ev.payload.get("status")
        if st == "error" and self._last_state.get(agent) != "error":
            self._last_state[agent] = "error"
            await self._send(f"⚠️ Agent {agent} error: {ev.payload.get('detail', '')}")
        elif st in ("idle", "running") and self._last_state.get(agent) == "error":
            self._last_state[agent] = "ok"
            await self._send(f"✅ Agent {agent} recovered")

    def _subscribe(self) -> None:
        if self._subscribed:
            return
        self.bus.subscribe(EventType.MT5_DISCONNECTED, self._on_mt5_disconnected)
        self.bus.subscribe(EventType.MT5_CONNECTED, self._on_mt5_connected)
        self.bus.subscribe(EventType.AGENT_STATUS, self._on_agent_status)
        self._subscribed = True

    async def run(self):
        self._subscribe()
        if not self._started:
            self._started = True
            host = os.environ.get("HOST") or socket.gethostname()
            await self._send(f"🟢 Bot started on {host}")
        await asyncio.sleep(3600)
