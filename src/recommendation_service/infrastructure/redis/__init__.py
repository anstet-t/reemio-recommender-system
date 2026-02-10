"""Redis cache infrastructure with graceful degradation."""

from typing import Any

import orjson
import redis.asyncio as aioredis
import structlog

from recommendation_service.config import get_settings

logger = structlog.get_logger()

_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis | None:
    """Get or create the global async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        try:
            _redis_client = aioredis.from_url(
                settings.redis_url,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            await _redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning("Redis unavailable, caching disabled", error=str(e))
            _redis_client = None
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection on shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class CacheService:
    """Async Redis cache with orjson serialization. No-ops if Redis is unavailable."""

    def __init__(self, client: aioredis.Redis | None):
        self.client = client

    async def get(self, key: str) -> Any | None:
        if not self.client:
            return None
        try:
            data = await self.client.get(key)
            if data:
                return orjson.loads(data)
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        if not self.client:
            return
        try:
            await self.client.set(key, orjson.dumps(value), ex=ttl_seconds)
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        if not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))

    async def health_check(self) -> bool:
        if not self.client:
            return False
        try:
            return await self.client.ping()
        except Exception:
            return False
