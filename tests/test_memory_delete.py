"""Tests for DELETE /memory/{path} endpoint."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from heare_memory.routers.memory import router


@pytest.fixture
def app_with_dependency_override():
    """Create FastAPI app with dependency override capability."""

    app = FastAPI()
    app.include_router(router)

    return app


class TestDeleteMemoryNode:
    """Test DELETE /memory/{path} endpoint."""

    def test_delete_memory_node_success(self, app_with_dependency_override, monkeypatch):
        """Test successful deletion of a memory node (204)."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.delete_memory_node.return_value = True  # File was deleted

        # Override dependency
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.delete("/memory/test/file")

        # Verify response
        assert response.status_code == 204
        assert response.content == b""  # No content for 204

        # Verify service was called with sanitized path
        mock_service.delete_memory_node.assert_called_once_with("test/file.md")

    def test_delete_memory_node_not_found(self, app_with_dependency_override, monkeypatch):
        """Test 404 response when memory node doesn't exist."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.delete_memory_node.return_value = False  # File didn't exist

        # Override dependency
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.delete("/memory/test/nonexistent")

        # Verify response
        assert response.status_code == 404
        data = response.json()

        assert data["detail"]["error"] == "NotFound"
        assert "not found" in data["detail"]["message"]
        assert data["detail"]["path"] == "test/nonexistent"

        # Verify service was called
        mock_service.delete_memory_node.assert_called_once_with("test/nonexistent.md")

    def test_delete_read_only_mode(self, app_with_dependency_override, monkeypatch):
        """Test 403 response when service is in read-only mode."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = True
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service (won't be called)
        mock_service = AsyncMock()
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.delete("/memory/test/file")

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "ReadOnlyMode"
        assert "read-only" in data["detail"]["message"]

        # Verify service was not called
        mock_service.delete_memory_node.assert_not_called()

    def test_delete_invalid_path(self, app_with_dependency_override, monkeypatch):
        """Test 400 response for invalid paths."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.path_utils import PathValidationError

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock path sanitization to raise validation error
        def mock_sanitize_path(path):
            raise PathValidationError("Invalid path: contains dangerous pattern")

        monkeypatch.setattr("heare_memory.routers.memory.sanitize_path", mock_sanitize_path)

        # Mock the memory service (won't be called due to path validation)
        mock_service = AsyncMock()
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.delete("/memory/../escape")

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidPath"
        assert "Invalid path format" in data["detail"]["message"]

    def test_delete_memory_service_error(self, app_with_dependency_override, monkeypatch):
        """Test 500 response for memory service errors."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.services.memory_service import MemoryServiceError

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service to raise an error
        mock_service = AsyncMock()
        mock_service.delete_memory_node.side_effect = MemoryServiceError("Database error")

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.delete("/memory/test/file")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "InternalError"
        assert data["detail"]["message"] == "Internal server error occurred"

    def test_delete_unexpected_error(self, app_with_dependency_override, monkeypatch):
        """Test 500 response for unexpected errors."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service to raise unexpected error
        mock_service = AsyncMock()
        mock_service.delete_memory_node.side_effect = ValueError("Unexpected error")

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.delete("/memory/test/file")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "UnexpectedError"
        assert data["detail"]["message"] == "An unexpected error occurred"

    def test_path_sanitization(self, app_with_dependency_override, monkeypatch):
        """Test that paths are properly sanitized."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.delete_memory_node.return_value = True

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Test various path formats that should be sanitized
        test_cases = [
            "test/file",  # No extension
            "test\\file",  # Backslashes
            "/test/file",  # Leading slash
            "test//file",  # Double slashes
        ]

        for test_path in test_cases:
            response = client.delete(f"/memory/{test_path}")
            assert response.status_code == 204
            # Service should be called with sanitized path ending in .md
            args, _ = mock_service.delete_memory_node.call_args
            assert args[0].endswith(".md")

    def test_delete_idempotency(self, app_with_dependency_override, monkeypatch):
        """Test that DELETE is idempotent (multiple deletes of same file)."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service - first call succeeds, subsequent calls return False
        mock_service = AsyncMock()
        mock_service.delete_memory_node.side_effect = [True, False, False]

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # First delete - should succeed
        response1 = client.delete("/memory/test/file")
        assert response1.status_code == 204

        # Second delete - should return 404 (file already deleted)
        response2 = client.delete("/memory/test/file")
        assert response2.status_code == 404
        data = response2.json()
        assert data["detail"]["error"] == "NotFound"

        # Third delete - should also return 404 (idempotent)
        response3 = client.delete("/memory/test/file")
        assert response3.status_code == 404

        # Verify service was called three times
        assert mock_service.delete_memory_node.call_count == 3

    def test_delete_no_content_response(self, app_with_dependency_override, monkeypatch):
        """Test that successful DELETE returns empty body."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.delete_memory_node.return_value = True

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.delete("/memory/test/file")

        # 204 No Content should have empty body
        assert response.status_code == 204
        assert response.content == b""
        assert "Content-Length" not in response.headers or response.headers["Content-Length"] == "0"
