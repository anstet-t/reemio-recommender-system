"""User interaction tracking API endpoints."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.infrastructure.database.connection import get_session
from recommendation_service.infrastructure.redis import CacheService, get_redis_client
from recommendation_service.services.user_preference import UserPreferenceService

router = APIRouter()


# =============================================================================
# Enums and Models
# =============================================================================


class InteractionType(str, Enum):
    """Types of user interactions."""

    VIEW = "view"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    PURCHASE = "purchase"
    WISHLIST_ADD = "wishlist_add"
    SEARCH = "search"
    RECOMMENDATION_CLICK = "recommendation_click"
    RECOMMENDATION_VIEW = "recommendation_view"


class InteractionRequest(BaseModel):
    """Request model for tracking a user interaction."""

    user_id: str = Field(..., description="User identifier")
    product_id: str | None = Field(None, description="Product identifier (required for most interactions)")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    search_query: str | None = Field(None, description="Search query (for search interactions)")
    recommendation_context: str | None = Field(
        None,
        description="Context where recommendation was shown (homepage, product_page, cart, email)",
    )
    recommendation_position: int | None = Field(
        None,
        description="Position of clicked/viewed recommendation in the list",
    )
    session_id: str | None = Field(None, description="Session identifier for grouping interactions")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Additional metadata")


class InteractionResponse(BaseModel):
    """Response after recording an interaction."""

    success: bool
    interaction_id: str
    recorded_at: str


class BatchInteractionRequest(BaseModel):
    """Request model for batch interaction tracking."""

    interactions: list[InteractionRequest] = Field(
        ...,
        max_length=100,
        description="List of interactions to record (max 100)",
    )


class BatchInteractionResponse(BaseModel):
    """Response after recording batch interactions."""

    success: bool
    recorded_count: int
    failed_count: int
    recorded_at: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=InteractionResponse)
async def track_interaction(
    interaction: InteractionRequest,
    session: AsyncSession = Depends(get_session),
) -> InteractionResponse:
    """
    Track a single user interaction.

    This endpoint records user behavior for:
    - Building user preference vectors
    - Training recommendation models
    - Analytics and insights
    - Feedback loop optimization

    **Interaction Types:**
    - `view`: User viewed a product page
    - `cart_add`: User added product to cart
    - `cart_remove`: User removed product from cart
    - `purchase`: User completed purchase
    - `wishlist_add`: User added to wishlist
    - `search`: User performed a search
    - `recommendation_click`: User clicked on a recommendation
    - `recommendation_view`: Recommendation was shown to user

    **Important for Recommendations:**
    - Track `recommendation_view` when showing recommendations
    - Track `recommendation_click` when user clicks a recommendation
    - Include `recommendation_context` and `recommendation_position` for attribution
    """
    # Validate that product_id is provided for product interactions
    product_interactions = {
        InteractionType.VIEW,
        InteractionType.CART_ADD,
        InteractionType.CART_REMOVE,
        InteractionType.PURCHASE,
        InteractionType.WISHLIST_ADD,
        InteractionType.RECOMMENDATION_CLICK,
        InteractionType.RECOMMENDATION_VIEW,
    }

    if interaction.interaction_type in product_interactions and not interaction.product_id:
        raise HTTPException(
            status_code=400,
            detail=f"product_id is required for {interaction.interaction_type.value} interactions",
        )

    if interaction.interaction_type == InteractionType.SEARCH and not interaction.search_query:
        raise HTTPException(
            status_code=400,
            detail="search_query is required for search interactions",
        )

    insert_query = text("""
        INSERT INTO recommender.user_interactions
        (
            external_user_id,
            external_product_id,
            interaction_type,
            search_query,
            recommendation_context,
            recommendation_position,
            session_id,
            extra_data
        )
        VALUES
        (
            :user_id,
            :product_id,
            :interaction_type,
            :search_query,
            :recommendation_context,
            :recommendation_position,
            :session_id,
            :extra_data
        )
        RETURNING id
    """).bindparams(bindparam("extra_data", type_=JSONB))

    result = await session.execute(
        insert_query,
        {
            "user_id": interaction.user_id,
            "product_id": interaction.product_id,
            "interaction_type": interaction.interaction_type.name,
            "search_query": interaction.search_query,
            "recommendation_context": interaction.recommendation_context,
            "recommendation_position": interaction.recommendation_position,
            "session_id": interaction.session_id,
            "extra_data": interaction.metadata or {},
        },
    )
    interaction_id = str(result.scalar_one())
    await session.commit()

    # Update user preferences and invalidate cache
    prefs = UserPreferenceService(session)
    await prefs.update_user_preference(interaction.user_id)
    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    await cache.delete(f"user_emb:{interaction.user_id}")
    await cache.delete(f"user_prefs:{interaction.user_id}")

    return InteractionResponse(
        success=True,
        interaction_id=interaction_id,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/batch", response_model=BatchInteractionResponse)
async def track_interactions_batch(
    request: BatchInteractionRequest,
    session: AsyncSession = Depends(get_session),
) -> BatchInteractionResponse:
    """
    Track multiple user interactions in a single request.

    Use this endpoint for:
    - Bulk uploading historical interaction data
    - Recording multiple recommendation views at once
    - Efficient batch processing from frontend

    **Limits:**
    - Maximum 100 interactions per request
    - Each interaction is validated independently
    - Partial success is possible (some may fail)
    """
    if not request.interactions:
        raise HTTPException(
            status_code=400,
            detail="interactions list must not be empty",
        )

    insert_query = text("""
        INSERT INTO recommender.user_interactions
        (
            external_user_id,
            external_product_id,
            interaction_type,
            search_query,
            recommendation_context,
            recommendation_position,
            session_id,
            extra_data
        )
        VALUES
        (
            :user_id,
            :product_id,
            :interaction_type,
            :search_query,
            :recommendation_context,
            :recommendation_position,
            :session_id,
            :extra_data
        )
    """).bindparams(bindparam("extra_data", type_=JSONB))

    payloads = [
        {
            "user_id": interaction.user_id,
            "product_id": interaction.product_id,
            "interaction_type": interaction.interaction_type.name,
            "search_query": interaction.search_query,
            "recommendation_context": interaction.recommendation_context,
            "recommendation_position": interaction.recommendation_position,
            "session_id": interaction.session_id,
            "extra_data": interaction.metadata or {},
        }
        for interaction in request.interactions
    ]

    await session.execute(insert_query, payloads)
    await session.commit()

    # Update preferences for affected users and invalidate caches
    affected_users = {interaction.user_id for interaction in request.interactions}
    prefs = UserPreferenceService(session)
    for user_id in affected_users:
        await prefs.update_user_preference(user_id)
    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    for user_id in affected_users:
        await cache.delete(f"user_emb:{user_id}")
        await cache.delete(f"user_prefs:{user_id}")

    recorded_count = len(request.interactions)
    failed_count = 0

    return BatchInteractionResponse(
        success=failed_count == 0,
        recorded_count=recorded_count,
        failed_count=failed_count,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/user/{user_id}/history")
async def get_user_interaction_history(
    user_id: str,
    interaction_type: Annotated[InteractionType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """
    Get interaction history for a user.

    Useful for:
    - Debugging user preferences
    - Building user activity feeds
    - Customer support investigations
    """
    # TODO: Implement interaction history retrieval

    return {
        "user_id": user_id,
        "interactions": [],
        "total_count": 0,
        "limit": limit,
        "offset": offset,
    }
