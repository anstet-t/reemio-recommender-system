"""Embedding generation for vector search."""

from functools import lru_cache
from typing import Any

import structlog

from recommendation_service.config import get_settings

logger = structlog.get_logger()


class EmbeddingService:
    """
    Service for generating text embeddings using sentence-transformers.

    Uses a lightweight model (all-MiniLM-L6-v2) that runs locally
    and produces 384-dimensional vectors.
    """

    def __init__(self, model_name: str | None = None):
        """
        Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       Defaults to config setting.
        """
        self.settings = get_settings()
        self.model_name = model_name or self.settings.embedding_model
        self._model: Any = None

    @property
    def model(self) -> Any:
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model", model=self.model_name)
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed, using mock embeddings"
                )
                self._model = MockEmbeddingModel(self.settings.embedding_dimension)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts (batch).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    def generate_product_content(
        self,
        name: str,
        description: str,
        category: str,
    ) -> str:
        """
        Generate content string for product embedding.

        Combines product attributes into a single text for embedding.

        Args:
            name: Product name
            description: Product description
            category: Product category

        Returns:
            Combined text for embedding
        """
        return f"{name}. {description}. Category: {category}"

    def generate_user_preference_content(
        self,
        top_categories: list[str],
        recently_viewed: list[str],
        purchased: list[str],
        avg_price_range: tuple[float, float] | None = None,
    ) -> str:
        """
        Generate content string for user preference embedding.

        Combines user behavior into a text representation.

        Args:
            top_categories: User's top interest categories
            recently_viewed: Recently viewed product names
            purchased: Purchased product names
            avg_price_range: Optional (min, max) price range

        Returns:
            Combined text for embedding
        """
        parts = []

        if top_categories:
            parts.append(f"Interested in: {', '.join(top_categories)}")

        if avg_price_range:
            parts.append(f"Price range: ${avg_price_range[0]:.0f}-${avg_price_range[1]:.0f}")

        if recently_viewed:
            parts.append(f"Recently viewed: {', '.join(recently_viewed[:5])}")

        if purchased:
            parts.append(f"Purchased: {', '.join(purchased[:5])}")

        return ". ".join(parts) if parts else "No preference data"


class MockEmbeddingModel:
    """Mock embedding model for testing without sentence-transformers."""

    def __init__(self, dimension: int):
        self.dimension = dimension

    def encode(self, text: str | list[str], convert_to_numpy: bool = True) -> Any:
        import random

        if isinstance(text, str):
            # Generate deterministic pseudo-random vector based on text hash
            random.seed(hash(text) % (2**32))
            return [random.uniform(-1, 1) for _ in range(self.dimension)]

        # Batch
        return [
            self.encode(t, convert_to_numpy=convert_to_numpy)
            for t in text
        ]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Get cached embedding service instance."""
    return EmbeddingService()
