"""Custom exception classes for the Heare Memory service.

This module defines the complete hierarchy of custom exceptions used throughout
the memory service, providing proper categorization and standardized error handling.
"""

from typing import Any


class MemoryServiceException(Exception):  # noqa: N818
    """Base exception for all memory service operations.

    This serves as the root exception class for all custom exceptions
    in the memory service, providing common functionality and structure.
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ):
        """Initialize memory service exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (defaults to class name in snake_case)
            details: Additional context and error details
            status_code: HTTP status code to return (default: 500)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._get_default_error_code()
        self.details = details or {}
        self.status_code = status_code

    def _get_default_error_code(self) -> str:
        """Generate default error code from class name."""
        # Convert class name from CamelCase to snake_case
        class_name = self.__class__.__name__
        error_code = ""
        for i, char in enumerate(class_name):
            if char.isupper() and i > 0:
                error_code += "_"
            error_code += char.lower()
        return error_code


class ValidationError(MemoryServiceException):
    """Base class for validation-related errors."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize validation error.

        Args:
            message: Human-readable error message
            field: Name of the field that failed validation
            value: The invalid value that caused the error
            details: Additional validation context
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["invalid_value"] = str(value)

        super().__init__(
            message=message,
            details=error_details,
            status_code=400,
        )


class AuthenticationError(MemoryServiceException):
    """Base exception for authentication and authorization errors."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize authentication error.

        Args:
            message: Human-readable error message
            operation: The operation that was attempted
            details: Additional authentication context
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            details=error_details,
            status_code=403,
        )


class ReadOnlyModeError(AuthenticationError):
    """Raised when write operation is attempted in read-only mode."""

    def __init__(self, operation: str = "write", path: str | None = None):
        """Initialize read-only mode error.

        Args:
            operation: The write operation that was attempted
            path: The path that was being accessed
        """
        message = (
            f"Service is in read-only mode. Configure GITHUB_TOKEN for {operation} operations."
        )
        details = {
            "read_only": True,
            "operation": operation,
        }
        if path:
            details["path"] = path

        super().__init__(message=message, operation=operation, details=details)


class InvalidPathError(ValidationError):
    """Raised for invalid or unsafe memory paths."""

    def __init__(self, path: str, reason: str):
        """Initialize invalid path error.

        Args:
            path: The invalid path
            reason: Explanation of why the path is invalid
        """
        message = f"Invalid path '{path}': {reason}"
        super().__init__(
            message=message,
            field="path",
            value=path,
            details={"reason": reason},
        )


class MemoryNodeNotFoundError(MemoryServiceException):
    """Raised when a requested memory node doesn't exist."""

    def __init__(self, path: str):
        """Initialize memory node not found error.

        Args:
            path: The path that was not found
        """
        message = f"Memory node not found: {path}"
        super().__init__(
            message=message,
            details={"path": path},
            status_code=404,
        )


class MemoryNodeExistsError(MemoryServiceException):
    """Raised when trying to create a memory node that already exists."""

    def __init__(self, path: str):
        """Initialize memory node exists error.

        Args:
            path: The path that already exists
        """
        message = f"Memory node already exists: {path}"
        super().__init__(
            message=message,
            details={"path": path},
            status_code=409,
        )


class ContentValidationError(ValidationError):
    """Raised when memory node content fails validation."""

    def __init__(self, reason: str, content_length: int | None = None):
        """Initialize content validation error.

        Args:
            reason: Explanation of why the content is invalid
            content_length: Length of the invalid content if relevant
        """
        message = f"Invalid content: {reason}"
        details = {"reason": reason}
        if content_length is not None:
            details["content_length"] = content_length

        super().__init__(
            message=message,
            field="content",
            details=details,
        )


class FileSystemError(MemoryServiceException):
    """Base class for file system related errors."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize file system error.

        Args:
            message: Human-readable error message
            path: The file path involved in the error
            operation: The file operation that failed
            details: Additional file system context
        """
        error_details = details or {}
        if path:
            error_details["path"] = path
        if operation:
            error_details["operation"] = operation

        super().__init__(
            message=message,
            details=error_details,
            status_code=500,
        )


class FileNotFoundError(FileSystemError):
    """Raised when a file operation fails because the file doesn't exist."""

    def __init__(self, path: str, operation: str = "read"):
        """Initialize file not found error.

        Args:
            path: The path that was not found
            operation: The operation that was attempted
        """
        message = f"File not found: {path}"
        super().__init__(
            message=message,
            path=path,
            operation=operation,
            details={"path": path, "operation": operation},
        )
        self.status_code = 404


class FilePermissionError(FileSystemError):
    """Raised when a file operation fails due to insufficient permissions."""

    def __init__(self, path: str, operation: str):
        """Initialize file permission error.

        Args:
            path: The path that couldn't be accessed
            operation: The operation that was attempted
        """
        message = f"Permission denied for {operation} operation on: {path}"
        super().__init__(
            message=message,
            path=path,
            operation=operation,
            details={"path": path, "operation": operation},
        )
        self.status_code = 403


class DiskSpaceError(FileSystemError):
    """Raised when a file operation fails due to insufficient disk space."""

    def __init__(self, path: str, operation: str = "write"):
        """Initialize disk space error.

        Args:
            path: The path where the operation failed
            operation: The operation that was attempted
        """
        message = f"Insufficient disk space for {operation} operation: {path}"
        super().__init__(
            message=message,
            path=path,
            operation=operation,
            details={"path": path, "operation": operation},
        )


