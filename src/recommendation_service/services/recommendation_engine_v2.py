"""Hybrid recommendation engine with 4-stage pipeline.

Pipeline stages:
1. Candidate Generation - Fast retrieval (content + collaborative)
2. Hybrid Scoring - Blend multiple signals
3. Reranking - Cross-encoder for precise ordering
4. Business Rules - Diversity, freshness, stock filters
"""

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.services.embedding import EmbeddingService
from recommendation_service.services.reranker import RerankerService

logger = structlog.get_logger()


class HybridRecommendationEngine:
    """Hybrid recommendation engine with content + collaborative filtering."""

    # Hybrid scoring weights (α, β, γ)
    CONTENT_WEIGHT = 0.5  # Embedding similarity
    COLLABORATIVE_WEIGHT = 0.3  # Co-purchase, similar users
    POPULARITY_WEIGHT = 0.2  # Global popularity

    def __init__(self, session: AsyncSession, enable_reranking: bool = True):
        self.session = session
        self.embedding_service = EmbeddingService(session)
        self.reranker = RerankerService() if enable_reranking else None

    async def get_homepage_recommendations(
        self,
        user_id: str,
        limit: int = 12,
        diversity_limit_per_category: int = 3,
    ) -> dict[str, Any]:
        """Get personalized homepage recommendations."""
        request_id = str(uuid4())

        # Stage 1: Candidate Generation
        candidates = await self._generate_candidates_for_user(
            user_id, candidate_limit=limit * 5
        )

        if not candidates:
            # Fallback to popular products
            candidates = await self._get_popular_products(limit=limit * 2)

        # Stage 2: Hybrid Scoring
        candidates = await self._apply_hybrid_scoring(candidates, user_id)

        # Stage 3: Reranking
        if self.reranker:
            user_prefs = await self._get_user_preference_data(user_id)
            query = self.reranker.create_query_from_user_context(
                user_categories=user_prefs.get("top_categories"),
                context="homepage recommendations",
            )
            candidates = self.reranker.rerank(query, candidates, top_k=limit * 2)

        # Stage 4: Business Rules
        candidates = self._apply_diversity(candidates, diversity_limit_per_category)
        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        # Add position
        for i, p in enumerate(candidates):
            p["position"] = i + 1

        return {
            "recommendations": candidates,
            "request_id": request_id,
            "context": "homepage",
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_similar_products(
        self,
        product_id: str,
        user_id: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        """Get products similar to a given product."""
        request_id = str(uuid4())

        # Get source product
        source_product = await self._get_product_by_external_id(product_id)
        if not source_product:
            return self._empty_response(request_id, "product_page", user_id)

        # Stage 1: Candidate Generation (content-based)
        candidates = []
        source_embedding = source_product.get("embedding")

        if source_embedding:
            candidates = await self._search_similar_products(
                source_embedding, limit=limit * 4, exclude_ids=[product_id]
            )
        else:
            candidates = await self._get_products_by_category(
                source_product.get("category"), limit=limit * 2, exclude_ids=[product_id]
            )

        # Add collaborative signal (frequently bought together)
        collaborative_candidates = await self._get_co_purchased_products(
            product_id, limit=limit
        )
        candidates.extend(collaborative_candidates)

        # Stage 2: Hybrid Scoring
        candidates = await self._apply_hybrid_scoring(candidates, user_id, source_product)

        # Stage 3: Reranking
        if self.reranker:
            query = f"{source_product['name']} {source_product.get('category', '')}"
            candidates = self.reranker.rerank(query, candidates, top_k=limit * 2)

        # Stage 4: Business Rules
        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        for i, p in enumerate(candidates):
            p["position"] = i + 1

        return {
            "recommendations": candidates,
            "request_id": request_id,
            "context": "product_page",
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_cart_recommendations(
        self,
        user_id: str,
        cart_product_ids: list[str],
        limit: int = 6,
    ) -> dict[str, Any]:
        """Get recommendations based on cart contents."""
        request_id = str(uuid4())

        # Stage 1: Candidate Generation
        # Content-based: aggregate cart embeddings
        cart_embeddings = []
        for pid in cart_product_ids:
            product = await self._get_product_by_external_id(pid)
            if product and product.get("embedding"):
                cart_embeddings.append(product["embedding"])

        candidates = []
        if cart_embeddings:
            aggregated = self._aggregate_embeddings(cart_embeddings)
            candidates = await self._search_similar_products(
                aggregated,
                limit=limit * 4,
                exclude_ids=cart_product_ids,
            )

        # Collaborative: products bought with cart items
        for cart_pid in cart_product_ids[:3]:  # Check top 3 cart items
            collab_products = await self._get_co_purchased_products(
                cart_pid, limit=limit
            )
            candidates.extend(collab_products)

        # Deduplicate
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c["product_id"] not in seen and c["product_id"] not in cart_product_ids:
                seen.add(c["product_id"])
                unique_candidates.append(c)
        candidates = unique_candidates

        # Stage 2: Hybrid Scoring
        candidates = await self._apply_hybrid_scoring(candidates, user_id)

        # Stage 3: Reranking
        if self.reranker and candidates:
            query = "Cart completion recommendations"
            candidates = self.reranker.rerank(query, candidates, top_k=limit * 2)

        # Stage 4: Business Rules
        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        for i, p in enumerate(candidates):
            p["position"] = i + 1

        return {
            "recommendations": candidates,
            "request_id": request_id,
            "context": "cart",
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    # Stage 1: Candidate Generation
    # =========================================================================

    async def _generate_candidates_for_user(
        self, user_id: str, candidate_limit: int = 50
    ) -> list[dict[str, Any]]:
        """Generate candidates using both content and collaborative signals."""
        candidates = []

        # Content-based: user preference embedding
        user_embedding = await self._get_user_embedding(user_id)
        if user_embedding:
            content_candidates = await self._search_similar_products(
                user_embedding, limit=candidate_limit // 2, exclude_ids=[]
            )
            candidates.extend(content_candidates)

        # Collaborative: products from similar users
        collaborative_candidates = await self._get_collaborative_candidates(
            user_id, limit=candidate_limit // 2
        )
        candidates.extend(collaborative_candidates)

        return candidates

    async def _get_collaborative_candidates(
        self, user_id: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Get recommendations based on similar users (collaborative filtering)."""
        # Find products purchased by users with similar interaction patterns
        query = text("""
            WITH user_products AS (
                -- Products this user has interacted with
                SELECT DISTINCT external_product_id
                FROM recommender.user_interactions
                WHERE external_user_id = :user_id
            ),
            similar_users AS (
                -- Users who interacted with same products
                SELECT
                    ui.external_user_id,
                    COUNT(DISTINCT ui.external_product_id) as overlap
                FROM recommender.user_interactions ui
                WHERE ui.external_product_id IN (SELECT external_product_id FROM user_products)
                AND ui.external_user_id != :user_id
                GROUP BY ui.external_user_id
                HAVING COUNT(DISTINCT ui.external_product_id) >= 2
                ORDER BY overlap DESC
                LIMIT 10
            ),
            recommended_products AS (
                -- Products similar users liked that this user hasn't seen
                SELECT
                    ui.external_product_id,
                    COUNT(*) as frequency
                FROM recommender.user_interactions ui
                WHERE ui.external_user_id IN (SELECT external_user_id FROM similar_users)
                AND ui.external_product_id NOT IN (SELECT external_product_id FROM user_products)
                AND ui.interaction_type IN ('PURCHASE', 'CART_ADD', 'WISHLIST_ADD')
                GROUP BY ui.external_product_id
                ORDER BY frequency DESC
                LIMIT :limit
            )
            SELECT
                pe.external_product_id as product_id,
                pe.name,
                pe.category,
                pe.price_cents,
                pe.popularity_score,
                rp.frequency as collaborative_score
            FROM recommended_products rp
            JOIN recommender.product_embeddings pe ON pe.external_product_id = rp.external_product_id
            WHERE pe.is_active = true
        """)

        result = await self.session.execute(query, {"user_id": user_id, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "product_id": str(r.product_id),
                "external_product_id": r.product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "image_url": None,
                "score": float(r.collaborative_score) / 10.0,  # Normalize
                "signal": "collaborative",
            }
            for r in rows
        ]

    async def _get_co_purchased_products(
        self, product_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get products frequently bought together."""
        query = text("""
            WITH source_orders AS (
                SELECT DISTINCT oi."orderId"
                FROM public.order_items oi
                WHERE oi."productId" = :product_id
            )
            SELECT
                pe.external_product_id as product_id,
                pe.name,
                pe.category,
                pe.price_cents,
                COUNT(*) as frequency
            FROM public.order_items oi
            JOIN source_orders so ON oi."orderId" = so."orderId"
            JOIN recommender.product_embeddings pe ON pe.external_product_id = oi."productId"
            WHERE oi."productId" != :product_id
            AND pe.is_active = true
            GROUP BY pe.external_product_id, pe.name, pe.category, pe.price_cents
            ORDER BY frequency DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            query, {"product_id": product_id, "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "product_id": str(r.product_id),
                "external_product_id": r.product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "image_url": None,
                "score": float(r.frequency),
                "signal": "co_purchase",
            }
            for r in rows
        ]

    # =========================================================================
    # Stage 2: Hybrid Scoring
    # =========================================================================

    async def _apply_hybrid_scoring(
        self,
        candidates: list[dict[str, Any]],
        user_id: str | None = None,
        context_product: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply hybrid scoring: α×content + β×collaborative + γ×popularity."""
        if not candidates:
            return []

        # Normalize scores by signal type
        content_candidates = [c for c in candidates if c.get("signal") != "collaborative"]
        collab_candidates = [c for c in candidates if c.get("signal") == "collaborative"]

        # Normalize content scores (cosine similarity typically 0-1)
        if content_candidates:
            max_content = max(c.get("score", 0) for c in content_candidates) or 1.0
            for c in content_candidates:
                c["content_score"] = c.get("score", 0) / max_content

        # Normalize collaborative scores
        if collab_candidates:
            max_collab = max(c.get("score", 0) for c in collab_candidates) or 1.0
            for c in collab_candidates:
                c["collaborative_score"] = c.get("score", 0) / max_collab

        # Get popularity scores (already normalized 0-1 in DB)
        for c in candidates:
            if "popularity_score" not in c:
                # Fetch from DB if needed
                c["popularity_score"] = 0.5  # Default

        # Calculate hybrid score
        for c in candidates:
            content_score = c.get("content_score", c.get("score", 0))
            collab_score = c.get("collaborative_score", 0)
            pop_score = c.get("popularity_score", 0.5)

            hybrid_score = (
                self.CONTENT_WEIGHT * content_score
                + self.COLLABORATIVE_WEIGHT * collab_score
                + self.POPULARITY_WEIGHT * pop_score
            )

            c["hybrid_score"] = hybrid_score
            c["score"] = hybrid_score  # Update main score

        # Sort by hybrid score
        candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

        return candidates

    # =========================================================================
    # Stage 4: Business Rules
    # =========================================================================

    def _apply_diversity(
        self, candidates: list[dict[str, Any]], limit_per_category: int
    ) -> list[dict[str, Any]]:
        """Apply diversity by limiting items per category."""
        category_counts: dict[str, int] = defaultdict(int)
        diverse_candidates = []

        for candidate in candidates:
            category = candidate.get("category", "Unknown")
            if category_counts[category] < limit_per_category:
                diverse_candidates.append(candidate)
                category_counts[category] += 1

        return diverse_candidates

    def _apply_business_rules(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply business rules (boost new, penalize out-of-stock, etc)."""
        # Filter out of stock
        candidates = [c for c in candidates if c.get("stock", 1) > 0]

        # Could add more rules:
        # - Boost products with high margin
        # - Boost products on sale
        # - Penalize recently returned items
        # - Boost new arrivals

        return candidates

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_user_embedding(self, user_id: str) -> list[float] | None:
        """Get user preference embedding."""
        query = text("""
            SELECT embedding
            FROM recommender.user_preference_embeddings
            WHERE external_user_id = :user_id
        """)
        result = await self.session.execute(query, {"user_id": user_id})
        row = result.fetchone()

        if row and row.embedding:
            if isinstance(row.embedding, str):
                return json.loads(row.embedding)
            return row.embedding
        return None

    async def _get_user_preference_data(self, user_id: str) -> dict[str, Any]:
        """Get user preference data (categories, price range, etc)."""
        query = text("""
            SELECT top_categories, avg_price_min, avg_price_max
            FROM recommender.user_preference_embeddings
            WHERE external_user_id = :user_id
        """)
        result = await self.session.execute(query, {"user_id": user_id})
        row = result.fetchone()

        if row:
            top_categories = row.top_categories
            if isinstance(top_categories, str):
                top_categories = json.loads(top_categories)

            return {
                "top_categories": top_categories or [],
                "avg_price_min": row.avg_price_min,
                "avg_price_max": row.avg_price_max,
            }
        return {"top_categories": [], "avg_price_min": None, "avg_price_max": None}

    async def _get_product_by_external_id(self, external_id: str) -> dict[str, Any] | None:
        """Get product by external ID."""
        query = text("""
            SELECT
                id, external_product_id, name, category, price_cents, stock,
                is_active, embedding, popularity_score
            FROM recommender.product_embeddings
            WHERE external_product_id = :external_id
        """)
        result = await self.session.execute(query, {"external_id": external_id})
        row = result.fetchone()

        if row:
            embedding = row.embedding
            if isinstance(embedding, str):
                embedding = json.loads(embedding)

            return {
                "id": row.id,
                "product_id": str(row.external_product_id),
                "external_product_id": row.external_product_id,
                "name": row.name,
                "category": row.category or "Unknown",
                "price": row.price_cents / 100,
                "stock": row.stock,
                "is_active": row.is_active,
                "embedding": embedding,
                "popularity_score": row.popularity_score,
            }
        return None

    async def _search_similar_products(
        self, query_embedding: list[float], limit: int = 12, exclude_ids: list[str] = None
    ) -> list[dict[str, Any]]:
        """Search for products similar to query embedding."""
        exclude_ids = exclude_ids or []

        query = text("""
            SELECT
                external_product_id, name, category, price_cents,
                is_active, embedding, popularity_score, stock
            FROM recommender.product_embeddings
            WHERE is_active = true
            AND embedding IS NOT NULL
            AND external_product_id != ALL(:exclude_ids)
        """)
        result = await self.session.execute(query, {"exclude_ids": exclude_ids})
        rows = result.fetchall()

        scored_products = []
        for row in rows:
            embedding = row.embedding
            if isinstance(embedding, str):
                embedding = json.loads(embedding)

            if embedding:
                similarity = self._cosine_similarity(query_embedding, embedding)
                scored_products.append(
                    {
                        "product_id": str(row.external_product_id),
                        "external_product_id": row.external_product_id,
                        "name": row.name,
                        "category": row.category or "Unknown",
                        "price": row.price_cents / 100,
                        "stock": row.stock,
                        "image_url": None,
                        "score": similarity,
                        "popularity_score": row.popularity_score,
                        "signal": "content",
                    }
                )

        scored_products.sort(key=lambda x: x["score"], reverse=True)
        return scored_products[:limit]

    async def _get_popular_products(self, limit: int = 12) -> list[dict[str, Any]]:
        """Get popular products as fallback."""
        query = text("""
            SELECT
                external_product_id, name, category, price_cents,
                is_active, popularity_score, stock
            FROM recommender.product_embeddings
            WHERE is_active = true AND stock > 0
            ORDER BY popularity_score DESC, id
            LIMIT :limit
        """)
        result = await self.session.execute(query, {"limit": limit})
        rows = result.fetchall()

        return [
            {
                "product_id": str(r.external_product_id),
                "external_product_id": r.external_product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "stock": r.stock,
                "image_url": None,
                "score": r.popularity_score,
                "signal": "popularity",
            }
            for r in rows
        ]

    async def _get_products_by_category(
        self, category: str | None, limit: int = 8, exclude_ids: list[str] = None
    ) -> list[dict[str, Any]]:
        """Get products in a category."""
        exclude_ids = exclude_ids or []

        if not category:
            return await self._get_popular_products(limit)

        query = text("""
            SELECT
                external_product_id, name, category, price_cents,
                is_active, popularity_score, stock
            FROM recommender.product_embeddings
            WHERE is_active = true
            AND category = :category
            AND external_product_id != ALL(:exclude_ids)
            AND stock > 0
            ORDER BY popularity_score DESC
            LIMIT :limit
        """)
        result = await self.session.execute(
            query, {"category": category, "exclude_ids": exclude_ids, "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "product_id": str(r.external_product_id),
                "external_product_id": r.external_product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "stock": r.stock,
                "image_url": None,
                "score": r.popularity_score,
                "signal": "category",
            }
            for r in rows
        ]

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _aggregate_embeddings(self, embeddings: list[list[float]]) -> list[float]:
        """Aggregate embeddings by averaging."""
        if not embeddings:
            return []

        dim = len(embeddings[0])
        aggregated = [0.0] * dim

        for emb in embeddings:
            for i, val in enumerate(emb):
                aggregated[i] += val

        n = len(embeddings)
        return [v / n for v in aggregated]

    def _empty_response(
        self, request_id: str, context: str, user_id: str | None
    ) -> dict[str, Any]:
        """Return empty response."""
        return {
            "recommendations": [],
            "request_id": request_id,
            "context": context,
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
