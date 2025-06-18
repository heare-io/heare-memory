"""Tests for custom exception classes and their hierarchy."""

from src.heare_memory.exceptions import (
    AuthenticationError,
    ConcurrentModificationError,
    ConfigurationError,
    ContentValidationError,
    DiskSpaceError,
    FileNotFoundError,
    FilePermissionError,
    FileSystemError,
    GitCommitError,
    GitOperationError,
    GitPushError,
    GitRepositoryError,
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


class TestMemoryServiceException:
    """Test the base MemoryServiceException class."""

    def test_basic_initialization(self):
        """Test basic exception initialization."""
        exc = MemoryServiceException("Test message")

        assert str(exc) == "Test message"
        assert exc.message == "Test message"
        assert exc.error_code == "memory_service_exception"
        assert exc.details == {}
        assert exc.status_code == 500

    def test_custom_parameters(self):
        """Test initialization with custom parameters."""
        details = {"key": "value", "number": 42}
        exc = MemoryServiceException(
            message="Custom message",
            error_code="custom_error",
            details=details,
            status_code=400,
        )

        assert exc.message == "Custom message"
        assert exc.error_code == "custom_error"
        assert exc.details == details
        assert exc.status_code == 400

    def test_default_error_code_generation(self):
        """Test automatic error code generation from class name."""
        # Test with the base class
        exc = MemoryServiceException("test")
        assert exc.error_code == "memory_service_exception"

        # Test with a derived class
        exc = MemoryNodeNotFoundError("test/path.md")
        assert exc.error_code == "memory_node_not_found_error"


class TestValidationErrors:
    """Test validation-related exception classes."""

    def test_validation_error_basic(self):
        """Test basic ValidationError functionality."""
        exc = ValidationError("Invalid input")

        assert exc.message == "Invalid input"
        assert exc.status_code == 400
        assert exc.error_code == "validation_error"

    def test_validation_error_with_field(self):
        """Test ValidationError with field information."""
        exc = ValidationError(
            message="Field validation failed",
            field="username",
            value="ab",
            details={"min_length": 5},
        )

        assert exc.details["field"] == "username"
        assert exc.details["invalid_value"] == "ab"
        assert exc.details["min_length"] == 5

    def test_invalid_path_error(self):
        """Test InvalidPathError."""
        exc = InvalidPathError("../invalid", "contains directory traversal")

        assert exc.status_code == 400
        assert exc.details["field"] == "path"
        assert exc.details["invalid_value"] == "../invalid"
        assert exc.details["reason"] == "contains directory traversal"
        assert "Invalid path" in exc.message

    def test_content_validation_error(self):
        """Test ContentValidationError."""
        exc = ContentValidationError("content too large", content_length=5000000)

        assert exc.status_code == 400
        assert exc.details["field"] == "content"
        assert exc.details["reason"] == "content too large"
        assert exc.details["content_length"] == 5000000


class TestAuthenticationErrors:
    """Test authentication and authorization exception classes."""

    def test_authentication_error_basic(self):
        """Test basic AuthenticationError functionality."""
        exc = AuthenticationError("Access denied")

        assert exc.message == "Access denied"
        assert exc.status_code == 403
        assert exc.error_code == "authentication_error"

    def test_authentication_error_with_operation(self):
        """Test AuthenticationError with operation information."""
        exc = AuthenticationError(
            message="Permission denied",
            operation="write",
            details={"resource": "memory_node"},
        )

        assert exc.details["operation"] == "write"
        assert exc.details["resource"] == "memory_node"

    def test_read_only_mode_error(self):
        """Test ReadOnlyModeError with default and custom parameters."""
        # Test with defaults
        exc = ReadOnlyModeError()

        assert exc.status_code == 403
        assert "read-only mode" in exc.message
        assert exc.details["read_only"] is True
        assert exc.details["operation"] == "write"

        # Test with custom parameters
        exc = ReadOnlyModeError(operation="delete", path="test/file.md")

        assert exc.details["operation"] == "delete"
        assert exc.details["path"] == "test/file.md"


class TestMemoryNodeErrors:
    """Test memory node specific exception classes."""

    def test_memory_node_not_found_error(self):
        """Test MemoryNodeNotFoundError."""
        exc = MemoryNodeNotFoundError("test/missing.md")

        assert exc.status_code == 404
        assert exc.details["path"] == "test/missing.md"
        assert "not found" in exc.message
        assert "test/missing.md" in exc.message

    def test_memory_node_exists_error(self):
        """Test MemoryNodeExistsError."""
        exc = MemoryNodeExistsError("test/existing.md")

        assert exc.status_code == 409
        assert exc.details["path"] == "test/existing.md"
        assert "already exists" in exc.message
        assert "test/existing.md" in exc.message

    def test_concurrent_modification_error(self):
        """Test ConcurrentModificationError."""
        exc = ConcurrentModificationError(
            "test/file.md",
            expected_sha="abc123",
            actual_sha="def456",
        )

        assert exc.status_code == 409
        assert exc.details["path"] == "test/file.md"
        assert exc.details["expected_sha"] == "abc123"
        assert exc.details["actual_sha"] == "def456"
        assert "Concurrent modification" in exc.message

    def test_concurrent_modification_error_minimal(self):
        """Test ConcurrentModificationError with minimal parameters."""
        exc = ConcurrentModificationError("test/file.md")

        assert exc.details["path"] == "test/file.md"
        assert "expected_sha" not in exc.details
        assert "actual_sha" not in exc.details


class TestFileSystemErrors:
    """Test file system related exception classes."""

    def test_file_system_error_basic(self):
        """Test basic FileSystemError functionality."""
        exc = FileSystemError("File operation failed")

        assert exc.message == "File operation failed"
        assert exc.status_code == 500
        assert exc.error_code == "file_system_error"

    def test_file_system_error_with_context(self):
        """Test FileSystemError with path and operation context."""
        exc = FileSystemError(
            message="Operation failed",
            path="test/file.md",
            operation="write",
            details={"errno": 28},
        )

        assert exc.details["path"] == "test/file.md"
        assert exc.details["operation"] == "write"
        assert exc.details["errno"] == 28

    def test_file_not_found_error(self):
        """Test FileNotFoundError."""
        exc = FileNotFoundError("test/missing.md", operation="read")

        assert exc.status_code == 404
        assert exc.details["path"] == "test/missing.md"
        assert exc.details["operation"] == "read"
        assert "File not found" in exc.message

    def test_file_permission_error(self):
        """Test FilePermissionError."""
        exc = FilePermissionError("test/protected.md", operation="write")

        assert exc.status_code == 403
        assert exc.details["path"] == "test/protected.md"
        assert exc.details["operation"] == "write"
        assert "Permission denied" in exc.message

    def test_disk_space_error(self):
        """Test DiskSpaceError."""
        exc = DiskSpaceError("test/large.md", operation="write")

        assert exc.status_code == 500  # Default, can be overridden
        assert exc.details["path"] == "test/large.md"
        assert exc.details["operation"] == "write"
        assert "Insufficient disk space" in exc.message


class TestGitErrors:
    """Test Git operation exception classes."""

    def test_git_operation_error_basic(self):
        """Test basic GitOperationError functionality."""
        exc = GitOperationError("Git operation failed", "commit")

        assert exc.message == "Git operation failed"
        assert exc.details["git_operation"] == "commit"
        assert exc.status_code == 500

    def test_git_operation_error_with_path(self):
        """Test GitOperationError with file path."""
        exc = GitOperationError(
            message="Commit failed",
            operation="commit",
            path="test/file.md",
            details={"exit_code": 1},
        )

        assert exc.details["git_operation"] == "commit"
        assert exc.details["path"] == "test/file.md"
        assert exc.details["exit_code"] == 1

    def test_git_repository_error(self):
        """Test GitRepositoryError."""
        exc = GitRepositoryError("Repository not initialized", "init")

        assert exc.details["git_operation"] == "init"
        assert "Repository not initialized" in exc.message

    def test_git_commit_error(self):
        """Test GitCommitError."""
        exc = GitCommitError("Nothing to commit", path="test/file.md")

        assert exc.details["git_operation"] == "commit"
        assert exc.details["path"] == "test/file.md"
        assert "Nothing to commit" in exc.message

    def test_git_push_error(self):
        """Test GitPushError."""
        exc = GitPushError("Push rejected", remote="origin")

        assert exc.details["git_operation"] == "push"
        assert exc.details["remote"] == "origin"
        assert "Push rejected" in exc.message


class TestSearchErrors:
    """Test search operation exception classes."""

    def test_search_error_basic(self):
        """Test basic SearchError functionality."""
        exc = SearchError("Search operation failed")

        assert exc.message == "Search operation failed"
        assert exc.status_code == 500
        assert exc.error_code == "search_error"

    def test_search_error_with_context(self):
        """Test SearchError with query and backend context."""
        exc = SearchError(
            message="Search failed",
            query="test query",
            backend="ripgrep",
            details={"exit_code": 2},
        )

        assert exc.details["query"] == "test query"
        assert exc.details["backend"] == "ripgrep"
        assert exc.details["exit_code"] == 2

    def test_search_timeout_error(self):
        """Test SearchTimeoutError."""
        exc = SearchTimeoutError("complex query", 30.5)

        assert exc.status_code == 500  # Base class default, might be overridden
        assert exc.details["query"] == "complex query"
        assert exc.details["timeout_seconds"] == 30.5
        assert "timed out after 30.5 seconds" in exc.message

    def test_invalid_search_query_error(self):
        """Test InvalidSearchQueryError."""
        exc = InvalidSearchQueryError("*[", "invalid regex syntax")

        assert exc.status_code == 400
        assert exc.details["field"] == "query"
        assert exc.details["invalid_value"] == "*["
        assert exc.details["reason"] == "invalid regex syntax"
        assert "Invalid search query" in exc.message


class TestServiceLevelErrors:
    """Test service-level exception classes."""

    def test_service_unavailable_error(self):
        """Test ServiceUnavailableError."""
        exc = ServiceUnavailableError("maintenance mode", retry_after=300)

        assert exc.status_code == 503
        assert exc.details["reason"] == "maintenance mode"
        assert exc.details["retry_after"] == 300
        assert "temporarily unavailable" in exc.message

    def test_service_unavailable_error_no_retry(self):
        """Test ServiceUnavailableError without retry_after."""
        exc = ServiceUnavailableError("database connection lost")

        assert exc.details["reason"] == "database connection lost"
        assert "retry_after" not in exc.details

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        exc = RateLimitError(100, 3600, reset_time=1234567890)

        assert exc.status_code == 429
        assert exc.details["limit"] == 100
        assert exc.details["window"] == 3600
        assert exc.details["reset_time"] == 1234567890
        assert "Rate limit exceeded" in exc.message

    def test_rate_limit_error_no_reset_time(self):
        """Test RateLimitError without reset_time."""
        exc = RateLimitError(50, 60)

        assert exc.details["limit"] == 50
        assert exc.details["window"] == 60
        assert "reset_time" not in exc.details

    def test_configuration_error(self):
        """Test ConfigurationError."""
        exc = ConfigurationError("github_token", "token is invalid")

        assert exc.status_code == 500
        assert exc.details["setting"] == "github_token"
        assert exc.details["reason"] == "token is invalid"
        assert "Configuration error for 'github_token'" in exc.message


class TestExceptionHierarchy:
    """Test the exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from MemoryServiceException."""
        custom_exceptions = [
            ValidationError("test"),
            AuthenticationError("test"),
            ReadOnlyModeError(),
            InvalidPathError("test", "reason"),
            MemoryNodeNotFoundError("test"),
            MemoryNodeExistsError("test"),
            ContentValidationError("test"),
            FileSystemError("test"),
            FileNotFoundError("test"),
            FilePermissionError("test", "read"),
            DiskSpaceError("test"),
            GitOperationError("test", "commit"),
            GitRepositoryError("test"),
            GitCommitError("test"),
            GitPushError("test"),
            SearchError("test"),
            SearchTimeoutError("test", 30),
            InvalidSearchQueryError("test", "reason"),
            ConcurrentModificationError("test"),
            ServiceUnavailableError("test"),
            RateLimitError(100, 3600),
            ConfigurationError("test", "reason"),
        ]

        for exc in custom_exceptions:
            assert isinstance(exc, MemoryServiceException)

    def test_exception_categorization(self):
        """Test that exceptions are properly categorized."""
        # Validation errors
        validation_errors = [
            ValidationError("test"),
            InvalidPathError("test", "reason"),
            ContentValidationError("test"),
            InvalidSearchQueryError("test", "reason"),
        ]

        for exc in validation_errors:
            assert isinstance(exc, ValidationError)
            assert exc.status_code == 400

        # Authentication errors
        auth_errors = [
            AuthenticationError("test"),
            ReadOnlyModeError(),
        ]

        for exc in auth_errors:
            assert isinstance(exc, AuthenticationError)
            assert exc.status_code == 403

        # File system errors
        fs_errors = [
            FileSystemError("test"),
            FileNotFoundError("test"),
            FilePermissionError("test", "read"),
            DiskSpaceError("test"),
        ]

        for exc in fs_errors:
            assert isinstance(exc, FileSystemError)

        # Git errors
        git_errors = [
            GitOperationError("test", "commit"),
            GitRepositoryError("test"),
            GitCommitError("test"),
            GitPushError("test"),
        ]

        for exc in git_errors:
            assert isinstance(exc, GitOperationError)

        # Search errors
        search_errors = [
            SearchError("test"),
            SearchTimeoutError("test", 30),
        ]

        for exc in search_errors:
            assert isinstance(exc, SearchError)


class TestBackwardCompatibility:
    """Test backward compatibility with existing exception names."""

    def test_compatibility_aliases(self):
        """Test that compatibility aliases work correctly."""
        # These should import without error and be equivalent
        from src.heare_memory.exceptions import (
            FileManagerError,
            MemoryNotFoundError,
            MemoryServiceError,
            PathValidationError,
            SearchBackendError,
        )

        # Test that aliases point to the correct classes
        assert FileManagerError is FileSystemError
        assert MemoryNotFoundError is MemoryNodeNotFoundError
        assert MemoryServiceError is MemoryServiceException
        assert PathValidationError is InvalidPathError
        assert SearchBackendError is SearchError

    def test_existing_code_compatibility(self):
        """Test that existing code patterns still work."""
        # Test old-style exception usage
        try:
            from src.heare_memory.exceptions import PathValidationError

            raise PathValidationError("test/path", "invalid format")
        except InvalidPathError as exc:
            assert exc.details["field"] == "path"
            assert exc.details["invalid_value"] == "test/path"
            assert exc.details["reason"] == "invalid format"

    def test_invalid_search_query_error(self):
        """Test InvalidSearchQueryError."""
        exc = InvalidSearchQueryError("*[", "invalid regex syntax")

        assert exc.status_code == 400
        assert exc.details["field"] == "query"
        assert exc.details["invalid_value"] == "*["
        assert exc.details["reason"] == "invalid regex syntax"
        assert "Invalid search query" in exc.message
