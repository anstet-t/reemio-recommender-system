"""Unit tests for search service hybrid scoring."""

import numpy as np
import pytest

from recommendation_service.services.search import SearchService


@pytest.fixture
def service() -> SearchService:
    """Create search service without DB session (for pure function tests)."""
    svc = object.__new__(SearchService)
    svc.TEXT_SEARCH_WEIGHT = 0.6
    svc.EMBEDDING_WEIGHT = 0.4
    return svc


def _make_candidate(
    name: str = "Test Product",
    text_score: float = 0.5,
    embedding: list[float] | None = None,
) -> dict:
    """Helper to create a candidate dict."""
    return {
        "product_id": "p1",
        "external_product_id": "p1",
        "name": name,
        "category": "Test",
        "price": 100.0,
        "stock": 10,
        "image_url": None,
        "score": text_score,
        "popularity_score": 0.5,
        "text_score": text_score,
        "signal": "search",
        "_embedding_raw": embedding,
    }


class TestBlendWithEmbeddings:
    """Tests for hybrid text + embedding score blending."""

    def test_no_query_embedding_keeps_text_scores(self, service: SearchService) -> None:
        candidates = [_make_candidate(text_score=0.8)]
        result = service.blend_with_embeddings(candidates, None)
        assert result[0]["score"] == 0.8
        assert "_embedding_raw" not in result[0]

    def test_no_candidates_returns_empty(self, service: SearchService) -> None:
        result = service.blend_with_embeddings([], [1.0, 0.0, 0.0])
        assert result == []

    def test_blends_text_and_embedding(self, service: SearchService) -> None:
        """With identical query/product embedding, cosine=1.0, blend should be 0.6*text + 0.4*1.0."""
        emb = [1.0, 0.0, 0.0]
        candidates = [_make_candidate(text_score=0.5, embedding=emb)]
        result = service.blend_with_embeddings(candidates, emb)
        expected = 0.6 * 0.5 + 0.4 * 1.0  # 0.7
        assert result[0]["score"] == pytest.approx(expected, abs=1e-3)

    def test_orthogonal_embedding_only_text_component(self, service: SearchService) -> None:
        """Orthogonal vectors → cosine=0, blend should be 0.6*text + 0.4*0."""
        candidates = [_make_candidate(text_score=0.8, embedding=[0.0, 1.0, 0.0])]
        result = service.blend_with_embeddings(candidates, [1.0, 0.0, 0.0])
        expected = 0.6 * 0.8 + 0.4 * 0.0  # 0.48
        assert result[0]["score"] == pytest.approx(expected, abs=1e-3)

    def test_strips_raw_embedding(self, service: SearchService) -> None:
        candidates = [_make_candidate(embedding=[1.0, 0.0])]
        result = service.blend_with_embeddings(candidates, [1.0, 0.0])
        assert "_embedding_raw" not in result[0]

    def test_no_embedding_keeps_text_score(self, service: SearchService) -> None:
        """Candidate with no embedding should keep text-only score."""
        candidates = [_make_candidate(text_score=0.9, embedding=None)]
        result = service.blend_with_embeddings(candidates, [1.0, 0.0])
        assert result[0]["score"] == 0.9

    def test_sorts_by_blended_score(self, service: SearchService) -> None:
        """Results should be sorted descending by blended score."""
        emb = [1.0, 0.0, 0.0]
        candidates = [
            _make_candidate(name="Low", text_score=0.1, embedding=emb),
            _make_candidate(name="High", text_score=0.9, embedding=emb),
        ]
        candidates[1]["product_id"] = "p2"
        result = service.blend_with_embeddings(candidates, emb)
        assert result[0]["name"] == "High"
        assert result[1]["name"] == "Low"

    def test_json_string_embedding_parsed(self, service: SearchService) -> None:
        """Embedding stored as JSON string should be parsed correctly."""
        import json

        emb = [1.0, 0.0, 0.0]
        candidates = [_make_candidate(text_score=0.5, embedding=json.dumps(emb))]
        result = service.blend_with_embeddings(candidates, emb)
        expected = 0.6 * 0.5 + 0.4 * 1.0
        assert result[0]["score"] == pytest.approx(expected, abs=1e-3)
