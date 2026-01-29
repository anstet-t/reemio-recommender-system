"""Embedding service for generating text embeddings.

Uses sentence-transformers to generate embeddings for products and user preferences.
"""

import json
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from recommendation_service.config import get_settings

logger = structlog.get_logger()

# Lazy-loaded model to avoid loading on import
_embedding_model = None


def get_embedding_model():
    """Get or initialize the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            model_name = settings.embedding_model
            logger.info("Loading embedding model", model=model_name)
            _embedding_model = SentenceTransformer(model_name)
            logger.info(
                "Embedding model loaded",
                model=model_name,
                dimension=_embedding_model.get_sentence_embedding_dimension(),
            )
        except ImportError:
            logger.warning(
                "sentence-transformers not installed, embeddings will be unavailable"
            )
            return None
    return _embedding_model


class EmbeddingService:
    """Service for generating and managing embeddings."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self._model = None

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            self._model = get_embedding_model()
        return self._model

    def generate_embedding(self, text: str) -> list[float] | None:
        """Generate an embedding for a single text."""
        if self.model is None:
            logger.warning("Embedding model not available")
            return None

        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error("Error generating embedding", error=str(e))
            return None

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts."""
        if self.model is None:
            logger.warning("Embedding model not available")
            return [None] * len(texts)

        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error("Error generating batch embeddings", error=str(e))
            return [None] * len(texts)

    def create_product_text(self, product: dict[str, Any]) -> str:
        """Create text representation of a product for embedding."""
        parts = []

        # Product name (most important)
        if name := product.get("name"):
            parts.append(name)

        # Category
        if category := product.get("category") or product.get("category_name"):
            parts.append(f"Category: {category}")

        # Description if available
        if description := product.get("description"):
            # Truncate long descriptions
            if len(description) > 500:
                description = description[:500] + "..."
            parts.append(description)

        # Price range indicator
        price_cents = product.get("price_cents", 0)
        if price_cents > 0:
            price = price_cents / 100
            if price < 25:
                parts.append("Budget friendly")
            elif price < 100:
                parts.append("Mid-range")
            elif price < 500:
                parts.append("Premium")
            else:
                parts.append("Luxury")

        return " | ".join(parts)

    async def generate_product_embedding(
        self, product: dict[str, Any]
    ) -> list[float] | None:
        """Generate embedding for a product."""
        text = self.create_product_text(product)
        return self.generate_embedding(text)

    async def update_product_embeddings(
        self, batch_size: int = 50, only_missing: bool = True
    ) -> dict[str, int]:
        """
        Generate embeddings for products in the database.

        Args:
            batch_size: Number of products to process per batch
            only_missing: If True, only process products without embeddings

        Returns:
            Summary of the operation
        """
        if self.session is None:
            raise ValueError("Session required for database operations")

        # Get products needing embeddings
        if only_missing:
            query = text("""
                SELECT id, external_product_id, name, category, price_cents
                FROM recommender.product_embeddings
                WHERE embedding IS NULL AND is_active = true
                ORDER BY id
                LIMIT :limit
            """)
        else:
            query = text("""
                SELECT id, external_product_id, name, category, price_cents
                FROM recommender.product_embeddings
                WHERE is_active = true
                ORDER BY id
                LIMIT :limit
            """)

        updated = 0
        errors = 0

        while True:
            result = await self.session.execute(query, {"limit": batch_size})
            products = result.fetchall()

            if not products:
                break

            # Prepare texts for batch embedding
            texts = []
            product_ids = []
            for p in products:
                product_dict = {
                    "name": p.name,
                    "category": p.category,
                    "price_cents": p.price_cents,
                }
                texts.append(self.create_product_text(product_dict))
                product_ids.append(p.id)

            # Generate embeddings
            embeddings = self.generate_embeddings_batch(texts)

            # Update database
            for pid, emb in zip(product_ids, embeddings):
                if emb is not None:
                    try:
                        # Store as JSON since we don't have pgvector
                        update_query = text("""
                            UPDATE recommender.product_embeddings
                            SET embedding = :embedding,
                                embedding_updated_at = NOW()
                            WHERE id = :id
                        """)
                        await self.session.execute(
                            update_query,
                            {"id": pid, "embedding": json.dumps(emb)},
                        )
                        updated += 1
                    except Exception as e:
                        logger.error("Error updating embedding", id=pid, error=str(e))
                        errors += 1
                else:
                    errors += 1

            await self.session.commit()
            logger.info("Batch embeddings updated", updated=updated, errors=errors)

            # If we got fewer than batch_size, we're done
            if len(products) < batch_size:
                break

        return {"updated": updated, "errors": errors}

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
