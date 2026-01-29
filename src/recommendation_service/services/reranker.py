"""Reranking service using cross-encoder models."""

import structlog

logger = structlog.get_logger()

# Lazy-loaded reranker model
_reranker_model = None


def get_reranker_model():
    """Get or initialize the reranker model."""
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder

            model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            logger.info("Loading reranker model", model=model_name)
            _reranker_model = CrossEncoder(model_name)
            logger.info("Reranker model loaded", model=model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed, reranking will be unavailable"
            )
            return None
    return _reranker_model


class RerankerService:
    """Service for reranking recommendations using cross-encoder models."""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        """Lazy load the reranker model."""
        if self._model is None:
            self._model = get_reranker_model()
        return self._model

    def rerank(
        self, query: str, candidates: list[dict], top_k: int | None = None
    ) -> list[dict]:
        """
        Rerank candidates using cross-encoder model.

        Args:
            query: The query text (user context or product description)
            candidates: List of candidate products with 'name', 'category', etc.
            top_k: Number of top results to return (None = return all)

        Returns:
            Reranked list of candidates with updated scores
        """
        if self.model is None:
            logger.warning("Reranker model not available, returning original ranking")
            return candidates[:top_k] if top_k else candidates

        if not candidates:
            return []

        # Prepare query-document pairs
        pairs = []
        for candidate in candidates:
            # Create document text from candidate
            doc_text = self._create_document_text(candidate)
            pairs.append([query, doc_text])

        try:
            # Get reranking scores
            scores = self.model.predict(pairs)

            # Update candidate scores
            for candidate, score in zip(candidates, scores):
                candidate["rerank_score"] = float(score)
                # Keep original score for reference
                candidate["original_score"] = candidate.get("score", 0.0)
                # Update main score
                candidate["score"] = float(score)

            # Sort by rerank score
            reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

            return reranked[:top_k] if top_k else reranked

        except Exception as e:
            logger.error("Error during reranking", error=str(e))
            return candidates[:top_k] if top_k else candidates

    def _create_document_text(self, candidate: dict) -> str:
        """Create document text from candidate for reranking."""
        parts = []

        if name := candidate.get("name"):
            parts.append(name)

        if category := candidate.get("category"):
            parts.append(f"Category: {category}")

        if description := candidate.get("description"):
            # Truncate long descriptions
            if len(description) > 200:
                description = description[:200] + "..."
            parts.append(description)

        return " | ".join(parts)

    def create_query_from_user_context(
        self, user_categories: list[str] | None = None, context: str | None = None
    ) -> str:
        """Create query text from user context for reranking."""
        parts = []

        if context:
            parts.append(context)

        if user_categories:
            parts.append(f"Interested in: {', '.join(user_categories[:3])}")

        return " ".join(parts) if parts else "Product recommendations"
