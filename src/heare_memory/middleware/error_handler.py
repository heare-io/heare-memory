"""Enhanced error handling middleware for comprehensive exception management."""

import logging
import traceback
import uuid
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from ..exceptions import (
    AuthenticationError,
    ConcurrentModificationError,
    ConfigurationError,
    ContentValidationError,
    DiskSpaceError,
    FileNotFoundError,
    FilePermissionError,
    FileSystemError,
    GitOperationError,
    InvalidPathError,
    InvalidSearchQueryError,
    MemoryNodeExistsError,
    MemoryNodeNotFoundError,
    MemoryServiceException,
    RateLimitError,
    ReadOnlyModeError,
    SearchError,
    SearchTimeoutError,
    ServiceUnavailableError,
    ValidationError,
)
from ..models.errors import ErrorResponse, ValidationErrorDetail

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware for comprehensive exception handling and formatting.

    This middleware catches all exceptions, maps them to appropriate HTTP status codes,
    formats error responses consistently, and provides comprehensive logging with
    request context and correlation IDs.
    """

    def __init__(self, app: Any, include_debug_info: bool = False):
        """Initialize error handler middleware.

        Args:
            app: The ASGI application
            include_debug_info: Whether to include debug information in error responses
        """
        super().__init__(app)
        self.include_debug_info = include_debug_info

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Handle request and catch exceptions with comprehensive error formatting.

        Args:
            request: The incoming request
            call_next: The next middleware or endpoint

        Returns:
            Response: The response, possibly with error formatting
        """
        # Generate correlation ID for error tracking
        request_id = str(uuid.uuid4())

        # Store request ID in request state for access by other components
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            return response

        except HTTPException:
            # Re-raise HTTP exceptions to let FastAPI handle them
            # FastAPI will format these according to its own standards
            raise

        except PydanticValidationError as exc:
            # Handle Pydantic validation errors with detailed field information
            return await self._handle_pydantic_validation_error(exc, request, request_id)

        except MemoryServiceException as exc:
            # Handle our custom exceptions with proper status codes and formatting
            return await self._handle_memory_service_exception(exc, request, request_id)

        except Exception as exc:
            # Handle unexpected exceptions with proper logging and sanitized responses
            return await self._handle_unexpected_exception(exc, request, request_id)

    async def _handle_pydantic_validation_error(
        self,
        exc: PydanticValidationError,
        request: Request,
        request_id: str,
    ) -> JSONResponse:
        """Handle Pydantic validation errors with detailed field information.

        Args:
            exc: The Pydantic validation error
            request: The request that caused the error
            request_id: Unique request identifier

        Returns:
            JSONResponse with formatted validation error
        """
        logger.warning(
            "Validation error in request %s %s [%s]: %s",
            request.method,
            request.url,
            request_id,
            exc,
        )

        # Convert Pydantic errors to our format
        field_errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            field_errors.append(
                ValidationErrorDetail(
                    field=field_path,
                    message=error["msg"],
                    invalid_value=error.get("input"),
                    constraint=error["type"],
                )
            )

        error_response = ErrorResponse.validation_error(
            message="Request validation failed",
            field_errors=field_errors,
            path=str(request.url.path),
            request_id=request_id,
        )

        return JSONResponse(
            status_code=422,  # Unprocessable Entity for validation errors
            content=error_response.model_dump(),
        )

    async def _handle_memory_service_exception(
        self,
        exc: MemoryServiceException,
        request: Request,
        request_id: str,
    ) -> JSONResponse:
        """Handle custom memory service exceptions with proper status mapping.

        Args:
            exc: The memory service exception
            request: The request that caused the error
            request_id: Unique request identifier

        Returns:
            JSONResponse with formatted error response
        """
        # Map exception types to appropriate status codes
        status_code = self._get_status_code_for_exception(exc)

        # Log error with appropriate level based on status code
        if status_code >= 500:
            logger.error(
                "Server error in request %s %s [%s]: %s",
                request.method,
                request.url,
                request_id,
                exc,
                exc_info=exc,
            )
        elif status_code >= 400:
            logger.warning(
                "Client error in request %s %s [%s]: %s",
                request.method,
                request.url,
                request_id,
                exc,
            )
        else:
            logger.info(
                "Request handled with error %s %s [%s]: %s",
                request.method,
                request.url,
                request_id,
                exc,
            )

        # Create error response from exception
        error_response = ErrorResponse.from_exception(
            exc=exc,
            path=str(request.url.path),
            request_id=request_id,
        )

        # Add debug information if enabled and this is a server error
        if self.include_debug_info and status_code >= 500:
            error_response.details["debug"] = {
                "exception_type": type(exc).__name__,
                "traceback": traceback.format_exc().split("\n"),
            }

        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump(),
        )

    async def _handle_unexpected_exception(
        self,
        exc: Exception,
        request: Request,
        request_id: str,
    ) -> JSONResponse:
        """Handle unexpected exceptions with proper logging and sanitized responses.

        Args:
            exc: The unexpected exception
            request: The request that caused the error
            request_id: Unique request identifier

        Returns:
            JSONResponse with generic error response
        """
        logger.error(
            "Unexpected exception in request %s %s [%s]: %s",
            request.method,
            request.url,
            request_id,
            exc,
            exc_info=exc,
        )

        # Create generic error response to avoid leaking internal details
        error_response = ErrorResponse.internal_server_error(
            message="An internal server error occurred",
            path=str(request.url.path),
            request_id=request_id,
            include_debug_info=self.include_debug_info,
        )

        # Add debug information if enabled
        if self.include_debug_info:
            error_response.details.update(
                {
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "traceback": traceback.format_exc().split("\n"),
                }
            )

        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(),
        )

    def _get_status_code_for_exception(self, exc: MemoryServiceException) -> int:
        """Get appropriate HTTP status code for a memory service exception.

        Args:
            exc: The memory service exception

        Returns:
            HTTP status code
        """
        # Use the status code from the exception if available
        if hasattr(exc, "status_code") and exc.status_code:
            return exc.status_code

        # Fallback mapping based on exception type
        exception_status_map = {
            # Validation errors (400 Bad Request)
            ValidationError: 400,
            InvalidPathError: 400,
            ContentValidationError: 400,
            InvalidSearchQueryError: 400,
            # Authentication/Authorization errors (403 Forbidden)
            AuthenticationError: 403,
            ReadOnlyModeError: 403,
            FilePermissionError: 403,
            # Not found errors (404 Not Found)
            MemoryNodeNotFoundError: 404,
            FileNotFoundError: 404,
            # Conflict errors (409 Conflict)
            MemoryNodeExistsError: 409,
            ConcurrentModificationError: 409,
            # Rate limiting (429 Too Many Requests)
            RateLimitError: 429,
            # Service unavailable (503 Service Unavailable)
            ServiceUnavailableError: 503,
            # File system errors (500 Internal Server Error)
            FileSystemError: 500,
            DiskSpaceError: 507,  # Insufficient Storage
            # Git operation errors (500 Internal Server Error)
            GitOperationError: 500,
            # Search errors (500 Internal Server Error, timeout gets 408)
            SearchError: 500,
            SearchTimeoutError: 408,  # Request Timeout
            # Configuration errors (500 Internal Server Error)
            ConfigurationError: 500,
        }

        # Get status code based on exception type hierarchy
        for exc_type, status_code in exception_status_map.items():
            if isinstance(exc, exc_type):
                return status_code

        # Default to 500 for unknown custom exceptions
        return 500
