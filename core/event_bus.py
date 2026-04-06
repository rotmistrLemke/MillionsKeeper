import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable, List, Dict
from core.events import Event, EventType

HandlerType = Callable[[Event], Awaitable[None]]


class EventBus:
    """
    Асинхронная шина событий.
    Поддерживает wildcard-подписки: "market.*" поймает все market.* события.
    Глобальная подписка "*" получает все события.
    """

    def __init__(self):
        self._handlers: Dict[str, List[HandlerType]] = defaultdict(list)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._running = False
        self._logger = logging.getLogger("EventBus")
        # История последних N событий каждого типа (для снепшота новым WS-клиентам)
        self._history: Dict[str, list] = defaultdict(list)
        self._history_limit = 100

    def subscribe(self, event_type: str, handler: HandlerType):
        """Подписка. event_type может быть точным, wildcard 'market.*' или '*'."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: HandlerType):
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event):
        """Асинхронная публикация. Не блокирует вызывающий код."""
        await self._queue.put(event)
        self._store_history(event)

    def publish_sync(self, event: Event):
        """Публикация из синхронного (threading) кода."""
        try:
            self._queue.put_nowait(event)
            self._store_history(event)
        except asyncio.QueueFull:
            self._logger.warning(f"EventBus queue full, dropping: {event.type}")

    def _store_history(self, event: Event):
        hist = self._history[event.type]
        hist.append(event)
        if len(hist) > self._history_limit:
            hist.pop(0)

    async def _dispatch(self, event: Event):
        handlers = list(self._handlers.get(event.type, []))
        # wildcard по первому сегменту
        prefix = event.type.split(".")[0] + ".*"
        handlers += list(self._handlers.get(prefix, []))
        # глобальный
        handlers += list(self._handlers.get("*", []))

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                self._logger.error(f"Handler {handler.__qualname__} failed for {event.type}: {e}")

    async def run(self):
        """Основной цикл диспетчеризации. Запускается через asyncio.create_task()."""
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self._logger.error(f"EventBus dispatch error: {e}")

    def stop(self):
        self._running = False

    def get_recent_events(self, event_type: str = None, limit: int = 50) -> list:
        """Для снепшота при подключении нового WS-клиента."""
        if event_type:
            return list(self._history.get(event_type, []))[-limit:]
        all_events = []
        for events in self._history.values():
            all_events.extend(events)
        return sorted(all_events, key=lambda e: e.timestamp, reverse=True)[:limit]


# Глобальный синглтон
bus = EventBus()
