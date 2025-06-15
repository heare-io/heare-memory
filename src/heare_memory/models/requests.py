"""Request models for the memory API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..path_utils import sanitize_path, validate_path


class MemoryCreateRequest(BaseModel):
    """Request model for creating a memory node."""

    content: str = Field(
        min_length=1,
        max_length=10_000_000,  # 10MB max content
        description="Markdown content to store",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is proper UTF-8 and has reasonable size."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")

        # Check for null bytes or other control characters
        if "\x00" in v:
            raise ValueError("Content cannot contain null bytes")

        return v


class MemoryUpdateRequest(BaseModel):
    """Request model for updating a memory node."""

    content: str = Field(
        min_length=1,
        max_length=10_000_000,  # 10MB max content
        description="Updated markdown content",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is proper UTF-8 and has reasonable size."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")

        # Check for null bytes or other control characters
        if "\x00" in v:
            raise ValueError("Content cannot contain null bytes")

        return v


class MemoryListRequest(BaseModel):
    """Request model for listing memory nodes."""

    prefix: str | None = Field(
        default=None,
        max_length=512,
        description="Directory prefix to filter by",
    )
    recursive: bool = Field(
        default=True,
        description="Whether to list files recursively",
    )
    include_content: bool = Field(
        default=False,
        description="Whether to include file content in response",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    )

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, v: str | None) -> str | None:
        """Validate prefix is safe and properly formatted."""
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        # Basic security checks
        if ".." in v or v.startswith("/") or "\x00" in v:
            raise ValueError("Invalid prefix: contains dangerous patterns")

        # Remove trailing slashes
        v = v.rstrip("/")

        return v


class SearchRequest(BaseModel):
    """Request model for searching memory content."""

    query: str = Field(
        min_length=1,
        max_length=256,
        description="Search query string",
    )
    prefix: str | None = Field(
        default=None,
        max_length=512,
        description="Directory prefix to search within",
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether search should be case sensitive",
    )
    context_lines: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Number of context lines before/after matches",
    )
    limit: int | None = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate search query for security and format."""
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")

        # Check for null bytes or other control characters
        if "\x00" in v:
            raise ValueError("Query cannot contain null bytes")

        return v

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, v: str | None) -> str | None:
        """Validate prefix is safe and properly formatted."""
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        # Basic security checks
        if ".." in v or v.startswith("/") or "\x00" in v:
            raise ValueError("Invalid prefix: contains dangerous patterns")

        # Remove trailing slashes
        v = v.rstrip("/")

        return v


class BatchOperation(BaseModel):
    """A single operation in a batch request."""

    action: Literal["create", "update", "delete"] = Field(
        description="Type of operation to perform"
    )
    path: str = Field(
        min_length=1,
        max_length=512,
        description="Memory node path for the operation",
    )
    content: str | None = Field(
        default=None,
        max_length=10_000_000,  # 10MB max content
        description="Content for create/update operations",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Validate and sanitize the memory path."""
        try:
            # This will raise PathValidationError if invalid
            sanitized = sanitize_path(v)
            validate_path(sanitized)
            return sanitized
        except Exception as e:
            raise ValueError(f"Invalid path: {e}") from e

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        """Validate content if provided."""
        if v is None:
            return v

        # Check for null bytes or other control characters
        if "\x00" in v:
            raise ValueError("Content cannot contain null bytes")

        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")

        return v

    def model_post_init(self, __context=None) -> None:
        """Validate operation consistency after all fields are set."""
        if self.action in ("create", "update") and self.content is None:
            raise ValueError(f"Content is required for {self.action} operations")

        if self.action == "delete" and self.content is not None:
            raise ValueError("Content should not be provided for delete operations")


class BatchRequest(BaseModel):
    """Request model for batch operations."""

    operations: list[BatchOperation] = Field(
        min_length=1,
        max_length=100,  # Max 100 operations per batch
        description="List of operations to perform atomically",
    )
    commit_message: str = Field(
        default="Batch update",
        min_length=1,
        max_length=256,
        description="Git commit message for the batch",
    )

    @field_validator("commit_message")
    @classmethod
    def validate_commit_message(cls, v: str) -> str:
        """Validate commit message format."""
        v = v.strip()
        if not v:
            raise ValueError("Commit message cannot be empty")

        # Check for control characters
        if any(ord(c) < 32 for c in v if c not in ("\t", "\n", "\r")):
            raise ValueError("Commit message contains invalid characters")

        return v

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, v: list[BatchOperation]) -> list[BatchOperation]:
        """Validate the list of operations."""
        if not v:
            raise ValueError("At least one operation is required")

        # Check for duplicate paths in create/update operations
        paths_seen = set()
        for op in v:
            if op.action in ("create", "update"):
                if op.path in paths_seen:
                    raise ValueError(f"Duplicate path in batch: {op.path}")
                paths_seen.add(op.path)

        return v
