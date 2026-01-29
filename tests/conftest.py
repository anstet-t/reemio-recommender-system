"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

from recommendation_service.config import Settings, get_settings
from recommendation_service.main import create_app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Get test settings with overrides."""
    return Settings(
        app_env="test",
        debug=True,
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="test",
        postgres_password="test",
        postgres_db="test_db",
        redis_host="localhost",
        redis_port=6379,
        pinecone_api_key="test-key",
    )


@pytest.fixture
def app(test_settings: Settings) -> Any:
    """Create test application."""
    # Override settings
    def get_test_settings() -> Settings:
        return test_settings

    app = create_app()
    app.dependency_overrides[get_settings] = get_test_settings
    return app


@pytest.fixture
def client(app: Any) -> TestClient:
    """Create synchronous test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app: Any) -> AsyncGenerator[AsyncClient, None]:
    """Create asynchronous test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_user_id() -> str:
    """Sample user ID for tests."""
    return "test-user-123"


@pytest.fixture
def sample_product_id() -> str:
    """Sample product ID for tests."""
    return "test-product-456"


@pytest.fixture
def sample_interaction_data(sample_user_id: str, sample_product_id: str) -> dict:
    """Sample interaction request data."""
    return {
        "user_id": sample_user_id,
        "product_id": sample_product_id,
        "interaction_type": "view",
        "session_id": "test-session-789",
    }
