"""Tests for PUT /memory/{path} endpoint."""

from datetime import datetime
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


class TestPutMemoryNode:
    """Test PUT /memory/{path} endpoint."""

    def test_create_memory_node_success(self, app_with_dependency_override):
        """Test successful creation of a new memory node (201)."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Create test data
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=25,
            sha="abc123",
            exists=True,
        )
        memory_node = MemoryNode(
            path="test/new-file.md",
            content="# New File\n\nContent",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.create_or_update_memory_node.return_value = (
            memory_node,
            True,
        )  # True = created

        # Override dependency
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.put("/memory/test/new-file", json={"content": "# New File\n\nContent"})

        # Verify response
        assert response.status_code == 201  # Created
        data = response.json()

        assert data["path"] == "test/new-file.md"
        assert data["content"] == "# New File\n\nContent"
        assert data["metadata"]["size"] == 25
        assert data["metadata"]["sha"] == "abc123"

        # Verify headers
        assert "X-Git-SHA" in response.headers
        assert "Last-Modified" in response.headers
        assert "ETag" in response.headers
        assert response.headers["X-Git-SHA"] == "abc123"

        # Verify service was called with sanitized path
        mock_service.create_or_update_memory_node.assert_called_once_with(
            "test/new-file.md", "# New File\n\nContent"
        )

    def test_update_memory_node_success(self, app_with_dependency_override):
        """Test successful update of an existing memory node (200)."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Create test data
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=30,
            sha="def456",
            exists=True,
        )
        memory_node = MemoryNode(
            path="test/existing.md",
            content="# Updated Content\n\nNew",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.create_or_update_memory_node.return_value = (
            memory_node,
            False,
        )  # False = updated

        # Override dependency
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.put("/memory/test/existing", json={"content": "# Updated Content\n\nNew"})

        # Verify response
        assert response.status_code == 200  # OK (updated)
        data = response.json()

        assert data["path"] == "test/existing.md"
        assert data["content"] == "# Updated Content\n\nNew"
        assert data["metadata"]["size"] == 30
        assert data["metadata"]["sha"] == "def456"

    def test_put_invalid_json_body(self, app_with_dependency_override):
        """Test 400 response for invalid JSON body."""
        from heare_memory.dependencies import get_memory_service

        # Mock the memory service (won't be called)
        mock_service = AsyncMock()
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Test missing content field
        response = client.put("/memory/test/file", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidRequest"
        assert "content" in data["detail"]["message"]

        # Test invalid content type
        response = client.put("/memory/test/file", json={"content": 123})
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidContent"
        assert "string" in data["detail"]["message"]

    def test_put_content_too_large(self, app_with_dependency_override):
        """Test 400 response for content that's too large."""
        from heare_memory.dependencies import get_memory_service

        # Mock the memory service (won't be called)
        mock_service = AsyncMock()
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Create content that's too large (>10MB)
        large_content = "x" * (10_000_001)

        response = client.put("/memory/test/large", json={"content": large_content})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "ContentTooLarge"
        assert "10MB" in data["detail"]["message"]

    def test_put_read_only_mode(self, app_with_dependency_override, monkeypatch):
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

        response = client.put("/memory/test/file", json={"content": "# Test Content"})

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "ReadOnlyMode"
        assert "read-only" in data["detail"]["message"]

        # Verify service was not called
        mock_service.create_or_update_memory_node.assert_not_called()

    def test_put_invalid_path(self, app_with_dependency_override, monkeypatch):
        """Test 400 response for invalid paths."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.path_utils import PathValidationError

        # Mock path sanitization to raise validation error
        def mock_sanitize_path(path):
            raise PathValidationError("Invalid path: contains dangerous pattern")

        monkeypatch.setattr("heare_memory.routers.memory.sanitize_path", mock_sanitize_path)

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service (won't be called due to path validation)
        mock_service = AsyncMock()
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.put("/memory/../escape", json={"content": "# Test Content"})

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidPath"
        assert "Invalid path format" in data["detail"]["message"]

    def test_put_memory_service_error(self, app_with_dependency_override, monkeypatch):
        """Test 500 response for memory service errors."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.services.memory_service import MemoryServiceError

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Mock the memory service to raise an error
        mock_service = AsyncMock()
        mock_service.create_or_update_memory_node.side_effect = MemoryServiceError("Database error")

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.put("/memory/test/file", json={"content": "# Test Content"})

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "InternalError"
        assert data["detail"]["message"] == "Internal server error occurred"

    def test_put_unicode_error(self, app_with_dependency_override, monkeypatch):
        """Test 400 response for invalid UTF-8 content."""
        from heare_memory.dependencies import get_memory_service

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # This test simulates a case where content encoding fails
        # In practice, FastAPI/Pydantic would catch most of these earlier
        mock_service = AsyncMock()
        mock_service.create_or_update_memory_node.side_effect = UnicodeDecodeError(
            "utf-8", b"\xff", 0, 1, "invalid start byte"
        )

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.put(
            "/memory/test/file",
            json={"content": "Valid content"},  # The error would come from the service
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidEncoding"
        assert "UTF-8" in data["detail"]["message"]

    def test_path_sanitization(self, app_with_dependency_override, monkeypatch):
        """Test that paths are properly sanitized."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Create test data
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=20,
            sha="sanitized123",
            exists=True,
        )
        memory_node = MemoryNode(
            path="sanitized/path.md",
            content="# Sanitized Content",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.create_or_update_memory_node.return_value = (memory_node, True)

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
            response = client.put(f"/memory/{test_path}", json={"content": "# Test Content"})
            assert response.status_code == 201
            # Service should be called with sanitized path ending in .md
            args, _ = mock_service.create_or_update_memory_node.call_args
            assert args[0].endswith(".md")

    def test_etag_and_headers(self, app_with_dependency_override, monkeypatch):
        """Test that proper headers are set."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Mock settings to not be read-only
        mock_settings = Mock()
        mock_settings.is_read_only = False
        monkeypatch.setattr("heare_memory.config.settings", mock_settings)

        # Create test data with specific values for header testing
        test_datetime = datetime(2024, 1, 15, 14, 30, 45)
        metadata = MemoryNodeMetadata(
            created_at=test_datetime,
            updated_at=test_datetime,
            size=123,
            sha="sha456",
            exists=True,
        )
        memory_node = MemoryNode(
            path="test.md",
            content="# Content",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.create_or_update_memory_node.return_value = (memory_node, False)  # Update

        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        response = client.put("/memory/test", json={"content": "# Content"})

        assert response.status_code == 200

        # Verify headers
        assert response.headers["X-Git-SHA"] == "sha456"
        assert response.headers["ETag"] == '"sha456-123"'
        assert response.headers["Last-Modified"] == "Mon, 15 Jan 2024 14:30:45 GMT"
        assert "application/json" in response.headers["Content-Type"]

        # True = created
        mock_service.create_or_update_memory_node.return_value = (memory_node, True)
