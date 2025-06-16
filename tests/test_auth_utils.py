"""Tests for authentication utility functions."""

from src.heare_memory.models.auth import (
    OperationType,
    get_operation_type,
    is_public_endpoint,
    is_write_operation,
)


class TestAuthenticationUtils:
    """Test authentication utility functions."""

    def test_is_write_operation_get_requests(self):
        """Test that GET requests are not write operations."""
        assert is_write_operation("GET", "/memory/test") is False
        assert is_write_operation("get", "/memory/test") is False  # Case insensitive
        assert is_write_operation("HEAD", "/memory/test") is False

    def test_is_write_operation_write_methods(self):
        """Test that write methods are detected as write operations."""
        assert is_write_operation("POST", "/memory/test") is True
        assert is_write_operation("PUT", "/memory/test") is True
        assert is_write_operation("PATCH", "/memory/test") is True
        assert is_write_operation("DELETE", "/memory/test") is True

    def test_is_write_operation_options(self):
        """Test that OPTIONS requests are not write operations."""
        assert is_write_operation("OPTIONS", "/memory/test") is False

    def test_is_public_endpoint_health(self):
        """Test that health endpoint is public."""
        assert is_public_endpoint("/health") is True
        assert is_public_endpoint("/health/") is True
        assert is_public_endpoint("health") is True

    def test_is_public_endpoint_docs(self):
        """Test that documentation endpoints are public."""
        assert is_public_endpoint("/docs") is True
        assert is_public_endpoint("/redoc") is True
        assert is_public_endpoint("/openapi.json") is True
        assert is_public_endpoint("/schema") is True

    def test_is_public_endpoint_memory_endpoints(self):
        """Test that memory endpoints are not public."""
        assert is_public_endpoint("/memory/test") is False
        assert is_public_endpoint("/memory/") is False
        assert is_public_endpoint("/memory") is False

    def test_is_public_endpoint_root(self):
        """Test that root endpoint is public."""
        assert is_public_endpoint("/") is True
        assert is_public_endpoint("") is True

    def test_is_public_endpoint_query_params(self):
        """Test that query parameters are ignored for public endpoint detection."""
        assert is_public_endpoint("/health?status=check") is True
        assert is_public_endpoint("/memory/test?include_content=true") is False

    def test_get_operation_type_read(self):
        """Test operation type detection for read operations."""
        assert get_operation_type("GET", "/memory/test") == OperationType.READ
        assert get_operation_type("HEAD", "/memory/test") == OperationType.READ

    def test_get_operation_type_write(self):
        """Test operation type detection for write operations."""
        assert get_operation_type("POST", "/memory/test") == OperationType.WRITE
        assert get_operation_type("PUT", "/memory/test") == OperationType.WRITE
        assert get_operation_type("PATCH", "/memory/test") == OperationType.WRITE
        assert get_operation_type("DELETE", "/memory/test") == OperationType.WRITE

    def test_get_operation_type_options(self):
        """Test operation type detection for OPTIONS requests."""
        assert get_operation_type("OPTIONS", "/memory/test") == OperationType.OPTIONS

    def test_get_operation_type_health(self):
        """Test operation type detection for health endpoints."""
        assert get_operation_type("GET", "/health") == OperationType.HEALTH
        assert get_operation_type("POST", "/health") == OperationType.HEALTH  # Even if POST

    def test_get_operation_type_schema(self):
        """Test operation type detection for schema endpoints."""
        assert get_operation_type("GET", "/schema") == OperationType.SCHEMA
        assert get_operation_type("GET", "/docs") == OperationType.SCHEMA
        assert get_operation_type("GET", "/redoc") == OperationType.SCHEMA
        assert get_operation_type("GET", "/openapi.json") == OperationType.SCHEMA

    def test_get_operation_type_case_insensitive(self):
        """Test that operation type detection is case insensitive."""
        assert get_operation_type("get", "/memory/test") == OperationType.READ
        assert get_operation_type("PUT", "/MEMORY/TEST") == OperationType.WRITE
        assert get_operation_type("GET", "/HEALTH") == OperationType.HEALTH

    def test_endpoint_normalization(self):
        """Test that endpoint paths are properly normalized."""
        # Leading/trailing slashes should be handled
        assert is_public_endpoint("health") is True
        assert is_public_endpoint("/health") is True
        assert is_public_endpoint("/health/") is True
        assert is_public_endpoint("//health//") is True

        # Case sensitivity
        assert is_public_endpoint("/HEALTH") is True
        assert is_public_endpoint("/Health") is True
