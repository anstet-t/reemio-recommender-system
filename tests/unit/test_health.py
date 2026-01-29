"""Unit tests for health endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test basic health check returns healthy status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data


def test_liveness_check(client: TestClient) -> None:
    """Test liveness check returns alive status."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "alive"


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check returns expected structure."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert "ready" in data
    assert "checks" in data
    assert isinstance(data["checks"], dict)
