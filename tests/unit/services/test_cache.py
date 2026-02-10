"""Unit tests for Redis cache service."""

import pytest

from recommendation_service.infrastructure.redis import CacheService


class TestCacheServiceGracefulDegradation:
    """CacheService should no-op safely when Redis is unavailable."""

    @pytest.fixture
    def cache(self) -> CacheService:
        return CacheService(None)

    @pytest.mark.asyncio
    async def test_get_returns_none(self, cache: CacheService) -> None:
        assert await cache.get("any-key") is None

    @pytest.mark.asyncio
    async def test_set_is_noop(self, cache: CacheService) -> None:
        await cache.set("key", {"data": "value"})  # should not raise

    @pytest.mark.asyncio
    async def test_delete_is_noop(self, cache: CacheService) -> None:
        await cache.delete("key")  # should not raise

    @pytest.mark.asyncio
    async def test_health_check_returns_false(self, cache: CacheService) -> None:
        assert await cache.health_check() is False
