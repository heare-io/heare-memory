"""Core memory node data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field

from .file_metadata import FileMetadata


class MemoryNodeMetadata(BaseModel):
    """Metadata for a memory node."""

    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
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

    @computed_field
    @property
    def is_empty(self) -> bool:
        """Whether the content is empty or whitespace only."""
        return not self.content.strip()

    def get_lines(self, start: int | None = None, end: int | None = None) -> list[str]:
        """
        Get specific lines from the content.

        Args:
            start: Start line number (1-based, inclusive)
            end: End line number (1-based, inclusive)

        Returns:
            List of lines in the specified range
        """
        lines = self.content.splitlines()

        start_idx = max(0, start - 1) if start is not None else 0  # Convert to 0-based
        end_idx = (
            min(len(lines), end) if end is not None else len(lines)
        )  # Convert to 0-based exclusive

        return lines[start_idx:end_idx]

    def find_text(self, query: str, case_sensitive: bool = False) -> list[int]:
        """
        Find line numbers containing the query text.

        Args:
            query: Text to search for
            case_sensitive: Whether to perform case-sensitive search

        Returns:
            List of line numbers (1-based) containing the query
        """
        lines = self.content.splitlines()
        matches = []

        search_query = query if case_sensitive else query.lower()

        for i, line in enumerate(lines, 1):
            search_line = line if case_sensitive else line.lower()
            if search_query in search_line:
                matches.append(i)

        return matches


class MemoryNodeCreate(BaseModel):
    """Request model for creating/updating memory nodes."""

    content: str = Field(description="Markdown content to store")


class MemoryNodeList(BaseModel):
    """Response model for memory node listings."""

    nodes: list[MemoryNode] = Field(description="List of memory nodes")
    total: int = Field(description="Total number of nodes")
    prefix: str | None = Field(description="Filter prefix used")


class SearchResult(BaseModel):
    """A single search result."""

    path: str = Field(description="Path of the matching file")
    line_number: int = Field(description="Line number of the match")
    line_content: str = Field(description="Content of the matching line")
    context_before: list[str] = Field(description="Lines before the match")
    context_after: list[str] = Field(description="Lines after the match")


class SearchResponse(BaseModel):
    """Response model for search operations."""

    results: list[SearchResult] = Field(description="Search results")
    total: int = Field(description="Total number of matches")
    query: str = Field(description="Search query used")
    prefix: str | None = Field(description="Search prefix used")


class BatchOperation(BaseModel):
    """A single batch operation."""

    action: str = Field(description="Operation type: create, update, delete")
    path: str = Field(description="Memory node path")
    content: str | None = Field(description="Content for create/update operations")


class BatchRequest(BaseModel):
    """Request model for batch operations."""

    operations: list[BatchOperation] = Field(description="List of operations to perform")
    commit_message: str = Field(description="Git commit message for the batch")


class BatchResponse(BaseModel):
    """Response model for batch operations."""

    success: bool = Field(description="Whether all operations succeeded")
    completed: int = Field(description="Number of completed operations")
    total: int = Field(description="Total number of operations")
    commit_sha: str | None = Field(description="Git commit SHA if successful")


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(description="Additional error details")
