"""
cache/market_cache.py — Redis-based кэш рыночных данных.

TTL:
  M1  = 70s   (чуть больше 1 минуты, чтобы не протухло до следующего бара)
  H1  = 3610s
  D1  = 86410s

Fallback: in-memory dict при недоступности Redis.

Key pattern: mk:bars:{symbol}:{timeframe}
"""
from __future__ import annotations

import json
import logging
from typing import Optional, Any

logger = logging.getLogger("MarketCache")

_TTL: dict[str, int] = {
    "M1":  70,
    "M5":  310,
    "M15": 910,
    "H1":  3610,
    "H4":  14410,
    "D1":  86410,
}

_DEFAULT_TTL = 120


class MarketCache:
    """
    Redis-based кэш с in-memory fallback.
    Потокобезопасен через asyncio (один event loop).
    """

    def __init__(self, redis_url: str, enabled: bool = True):
        self._url = redis_url
        self._enabled = enabled
        self._redis: Optional[Any] = None
        self._mem: dict[str, str] = {}  # fallback

    async def connect(self) -> None:
        if not self._enabled:
            logger.info("Redis кэш отключён (ENABLE_REDIS_CACHE=false)")
            return
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
            )
            await self._redis.ping()
            logger.info(f"Redis подключён: {self._url}")
        except Exception as e:
            logger.warning(f"Redis недоступен ({e}), используется in-memory fallback")
            self._redis = None

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    # ── Bars ──────────────────────────────────────────────────────────

    def _bars_key(self, symbol: str, timeframe: str) -> str:
        return f"mk:bars:{symbol}:{timeframe}"

    async def get_bars(self, symbol: str, timeframe: str) -> Optional[list[dict]]:
        key = self._bars_key(symbol, timeframe)
        raw = await self._get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_bars(self, symbol: str, timeframe: str, bars: list[dict]) -> None:
        key = self._bars_key(symbol, timeframe)
        ttl = _TTL.get(timeframe, _DEFAULT_TTL)
        await self._set(key, json.dumps(bars), ttl)

    # ── Account info ──────────────────────────────────────────────────

    _ACCOUNT_KEY = "mk:account"
    _ACCOUNT_TTL = 10  # seconds

    async def get_account(self) -> Optional[dict]:
        raw = await self._get(self._ACCOUNT_KEY)
        return json.loads(raw) if raw else None

    async def set_account(self, info: dict) -> None:
        await self._set(self._ACCOUNT_KEY, json.dumps(info), self._ACCOUNT_TTL)

    # ── Positions ─────────────────────────────────────────────────────

    _POSITIONS_KEY = "mk:positions"
    _POSITIONS_TTL = 5

    async def get_positions(self) -> Optional[list[dict]]:
        raw = await self._get(self._POSITIONS_KEY)
        return json.loads(raw) if raw else None

    async def set_positions(self, positions: list[dict]) -> None:
        await self._set(self._POSITIONS_KEY, json.dumps(positions), self._POSITIONS_TTL)

    # ── Generic ───────────────────────────────────────────────────────

    async def _get(self, key: str) -> Optional[str]:
        if self._redis:
            try:
                return await self._redis.get(key)
            except Exception as e:
                logger.debug(f"Redis GET error ({key}): {e}")
        return self._mem.get(key)

    async def _set(self, key: str, value: str, ttl: int) -> None:
        if self._redis:
            try:
                await self._redis.set(key, value, ex=ttl)
                return
            except Exception as e:
                logger.debug(f"Redis SET error ({key}): {e}")
        # fallback — хранится без TTL в памяти
        self._mem[key] = value

    async def invalidate(self, pattern: str) -> None:
        """Инвалидирует ключи по паттерну (только Redis)."""
        if self._redis:
            try:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
            except Exception as e:
                logger.debug(f"Redis KEYS error: {e}")


# Синглтон — создаётся в app startup
_cache: Optional[MarketCache] = None


def get_cache() -> MarketCache:
    if _cache is None:
        raise RuntimeError("MarketCache не инициализирован. Вызовите init_cache() при старте.")
    return _cache


async def init_cache(redis_url: str, enabled: bool = True) -> MarketCache:
    global _cache
    _cache = MarketCache(redis_url, enabled)
    await _cache.connect()
    return _cache
