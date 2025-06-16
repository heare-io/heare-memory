"""Authentication models and context for memory service."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuthenticationError(Exception):
    """Base authentication error."""

    def __init__(
        self,
        message: str,
        error_code: str = "authentication_error",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ReadOnlyModeError(AuthenticationError):
    """Raised when write operation is attempted in read-only mode."""

    def __init__(self, operation: str = "write", path: str | None = None):
        message = (
            f"Service is in read-only mode. Configure GITHUB_TOKEN for {operation} operations."
        )
        details = {
            "read_only": True,
            "operation": operation,
        }
        if path:
            details["path"] = path

        super().__init__(message=message, error_code="read_only_mode", details=details)


class OperationType(str, Enum):
    """Types of operations for authentication context."""

    READ = "read"
    WRITE = "write"
    HEALTH = "health"
    SCHEMA = "schema"
    OPTIONS = "options"


class AuthContext(BaseModel):
    """Authentication context for requests."""

    request_id: str = Field(description="Unique request identifier")
    timestamp: datetime = Field(description="Request timestamp", default_factory=datetime.utcnow)
    read_only_mode: bool = Field(description="Whether service is in read-only mode")
    github_token_configured: bool = Field(description="Whether GitHub token is configured")
    operation_type: OperationType = Field(description="Type of operation being performed")
    bypass_auth: bool = Field(description="Whether authentication is bypassed", default=False)

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class AuthenticationResponse(BaseModel):
    """Response model for authentication errors."""

    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(description="Additional error context")


def is_write_operation(method: str, path: str) -> bool:
    """
    Determine if a request represents a write operation.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: Request path

    Returns:
        True if this is a write operation
    """
    # GET and HEAD are always read operations
    if method.upper() in ("GET", "HEAD"):
        return False

    # OPTIONS is for CORS preflight, not a write operation
    # All other methods (POST, PUT, PATCH, DELETE) are write operations
    return method.upper() != "OPTIONS"


def is_public_endpoint(path: str) -> bool:
    """
    Determine if an endpoint should bypass authentication.

    Args:
        path: Request path

    Returns:
        True if this endpoint should be publicly accessible
    """
    # Normalize path - remove leading/trailing slashes and query parameters
    normalized_path = path.strip("/").split("?")[0].lower()

    # Public endpoints that should always be accessible
    public_paths = {
        "health",  # Health check endpoint
        "docs",  # OpenAPI documentation
        "redoc",  # ReDoc documentation
        "openapi.json",  # OpenAPI specification
        "schema",  # Schema endpoint
        "",  # Root might redirect to docs
    }

    return normalized_path in public_paths


def get_operation_type(method: str, path: str) -> OperationType:
    """
    Determine the operation type for a request.

    Args:
        method: HTTP method
        path: Request path

    Returns:
        Operation type for authentication context
    """
    if method.upper() == "OPTIONS":
        return OperationType.OPTIONS

    # Check for special endpoints
    normalized_path = path.strip("/").split("?")[0].lower()

    if normalized_path == "health":
        return OperationType.HEALTH

    if normalized_path in ("schema", "docs", "redoc", "openapi.json"):
        return OperationType.SCHEMA

    # Determine read vs write based on method
    if is_write_operation(method, path):
        return OperationType.WRITE
    else:
        return OperationType.READ
