"""Recommendation system evaluation metrics and utilities."""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


@dataclass
class EvaluationMetrics:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision_at_k": round(self.precision_at_k, 4),
            "recall_at_k": round(self.recall_at_k, 4),
            "ndcg_at_k": round(self.ndcg_at_k, 4),
            "mrr": round(self.mrr, 4),
            "hit_rate": round(self.hit_rate, 4),
            "catalog_coverage": round(self.catalog_coverage, 4),
            "diversity": round(self.diversity, 4),
            "novelty": round(self.novelty, 4),
            "num_users_evaluated": self.num_users_evaluated,
            "num_recommendations": self.num_recommendations,
            "k": self.k,
        }


class RecommendationEvaluator:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate(
        self,
        k: int = 10,
        test_days: int = 7,
        min_interactions: int = 5,
    ) -> EvaluationMetrics:
        """
        Evaluate recommendation quality using temporal split.

        Uses interactions from last `test_days` as ground truth,
        and generates recommendations based on earlier history.
        """
        logger.info("Starting evaluation", k=k, test_days=test_days)

        cutoff_date = datetime.now() - timedelta(days=test_days)

        test_data = await self._get_test_interactions(cutoff_date)
        train_users = await self._get_users_with_history(cutoff_date, min_interactions)

        if not train_users:
            logger.warning("No users with sufficient history for evaluation")
            return self._empty_metrics(k)

        all_products = await self._get_all_products()
        product_popularity = await self._get_product_popularity()

        precisions = []
        recalls = []
        ndcgs = []
        mrrs = []
        hits = []
        all_recommended = set()
        category_counts = []

        from recommendation_service.services.recommendation_engine_v2 import HybridRecommendationEngine
        engine = HybridRecommendationEngine(self.session)

        for user_id in train_users:
            user_test_items = test_data.get(user_id, set())
            if not user_test_items:
                continue

            try:
                result = await engine.get_homepage_recommendations(user_id=user_id, limit=k)
                recommendations = result.get("recommendations", [])
                rec_ids = [r["product_id"] for r in recommendations]
            except Exception as e:
                logger.warning("Failed to get recommendations", user_id=user_id, error=str(e))
                continue

            all_recommended.update(rec_ids)

            precision = self._precision_at_k(rec_ids, user_test_items, k)
            recall = self._recall_at_k(rec_ids, user_test_items, k)
            ndcg = self._ndcg_at_k(rec_ids, user_test_items, k)
            mrr = self._mrr(rec_ids, user_test_items)
            hit = 1.0 if len(set(rec_ids) & user_test_items) > 0 else 0.0

            precisions.append(precision)
            recalls.append(recall)
            ndcgs.append(ndcg)
            mrrs.append(mrr)
            hits.append(hit)

            categories = [r.get("category") for r in recommendations]
            category_counts.append(len(set(categories)))

        if not precisions:
            return self._empty_metrics(k)

        catalog_coverage = len(all_recommended) / len(all_products) if all_products else 0
        diversity = sum(category_counts) / len(category_counts) / k if category_counts else 0
        novelty = self._calculate_novelty(all_recommended, product_popularity)

        metrics = EvaluationMetrics(
            precision_at_k=sum(precisions) / len(precisions),
            recall_at_k=sum(recalls) / len(recalls),
            ndcg_at_k=sum(ndcgs) / len(ndcgs),
            mrr=sum(mrrs) / len(mrrs),
            hit_rate=sum(hits) / len(hits),
            catalog_coverage=catalog_coverage,
            diversity=diversity,
            novelty=novelty,
            num_users_evaluated=len(precisions),
            num_recommendations=len(all_recommended),
            k=k,
        )

        logger.info("Evaluation complete", metrics=metrics.to_dict())
        return metrics

    async def compare_strategies(self, k: int = 10) -> dict[str, Any]:
        """Compare different recommendation strategies."""
        results = {}

        results["hybrid"] = (await self.evaluate(k=k)).to_dict()
        results["popularity_baseline"] = (await self._evaluate_popularity_baseline(k)).to_dict()
        results["random_baseline"] = (await self._evaluate_random_baseline(k)).to_dict()

        return {
            "comparison": results,
            "best_strategy": max(results.keys(), key=lambda x: results[x]["ndcg_at_k"]),
            "evaluated_at": datetime.now().isoformat(),
        }

    async def get_coverage_report(self) -> dict[str, Any]:
        """Analyze catalog coverage and recommendation distribution."""
        query = text("""
            WITH rec_counts AS (
                SELECT
                    pe.category,
                    COUNT(DISTINCT pe.external_product_id) as total_products,
                    COUNT(DISTINCT CASE WHEN ui.id IS NOT NULL THEN pe.external_product_id END) as interacted_products
                FROM recommender.product_embeddings pe
                LEFT JOIN recommender.user_interactions ui ON ui.external_product_id = pe.external_product_id
                WHERE pe.is_active = true
                GROUP BY pe.category
            )
            SELECT
                category,
                total_products,
                interacted_products,
                ROUND(interacted_products::numeric / NULLIF(total_products, 0) * 100, 2) as coverage_pct
            FROM rec_counts
            ORDER BY total_products DESC
        """)

        result = await self.session.execute(query)
        rows = result.fetchall()

        return {
            "by_category": [
                {
                    "category": r.category or "Unknown",
                    "total_products": r.total_products,
                    "interacted_products": r.interacted_products,
                    "coverage_pct": float(r.coverage_pct or 0),
                }
                for r in rows
            ],
            "total_products": sum(r.total_products for r in rows),
            "total_interacted": sum(r.interacted_products for r in rows),
        }

    async def get_user_engagement_stats(self) -> dict[str, Any]:
        """Get user engagement statistics."""
        query = text("""
            SELECT
                interaction_type,
                COUNT(*) as count,
                COUNT(DISTINCT external_user_id) as unique_users,
                COUNT(DISTINCT external_product_id) as unique_products
            FROM recommender.user_interactions
            GROUP BY interaction_type
            ORDER BY count DESC
        """)

        result = await self.session.execute(query)
        rows = result.fetchall()

        return {
            "by_interaction_type": [
                {
                    "type": r.interaction_type,
                    "count": r.count,
                    "unique_users": r.unique_users,
                    "unique_products": r.unique_products,
                }
                for r in rows
            ],
            "total_interactions": sum(r.count for r in rows),
            "total_users": len(set(r.unique_users for r in rows)),
        }

    def _precision_at_k(self, recommended: list[str], relevant: set[str], k: int) -> float:
        if not recommended:
            return 0.0
        recommended_k = recommended[:k]
        hits = len(set(recommended_k) & relevant)
        return hits / len(recommended_k)

    def _recall_at_k(self, recommended: list[str], relevant: set[str], k: int) -> float:
        if not relevant:
            return 0.0
        recommended_k = recommended[:k]
        hits = len(set(recommended_k) & relevant)
        return hits / len(relevant)

    def _ndcg_at_k(self, recommended: list[str], relevant: set[str], k: int) -> float:
        dcg = 0.0
        for i, item in enumerate(recommended[:k]):
            if item in relevant:
                dcg += 1.0 / math.log2(i + 2)

        ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))

        return dcg / ideal_dcg if ideal_dcg > 0 else 0.0

    def _mrr(self, recommended: list[str], relevant: set[str]) -> float:
        for i, item in enumerate(recommended):
            if item in relevant:
                return 1.0 / (i + 1)
        return 0.0

    def _calculate_novelty(self, recommended: set[str], popularity: dict[str, float]) -> float:
        if not recommended:
            return 0.0
        novelty_scores = []
        for item in recommended:
            pop = popularity.get(item, 0.0)
            if pop > 0:
                novelty_scores.append(-math.log2(pop))
            else:
                novelty_scores.append(10.0)
        return sum(novelty_scores) / len(novelty_scores) if novelty_scores else 0.0

    async def _get_test_interactions(self, cutoff_date: datetime) -> dict[str, set[str]]:
        query = text("""
            SELECT external_user_id, external_product_id
            FROM recommender.user_interactions
            WHERE created_at >= :cutoff
            AND lower(interaction_type::text) IN ('purchase', 'cart_add', 'view')
        """)
        result = await self.session.execute(query, {"cutoff": cutoff_date})
        rows = result.fetchall()

        test_data = defaultdict(set)
        for row in rows:
            test_data[row.external_user_id].add(row.external_product_id)
        return dict(test_data)

    async def _get_users_with_history(self, cutoff_date: datetime, min_interactions: int) -> list[str]:
        query = text("""
            SELECT external_user_id
            FROM recommender.user_interactions
            WHERE created_at < :cutoff
            GROUP BY external_user_id
            HAVING COUNT(*) >= :min_interactions
        """)
        result = await self.session.execute(query, {"cutoff": cutoff_date, "min_interactions": min_interactions})
        return [row.external_user_id for row in result.fetchall()]

    async def _get_all_products(self) -> set[str]:
        query = text("SELECT external_product_id FROM recommender.product_embeddings WHERE is_active = true")
        result = await self.session.execute(query)
        return {row.external_product_id for row in result.fetchall()}

    async def _get_product_popularity(self) -> dict[str, float]:
        query = text("""
            SELECT external_product_id, COUNT(*) as count
            FROM recommender.user_interactions
            GROUP BY external_product_id
        """)
        result = await self.session.execute(query)
        rows = result.fetchall()
        total = sum(row.count for row in rows)
        return {row.external_product_id: row.count / total for row in rows} if total > 0 else {}

    async def _evaluate_popularity_baseline(self, k: int) -> EvaluationMetrics:
        """Evaluate popularity-based recommendations as baseline."""
        cutoff_date = datetime.now() - timedelta(days=7)
        test_data = await self._get_test_interactions(cutoff_date)

        query = text("""
            SELECT external_product_id
            FROM recommender.product_embeddings
            WHERE is_active = true
            ORDER BY popularity_score DESC NULLS LAST
            LIMIT :k
        """)
        result = await self.session.execute(query, {"k": k})
        popular_items = [row.external_product_id for row in result.fetchall()]

        precisions, recalls, ndcgs, hits = [], [], [], []
        for user_id, relevant in test_data.items():
            precisions.append(self._precision_at_k(popular_items, relevant, k))
            recalls.append(self._recall_at_k(popular_items, relevant, k))
            ndcgs.append(self._ndcg_at_k(popular_items, relevant, k))
            hits.append(1.0 if set(popular_items) & relevant else 0.0)

        if not precisions:
            return self._empty_metrics(k)

        return EvaluationMetrics(
            precision_at_k=sum(precisions) / len(precisions),
            recall_at_k=sum(recalls) / len(recalls),
            ndcg_at_k=sum(ndcgs) / len(ndcgs),
            mrr=0.0,
            hit_rate=sum(hits) / len(hits),
            catalog_coverage=len(set(popular_items)) / len(await self._get_all_products()),
            diversity=0.0,
            novelty=0.0,
            num_users_evaluated=len(precisions),
            num_recommendations=len(popular_items),
            k=k,
        )

    async def _evaluate_random_baseline(self, k: int) -> EvaluationMetrics:
        """Evaluate random recommendations as baseline."""
        import random

        cutoff_date = datetime.now() - timedelta(days=7)
        test_data = await self._get_test_interactions(cutoff_date)
        all_products = list(await self._get_all_products())

        precisions, recalls, ndcgs, hits = [], [], [], []
        for user_id, relevant in test_data.items():
            random_items = random.sample(all_products, min(k, len(all_products)))
            precisions.append(self._precision_at_k(random_items, relevant, k))
            recalls.append(self._recall_at_k(random_items, relevant, k))
            ndcgs.append(self._ndcg_at_k(random_items, relevant, k))
            hits.append(1.0 if set(random_items) & relevant else 0.0)

        if not precisions:
            return self._empty_metrics(k)

        return EvaluationMetrics(
            precision_at_k=sum(precisions) / len(precisions),
            recall_at_k=sum(recalls) / len(recalls),
            ndcg_at_k=sum(ndcgs) / len(ndcgs),
            mrr=0.0,
            hit_rate=sum(hits) / len(hits),
            catalog_coverage=1.0,
            diversity=1.0,
            novelty=5.0,
            num_users_evaluated=len(precisions),
            num_recommendations=k,
            k=k,
        )

    def _empty_metrics(self, k: int) -> EvaluationMetrics:
        return EvaluationMetrics(
            precision_at_k=0.0,
            recall_at_k=0.0,
            ndcg_at_k=0.0,
            mrr=0.0,
            hit_rate=0.0,
            catalog_coverage=0.0,
            diversity=0.0,
            novelty=0.0,
            num_users_evaluated=0,
            num_recommendations=0,
            k=k,
        )
