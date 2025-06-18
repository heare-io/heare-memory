"""Tests for comprehensive error handling middleware and custom exceptions."""

import json
import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from src.heare_memory.exceptions import (
    AuthenticationError,
    ConcurrentModificationError,
    ContentValidationError,
    GitOperationError,
    InvalidPathError,
    MemoryNodeNotFoundError,
    MemoryServiceException,
    RateLimitError,
    ReadOnlyModeError,
    SearchTimeoutError,
    ServiceUnavailableError,
    ValidationError,
)
from src.heare_memory.middleware.error_handler import ErrorHandlerMiddleware
from src.heare_memory.models.errors import ErrorResponse, ValidationErrorDetail


@pytest.fixture
def test_app():
    """Create a test FastAPI app with error handling middleware."""
    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware, include_debug_info=True)

    @app.get("/test/success")
    async def success_endpoint():
        return {"status": "success"}

    @app.get("/test/http-exception")
    async def http_exception_endpoint():
        raise HTTPException(status_code=400, detail="Test HTTP exception")

    @app.get("/test/validation-error")
    async def validation_error_endpoint():
        raise ValidationError("Test validation error", field="test_field", value="invalid")

    @app.get("/test/memory-not-found")
    async def memory_not_found_endpoint():
        raise MemoryNodeNotFoundError("test/path.md")

    @app.get("/test/read-only-mode")
    async def read_only_mode_endpoint():
        raise ReadOnlyModeError("write", "test/path.md")

    @app.get("/test/invalid-path")
    async def invalid_path_endpoint():
        raise InvalidPathError("../invalid", "contains directory traversal")

    @app.get("/test/content-validation")
    async def content_validation_endpoint():
        raise ContentValidationError("content too large", content_length=10000000)

    @app.get("/test/concurrent-modification")
    async def concurrent_modification_endpoint():
        raise ConcurrentModificationError("test/path.md", "abc123", "def456")

    @app.get("/test/rate-limit")
    async def rate_limit_endpoint():
        raise RateLimitError(100, 3600, 1234567890)

    @app.get("/test/service-unavailable")
    async def service_unavailable_endpoint():
        raise ServiceUnavailableError("maintenance mode", retry_after=300)

    @app.get("/test/search-timeout")
    async def search_timeout_endpoint():
        raise SearchTimeoutError("test query", 30.0)

    @app.get("/test/git-error")
    async def git_error_endpoint():
        raise GitOperationError("commit failed", "commit", "test/path.md")

    @app.get("/test/unexpected-error")
    async def unexpected_error_endpoint():
        raise ValueError("Unexpected error for testing")

    @app.get("/test/pydantic-validation")
    async def pydantic_validation_endpoint():
        # Simulate a Pydantic validation error
        try:
            from pydantic import BaseModel, Field

            class TestModel(BaseModel):
                required_field: str = Field(min_length=5)

            TestModel(required_field="hi")  # This will fail validation
        except PydanticValidationError as e:
            raise e

    return app


@pytest.fixture
def client(test_app):
    """Create a test client with the error handling app."""
    return TestClient(test_app)


def test_successful_request(client):
    """Test that successful requests pass through unchanged."""
    response = client.get("/test/success")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_http_exception_passthrough(client):
    """Test that HTTP exceptions are passed through to FastAPI."""
    response = client.get("/test/http-exception")
    assert response.status_code == 400
    # FastAPI formats HTTP exceptions differently than our error handler


def test_validation_error_handling(client):
    """Test validation error handling with proper status code and format."""
    response = client.get("/test/validation-error")
    assert response.status_code == 400

    data = response.json()
    assert data["error"] == "validation_error"
    assert data["message"] == "Test validation error"
    assert "field" in data["details"]
    assert data["details"]["field"] == "test_field"
    assert "request_id" in data
    assert "timestamp" in data


def test_memory_not_found_error(client):
    """Test memory node not found error handling."""
    response = client.get("/test/memory-not-found")
    assert response.status_code == 404

    data = response.json()
    assert data["error"] == "memory_node_not_found_error"
    assert "test/path.md" in data["message"]
    assert data["details"]["path"] == "test/path.md"


