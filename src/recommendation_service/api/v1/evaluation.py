"""Evaluation API endpoints for recommendation system metrics."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.infrastructure.database.connection import get_session
from recommendation_service.services.evaluation import RecommendationEvaluator

router = APIRouter()


class MetricsResponse(BaseModel):
    precision_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    mrr: float
    hit_rate: float
    catalog_coverage: float
    diversity: float
    novelty: float
    num_users_evaluated: int
    num_recommendations: int
    k: int


class ComparisonResponse(BaseModel):
    comparison: dict
    best_strategy: str
    evaluated_at: str


class CoverageResponse(BaseModel):
    by_category: list[dict]
    total_products: int
    total_interacted: int


class EngagementResponse(BaseModel):
    by_interaction_type: list[dict]
    total_interactions: int
    total_users: int


@router.get("/metrics", response_model=MetricsResponse)
async def get_evaluation_metrics(
    k: Annotated[int, Query(ge=1, le=50, description="Number of recommendations to evaluate")] = 10,
    test_days: Annotated[int, Query(ge=1, le=30, description="Days to use as test period")] = 7,
    session: AsyncSession = Depends(get_session),
) -> MetricsResponse:
    """
    Evaluate recommendation system quality.

    Returns standard ranking metrics:
    - **Precision@K**: Fraction of recommended items that are relevant
    - **Recall@K**: Fraction of relevant items that were recommended
    - **NDCG@K**: Normalized Discounted Cumulative Gain (position-aware)
    - **MRR**: Mean Reciprocal Rank
    - **Hit Rate**: Fraction of users with at least one relevant recommendation
    - **Catalog Coverage**: Fraction of catalog that gets recommended
    - **Diversity**: Category diversity in recommendations
    - **Novelty**: How novel/non-popular are the recommendations
    """
    evaluator = RecommendationEvaluator(session)
    metrics = await evaluator.evaluate(k=k, test_days=test_days)
    return MetricsResponse(**metrics.to_dict())


@router.get("/compare", response_model=ComparisonResponse)
async def compare_strategies(
    k: Annotated[int, Query(ge=1, le=50)] = 10,
    session: AsyncSession = Depends(get_session),
) -> ComparisonResponse:
    """
    Compare recommendation strategies.

    Compares:
    - **Hybrid**: Content + Collaborative + Popularity (our main approach)
    - **Popularity Baseline**: Just recommend popular items
    - **Random Baseline**: Random recommendations

    Returns which strategy performs best on NDCG@K.
    """
    evaluator = RecommendationEvaluator(session)
    comparison = await evaluator.compare_strategies(k=k)
    return ComparisonResponse(**comparison)


@router.get("/coverage", response_model=CoverageResponse)
async def get_coverage_report(
    session: AsyncSession = Depends(get_session),
) -> CoverageResponse:
    """
    Get catalog coverage analysis.

    Shows how well the recommendation system covers the product catalog,
    broken down by category.
    """
    evaluator = RecommendationEvaluator(session)
    report = await evaluator.get_coverage_report()
    return CoverageResponse(**report)


@router.get("/engagement", response_model=EngagementResponse)
async def get_engagement_stats(
    session: AsyncSession = Depends(get_session),
) -> EngagementResponse:
    """
    Get user engagement statistics.

    Shows interaction counts by type (VIEW, PURCHASE, CART_ADD, etc.)
    to understand user behavior patterns.
    """
    evaluator = RecommendationEvaluator(session)
    stats = await evaluator.get_user_engagement_stats()
    return EngagementResponse(**stats)
