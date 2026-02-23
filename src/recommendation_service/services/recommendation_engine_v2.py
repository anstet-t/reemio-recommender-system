"""Hybrid recommendation engine with 4-stage pipeline."""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
import orjson
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.infrastructure.redis import CacheService
from recommendation_service.services.embedding import EmbeddingService
from recommendation_service.services.reranker import RerankerService

logger = structlog.get_logger()


class HybridRecommendationEngine:
    """Hybrid recommendation engine with content + collaborative filtering."""

    CONTENT_WEIGHT = 0.5
    COLLABORATIVE_WEIGHT = 0.3
    POPULARITY_WEIGHT = 0.2

    def __init__(
        self,
        session: AsyncSession,
        cache: CacheService | None = None,
        enable_reranking: bool = True,
    ):
        self.session = session
        self.cache = cache
        self.embedding_service = EmbeddingService(session)
        self.reranker = RerankerService() if enable_reranking else None

    async def get_homepage_recommendations(
        self,
        user_id: str | None = None,
        limit: int = 12,
        diversity_limit_per_category: int = 3,
    ) -> dict[str, Any]:
        """Get homepage recommendations - personalized if user data exists, otherwise popular."""
        request_id = str(uuid4())

        candidates = []
        has_user_data = False

        if user_id:
            user_embedding = await self._get_user_embedding(user_id)
            if user_embedding:
                has_user_data = True
                # Run content + collaborative search in parallel
                content_task = self._search_similar_products(
                    user_embedding, limit=limit * 3, exclude_ids=[]
                )
                collab_task = self._get_collaborative_candidates(user_id, limit=limit * 2)
                content_candidates, collab_candidates = await asyncio.gather(
                    content_task, collab_task
                )
                candidates.extend(content_candidates)
                if collab_candidates:
                    candidates.extend(collab_candidates)
            else:
                collab_candidates = await self._get_collaborative_candidates(
                    user_id, limit=limit * 2
                )
                if collab_candidates:
                    has_user_data = True
                    candidates.extend(collab_candidates)

        if not candidates:
            candidates = await self._get_popular_products(limit=limit * 2)

        candidates = self._deduplicate_candidates(candidates)

        if has_user_data:
            candidates = self._apply_hybrid_scoring(candidates)
            if self.reranker:
                user_prefs = await self._get_user_preference_data(user_id)
                if user_prefs.get("top_categories"):
                    query = self.reranker.create_query_from_user_context(
                        user_categories=user_prefs.get("top_categories"),
                        context="homepage recommendations",
                    )
                    candidates = self._rerank_and_normalize(query, candidates, top_k=limit * 2)
        else:
            candidates = self._normalize_popularity_scores(candidates)

        candidates = self._apply_diversity(candidates, diversity_limit_per_category)
        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        for i, p in enumerate(candidates):
            p["position"] = i + 1
            p["score"] = max(0.0, min(1.0, p.get("score", 0.5)))

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

        source_product = await self._get_product_by_external_id(product_id)
        if not source_product:
            return self._empty_response(request_id, "product_page", user_id)

        candidates = []
        source_embedding = source_product.get("embedding")

        # Run similarity search and co-purchase query in parallel
        if source_embedding:
            similar_task = self._search_similar_products(
                source_embedding, limit=limit * 4, exclude_ids=[product_id]
            )
        else:
            similar_task = self._get_products_by_category(
                source_product.get("category"), limit=limit * 2, exclude_ids=[product_id]
            )

        co_purchase_task = self._get_co_purchased_products(product_id, limit=limit)
        candidates, co_purchased = await asyncio.gather(similar_task, co_purchase_task)
        candidates = list(candidates)
        candidates.extend(co_purchased)

        candidates = self._deduplicate_candidates(candidates, exclude_ids=[product_id])
        candidates = self._apply_hybrid_scoring(candidates)

        if self.reranker and source_product.get("name"):
            query = f"{source_product['name']} {source_product.get('category', '')}"
            candidates = self._rerank_and_normalize(query, candidates, top_k=limit * 2)

        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        for i, p in enumerate(candidates):
            p["position"] = i + 1
            p["score"] = max(0.0, min(1.0, p.get("score", 0.5)))

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

        cart_embeddings = []
        cart_categories = set()
        for pid in cart_product_ids:
            product = await self._get_product_by_external_id(pid)
            if product:
                if product.get("embedding"):
                    cart_embeddings.append(product["embedding"])
                if product.get("category"):
                    cart_categories.add(product["category"])

        candidates = []
        if cart_embeddings:
            aggregated = self._aggregate_embeddings(cart_embeddings)
            candidates = await self._search_similar_products(
                aggregated, limit=limit * 4, exclude_ids=cart_product_ids
            )

        for cart_pid in cart_product_ids[:3]:
            collab_products = await self._get_co_purchased_products(cart_pid, limit=limit)
            candidates.extend(collab_products)

        candidates = self._deduplicate_candidates(candidates, exclude_ids=cart_product_ids)
        candidates = self._apply_hybrid_scoring(candidates)

        if self.reranker and cart_categories:
            query = f"Products complementary to {', '.join(list(cart_categories)[:3])}"
            candidates = self._rerank_and_normalize(query, candidates, top_k=limit * 2)

        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        for i, p in enumerate(candidates):
            p["position"] = i + 1
            p["score"] = max(0.0, min(1.0, p.get("score", 0.5)))

        return {
            "recommendations": candidates,
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
        """Get products frequently bought together with the given product."""
        request_id = str(uuid4())

        candidates = await self._get_co_purchased_products(product_id, limit=limit * 2)

        if len(candidates) < limit:
            source_product = await self._get_product_by_external_id(product_id)
            if source_product and source_product.get("embedding"):
                similar = await self._search_similar_products(
                    source_product["embedding"],
                    limit=limit - len(candidates),
                    exclude_ids=[product_id] + [c["product_id"] for c in candidates],
                )
                candidates.extend(similar)

        candidates = self._deduplicate_candidates(candidates, exclude_ids=[product_id])

        max_score = max((c.get("score", 1) for c in candidates), default=1) or 1
        for c in candidates:
            c["score"] = max(0.0, min(1.0, c.get("score", 0.5) / max_score))

        candidates = candidates[:limit]
        for i, p in enumerate(candidates):
            p["position"] = i + 1

        return {
            "recommendations": candidates,
            "request_id": request_id,
            "context": "frequently_bought_together",
            "user_id": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _deduplicate_candidates(
        self, candidates: list[dict[str, Any]], exclude_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Remove duplicate products from candidates."""
        exclude_ids = exclude_ids or []
        seen = set()
        unique = []
        for c in candidates:
            pid = c.get("product_id")
            if pid and pid not in seen and pid not in exclude_ids:
                seen.add(pid)
                unique.append(c)
        return unique

    def _apply_hybrid_scoring(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply hybrid scoring and normalize to 0-1 range."""
        if not candidates:
            return []

        content_candidates = [c for c in candidates if c.get("signal") in ("content", "category")]
        collab_candidates = [c for c in candidates if c.get("signal") in ("collaborative", "co_purchase")]
        pop_candidates = [c for c in candidates if c.get("signal") == "popularity"]

        if content_candidates:
            max_score = max(abs(c.get("score", 0)) for c in content_candidates) or 1.0
            for c in content_candidates:
                c["content_score"] = max(0.0, c.get("score", 0)) / max_score

        if collab_candidates:
            max_score = max(c.get("score", 0) for c in collab_candidates) or 1.0
            for c in collab_candidates:
                c["collaborative_score"] = c.get("score", 0) / max_score

        if pop_candidates:
            max_score = max(c.get("score", 0) for c in pop_candidates) or 1.0
            for c in pop_candidates:
                c["popularity_score"] = c.get("score", 0) / max_score

        for c in candidates:
            content = c.get("content_score", 0)
            collab = c.get("collaborative_score", 0)
            pop = c.get("popularity_score", c.get("score", 0.5))

            if c.get("signal") == "popularity":
                c["score"] = pop
            else:
                hybrid = (
                    self.CONTENT_WEIGHT * content
                    + self.COLLABORATIVE_WEIGHT * collab
                    + self.POPULARITY_WEIGHT * pop
                )
                c["score"] = max(0.0, min(1.0, hybrid))

        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return candidates

    def _normalize_popularity_scores(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize popularity scores to 0-1 range."""
        if not candidates:
            return []

        max_score = max(c.get("score", 0) for c in candidates) or 1.0
        min_score = min(c.get("score", 0) for c in candidates)
        score_range = max_score - min_score or 1.0

        for c in candidates:
            raw = c.get("score", 0)
            c["score"] = (raw - min_score) / score_range

        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return candidates

    def _rerank_and_normalize(
        self, query: str, candidates: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        """Rerank candidates and normalize scores to 0-1."""
        if not self.reranker or not candidates:
            return candidates

        reranked = self.reranker.rerank(query, candidates, top_k=top_k)

        if reranked:
            scores = [c.get("score", 0) for c in reranked]
            min_score = min(scores)
            max_score = max(scores)
            score_range = max_score - min_score if max_score != min_score else 1.0

            for c in reranked:
                raw = c.get("score", 0)
                c["score"] = (raw - min_score) / score_range

        return reranked

    def _apply_diversity(
        self, candidates: list[dict[str, Any]], limit_per_category: int
    ) -> list[dict[str, Any]]:
        """Apply diversity by limiting items per category."""
        category_counts: dict[str, int] = defaultdict(int)
        diverse = []

        for candidate in candidates:
            category = candidate.get("category", "Unknown")
            if category_counts[category] < limit_per_category:
                diverse.append(candidate)
                category_counts[category] += 1

        return diverse

    def _apply_business_rules(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply business rules."""
        return [c for c in candidates if c.get("stock", 1) > 0]

    async def _get_user_embedding(self, user_id: str) -> list[float] | None:
        """Get user preference embedding (cached for 1 hour)."""
        cache_key = f"user_emb:{user_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        query = text("""
            SELECT embedding
            FROM recommender.user_preference_embeddings
            WHERE external_user_id = :user_id
        """)
        result = await self.session.execute(query, {"user_id": user_id})
        row = result.fetchone()

        if row and row.embedding:
            embedding = orjson.loads(row.embedding) if isinstance(row.embedding, str) else row.embedding
            if self.cache:
                await self.cache.set(cache_key, embedding, ttl_seconds=3600)
            return embedding
        return None

    async def _get_user_preference_data(self, user_id: str) -> dict[str, Any]:
        """Get user preference data (cached for 1 hour)."""
        cache_key = f"user_prefs:{user_id}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        query = text("""
            SELECT top_categories, avg_price_min, avg_price_max
            FROM recommender.user_preference_embeddings
            WHERE external_user_id = :user_id
        """)
        result = await self.session.execute(query, {"user_id": user_id})
        row = result.fetchone()

        empty = {"top_categories": [], "avg_price_min": None, "avg_price_max": None}
        if row:
            top_categories = row.top_categories
            if isinstance(top_categories, str):
                top_categories = orjson.loads(top_categories)
            data = {
                "top_categories": top_categories or [],
                "avg_price_min": row.avg_price_min,
                "avg_price_max": row.avg_price_max,
            }
            if self.cache:
                await self.cache.set(cache_key, data, ttl_seconds=3600)
            return data
        return empty

    async def _get_collaborative_candidates(
        self, user_id: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        """Get recommendations based on similar users."""
        query = text("""
            WITH user_products AS (
                SELECT DISTINCT external_product_id
                FROM recommender.user_interactions
                WHERE external_user_id = :user_id
            ),
            similar_users AS (
                SELECT ui.external_user_id, COUNT(DISTINCT ui.external_product_id) as overlap
                FROM recommender.user_interactions ui
                WHERE ui.external_product_id IN (SELECT external_product_id FROM user_products)
                AND ui.external_user_id != :user_id
                GROUP BY ui.external_user_id
                HAVING COUNT(DISTINCT ui.external_product_id) >= 2
                ORDER BY overlap DESC
                LIMIT 10
            ),
            recommended_products AS (
                SELECT ui.external_product_id, COUNT(*) as frequency
                FROM recommender.user_interactions ui
                WHERE ui.external_user_id IN (SELECT external_user_id FROM similar_users)
                AND ui.external_product_id NOT IN (SELECT external_product_id FROM user_products)
                AND lower(ui.interaction_type::text) IN ('purchase', 'cart_add', 'wishlist_add')
                GROUP BY ui.external_product_id
                ORDER BY frequency DESC
                LIMIT :limit
            )
            SELECT
                pe.external_product_id as product_id, pe.name, pe.category,
                pe.price_cents, pe.popularity_score, pe.stock, rp.frequency as score
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
                "stock": r.stock,
                "image_url": None,
                "score": float(r.score),
                "popularity_score": r.popularity_score,
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
                pe.external_product_id as product_id, pe.name, pe.category,
                pe.price_cents, pe.stock, COUNT(*) as frequency
            FROM public.order_items oi
            JOIN source_orders so ON oi."orderId" = so."orderId"
            JOIN recommender.product_embeddings pe ON pe.external_product_id = oi."productId"
            WHERE oi."productId" != :product_id AND pe.is_active = true
            GROUP BY pe.external_product_id, pe.name, pe.category, pe.price_cents, pe.stock
            ORDER BY frequency DESC
            LIMIT :limit
        """)

        result = await self.session.execute(query, {"product_id": product_id, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "product_id": str(r.product_id),
                "external_product_id": r.product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "stock": r.stock,
                "image_url": None,
                "score": float(r.frequency),
                "signal": "co_purchase",
            }
            for r in rows
        ]

    async def _get_product_by_external_id(self, external_id: str) -> dict[str, Any] | None:
        """Get product by external ID."""
        query = text("""
            SELECT id, external_product_id, name, category, price_cents, stock,
                   is_active, embedding, popularity_score
            FROM recommender.product_embeddings
            WHERE external_product_id = :external_id
        """)
        result = await self.session.execute(query, {"external_id": external_id})
        row = result.fetchone()

        if row:
            embedding = row.embedding
            if isinstance(embedding, str):
                embedding = orjson.loads(embedding)

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
        self, query_embedding: list[float], limit: int = 12, exclude_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Search for products similar to query embedding using vectorized cosine similarity."""
        exclude_ids = exclude_ids or []
        candidate_limit = min(limit * 10, 200)

        query = text("""
            SELECT external_product_id, name, category, price_cents,
                   embedding, popularity_score, stock
            FROM recommender.product_embeddings
            WHERE is_active = true AND embedding IS NOT NULL
            AND external_product_id != ALL(:exclude_ids)
            ORDER BY popularity_score DESC NULLS LAST
            LIMIT :candidate_limit
        """)
        result = await self.session.execute(
            query, {"exclude_ids": exclude_ids, "candidate_limit": candidate_limit}
        )
        rows = result.fetchall()

        # Parse embeddings and filter valid candidates
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        candidates = []
        embeddings_list = []
        for row in rows:
            embedding = row.embedding
            if isinstance(embedding, str):
                embedding = orjson.loads(embedding)
            if isinstance(embedding, list) and embedding:
                candidates.append(row)
                embeddings_list.append(embedding)

        if not embeddings_list:
            return []

        # Batch cosine similarity: (N, 384) @ (384,) / (norms * query_norm)
        emb_matrix = np.array(embeddings_list, dtype=np.float32)
        norms = np.linalg.norm(emb_matrix, axis=1)
        valid_mask = norms > 0
        similarities = np.zeros(len(embeddings_list), dtype=np.float32)
        similarities[valid_mask] = (
            emb_matrix[valid_mask] @ query_vec / (norms[valid_mask] * query_norm)
        )

        # Build scored list from valid results
        scored = []
        for i, row in enumerate(candidates):
            if valid_mask[i]:
                scored.append({
                    "product_id": str(row.external_product_id),
                    "external_product_id": row.external_product_id,
                    "name": row.name,
                    "category": row.category or "Unknown",
                    "price": row.price_cents / 100,
                    "stock": row.stock,
                    "image_url": None,
                    "score": float(similarities[i]),
                    "popularity_score": row.popularity_score,
                    "signal": "content",
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def _get_popular_products(self, limit: int = 12) -> list[dict[str, Any]]:
        """Get popular products as fallback (cached for 5 minutes)."""
        cache_key = f"popular:{limit}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        query = text("""
            SELECT external_product_id, name, category, price_cents, popularity_score, stock
            FROM recommender.product_embeddings
            WHERE is_active = true AND stock > 0
            ORDER BY popularity_score DESC NULLS LAST, id
            LIMIT :limit
        """)
        result = await self.session.execute(query, {"limit": limit})
        rows = result.fetchall()

        products = [
            {
                "product_id": str(r.external_product_id),
                "external_product_id": r.external_product_id,
                "name": r.name,
                "category": r.category or "Unknown",
                "price": r.price_cents / 100,
                "stock": r.stock,
                "image_url": None,
                "score": r.popularity_score or 0.5,
                "signal": "popularity",
            }
            for r in rows
        ]

        if self.cache and products:
            await self.cache.set(cache_key, products, ttl_seconds=1800)

        return products

    async def _get_products_by_category(
        self, category: str | None, limit: int = 8, exclude_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get products in a category."""
        exclude_ids = exclude_ids or []

        if not category:
            return await self._get_popular_products(limit)

        query = text("""
            SELECT external_product_id, name, category, price_cents, popularity_score, stock
            FROM recommender.product_embeddings
            WHERE is_active = true AND category = :category
            AND external_product_id != ALL(:exclude_ids) AND stock > 0
            ORDER BY popularity_score DESC NULLS LAST
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
                "score": r.popularity_score or 0.5,
                "signal": "category",
            }
            for r in rows
        ]

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors using numpy."""
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _aggregate_embeddings(self, embeddings: list[list[float]]) -> list[float]:
        """Aggregate embeddings by averaging using numpy."""
        if not embeddings:
            return []
        return np.mean(np.array(embeddings, dtype=np.float32), axis=0).tolist()

    async def get_search_recommendations(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 12,
        category: str | None = None,
        diversity_limit_per_category: int = 4,
    ) -> dict[str, Any]:
        """Get recommendations based on a search query.

        4-stage pipeline:
        1. PG full-text search + trigram for candidate retrieval
        2. Blend text search score with embedding cosine similarity
        3. Optional Pinecone reranking
        4. Diversity + stock filtering business rules
        """
        from recommendation_service.services.search import SearchService

        request_id = str(uuid4())
        search_service = SearchService(self.session)

        # Get user preferences for personalization (cached, ~5ms with Redis)
        user_categories = None
        if user_id:
            user_prefs = await self._get_user_preference_data(user_id)
            user_categories = user_prefs.get("top_categories")

        # Stage 1: PG full-text + trigram candidate retrieval
        candidates = await search_service.search_products(
            query=query,
            limit=limit * 3,
            category=category,
            user_categories=user_categories,
        )

        if not candidates:
            return self._empty_response(request_id, "search", user_id)

        # Stage 2: Blend with embedding cosine similarity
        query_embedding = self.embedding_service.generate_embedding(query)
        candidates = search_service.blend_with_embeddings(candidates, query_embedding)

        # Stage 3: Optional Pinecone reranking
        if self.reranker and len(candidates) > 1:
            candidates = self._rerank_and_normalize(query, candidates, top_k=limit * 2)

        # Stage 4: Business rules
        candidates = self._apply_diversity(candidates, diversity_limit_per_category)
        candidates = self._apply_business_rules(candidates)
        candidates = candidates[:limit]

        for i, p in enumerate(candidates):
            p["position"] = i + 1
            p["score"] = max(0.0, min(1.0, p.get("score", 0.5)))
            # Clean up internal scoring fields
            p.pop("text_score", None)
            p.pop("_embedding_raw", None)

        return {
            "recommendations": candidates,
            "request_id": request_id,
            "context": "search",
            "user_id": user_id,
            "search_query": query,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

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
