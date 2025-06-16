"""Authentication middleware for memory service."""

import logging
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..models.auth import (
    AuthContext,
    AuthenticationResponse,
    OperationType,
    ReadOnlyModeError,
    get_operation_type,
    is_public_endpoint,
)

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for handling read-only mode and request validation.

    This middleware:
    - Detects read-only mode and blocks write operations
    - Adds authentication context to requests
    - Allows public endpoints to bypass authentication
    - Handles CORS preflight requests
    - Provides consistent error responses
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through authentication middleware.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response
        """
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())

        # Extract request details
        method = request.method
        path = request.url.path

        # Determine operation type
        operation_type = get_operation_type(method, path)

        # Check if this is a public endpoint that bypasses authentication
        bypass_auth = is_public_endpoint(path)

        # Create authentication context
        auth_context = AuthContext(
            request_id=request_id,
            read_only_mode=settings.is_read_only,
            github_token_configured=bool(settings.github_token),
            operation_type=operation_type,
            bypass_auth=bypass_auth,
        )

        # Add authentication context to request state
        request.state.auth = auth_context

        logger.debug(
            f"Request {request_id}: {method} {path} - "
            f"operation={operation_type.value}, bypass={bypass_auth}, "
            f"read_only={auth_context.read_only_mode}"
        )

        try:
            # Perform authentication checks
            await self._check_authentication(request, auth_context)

            # Continue to next middleware or endpoint
            response = await call_next(request)

            # Add request ID to response headers for tracking
            response.headers["X-Request-ID"] = request_id

            return response

        except ReadOnlyModeError as e:
            # Handle read-only mode violations
            logger.warning(
                f"Request {request_id}: Read-only mode violation - {method} {path}: {e.message}"
            )

            return self._create_error_response(
                status_code=403,
                error_code=e.error_code,
                message=e.message,
                details=e.details,
                request_id=request_id,
            )

        except Exception as e:
            # Handle unexpected authentication errors
            logger.error(
                f"Request {request_id}: Authentication error - {method} {path}: {e}", exc_info=True
            )

            return self._create_error_response(
                status_code=500,
                error_code="internal_error",
                message="Internal authentication error occurred",
                details={"path": path, "method": method},
                request_id=request_id,
            )

    async def _check_authentication(self, request: Request, auth_context: AuthContext) -> None:
        """
        Perform authentication checks based on context.

        Args:
            request: HTTP request
            auth_context: Authentication context

        Raises:
            ReadOnlyModeError: If write operation attempted in read-only mode
        """
        # Skip authentication for public endpoints
        if auth_context.bypass_auth:
            logger.debug(f"Request {auth_context.request_id}: Bypassing auth for public endpoint")
            return

        # Skip authentication for read operations
        if auth_context.operation_type in (OperationType.READ, OperationType.OPTIONS):
            logger.debug(f"Request {auth_context.request_id}: Allowing read/options operation")
            return

        # Check for write operations in read-only mode
        if auth_context.read_only_mode and auth_context.operation_type == OperationType.WRITE:
            # Extract path from request for better error context
            path = request.url.path
            raise ReadOnlyModeError(operation="write", path=path)

        logger.debug(f"Request {auth_context.request_id}: Authentication checks passed")

    def _create_error_response(
        self, status_code: int, error_code: str, message: str, details: dict, request_id: str
    ) -> JSONResponse:
        """
        Create a standardized error response.

        Args:
            status_code: HTTP status code
            error_code: Application error code
            message: Human-readable error message
            details: Additional error context
            request_id: Request identifier

        Returns:
            JSON error response
        """
        error_response = AuthenticationResponse(error=error_code, message=message, details=details)

        return JSONResponse(
            status_code=status_code,
            content=error_response.dict(),
            headers={"X-Request-ID": request_id},
        )


def get_auth_context(request: Request) -> AuthContext | None:
    """
    Get authentication context from request state.

    Args:
        request: HTTP request

    Returns:
        Authentication context if available, None otherwise
    """
    return getattr(request.state, "auth", None)


def require_write_access(request: Request) -> None:
    """
    Ensure request has write access, raise error if in read-only mode.

    Args:
        request: HTTP request

    Raises:
        ReadOnlyModeError: If service is in read-only mode
    """
    auth_context = get_auth_context(request)

    if auth_context and auth_context.read_only_mode:
        path = request.url.path
        raise ReadOnlyModeError(operation="write", path=path)
