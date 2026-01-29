"""Recommendation engine service.

Provides personalized product recommendations using embedding similarity search.
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

logger = structlog.get_logger()


class RecommendationEngine:
    """Engine for generating product recommendations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.embedding_service = EmbeddingService(session)

    async def get_homepage_recommendations(
        self,
        user_id: str,
        limit: int = 12,
        diversity_limit_per_category: int = 3,
    ) -> dict[str, Any]:
        """
        Get personalized homepage recommendations for a user.

        Args:
            user_id: The user's ID
            limit: Maximum number of recommendations
            diversity_limit_per_category: Max items per category for diversity

        Returns:
            Recommendation response with products and metadata
        """
        request_id = str(uuid4())

        # Try to get user preference embedding
        user_embedding = await self._get_user_embedding(user_id)

        if user_embedding:
            # Personalized recommendations based on user embedding
            products = await self._search_similar_products(
                user_embedding, limit=limit * 2, exclude_ids=[]
            )
        else:
            # Fall back to popular products for new/cold-start users
            products = await self._get_popular_products(limit=limit * 2)

        # Apply diversity: limit items per category
        products = self._apply_diversity(products, diversity_limit_per_category)

        # Take top N
        products = products[:limit]

        # Add position
        for i, p in enumerate(products):
            p["position"] = i + 1

        return {
            "recommendations": products,
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
        """
        Get products similar to a given product.

        Args:
            product_id: The source product ID
            user_id: Optional user ID for personalization
            limit: Maximum number of recommendations

        Returns:
            Recommendation response with similar products
        """
        request_id = str(uuid4())

        # Get source product embedding
        source_product = await self._get_product_by_external_id(product_id)
        if not source_product:
            logger.warning("Product not found", product_id=product_id)
            return {
                "recommendations": [],
                "request_id": request_id,
                "context": "product_page",
                "user_id": user_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        source_embedding = source_product.get("embedding")
        if not source_embedding:
            # Fall back to products in same category
            products = await self._get_products_by_category(
                source_product.get("category"), limit=limit, exclude_ids=[product_id]
            )
        else:
            # Similarity search
            products = await self._search_similar_products(
                source_embedding, limit=limit + 1, exclude_ids=[product_id]
            )

        # If user_id provided, optionally blend with user preferences
        if user_id:
            user_embedding = await self._get_user_embedding(user_id)
            if user_embedding:
                # Re-rank based on user preferences
                products = self._rerank_with_user_preferences(
                    products, user_embedding, weight=0.3
                )

        products = products[:limit]

        for i, p in enumerate(products):
            p["position"] = i + 1

        return {
            "recommendations": products,
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
        """
        Get recommendations based on cart contents.

        Args:
            user_id: The user's ID
            cart_product_ids: Product IDs currently in cart
            limit: Maximum number of recommendations

        Returns:
            Recommendation response with complementary products
        """
        request_id = str(uuid4())

        # Get cart product embeddings
        cart_embeddings = []
        for pid in cart_product_ids:
            product = await self._get_product_by_external_id(pid)
            if product and product.get("embedding"):
                cart_embeddings.append(product["embedding"])

        if not cart_embeddings:
            # Fall back to popular products
            products = await self._get_popular_products(limit=limit)
        else:
            # Aggregate cart embeddings (average)
            aggregated = self._aggregate_embeddings(cart_embeddings)

            # Search for similar/complementary products
            products = await self._search_similar_products(
                aggregated, limit=limit + len(cart_product_ids), exclude_ids=cart_product_ids
            )

        products = products[:limit]

        for i, p in enumerate(products):
            p["position"] = i + 1

        return {
            "recommendations": products,
            "request_id": request_id,
            "context": "cart",
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_frequently_bought_together(
        self,
        product_id: str,
        limit: int = 4,
    ) -> dict[str, Any]:
        """
        Get products frequently bought together with the given product.

        Args:
            product_id: The source product ID
            limit: Maximum number of recommendations

        Returns:
            Recommendation response with co-purchased products
        """
        request_id = str(uuid4())

        # Query co-purchase data from order history
        query = text("""
            WITH source_orders AS (
                -- Orders containing the source product
                SELECT DISTINCT oi."orderId"
                FROM public.order_items oi
                WHERE oi."productId" = :product_id
            ),
            copurchased AS (
                -- Products in the same orders
                SELECT
                    oi."productId" as co_product_id,
                    COUNT(*) as frequency
                FROM public.order_items oi
                JOIN source_orders so ON oi."orderId" = so."orderId"
                WHERE oi."productId" != :product_id
                GROUP BY oi."productId"
                ORDER BY frequency DESC
                LIMIT :limit
            )
            SELECT
                pe.external_product_id as product_id,
                pe.name,
                pe.category,
                pe.price_cents,
                pe.is_active,
                cp.frequency,
                pe.embedding
            FROM copurchased cp
            JOIN recommender.product_embeddings pe ON pe.external_product_id = cp.co_product_id
            WHERE pe.is_active = true
            ORDER BY cp.frequency DESC
        """)

        result = await self.session.execute(
            query, {"product_id": product_id, "limit": limit * 2}
        )
        rows = result.fetchall()

        if len(rows) >= limit:
            # Have enough co-purchase data
            products = [
                {
                    "product_id": str(r.product_id),
                    "external_product_id": r.product_id,
                    "name": r.name,
                    "category": r.category or "Unknown",
                    "price": r.price_cents / 100,
                    "image_url": None,
                    "score": float(r.frequency),
                }
                for r in rows[:limit]
            ]
        else:
            # Fall back to similar products
            similar = await self.get_similar_products(product_id, limit=limit)
            products = similar["recommendations"]

        for i, p in enumerate(products):
            p["position"] = i + 1

        return {
            "recommendations": products,
            "request_id": request_id,
            "context": "frequently_bought_together",
            "user_id": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    async def _get_user_embedding(self, user_id: str) -> list[float] | None:
        """Get user preference embedding from database."""
        query = text("""
            SELECT embedding
            FROM recommender.user_preference_embeddings
            WHERE external_user_id = :user_id
        """)
        result = await self.session.execute(query, {"user_id": user_id})
        row = result.fetchone()

        if row and row.embedding:
            # Parse JSON embedding
            if isinstance(row.embedding, str):
                return json.loads(row.embedding)
            return row.embedding
        return None

    async def _get_product_by_external_id(
        self, external_id: str
    ) -> dict[str, Any] | None:
        """Get a product by its external ID."""
        query = text("""
            SELECT
                id,
                external_product_id,
                name,
                category,
                price_cents,
                stock,
                is_active,
                embedding,
                popularity_score
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

    async def _get_popular_products(self, limit: int = 12) -> list[dict[str, Any]]:
        """Get popular products as fallback for cold-start."""
        query = text("""
            SELECT
                external_product_id,
                name,
                category,
                price_cents,
                is_active,
                popularity_score
            FROM recommender.product_embeddings
            WHERE is_active = true
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
                "image_url": None,
                "score": r.popularity_score,
            }
            for r in rows
        ]

    async def _get_products_by_category(
        self, category: str | None, limit: int = 8, exclude_ids: list[str] = None
    ) -> list[dict[str, Any]]:
        """Get products in a specific category."""
        exclude_ids = exclude_ids or []

        if category:
            query = text("""
                SELECT
                    external_product_id,
                    name,
                    category,
                    price_cents,
                    is_active,
                    popularity_score
                FROM recommender.product_embeddings
                WHERE is_active = true
                AND category = :category
                AND external_product_id != ALL(:exclude_ids)
                ORDER BY popularity_score DESC
                LIMIT :limit
            """)
            result = await self.session.execute(
                query,
                {"category": category, "exclude_ids": exclude_ids, "limit": limit},
            )
        else:
            # No category, get popular products
            return await self._get_popular_products(limit)

        rows = result.fetchall()

        return [
            {
                "product_id": str(r.external_product_id),
                "external_product_id": r.external_product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "image_url": None,
                "score": r.popularity_score,
            }
            for r in rows
        ]

    async def _search_similar_products(
        self,
        query_embedding: list[float],
        limit: int = 12,
        exclude_ids: list[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Search for products similar to a query embedding.

        Since we don't have pgvector, this loads embeddings and computes
        similarity in Python. For large catalogs, consider using a vector
        database or pgvector.
        """
        exclude_ids = exclude_ids or []

        # Fetch all active products with embeddings
        query = text("""
            SELECT
                external_product_id,
                name,
                category,
                price_cents,
                is_active,
                embedding,
                popularity_score
            FROM recommender.product_embeddings
            WHERE is_active = true
            AND embedding IS NOT NULL
            AND external_product_id != ALL(:exclude_ids)
        """)
        result = await self.session.execute(query, {"exclude_ids": exclude_ids})
        rows = result.fetchall()

        # Calculate similarity scores
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
                        "image_url": None,
                        "score": similarity,
                    }
                )

        # Sort by similarity score
        scored_products.sort(key=lambda x: x["score"], reverse=True)

        return scored_products[:limit]

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _aggregate_embeddings(self, embeddings: list[list[float]]) -> list[float]:
        """Aggregate multiple embeddings by averaging."""
        if not embeddings:
            return []

        dim = len(embeddings[0])
        aggregated = [0.0] * dim

        for emb in embeddings:
            for i, val in enumerate(emb):
                aggregated[i] += val

        n = len(embeddings)
        return [v / n for v in aggregated]

    def _apply_diversity(
        self, products: list[dict[str, Any]], limit_per_category: int
    ) -> list[dict[str, Any]]:
        """Apply diversity by limiting items per category."""
        category_counts: dict[str, int] = defaultdict(int)
        diverse_products = []

        for product in products:
            category = product.get("category", "Unknown")
            if category_counts[category] < limit_per_category:
                diverse_products.append(product)
                category_counts[category] += 1

        return diverse_products

    def _rerank_with_user_preferences(
        self,
        products: list[dict[str, Any]],
        user_embedding: list[float],
        weight: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Re-rank products based on user preference similarity."""
        # Would need product embeddings to implement this properly
        # For now, return products as-is
        return products
