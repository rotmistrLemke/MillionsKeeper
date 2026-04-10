"""
core/event_bus.py — Асинхронная шина событий (publish/subscribe).

Поддерживает:
  - Подписку на конкретный EventType или "*" (все события)
  - Асинхронные обработчики (coroutine functions)
  - Отключение через bus.stop()
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Coroutine, Union

from core.events import Event, EventType

logger = logging.getLogger("EventBus")

Handler = Callable[[Event], Coroutine]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: Union[EventType, str], handler: Handler) -> None:
        key = event_type if isinstance(event_type, str) else event_type.value
        self._subscribers[key].append(handler)

    def unsubscribe(self, event_type: Union[EventType, str], handler: Handler) -> None:
        key = event_type if isinstance(event_type, str) else event_type.value
        try:
            self._subscribers[key].remove(handler)
        except ValueError:
            pass

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    async def run(self) -> None:
        self._running = True
        logger.info("EventBus started")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            handlers = (
                self._subscribers.get(event.type.value, [])
                + self._subscribers.get("*", [])
            )
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler {handler} error for {event.type}: {e}", exc_info=True)

    def stop(self) -> None:
        self._running = False


# Глобальный синглтон — импортируется как `from core.event_bus import bus`
bus = EventBus()