def test_read_only_mode_error(client):
    """Test read-only mode error handling."""
    response = client.get("/test/read-only-mode")
    assert response.status_code == 403

    data = response.json()
    assert data["error"] == "read_only_mode_error"
    assert "read-only mode" in data["message"]
    assert data["details"]["read_only"] is True
    assert data["details"]["operation"] == "write"
    assert data["details"]["path"] == "test/path.md"


def test_invalid_path_error(client):
    """Test invalid path error handling."""
    response = client.get("/test/invalid-path")
    assert response.status_code == 400

    data = response.json()
    assert data["error"] == "invalid_path_error"
    assert "Invalid path" in data["message"]
    assert data["details"]["field"] == "path"
    assert data["details"]["invalid_value"] == "../invalid"
    assert data["details"]["reason"] == "contains directory traversal"


def test_content_validation_error(client):
    """Test content validation error handling."""
    response = client.get("/test/content-validation")
    assert response.status_code == 400

    data = response.json()
    assert data["error"] == "content_validation_error"
    assert "Invalid content" in data["message"]
    assert data["details"]["field"] == "content"
    assert data["details"]["content_length"] == 10000000


def test_concurrent_modification_error(client):
    """Test concurrent modification error handling."""
    response = client.get("/test/concurrent-modification")
    assert response.status_code == 409

    data = response.json()
    assert data["error"] == "concurrent_modification_error"
    assert "Concurrent modification" in data["message"]
    assert data["details"]["path"] == "test/path.md"
    assert data["details"]["expected_sha"] == "abc123"
    assert data["details"]["actual_sha"] == "def456"


def test_rate_limit_error(client):
    """Test rate limit error handling."""
    response = client.get("/test/rate-limit")
    assert response.status_code == 429

    data = response.json()
    assert data["error"] == "rate_limit_error"
    assert "Rate limit exceeded" in data["message"]
    assert data["details"]["limit"] == 100
    assert data["details"]["window"] == 3600
    assert data["details"]["reset_time"] == 1234567890


def test_service_unavailable_error(client):
    """Test service unavailable error handling."""
    response = client.get("/test/service-unavailable")
    assert response.status_code == 503

    data = response.json()
    assert data["error"] == "service_unavailable_error"
    assert "temporarily unavailable" in data["message"]
    assert data["details"]["reason"] == "maintenance mode"
    assert data["details"]["retry_after"] == 300


def test_search_timeout_error(client):
    """Test search timeout error handling."""
    response = client.get("/test/search-timeout")
    assert response.status_code == 408

    data = response.json()
    assert data["error"] == "search_timeout_error"
    assert "timed out" in data["message"]
    assert data["details"]["query"] == "test query"
    assert data["details"]["timeout_seconds"] == 30.0


def test_git_operation_error(client):
    """Test git operation error handling."""
    response = client.get("/test/git-error")
    assert response.status_code == 500

    data = response.json()
    assert data["error"] == "git_operation_error"
    assert "commit failed" in data["message"]
    assert data["details"]["git_operation"] == "commit"
    assert data["details"]["path"] == "test/path.md"


def test_unexpected_error_handling(client):
    """Test handling of unexpected Python exceptions."""
    response = client.get("/test/unexpected-error")
    assert response.status_code == 500

    data = response.json()
    assert data["error"] == "internal_server_error"
    assert "internal server error" in data["message"]
    # Debug info should be included since we set include_debug_info=True
    assert "debug" in data["details"]
    assert data["details"]["exception_type"] == "ValueError"


def test_pydantic_validation_error_handling(client):
    """Test handling of Pydantic validation errors."""
    response = client.get("/test/pydantic-validation")
    assert response.status_code == 422

    data = response.json()
    assert data["error"] == "validation_error"
    assert "validation failed" in data["message"]
    assert "field_errors" in data["details"]
    assert len(data["details"]["field_errors"]) > 0

    # Check field error structure
    field_error = data["details"]["field_errors"][0]
    assert "field" in field_error
    assert "message" in field_error
    assert "constraint" in field_error


