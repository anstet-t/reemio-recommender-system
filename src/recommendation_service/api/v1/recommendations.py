"""Recommendation API endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.config import Settings, get_settings
from recommendation_service.infrastructure.database.connection import get_session
from recommendation_service.infrastructure.redis import CacheService, get_redis_client
from recommendation_service.services.recommendation_engine_v2 import (
    HybridRecommendationEngine,
)

logger = structlog.get_logger()

router = APIRouter()


class RecommendedProduct(BaseModel):
    """A recommended product with relevance score."""

    product_id: str
    external_product_id: str
    name: str
    category: str
    price: float
    image_url: str | None = None
    score: float = Field(..., description="Relevance/similarity score")
    position: int = Field(..., description="Position in recommendation list")


class RecommendationResponse(BaseModel):
    """Response containing recommendations."""

    recommendations: list[RecommendedProduct]
    request_id: str
    context: str
    user_id: str | None = None
    generated_at: str


@router.get("/homepage", response_model=RecommendationResponse)
async def get_homepage_recommendations(
    user_id: Annotated[str, Query(description="User ID for personalization")],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    """
    Get personalized homepage recommendations for a user.

    This endpoint returns products tailored to the user's preferences
    based on their interaction history (views, purchases, cart activity).

    **Algorithm:**
    1. Fetch user preference vector
    2. Search products index with user preference
    3. Apply diversity strategies (limit per category)
    4. Return ranked results

    **Usage in UI:**
    - Homepage "Recommended for You" section
    - Personalized product carousel
    """
    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    engine = HybridRecommendationEngine(session, cache=cache)
    result = await engine.get_homepage_recommendations(user_id=user_id, limit=limit)

    return RecommendationResponse(
        recommendations=[
            RecommendedProduct(**p) for p in result["recommendations"]
        ],
        request_id=result["request_id"],
        context=result["context"],
        user_id=result["user_id"],
        generated_at=result["generated_at"],
    )


@router.get("/product/{product_id}", response_model=RecommendationResponse)
async def get_similar_products(
    product_id: str,
    user_id: Annotated[str | None, Query(description="Optional user ID for personalization")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 8,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    """
    Get similar products for a product page.

    Returns products that are semantically similar to the given product,
    optionally personalized if user_id is provided.

    **Algorithm:**
    1. Fetch source product embedding
    2. Search for similar products (excluding source)
    3. Optionally blend with user preferences
    4. Return ranked results

    **Usage in UI:**
    - Product page "Similar Products" section
    - "You might also like" carousel
    """
    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    engine = HybridRecommendationEngine(session, cache=cache)
    result = await engine.get_similar_products(
        product_id=product_id, user_id=user_id, limit=limit
    )

    return RecommendationResponse(
        recommendations=[
            RecommendedProduct(**p) for p in result["recommendations"]
        ],
        request_id=result["request_id"],
        context=result["context"],
        user_id=result["user_id"],
        generated_at=result["generated_at"],
    )


@router.get("/cart", response_model=RecommendationResponse)
async def get_cart_recommendations(
    user_id: Annotated[str, Query(description="User ID")],
    cart_product_ids: Annotated[list[str], Query(description="Product IDs in cart")],
    limit: Annotated[int, Query(ge=1, le=20)] = 6,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    """
    Get recommendations based on cart contents.

    Returns complementary products that go well with items in the cart,
    useful for upselling and cross-selling.

    **Algorithm:**
    1. Fetch embeddings for all cart products
    2. Aggregate embeddings (weighted average)
    3. Search for complementary products (excluding cart items)
    4. Filter by price range relative to cart total
    5. Return ranked results

    **Usage in UI:**
    - Cart page "Complete your order" section
    - Checkout upsell carousel
    """
    if not cart_product_ids:
        raise HTTPException(
            status_code=400,
            detail="cart_product_ids must not be empty",
        )

    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    engine = HybridRecommendationEngine(session, cache=cache)
    result = await engine.get_cart_recommendations(
        user_id=user_id, cart_product_ids=cart_product_ids, limit=limit
    )

    return RecommendationResponse(
        recommendations=[
            RecommendedProduct(**p) for p in result["recommendations"]
        ],
        request_id=result["request_id"],
        context=result["context"],
        user_id=result["user_id"],
        generated_at=result["generated_at"],
    )


@router.get(
    "/frequently-bought-together/{product_id}",
    response_model=RecommendationResponse,
)
async def get_frequently_bought_together(
    product_id: str,
    limit: Annotated[int, Query(ge=1, le=10)] = 4,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    """
    Get frequently bought together products.

    Returns products that are commonly purchased together with
    the given product, based on historical order data.

    **Algorithm:**
    1. Query order history for co-purchases
    2. Calculate co-purchase frequency scores
    3. Return top co-purchased products
    4. Fall back to similar products if insufficient data

    **Usage in UI:**
    - Product page "Frequently Bought Together" section
    - Bundle suggestions
    """
    redis_client = await get_redis_client()
    cache = CacheService(redis_client)
    engine = HybridRecommendationEngine(session, cache=cache)
    result = await engine.get_frequently_bought_together(
        product_id=product_id, limit=limit
    )

    return RecommendationResponse(
        recommendations=[
            RecommendedProduct(**p) for p in result["recommendations"]
        ],
        request_id=result["request_id"],
        context=result["context"],
        user_id=result["user_id"],
        generated_at=result["generated_at"],
    )


@router.get("/search", response_model=RecommendationResponse)
async def get_search_recommendations(
    query: Annotated[str, Query(description="Search query text", min_length=1, max_length=500)],
    user_id: Annotated[
        str | None, Query(description="Optional user ID for personalization")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
    category: Annotated[str | None, Query(description="Optional category filter")] = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RecommendationResponse:
    """
    Get search-based product recommendations.

    Combines PostgreSQL full-text search (tsvector) with trigram fuzzy matching
    and semantic embedding similarity for hybrid ranking.

    **Algorithm:**
    1. PG full-text search + trigram fuzzy matching for candidate retrieval
    2. Blend text relevance (60%) with embedding cosine similarity (40%)
    3. Optional Pinecone reranking for final scoring
    4. Apply diversity and business rules

    **Usage in UI:**
    - Search results page
    - "Search for Fridge" -> returns relevant fridge products ranked by relevance
    """
    engine = HybridRecommendationEngine(session)
    result = await engine.get_search_recommendations(
        query=query, user_id=user_id, limit=limit, category=category
    )

    # Track search interaction
    if user_id:
        try:
            track_query = text("""
                INSERT INTO recommender.user_interactions
                (external_user_id, interaction_type, search_query,
                 recommendation_request_id, created_at)
                VALUES (:user_id, 'SEARCH', :search_query, :request_id, NOW())
            """)
            await session.execute(track_query, {
                "user_id": user_id,
                "search_query": query,
                "request_id": result["request_id"],
            })
            await session.commit()
        except Exception as e:
            logger.warning("Failed to track search interaction", error=str(e))

    return RecommendationResponse(
        recommendations=[
            RecommendedProduct(**p) for p in result["recommendations"]
        ],
        request_id=result["request_id"],
        context=result["context"],
        user_id=result["user_id"],
        generated_at=result["generated_at"],
    )
