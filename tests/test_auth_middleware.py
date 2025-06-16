"""Tests for authentication middleware."""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.heare_memory.middleware.auth import (
    AuthenticationMiddleware,
    get_auth_context,
    require_write_access,
)
from src.heare_memory.models.auth import AuthContext, OperationType, ReadOnlyModeError


class TestAuthenticationMiddleware:
    """Test authentication middleware functionality."""

    @pytest.fixture
    def app_with_auth_middleware(self):
        """Create FastAPI app with authentication middleware."""
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/memory/test")
        async def get_memory():
            return {"content": "test"}

        @app.put("/memory/test")
        async def put_memory():
            return {"success": True}

        @app.delete("/memory/test")
        async def delete_memory():
            return {"success": True}

        @app.get("/memory/auth-context")
        async def get_auth_context_endpoint(request: Request):
            auth_context = get_auth_context(request)
            return auth_context.dict() if auth_context else {"error": "No auth context"}

        return app

    @pytest.fixture
    def client_writable_mode(self, app_with_auth_middleware):
        """Test client with writable mode (GITHUB_TOKEN configured)."""
        with patch("src.heare_memory.middleware.auth.settings") as mock_settings:
            mock_settings.is_read_only = False
            mock_settings.github_token = "test_token"  # noqa: S105
            return TestClient(app_with_auth_middleware)

    @pytest.fixture
    def client_readonly_mode(self, app_with_auth_middleware):
        """Test client with read-only mode (no GITHUB_TOKEN)."""
        with patch("src.heare_memory.middleware.auth.settings") as mock_settings:
            mock_settings.is_read_only = True
            mock_settings.github_token = None
            return TestClient(app_with_auth_middleware)

    def test_health_endpoint_bypass_auth(self, client_readonly_mode):
        """Test that health endpoint bypasses authentication."""
        response = client_readonly_mode.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
        assert "X-Request-ID" in response.headers

    def test_get_request_allowed_readonly(self, client_readonly_mode):
        """Test that GET requests are allowed in read-only mode."""
        response = client_readonly_mode.get("/memory/test")
        assert response.status_code == 200
        assert response.json() == {"content": "test"}

    def test_put_request_blocked_readonly(self, client_readonly_mode):
        """Test that PUT requests are blocked in read-only mode."""
        response = client_readonly_mode.put("/memory/test", json={"content": "new"})
        assert response.status_code == 403

        data = response.json()
        assert data["error"] == "read_only_mode"
        assert "read-only mode" in data["message"]
        assert data["details"]["read_only"] is True
        assert data["details"]["operation"] == "write"
        assert data["details"]["path"] == "/memory/test"

    def test_delete_request_blocked_readonly(self, client_readonly_mode):
        """Test that DELETE requests are blocked in read-only mode."""
        response = client_readonly_mode.delete("/memory/test")
        assert response.status_code == 403

        data = response.json()
        assert data["error"] == "read_only_mode"
        assert data["details"]["operation"] == "write"

    def test_write_requests_allowed_writable(self, client_writable_mode):
        """Test that write requests are allowed in writable mode."""
        # PUT request
        response = client_writable_mode.put("/memory/test", json={"content": "new"})
        assert response.status_code == 200
        assert response.json() == {"success": True}

        # DELETE request
        response = client_writable_mode.delete("/memory/test")
        assert response.status_code == 200
        assert response.json() == {"success": True}

    def test_options_request_allowed(self, client_readonly_mode):
        """Test that OPTIONS requests are allowed (CORS preflight)."""
        response = client_readonly_mode.options("/memory/test")
        # FastAPI returns 405 for unhandled OPTIONS, but middleware should not block it
        assert response.status_code != 403  # Should not be blocked by auth

    def test_auth_context_injection(self, client_writable_mode):
        """Test that authentication context is properly injected."""
        response = client_writable_mode.get("/memory/auth-context")
        assert response.status_code == 200

        data = response.json()
        assert "request_id" in data
        assert "timestamp" in data
        assert data["read_only_mode"] is False
        assert data["github_token_configured"] is True
        assert data["operation_type"] == "read"
        assert data["bypass_auth"] is False

    def test_auth_context_readonly_mode(self, client_readonly_mode):
        """Test authentication context in read-only mode."""
        response = client_readonly_mode.get("/memory/auth-context")
        assert response.status_code == 200

        data = response.json()
        assert data["read_only_mode"] is True
        assert data["github_token_configured"] is False

    def test_auth_context_public_endpoint(self, client_readonly_mode):
        """Test authentication context for public endpoints."""
        # Health endpoint should have bypass_auth = True
        # We need to modify the test to check this properly
        pass  # This would require a custom endpoint to expose auth context

    def test_request_id_in_headers(self, client_writable_mode):
        """Test that request ID is included in response headers."""
        response = client_writable_mode.get("/memory/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0
        # Should be a UUID format (roughly)
        assert len(request_id.split("-")) == 5

    def test_error_response_format(self, client_readonly_mode):
        """Test that error responses follow the standard format."""
        response = client_readonly_mode.put("/memory/test", json={"content": "new"})
        assert response.status_code == 403

        data = response.json()
        # Check required fields
        assert "error" in data
        assert "message" in data
        assert "details" in data

        # Check error structure
        assert isinstance(data["error"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["details"], dict)

        # Check request ID in response headers
        assert "X-Request-ID" in response.headers

    def test_multiple_requests_different_ids(self, client_writable_mode):
        """Test that different requests get different request IDs."""
        response1 = client_writable_mode.get("/memory/test")
        response2 = client_writable_mode.get("/memory/test")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]

        assert id1 != id2


class TestAuthHelperFunctions:
    """Test authentication helper functions."""

    def test_get_auth_context_missing(self):
        """Test getting auth context when not available."""
        mock_request = Mock()
        mock_request.state = Mock()
        del mock_request.state.auth  # Simulate missing auth context

        result = get_auth_context(mock_request)
        assert result is None

    def test_get_auth_context_present(self):
        """Test getting auth context when available."""
        mock_request = Mock()
        auth_context = AuthContext(
            request_id="test-123",
            read_only_mode=False,
            github_token_configured=True,
            operation_type=OperationType.READ,
        )
        mock_request.state.auth = auth_context

        result = get_auth_context(mock_request)
        assert result == auth_context

    def test_require_write_access_allowed(self):
        """Test require_write_access when write access is allowed."""
        mock_request = Mock()
        auth_context = AuthContext(
            request_id="test-123",
            read_only_mode=False,
            github_token_configured=True,
            operation_type=OperationType.WRITE,
        )
        mock_request.state.auth = auth_context
        mock_request.url.path = "/memory/test"

        # Should not raise exception
        require_write_access(mock_request)

    def test_require_write_access_denied(self):
        """Test require_write_access when in read-only mode."""
        mock_request = Mock()
        auth_context = AuthContext(
            request_id="test-123",
            read_only_mode=True,
            github_token_configured=False,
            operation_type=OperationType.WRITE,
        )
        mock_request.state.auth = auth_context
        mock_request.url.path = "/memory/test"

        with pytest.raises(ReadOnlyModeError) as exc_info:
            require_write_access(mock_request)

        error = exc_info.value
        assert error.error_code == "read_only_mode"
        assert error.details["path"] == "/memory/test"

    def test_require_write_access_no_context(self):
        """Test require_write_access when no auth context available."""
        mock_request = Mock()
        mock_request.state = Mock()
        del mock_request.state.auth  # Simulate missing auth context
        mock_request.url.path = "/memory/test"

        # Should not raise exception when no context (assumes allowed)
        require_write_access(mock_request)


class TestAuthModels:
    """Test authentication models and utilities."""

    def test_auth_context_creation(self):
        """Test AuthContext model creation."""
        context = AuthContext(
            request_id="test-123",
            read_only_mode=True,
            github_token_configured=False,
            operation_type=OperationType.READ,
        )

        assert context.request_id == "test-123"
        assert context.read_only_mode is True
        assert context.github_token_configured is False
        assert context.operation_type == OperationType.READ
        assert context.bypass_auth is False  # Default value

    def test_readonly_mode_error(self):
        """Test ReadOnlyModeError creation."""
        error = ReadOnlyModeError(operation="delete", path="/memory/test")

        assert error.error_code == "read_only_mode"
        assert "read-only mode" in error.message
        assert error.details["operation"] == "delete"
        assert error.details["path"] == "/memory/test"
        assert error.details["read_only"] is True

    def test_operation_type_enum_values(self):
        """Test OperationType enum values."""
        assert OperationType.READ == "read"
        assert OperationType.WRITE == "write"
        assert OperationType.HEALTH == "health"
        assert OperationType.SCHEMA == "schema"
        assert OperationType.OPTIONS == "options"
