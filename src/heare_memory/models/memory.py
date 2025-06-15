"""Data models for memory nodes."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MemoryNodeMetadata(BaseModel):
    """Metadata for a memory node."""

    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    size: int = Field(description="Content size in bytes")
    sha: str = Field(description="Git SHA of last commit")


class MemoryNode(BaseModel):
    """A memory node with content and metadata."""

    path: str = Field(description="Memory node path")
    content: str = Field(description="Markdown content")
    metadata: MemoryNodeMetadata = Field(description="Node metadata")


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