def test_error_response_includes_correlation_id(client):
    """Test that all error responses include a correlation ID."""
    response = client.get("/test/validation-error")
    data = response.json()

    assert "request_id" in data
    assert data["request_id"] is not None
    # Should be a valid UUID format
    uuid.UUID(data["request_id"])


def test_error_response_includes_timestamp(client):
    """Test that all error responses include a timestamp."""
    response = client.get("/test/validation-error")
    data = response.json()

    assert "timestamp" in data
    assert data["timestamp"] is not None
    # Should be a valid ISO timestamp
    datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))


def test_error_response_includes_path(client):
    """Test that error responses include the API path."""
    response = client.get("/test/validation-error")
    data = response.json()

    assert "path" in data
    assert data["path"] == "/test/validation-error"


class TestErrorResponseModel:
    """Test the ErrorResponse model and its factory methods."""

    def test_from_exception_with_custom_exception(self):
        """Test creating error response from custom exception."""
        exc = MemoryNodeNotFoundError("test/path.md")
        response = ErrorResponse.from_exception(exc, path="/test/path", request_id="test-123")

        assert response.error == "memory_node_not_found_error"
        assert "not found" in response.message
        assert response.path == "/test/path"
        assert response.request_id == "test-123"
        assert response.details["path"] == "test/path.md"

    def test_from_exception_with_standard_exception(self):
        """Test creating error response from standard Python exception."""
        exc = ValueError("Test error")
        response = ErrorResponse.from_exception(exc)

        assert response.error == "value_error"
        assert response.message == "Test error"
        assert response.details["exception_type"] == "ValueError"

    def test_validation_error_factory(self):
        """Test the validation error factory method."""
        field_errors = [
            ValidationErrorDetail(
                field="test_field",
                message="Test validation error",
                invalid_value="invalid",
                constraint="min_length",
            )
        ]

        response = ErrorResponse.validation_error(
            message="Validation failed",
            field_errors=field_errors,
            path="/test",
            request_id="test-123",
        )

        assert response.error == "validation_error"
        assert response.message == "Validation failed"
        assert len(response.details["field_errors"]) == 1
        assert response.details["field_errors"][0]["field"] == "test_field"

    def test_not_found_error_factory(self):
        """Test the not found error factory method."""
        response = ErrorResponse.not_found_error(
            resource="memory_node",
            identifier="test/path.md",
            path="/memory/test/path.md",
            request_id="test-123",
        )

        assert response.error == "not_found"
        assert "memory_node not found: test/path.md" in response.message
        assert response.details["resource"] == "memory_node"
        assert response.details["identifier"] == "test/path.md"

    def test_forbidden_error_factory(self):
        """Test the forbidden error factory method."""
        response = ErrorResponse.forbidden_error(
            operation="write",
            reason="read-only mode",
            path="/memory/test",
            request_id="test-123",
        )

        assert response.error == "forbidden"
        assert "Forbidden: write - read-only mode" in response.message
        assert response.details["operation"] == "write"
        assert response.details["reason"] == "read-only mode"

    def test_conflict_error_factory(self):
        """Test the conflict error factory method."""
        response = ErrorResponse.conflict_error(
            resource="memory_node",
            reason="concurrent modification",
            path="/memory/test",
            request_id="test-123",
        )

        assert response.error == "conflict"
        assert "Conflict with memory_node: concurrent modification" in response.message
        assert response.details["resource"] == "memory_node"
        assert response.details["reason"] == "concurrent modification"


