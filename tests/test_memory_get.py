"""Tests for GET /memory/{path} endpoint."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from heare_memory.file_manager import FileManager
from heare_memory.git_manager import GitManager
from heare_memory.routers.memory import router
from heare_memory.services.memory_service import MemoryService


@pytest.fixture
def app():
    """Create FastAPI app with memory router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def app_with_dependency_override():
    """Create FastAPI app with dependency override capability."""
    from heare_memory.dependencies import get_memory_service

    app = FastAPI()
    app.include_router(router)

    # Store original dependency for cleanup
    app.original_dependency = get_memory_service

    return app


@pytest.fixture
def mock_file_manager():
    """Create a mock FileManager."""
    return AsyncMock(spec=FileManager)


@pytest.fixture
def mock_git_manager():
    """Create a mock GitManager."""
    return AsyncMock(spec=GitManager)


@pytest.fixture
def mock_memory_service(mock_file_manager, mock_git_manager):
    """Create a mock MemoryService."""
    return MemoryService(mock_file_manager, mock_git_manager)


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestGetMemoryNode:
    """Test GET /memory/{path} endpoint."""

    def test_get_memory_node_success(self, app_with_dependency_override):
        """Test successful retrieval of a memory node."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Create test data
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=100,
            sha="abc123",
            exists=True,
        )
        memory_node = MemoryNode(
            path="test/file.md",
            content="# Test Content\n\nThis is a test file.",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.get_memory_node.return_value = memory_node

        # Override dependency
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.get("/memory/test/file")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        assert data["path"] == "test/file.md"
        assert data["content"] == "# Test Content\n\nThis is a test file."
        assert data["metadata"]["size"] == 100
        assert data["metadata"]["sha"] == "abc123"

        # Verify headers
        assert "X-Git-SHA" in response.headers
        assert "Last-Modified" in response.headers
        assert "ETag" in response.headers
        assert response.headers["X-Git-SHA"] == "abc123"

        # Verify service was called with sanitized path
        mock_service.get_memory_node.assert_called_once_with("test/file.md")

    def test_get_memory_node_not_found(self, app_with_dependency_override):
        """Test 404 response when memory node doesn't exist."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.services.memory_service import MemoryNotFoundError

        # Mock the memory service to raise not found error
        mock_service = AsyncMock()
        mock_service.get_memory_node.side_effect = MemoryNotFoundError(
            "Memory node not found: test/nonexistent.md"
        )

        # Override dependency
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.get("/memory/test/nonexistent")

        # Verify response
        assert response.status_code == 404
        data = response.json()

        assert data["detail"]["error"] == "NotFound"
        assert "not found" in data["detail"]["message"]
        assert data["detail"]["path"] == "test/nonexistent"

    def test_get_memory_node_invalid_path(self, app_with_dependency_override, monkeypatch):
        """Test 400 response for invalid paths."""
        from heare_memory.dependencies import get_memory_service
        from heare_memory.path_utils import PathValidationError

        # Mock path sanitization to raise validation error
        def mock_sanitize_path(path):
            raise PathValidationError("Invalid path: contains dangerous pattern")

        monkeypatch.setattr("heare_memory.routers.memory.sanitize_path", mock_sanitize_path)

        # Mock the memory service (won't be called due to path validation)
        mock_service = AsyncMock()
        app_with_dependency_override.dependency_overrides[get_memory_service] = lambda: mock_service

        # Create client
        client = TestClient(app_with_dependency_override)

        # Make request
        response = client.get("/memory/../escape")

        # Verify response
        assert response.status_code == 400
        data = response.json()

        assert data["detail"]["error"] == "InvalidPath"
        assert "Invalid path format" in data["detail"]["message"]
        assert data["detail"]["path"] == "../escape"

    def test_get_memory_node_internal_error(self, client, monkeypatch):
        """Test 500 response for internal errors."""
        from heare_memory.services.memory_service import MemoryServiceError

        # Mock the memory service to raise internal error
        mock_service = AsyncMock()
        mock_service.get_memory_node.side_effect = MemoryServiceError("Database connection failed")

        def mock_get_memory_service():
            return mock_service

        monkeypatch.setattr(
            "heare_memory.routers.memory.get_memory_service", mock_get_memory_service
        )

        # Make request
        response = client.get("/memory/test/file")

        # Verify response
        assert response.status_code == 500
        data = response.json()

        assert data["detail"]["error"] == "InternalError"
        assert data["detail"]["message"] == "Internal server error occurred"
        assert data["detail"]["path"] == "test/file"

    def test_get_memory_node_unexpected_error(self, client, monkeypatch):
        """Test 500 response for unexpected errors."""
        # Mock the memory service to raise unexpected error
        mock_service = AsyncMock()
        mock_service.get_memory_node.side_effect = ValueError("Unexpected error")

        def mock_get_memory_service():
            return mock_service

        monkeypatch.setattr(
            "heare_memory.routers.memory.get_memory_service", mock_get_memory_service
        )

        # Make request
        response = client.get("/memory/test/file")

        # Verify response
        assert response.status_code == 500
        data = response.json()

        assert data["detail"]["error"] == "UnexpectedError"
        assert data["detail"]["message"] == "An unexpected error occurred"
        assert data["detail"]["path"] == "test/file"

    def test_path_sanitization(self, client, monkeypatch):
        """Test that paths are properly sanitized."""
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Create test data
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=50,
            sha="def456",
            exists=True,
        )
        memory_node = MemoryNode(
            path="sanitized/path.md",
            content="# Sanitized Content",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.get_memory_node.return_value = memory_node

        def mock_get_memory_service():
            return mock_service

        monkeypatch.setattr(
            "heare_memory.routers.memory.get_memory_service", mock_get_memory_service
        )

        # Test various path formats that should be sanitized
        test_cases = [
            "test/file",  # No extension
            "test\\file",  # Backslashes
            "/test/file",  # Leading slash
            "test//file",  # Double slashes
        ]

        for test_path in test_cases:
            response = client.get(f"/memory/{test_path}")
            assert response.status_code == 200
            # Service should be called with sanitized path ending in .md
            args, _ = mock_service.get_memory_node.call_args
            assert args[0].endswith(".md")

    def test_etag_generation(self, client, monkeypatch):
        """Test ETag header generation."""
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Create test data
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=123,
            sha="sha456",
            exists=True,
        )
        memory_node = MemoryNode(
            path="test.md",
            content="Content",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.get_memory_node.return_value = memory_node

        def mock_get_memory_service():
            return mock_service

        monkeypatch.setattr(
            "heare_memory.routers.memory.get_memory_service", mock_get_memory_service
        )

        # Make request
        response = client.get("/memory/test")

        # Verify ETag format: "sha-size"
        assert response.status_code == 200
        etag = response.headers["ETag"]
        assert etag == '"sha456-123"'

    def test_last_modified_header(self, client, monkeypatch):
        """Test Last-Modified header format."""
        from heare_memory.models.memory import MemoryNode, MemoryNodeMetadata

        # Create test data with specific datetime
        test_datetime = datetime(2024, 1, 15, 14, 30, 45)
        metadata = MemoryNodeMetadata(
            created_at=test_datetime,
            updated_at=test_datetime,
            size=100,
            sha="sha789",
            exists=True,
        )
        memory_node = MemoryNode(
            path="test.md",
            content="Content",
            metadata=metadata,
        )

        # Mock the memory service
        mock_service = AsyncMock()
        mock_service.get_memory_node.return_value = memory_node

        def mock_get_memory_service():
            return mock_service

        monkeypatch.setattr(
            "heare_memory.routers.memory.get_memory_service", mock_get_memory_service
        )

        # Make request
        response = client.get("/memory/test")

        # Verify Last-Modified format
        assert response.status_code == 200
        last_modified = response.headers["Last-Modified"]
        # Should be in HTTP date format
        assert last_modified == "Mon, 15 Jan 2024 14:30:45 GMT"
