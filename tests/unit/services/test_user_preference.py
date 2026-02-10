"""Unit tests for user preference service numpy optimizations."""

import math

import numpy as np
import pytest

from recommendation_service.services.user_preference import UserPreferenceService


@pytest.fixture
def service() -> UserPreferenceService:
    """Create service instance without DB session (for pure function tests)."""
    svc = object.__new__(UserPreferenceService)
    svc.RECENCY_DECAY_DAYS = 30.0
    return svc


class TestRecencyWeight:
    """Tests for recency decay calculation."""

    def test_day_zero_full_weight(self, service: UserPreferenceService) -> None:
        assert service._calculate_recency_weight(0) == pytest.approx(1.0)

    def test_day_30_decayed(self, service: UserPreferenceService) -> None:
        expected = math.exp(-1.0)  # e^(-30/30)
        assert service._calculate_recency_weight(30) == pytest.approx(expected)

    def test_day_60_further_decayed(self, service: UserPreferenceService) -> None:
        expected = math.exp(-2.0)
        assert service._calculate_recency_weight(60) == pytest.approx(expected)

    def test_monotonically_decreasing(self, service: UserPreferenceService) -> None:
        weights = [service._calculate_recency_weight(d) for d in range(0, 91, 10)]
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i + 1]


class TestWeightedEmbeddingAggregation:
    """Tests for numpy-vectorized weighted embedding aggregation."""

    def test_single_embedding(self, service: UserPreferenceService) -> None:
        result = service._aggregate_weighted_embeddings([([1.0, 0.0, 0.0], 1.0)])
        # Should be normalized unit vector
        assert result == pytest.approx([1.0, 0.0, 0.0])

    def test_weight_dominance(self, service: UserPreferenceService) -> None:
        """Higher-weighted embedding should dominate the result."""
        result = service._aggregate_weighted_embeddings([
            ([1.0, 0.0, 0.0], 10.0),  # heavy weight
            ([0.0, 1.0, 0.0], 1.0),   # light weight
        ])
        # First component should be much larger than second
        assert result[0] > result[1]

    def test_empty_list(self, service: UserPreferenceService) -> None:
        assert service._aggregate_weighted_embeddings([]) == []

    def test_result_is_normalized(self, service: UserPreferenceService) -> None:
        """Output vector should have unit norm."""
        result = service._aggregate_weighted_embeddings([
            ([3.0, 4.0], 1.0),
            ([1.0, 1.0], 2.0),
        ])
        norm = np.linalg.norm(result)
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_equal_weights_is_mean(self, service: UserPreferenceService) -> None:
        """Equal weights should produce normalized mean."""
        emb1 = [1.0, 0.0]
        emb2 = [0.0, 1.0]
        result = service._aggregate_weighted_embeddings([(emb1, 1.0), (emb2, 1.0)])
        # Mean of [1,0] and [0,1] is [0.5, 0.5], normalized is [0.707, 0.707]
        expected = np.array([0.5, 0.5])
        expected = expected / np.linalg.norm(expected)
        assert result == pytest.approx(expected.tolist(), abs=1e-6)
