"""Response models for the memory API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from .file_metadata import FileMetadata


class MemoryNodeMetadata(BaseModel):
    """Enhanced metadata for a memory node."""

    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last modification timestamp")
    size: int = Field(description="Content size in bytes", ge=0)
    sha: str = Field(description="Git SHA of last commit")
    exists: bool = Field(description="Whether the file exists", default=True)

    @classmethod
    def from_file_metadata(cls, file_meta: FileMetadata, sha: str) -> "MemoryNodeMetadata":
        """Create MemoryNodeMetadata from FileMetadata."""
        return cls(
            created_at=file_meta.created_at,
            updated_at=file_meta.modified_at,
            size=file_meta.size,
            sha=sha,
            exists=file_meta.exists,
        )


class MemoryNode(BaseModel):
    """A memory node with content and metadata."""

    path: str = Field(description="Memory node path")
    content: str = Field(description="Markdown content")
    metadata: MemoryNodeMetadata = Field(description="Node metadata")

    @computed_field
    @property
    def content_preview(self) -> str:
        """First 200 characters of content for previews."""
        if len(self.content) <= 200:
            return self.content
        return self.content[:197] + "..."

    @computed_field
    @property
    def line_count(self) -> int:
        """Number of lines in the content."""
        return len(self.content.splitlines())


class MemoryNodeSummary(BaseModel):
    """Summary of a memory node without full content."""

    path: str = Field(description="Memory node path")
    metadata: MemoryNodeMetadata = Field(description="Node metadata")
    content_preview: str = Field(description="Preview of content")
    line_count: int = Field(description="Number of lines in content")


class MemoryNodeListResponse(BaseModel):
    """Response model for memory node listings."""

    nodes: list[MemoryNode] = Field(description="List of memory nodes")
    total: int = Field(description="Total number of nodes found", ge=0)
    prefix: str | None = Field(description="Filter prefix used")
    recursive: bool = Field(description="Whether listing was recursive")
    include_content: bool = Field(description="Whether full content was included")

    @computed_field
    @property
    def total_size(self) -> int:
        """Total size of all nodes in bytes."""
        return sum(node.metadata.size for node in self.nodes)


class SearchMatch(BaseModel):
    """A single search match within a file."""

    line_number: int = Field(description="Line number of the match", ge=1)
    line_content: str = Field(description="Content of the matching line")
    match_start: int = Field(description="Start position of match in line", ge=0)
    match_end: int = Field(description="End position of match in line", ge=0)
    context_before: list[str] = Field(description="Lines before the match for context")
    context_after: list[str] = Field(description="Lines after the match for context")


class SearchResultFile(BaseModel):
    """Search results for a single file."""

    path: str = Field(description="Path of the matching file")
    matches: list[SearchMatch] = Field(description="List of matches in this file")
    metadata: MemoryNodeMetadata = Field(description="File metadata")

    @computed_field
    @property
    def match_count(self) -> int:
        """Number of matches in this file."""
        return len(self.matches)


class SearchResponse(BaseModel):
    """Response model for search operations."""

    files: list[SearchResultFile] = Field(description="Files with search matches")
    query: str = Field(description="Search query used")
    prefix: str | None = Field(description="Search prefix used")
    case_sensitive: bool = Field(description="Whether search was case sensitive")
    total_files: int = Field(description="Total number of files with matches", ge=0)
    total_matches: int = Field(description="Total number of matches found", ge=0)
    search_time_ms: float = Field(description="Search time in milliseconds", ge=0)

    @computed_field
    @property
    def has_results(self) -> bool:
        """Whether any matches were found."""
        return self.total_matches > 0


class BatchOperationResult(BaseModel):
    """Result of a single batch operation."""

    operation_index: int = Field(description="Index of operation in batch", ge=0)
    action: str = Field(description="Operation type performed")
    path: str = Field(description="Path that was operated on")
    success: bool = Field(description="Whether operation succeeded")
    error: str | None = Field(description="Error message if operation failed")
    metadata: MemoryNodeMetadata | None = Field(description="File metadata after operation")


class BatchResponse(BaseModel):
    """Response model for batch operations."""

    success: bool = Field(description="Whether all operations succeeded")
    commit_sha: str | None = Field(description="Git commit SHA if successful")
    commit_message: str = Field(description="Git commit message used")
    results: list[BatchOperationResult] = Field(description="Results of individual operations")
    completed: int = Field(description="Number of completed operations", ge=0)
    total: int = Field(description="Total number of operations", ge=0)
    error: str | None = Field(default=None, description="Overall error message if batch failed")

    @computed_field
    @property
    def success_rate(self) -> float:
        """Percentage of operations that succeeded."""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100.0


class CommitInfo(BaseModel):
    """Information about a git commit."""

    sha: str = Field(description="Full commit SHA")
    short_sha: str = Field(description="Short commit SHA (first 8 chars)")
    message: str = Field(description="Commit message")
    author: str = Field(description="Commit author")
    timestamp: datetime = Field(description="Commit timestamp")
    files_changed: list[str] = Field(description="List of files modified")

    @computed_field
    @property
    def files_count(self) -> int:
        """Number of files changed in this commit."""
        return len(self.files_changed)


class HistoryResponse(BaseModel):
    """Response model for commit history."""

    commits: list[CommitInfo] = Field(description="List of commits")
    path: str | None = Field(description="File path if filtered")
    total: int = Field(description="Total number of commits", ge=0)
    page: int = Field(description="Current page number", ge=1)
    per_page: int = Field(description="Number of commits per page", ge=1)

    @computed_field
    @property
    def has_more(self) -> bool:
        """Whether there are more commits available."""
        return (self.page * self.per_page) < self.total


class HealthStatus(BaseModel):
    """Health status information."""

    status: str = Field(description="Overall service status")
    git_available: bool = Field(description="Whether git is available")
    git_remote_configured: bool = Field(description="Whether git remote is configured")
    memory_root_exists: bool = Field(description="Whether memory root exists")
    memory_root_writable: bool = Field(description="Whether memory root is writable")
    read_only_mode: bool = Field(description="Whether service is in read-only mode")
    search_backend: str = Field(description="Search backend being used")
    uptime_seconds: float = Field(description="Service uptime in seconds", ge=0)

    @computed_field
    @property
    def is_healthy(self) -> bool:
        """Whether the service is considered healthy."""
        return self.git_available and self.memory_root_exists and self.memory_root_writable


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(description="Error code or type")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error details")
    path: str | None = Field(description="Related path if applicable")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")

    @classmethod
    def from_exception(cls, exc: Exception, path: str | None = None) -> "ErrorResponse":
        """Create error response from an exception."""
        return cls(
            error=type(exc).__name__,
            message=str(exc),
            path=path,
            details={"exception_type": type(exc).__name__},
        )


class APIResponse(BaseModel):
    """Generic API response wrapper."""

    success: bool = Field(description="Whether the request succeeded")
    data: Any | None = Field(description="Response data")
    error: ErrorResponse | None = Field(description="Error information if failed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

    @classmethod
    def success_response(cls, data: Any = None) -> "APIResponse":
        """Create a successful response."""
        return cls(success=True, data=data)

    @classmethod
    def error_response(cls, error: ErrorResponse) -> "APIResponse":
        """Create an error response."""
        return cls(success=False, error=error)