class TestCustomExceptions:
    """Test the custom exception classes."""

    def test_memory_service_exception_base(self):
        """Test the base MemoryServiceException class."""
        exc = MemoryServiceException(
            message="Test error",
            error_code="test_error",
            details={"key": "value"},
            status_code=400,
        )

        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.error_code == "test_error"
        assert exc.details == {"key": "value"}
        assert exc.status_code == 400

    def test_memory_service_exception_default_error_code(self):
        """Test automatic error code generation from class name."""
        exc = MemoryNodeNotFoundError("test/path.md")
        assert exc.error_code == "memory_node_not_found_error"

    def test_validation_error_with_field_info(self):
        """Test ValidationError with field information."""
        exc = ValidationError(
            message="Invalid value",
            field="test_field",
            value="invalid_value",
            details={"constraint": "min_length"},
        )

        assert exc.status_code == 400
        assert exc.details["field"] == "test_field"
        assert exc.details["invalid_value"] == "invalid_value"
        assert exc.details["constraint"] == "min_length"

    def test_read_only_mode_error(self):
        """Test ReadOnlyModeError with operation and path."""
        exc = ReadOnlyModeError(operation="write", path="test/path.md")

        assert exc.status_code == 403
        assert exc.details["read_only"] is True
        assert exc.details["operation"] == "write"
        assert exc.details["path"] == "test/path.md"

    def test_memory_node_not_found_error(self):
        """Test MemoryNodeNotFoundError."""
        exc = MemoryNodeNotFoundError("test/path.md")

        assert exc.status_code == 404
        assert exc.details["path"] == "test/path.md"
        assert "not found" in exc.message

    def test_concurrent_modification_error(self):
        """Test ConcurrentModificationError with SHA values."""
        exc = ConcurrentModificationError("test/path.md", "abc123", "def456")

        assert exc.status_code == 409
        assert exc.details["path"] == "test/path.md"
        assert exc.details["expected_sha"] == "abc123"
        assert exc.details["actual_sha"] == "def456"

    def test_rate_limit_error(self):
        """Test RateLimitError with limit and timing information."""
        exc = RateLimitError(100, 3600, 1234567890)

        assert exc.status_code == 429
        assert exc.details["limit"] == 100
        assert exc.details["window"] == 3600
        assert exc.details["reset_time"] == 1234567890

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError with retry information."""
        exc = ServiceUnavailableError("maintenance mode", retry_after=300)

        assert exc.status_code == 503
        assert exc.details["reason"] == "maintenance mode"
        assert exc.details["retry_after"] == 300


@pytest.mark.asyncio
async def test_error_handler_middleware_correlation_id():
    """Test that the middleware adds correlation IDs to requests."""
    middleware = ErrorHandlerMiddleware(None)

    # Mock request
    request = Mock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"
    request.url = Mock()
    request.url.__str__ = Mock(return_value="http://example.com/test")
    request.state = Mock()

    # Mock call_next that raises an exception
    async def mock_call_next(req):
        raise ValidationError("Test error")

    response = await middleware.dispatch(request, mock_call_next)

    # Check that request_id was set on request state
    assert hasattr(request.state, "request_id")
    assert request.state.request_id is not None

    # Check that response contains the request_id
    response_data = json.loads(response.body)
    assert "request_id" in response_data
    assert response_data["request_id"] == request.state.request_id


def test_status_code_mapping():
    """Test that the middleware maps exceptions to correct status codes."""
    middleware = ErrorHandlerMiddleware(None)

    # Test validation errors -> 400
    exc = ValidationError("test")
    assert middleware._get_status_code_for_exception(exc) == 400

    # Test authentication errors -> 403
    exc = AuthenticationError("test")
    assert middleware._get_status_code_for_exception(exc) == 403

    # Test not found errors -> 404
    exc = MemoryNodeNotFoundError("test")
    assert middleware._get_status_code_for_exception(exc) == 404

    # Test conflict errors -> 409
    exc = ConcurrentModificationError("test")
    assert middleware._get_status_code_for_exception(exc) == 409

    # Test rate limit errors -> 429
    exc = RateLimitError(100, 3600)
    assert middleware._get_status_code_for_exception(exc) == 429

    # Test service unavailable -> 503
    exc = ServiceUnavailableError("test")
    assert middleware._get_status_code_for_exception(exc) == 503

    # Test search timeout -> 408
    exc = SearchTimeoutError("test", 30)
    assert middleware._get_status_code_for_exception(exc) == 408

    # Test git errors -> 500
    exc = GitOperationError("test", "commit")
    assert middleware._get_status_code_for_exception(exc) == 500
