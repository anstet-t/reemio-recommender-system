"""API v1 router that aggregates all endpoint routers."""

from fastapi import APIRouter

from recommendation_service.api.v1 import (
    analytics,
    health,
    interactions,
    recommendations,
)

api_router = APIRouter()

# Include all routers
api_router.include_router(
    health.router,
    tags=["Health"],
)

api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["Recommendations"],
)

api_router.include_router(
    interactions.router,
    prefix="/interactions",
    tags=["Interactions"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"],
)
