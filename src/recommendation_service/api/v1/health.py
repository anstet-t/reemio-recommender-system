"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from recommendation_service import __version__
from recommendation_service.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    environment: str
    timestamp: str
    dependencies: dict[str, Any]


class ReadinessResponse(BaseModel):
    """Readiness check response model."""

    ready: bool
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.

    Returns the service status and version information.
    This endpoint is used by load balancers and orchestrators
    to determine if the service is running.
    """
    settings = get_settings()

    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        dependencies={
            "postgres": "configured",
            "pgvector": "configured",
            "redis": "configured",
        },
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check endpoint.

    Verifies that all dependencies are connected and ready.
    This endpoint is used by Kubernetes readiness probes.
    """
    checks: dict[str, bool] = {}

    # TODO: Implement actual dependency checks
    # Check PostgreSQL connection
    try:
        # await database.execute("SELECT 1")
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False

    # Check pgvector extension
    try:
        # await database.execute("SELECT * FROM pg_extension WHERE extname = 'vector'")
        checks["pgvector"] = True
    except Exception:
        checks["pgvector"] = False

    # Check Redis connection
    try:
        # await redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    all_ready = all(checks.values())

    return ReadinessResponse(
        ready=all_ready,
        checks=checks,
    )


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness check endpoint.

    Simple endpoint that returns 200 if the service is running.
    This endpoint is used by Kubernetes liveness probes.
    """
    return {"status": "alive"}
