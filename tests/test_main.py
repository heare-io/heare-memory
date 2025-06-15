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
    assert "read_only" in data
    assert "git_configured" in data


def test_app_creation() -> None:
    """Test that the app can be created successfully."""
    app = create_app()
    assert app is not None
    assert app.title == "Heare Memory Global Service"


def test_openapi_schema(client: TestClient) -> None:
    """Test that OpenAPI docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_schema_endpoint(client: TestClient) -> None:
    """Test the schema endpoint."""
    response = client.get("/schema")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema


def test_memory_endpoints_exist(client: TestClient) -> None:
    """Test that memory endpoints are accessible (even if not implemented)."""
    # Test memory endpoints return 501 (not implemented) rather than 404
    response = client.get("/memory/test")
    assert response.status_code == 501

    response = client.put("/memory/test", json={"content": "test"})
    assert response.status_code == 501

    response = client.delete("/memory/test")
    assert response.status_code == 501

    response = client.get("/memory/")
    assert response.status_code == 501
