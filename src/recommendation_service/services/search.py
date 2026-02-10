"""Search service combining PostgreSQL full-text search with embedding similarity."""

import json
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class SearchService:
    """Hybrid search: PG full-text (tsvector) + trigram fuzzy matching + embedding similarity."""

    TEXT_SEARCH_WEIGHT = 0.6
    EMBEDDING_WEIGHT = 0.4

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_products(
        self,
        query: str,
        limit: int = 20,
        category: str | None = None,
        user_categories: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search products using full-text search + trigram fuzzy matching.

        Returns candidates with combined text relevance scores.
        """
        category_filter = ""
        params: dict[str, Any] = {"query": query, "limit": limit}

        if category:
            category_filter = "AND pe.category = :category"
            params["category"] = category

        search_sql = text(f"""
            SELECT
                pe.external_product_id,
                pe.name,
                pe.category,
                pe.price_cents,
                pe.stock,
                pe.popularity_score,
                pe.embedding,
                ts_rank(pe.search_vector, plainto_tsquery('english', :query)) AS ts_score,
                similarity(pe.name, :query) AS trgm_score
            FROM recommender.product_embeddings pe
            WHERE pe.is_active = true
            AND pe.stock > 0
            {category_filter}
            AND (
                pe.search_vector @@ plainto_tsquery('english', :query)
                OR similarity(pe.name, :query) > 0.1
            )
            ORDER BY
                (ts_rank(pe.search_vector, plainto_tsquery('english', :query)) * 2
                 + similarity(pe.name, :query)) DESC
            LIMIT :limit
        """)

        result = await self.session.execute(search_sql, params)
        rows = result.fetchall()

        candidates = []
        for row in rows:
            # Combined text search score (ts_rank weighted 2x + trigram)
            text_score = (row.ts_score * 2 + row.trgm_score) / 3.0

            # Boost results matching user's preferred categories
            category_boost = 1.0
            if user_categories and row.category in user_categories:
                category_boost = 1.2

            candidates.append({
                "product_id": str(row.external_product_id),
                "external_product_id": row.external_product_id,
                "name": row.name,
                "category": row.category or "Unknown",
                "price": row.price_cents / 100,
                "stock": row.stock,
                "image_url": None,
                "score": text_score * category_boost,
                "popularity_score": row.popularity_score,
                "text_score": text_score,
                "signal": "search",
                "_embedding_raw": row.embedding,
            })

        return candidates

    def blend_with_embeddings(
        self,
        candidates: list[dict[str, Any]],
        query_embedding: list[float] | None,
    ) -> list[dict[str, Any]]:
        """Blend text search scores with embedding cosine similarity (60/40 split)."""
        import numpy as np

        if not query_embedding or not candidates:
            # Strip raw embeddings before returning
            for c in candidates:
                c.pop("_embedding_raw", None)
            return candidates

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            for c in candidates:
                c.pop("_embedding_raw", None)
            return candidates

        for candidate in candidates:
            raw_emb = candidate.pop("_embedding_raw", None)
            if raw_emb:
                if isinstance(raw_emb, str):
                    raw_emb = json.loads(raw_emb)
                if isinstance(raw_emb, list) and raw_emb:
                    emb_vec = np.array(raw_emb, dtype=np.float32)
                    emb_norm = np.linalg.norm(emb_vec)
                    if emb_norm > 0:
                        cosine_sim = float(np.dot(query_vec, emb_vec) / (query_norm * emb_norm))
                        text_score = candidate.get("text_score", 0)
                        candidate["score"] = (
                            text_score * self.TEXT_SEARCH_WEIGHT
                            + max(0, cosine_sim) * self.EMBEDDING_WEIGHT
                        )
                        continue
            # No embedding available — keep text-only score

        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return candidates
