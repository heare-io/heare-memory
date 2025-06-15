"""Basic tests for the main application."""

import pytest
from fastapi.testclient import TestClient

from heare_memory.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "heare-memory"
    assert "version" in data


def test_app_creation() -> None:
    """Test that the app can be created successfully."""
    app = create_app()
    assert app is not None
    assert app.title == "Heare Memory Global Service"
