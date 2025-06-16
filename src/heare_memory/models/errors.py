"""Error response models for standardized API error handling."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    """Detail for a single validation error."""

    field: str = Field(description="The field that failed validation")
    message: str = Field(description="Validation error message")
    invalid_value: Any = Field(description="The value that failed validation")
    constraint: str | None = Field(description="The validation constraint that failed")


class ErrorResponse(BaseModel):
    """Standardized error response model for all API errors."""

    error: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional error context and debugging information"
    )
    path: str | None = Field(default=None, description="API path where the error occurred")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error occurrence timestamp"
    )
    request_id: str | None = Field(
        default=None, description="Unique request identifier for error tracking"
    )

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create error response from an exception.

        Args:
            exc: The exception to convert
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse with appropriate fields populated
        """
        # Import here to avoid circular imports
        from ..exceptions import MemoryServiceException

        if isinstance(exc, MemoryServiceException):
            return cls(
                error=exc.error_code,
                message=exc.message,
                details=exc.details,
                path=path,
                request_id=request_id,
            )
        else:
            # Handle standard Python exceptions
            error_code = type(exc).__name__.lower().replace("error", "_error")
            if not error_code.endswith("_error"):
                error_code += "_error"

            return cls(
                error=error_code,
                message=str(exc),
                details={"exception_type": type(exc).__name__},
                path=path,
                request_id=request_id,
            )

    @classmethod
    def validation_error(
        cls,
        message: str,
        field_errors: list[ValidationErrorDetail] | None = None,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a validation error response.

        Args:
            message: Main validation error message
            field_errors: List of field-specific validation errors
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse for validation errors
        """
        details = {}
        if field_errors:
            details["field_errors"] = [error.model_dump() for error in field_errors]

        return cls(
            error="validation_error",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )

    @classmethod
    def not_found_error(
        cls,
        resource: str,
        identifier: str | None = None,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a not found error response.

        Args:
            resource: Type of resource that was not found
            identifier: Identifier of the resource that was not found
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse for not found errors
        """
        if identifier:
            message = f"{resource} not found: {identifier}"
            details = {"resource": resource, "identifier": identifier}
        else:
            message = f"{resource} not found"
            details = {"resource": resource}

        return cls(
            error="not_found",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )

    @classmethod
    def forbidden_error(
        cls,
        operation: str,
        reason: str | None = None,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a forbidden error response.

        Args:
            operation: The operation that was forbidden
            reason: Reason why the operation was forbidden
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse for forbidden errors
        """
        message = f"Forbidden: {operation} - {reason}" if reason else f"Forbidden: {operation}"

        details = {"operation": operation}
        if reason:
            details["reason"] = reason

        return cls(
            error="forbidden",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )

    @classmethod
    def conflict_error(
        cls,
        resource: str,
        reason: str,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a conflict error response.

        Args:
            resource: The resource that has a conflict
            reason: Reason for the conflict
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse for conflict errors
        """
        message = f"Conflict with {resource}: {reason}"
        details = {"resource": resource, "reason": reason}

        return cls(
            error="conflict",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )

    @classmethod
    def internal_server_error(
        cls,
        message: str = "An internal server error occurred",
        operation: str | None = None,
        path: str | None = None,
        request_id: str | None = None,
        include_debug_info: bool = False,
    ) -> "ErrorResponse":
        """Create an internal server error response.

        Args:
            message: Error message
            operation: The operation that failed
            path: The API path where the error occurred
            request_id: Unique request identifier
            include_debug_info: Whether to include debugging information

        Returns:
            ErrorResponse for internal server errors
        """
        details = {}
        if operation:
            details["operation"] = operation
        if include_debug_info:
            details["debug"] = True

        return cls(
            error="internal_server_error",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )

    @classmethod
    def service_unavailable_error(
        cls,
        reason: str,
        retry_after: int | None = None,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a service unavailable error response.

        Args:
            reason: Reason why the service is unavailable
            retry_after: Suggested retry delay in seconds
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse for service unavailable errors
        """
        message = f"Service temporarily unavailable: {reason}"
        details = {"reason": reason}
        if retry_after:
            details["retry_after"] = retry_after

        return cls(
            error="service_unavailable",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )

    @classmethod
    def rate_limit_error(
        cls,
        limit: int,
        window: int,
        reset_time: int | None = None,
        path: str | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a rate limit error response.

        Args:
            limit: The rate limit that was exceeded
            window: The time window in seconds
            reset_time: When the rate limit resets (Unix timestamp)
            path: The API path where the error occurred
            request_id: Unique request identifier

        Returns:
            ErrorResponse for rate limit errors
        """
        message = f"Rate limit exceeded: {limit} requests per {window} seconds"
        details = {
            "limit": limit,
            "window": window,
        }
        if reset_time:
            details["reset_time"] = reset_time

        return cls(
            error="rate_limit_exceeded",
            message=message,
            details=details,
            path=path,
            request_id=request_id,
        )


class BatchErrorResponse(BaseModel):
    """Error response for batch operations with partial failures."""

    success: bool = Field(description="Whether the overall batch succeeded")
    message: str = Field(description="Overall batch operation message")
    completed: int = Field(description="Number of operations completed successfully")
    total: int = Field(description="Total number of operations")
    errors: list[ErrorResponse] = Field(description="Errors for failed operations")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Batch operation timestamp"
    )
    request_id: str | None = Field(default=None, description="Unique request identifier")


# Compatibility aliases for existing code
StandardErrorResponse = ErrorResponse
