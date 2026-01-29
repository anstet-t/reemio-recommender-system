"""Unit tests for interaction endpoints."""

from fastapi.testclient import TestClient


def test_track_interaction_view(
    client: TestClient,
    sample_interaction_data: dict,
) -> None:
    """Test tracking a view interaction."""
    response = client.post("/api/v1/interactions", json=sample_interaction_data)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "interaction_id" in data
    assert "recorded_at" in data


def test_track_interaction_requires_product_id_for_view(
    client: TestClient,
    sample_user_id: str,
) -> None:
    """Test that view interaction requires product_id."""
    response = client.post(
        "/api/v1/interactions",
        json={
            "user_id": sample_user_id,
            "interaction_type": "view",
        },
    )
    assert response.status_code == 400


def test_track_interaction_search_requires_query(
    client: TestClient,
    sample_user_id: str,
) -> None:
    """Test that search interaction requires search_query."""
    response = client.post(
        "/api/v1/interactions",
        json={
            "user_id": sample_user_id,
            "interaction_type": "search",
        },
    )
    assert response.status_code == 400


def test_track_interaction_search_with_query(
    client: TestClient,
    sample_user_id: str,
) -> None:
    """Test tracking a search interaction with query."""
    response = client.post(
        "/api/v1/interactions",
        json={
            "user_id": sample_user_id,
            "interaction_type": "search",
            "search_query": "wireless headphones",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True


def test_batch_track_interactions(
    client: TestClient,
    sample_interaction_data: dict,
) -> None:
    """Test batch tracking interactions."""
    response = client.post(
        "/api/v1/interactions/batch",
        json={
            "interactions": [
                sample_interaction_data,
                {**sample_interaction_data, "interaction_type": "cart_add"},
            ],
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["recorded_count"] == 2
    assert data["failed_count"] == 0


def test_batch_track_empty_list_fails(client: TestClient) -> None:
    """Test that empty batch fails."""
    response = client.post(
        "/api/v1/interactions/batch",
        json={"interactions": []},
    )
    assert response.status_code == 400
