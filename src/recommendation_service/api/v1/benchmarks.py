"""Benchmark and resource profiling endpoints."""

import platform
import sys
from datetime import datetime, timezone
from typing import Any

import psutil
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.infrastructure.database.connection import get_session
from recommendation_service.infrastructure.redis import CacheService, get_redis_client
from recommendation_service.middleware.timing import get_endpoint_stats, reset_endpoint_stats

logger = structlog.get_logger()
router = APIRouter()


class BenchmarkResponse(BaseModel):
    """Full system resource and performance profile."""

    endpoint_latencies: dict[str, dict]
    system_resources: dict[str, Any]
    database_pool: dict[str, Any]
    cache_status: dict[str, Any]
    generated_at: str


@router.get("/profile", response_model=BenchmarkResponse)
async def get_benchmark_profile(
    session: AsyncSession = Depends(get_session),
) -> BenchmarkResponse:
    """
    Get full resource and performance profile.

    Returns endpoint latency stats (p50/p95), system resource usage
    (CPU, memory, threads), database pool stats, and cache health.
    """
    # System resources
    process = psutil.Process()
    system_resources = {
        "cpu_percent": process.cpu_percent(interval=0.1),
        "memory_rss_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        "memory_vms_mb": round(process.memory_info().vms / 1024 / 1024, 2),
        "threads": process.num_threads(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }

    # Database pool stats
    engine = session.get_bind()
    pool = engine.pool
    db_pool_stats = {}
    pool_size = getattr(pool, "size", None)
    db_pool_stats["pool_size"] = pool_size() if callable(pool_size) else (pool_size or "N/A")
    for attr in ("checkedin", "checkedout", "overflow"):
        val = getattr(pool, attr, None)
        db_pool_stats[attr] = val() if callable(val) else "N/A"

    # Cache status
    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    cache_healthy = await cache.health_check()
    cache_status = {
        "connected": cache_healthy,
        "type": "redis" if cache_healthy else "none",
    }

    return BenchmarkResponse(
        endpoint_latencies=get_endpoint_stats(),
        system_resources=system_resources,
        database_pool=db_pool_stats,
        cache_status=cache_status,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/reset")
async def reset_stats() -> dict[str, str]:
    """Reset all collected endpoint timing stats."""
    reset_endpoint_stats()
    return {"status": "ok", "message": "Endpoint stats reset"}
