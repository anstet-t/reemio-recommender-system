"""Unit tests for timing middleware and endpoint stats."""

import pytest

from recommendation_service.middleware.timing import EndpointStats, reset_endpoint_stats


class TestEndpointStats:
    """Tests for latency statistics calculation."""

    def test_empty_stats(self) -> None:
        stats = EndpointStats()
        d = stats.to_dict()
        assert d["count"] == 0
        assert d["avg_ms"] == 0.0
        assert d["p50_ms"] == 0.0
        assert d["p95_ms"] == 0.0

    def test_single_sample(self) -> None:
        stats = EndpointStats(latencies=[0.1])
        d = stats.to_dict()
        assert d["count"] == 1
        assert d["avg_ms"] == 100.0
        assert d["p50_ms"] == 100.0
        assert d["p95_ms"] == 100.0

    def test_multiple_samples(self) -> None:
        stats = EndpointStats(latencies=[0.1, 0.2, 0.3, 0.4, 0.5])
        d = stats.to_dict()
        assert d["count"] == 5
        assert d["avg_ms"] == pytest.approx(300.0)
        assert d["p50_ms"] == 300.0  # median of [100, 200, 300, 400, 500]
        assert d["p95_ms"] == 500.0

    def test_p95_with_outlier(self) -> None:
        """P95 should capture the tail latency."""
        latencies = [0.01] * 95 + [1.0] * 5  # 95% fast, 5% slow
        stats = EndpointStats(latencies=latencies)
        d = stats.to_dict()
        assert d["p95_ms"] == 1000.0  # the slow ones

    def test_reset_clears_stats(self) -> None:
        reset_endpoint_stats()  # ensure clean state