class GitOperationError(MemoryServiceException):
    """Base class for git operation related errors."""

    def __init__(
        self,
        message: str,
        operation: str,
        path: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize git operation error.

        Args:
            message: Human-readable error message
            operation: The git operation that failed
            path: The file path involved if applicable
            details: Additional git operation context
        """
        error_details = details or {}
        error_details["git_operation"] = operation
        if path:
            error_details["path"] = path

        super().__init__(
            message=message,
            details=error_details,
            status_code=500,
        )


class GitRepositoryError(GitOperationError):
    """Raised for git repository setup and configuration errors."""

    def __init__(self, message: str, operation: str = "repository"):
        """Initialize git repository error.

        Args:
            message: Human-readable error message
            operation: The repository operation that failed
        """
        super().__init__(message=message, operation=operation)


class GitCommitError(GitOperationError):
    """Raised for git commit operation errors."""

    def __init__(self, message: str, path: str | None = None):
        """Initialize git commit error.

        Args:
            message: Human-readable error message
            path: The file path involved in the commit
        """
        super().__init__(message=message, operation="commit", path=path)


class GitPushError(GitOperationError):
    """Raised for git push operation errors."""

    def __init__(self, message: str, remote: str | None = None):
        """Initialize git push error.

        Args:
            message: Human-readable error message
            remote: The remote repository that failed
        """
        details = {}
        if remote:
            details["remote"] = remote

        super().__init__(message=message, operation="push", details=details)


class SearchError(MemoryServiceException):
    """Base class for search operation errors."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        backend: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize search error.

        Args:
            message: Human-readable error message
            query: The search query that failed
            backend: The search backend that was used
            details: Additional search context
        """
        error_details = details or {}
        if query:
            error_details["query"] = query
        if backend:
            error_details["backend"] = backend

        super().__init__(
            message=message,
            details=error_details,
            status_code=500,
        )


class SearchTimeoutError(SearchError):
    """Raised when a search operation times out."""

    def __init__(self, query: str, timeout_seconds: float):
        """Initialize search timeout error.

        Args:
            query: The search query that timed out
            timeout_seconds: The timeout duration in seconds
        """
        message = f"Search timed out after {timeout_seconds} seconds"
        super().__init__(
            message=message,
            query=query,
            details={"timeout_seconds": timeout_seconds},
        )


class InvalidSearchQueryError(ValidationError):
    """Raised when a search query is invalid or malformed."""

    def __init__(self, query: str, reason: str):
        """Initialize invalid search query error.

        Args:
            query: The invalid search query
            reason: Explanation of why the query is invalid
        """
        message = f"Invalid search query: {reason}"
        super().__init__(
            message=message,
            field="query",
            value=query,
            details={"reason": reason},
        )


class ConcurrentModificationError(MemoryServiceException):
    """Raised when a memory node is modified concurrently."""

    def __init__(self, path: str, expected_sha: str | None = None, actual_sha: str | None = None):
        """Initialize concurrent modification error.

        Args:
            path: The path that was concurrently modified
            expected_sha: The expected SHA value
            actual_sha: The actual SHA value found
        """
        message = f"Concurrent modification detected for: {path}"
        details = {"path": path}
        if expected_sha:
            details["expected_sha"] = expected_sha
        if actual_sha:
            details["actual_sha"] = actual_sha

        super().__init__(
            message=message,
            details=details,
            status_code=409,
        )


class ServiceUnavailableError(MemoryServiceException):
    """Raised when the service is temporarily unavailable."""

    def __init__(self, reason: str, retry_after: int | None = None):
        """Initialize service unavailable error.

        Args:
            reason: Explanation of why the service is unavailable
            retry_after: Suggested retry delay in seconds
        """
        message = f"Service temporarily unavailable: {reason}"
        details = {"reason": reason}
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            details=details,
            status_code=503,
        )


class RateLimitError(MemoryServiceException):
    """Raised when rate limits are exceeded."""

    def __init__(self, limit: int, window: int, reset_time: int | None = None):
        """Initialize rate limit error.

        Args:
            limit: The rate limit that was exceeded
            window: The time window in seconds
            reset_time: When the rate limit resets (Unix timestamp)
        """
        message = f"Rate limit exceeded: {limit} requests per {window} seconds"
        details = {
            "limit": limit,
            "window": window,
        }
        if reset_time:
            details["reset_time"] = reset_time

        super().__init__(
            message=message,
            details=details,
            status_code=429,
        )


class ConfigurationError(MemoryServiceException):
    """Raised when there are configuration or setup errors."""

    def __init__(self, setting: str, reason: str):
        """Initialize configuration error.

        Args:
            setting: The configuration setting that is invalid
            reason: Explanation of the configuration issue
        """
        message = f"Configuration error for '{setting}': {reason}"
        super().__init__(
            message=message,
            details={"setting": setting, "reason": reason},
            status_code=500,
        )


# Exception hierarchy for compatibility with existing code
# These are aliases to maintain backward compatibility

PathValidationError = InvalidPathError
FileManagerError = FileSystemError
MemoryServiceError = MemoryServiceException
MemoryNotFoundError = MemoryNodeNotFoundError
SearchBackendError = SearchError
StartupError = ConfigurationError


# Git exceptions - these already exist in models/git.py but we provide
# compatibility aliases that inherit from our base exception
class GitError(GitOperationError):
    """Compatibility alias for git errors."""
