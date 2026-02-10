"""Unit tests for recommendation engine performance optimizations."""

import numpy as np
import pytest

from recommendation_service.services.recommendation_engine_v2 import (
    HybridRecommendationEngine,
)


@pytest.fixture
def engine() -> HybridRecommendationEngine:
    """Create engine instance without DB session (for pure function tests)."""
    e = object.__new__(HybridRecommendationEngine)
    e.cache = None
    return e


class TestCosineSimlarity:
    """Tests for numpy-vectorized cosine similarity."""

    def test_identical_vectors(self, engine: HybridRecommendationEngine) -> None:
        vec = [1.0, 2.0, 3.0]
        assert engine._cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self, engine: HybridRecommendationEngine) -> None:
        assert engine._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self, engine: HybridRecommendationEngine) -> None:
        assert engine._cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self, engine: HybridRecommendationEngine) -> None:
        assert engine._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert engine._cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0

    def test_high_dimensional(self, engine: HybridRecommendationEngine) -> None:
        """384-dim vectors (actual embedding size)."""
        rng = np.random.default_rng(42)
        vec1 = rng.random(384).tolist()
        vec2 = rng.random(384).tolist()
        sim = engine._cosine_similarity(vec1, vec2)
        assert -1.0 <= sim <= 1.0

    def test_matches_numpy_reference(self, engine: HybridRecommendationEngine) -> None:
        """Verify our implementation matches a known-correct numpy calculation."""
        rng = np.random.default_rng(99)
        a = rng.random(384)
        b = rng.random(384)
        expected = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        actual = engine._cosine_similarity(a.tolist(), b.tolist())
        assert actual == pytest.approx(expected, abs=1e-6)


class TestAggregateEmbeddings:
    """Tests for numpy-vectorized embedding aggregation."""

    def test_single_embedding(self, engine: HybridRecommendationEngine) -> None:
        result = engine._aggregate_embeddings([[1.0, 2.0, 3.0]])
        assert result == pytest.approx([1.0, 2.0, 3.0])

    def test_two_embeddings_averaged(self, engine: HybridRecommendationEngine) -> None:
        result = engine._aggregate_embeddings([[1.0, 0.0], [3.0, 4.0]])
        assert result == pytest.approx([2.0, 2.0])

    def test_empty_list(self, engine: HybridRecommendationEngine) -> None:
        assert engine._aggregate_embeddings([]) == []

    def test_preserves_dimension(self, engine: HybridRecommendationEngine) -> None:
        embeddings = [np.random.default_rng(i).random(384).tolist() for i in range(5)]
        result = engine._aggregate_embeddings(embeddings)
        assert len(result) == 384
