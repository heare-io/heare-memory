"""Git operation models and data structures."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GitOperationType(str, Enum):
    """Types of git operations."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    BATCH = "batch"


class GitCommitInfo(BaseModel):
    """Information about a git commit."""

    sha: str = Field(description="Commit SHA hash")
    message: str = Field(description="Commit message")
    author: str = Field(description="Commit author")
    timestamp: datetime = Field(description="Commit timestamp")
    files_changed: list[str] = Field(description="List of files changed in commit")


class GitRepositoryStatus(BaseModel):
    """Status of the git repository."""

    path: str = Field(description="Repository path")
    remote_url: str | None = Field(description="Remote repository URL")
    branch: str = Field(description="Current branch")
    last_commit: GitCommitInfo | None = Field(description="Last commit information")
    has_uncommitted_changes: bool = Field(description="Whether there are uncommitted changes")
    is_clean: bool = Field(description="Whether working directory is clean")
    ahead_by: int = Field(description="Number of commits ahead of remote")
    behind_by: int = Field(description="Number of commits behind remote")


class GitOperation(BaseModel):
    """A single git operation to be performed."""

    operation_type: GitOperationType = Field(description="Type of operation")
    file_path: str = Field(description="Path of file to operate on")
    content: str | None = Field(
        default=None, description="File content for create/update operations"
    )
    commit_message: str | None = Field(default=None, description="Custom commit message")


class GitBatchOperation(BaseModel):
    """A batch of git operations to be performed as a single commit."""

    operations: list[GitOperation] = Field(description="List of operations")
    commit_message: str = Field(description="Commit message for the batch")


class GitOperationResult(BaseModel):
    """Result of a git operation."""

    success: bool = Field(description="Whether operation succeeded")
    commit_sha: str | None = Field(description="SHA of created commit")
    error_message: str | None = Field(description="Error message if failed")
    files_changed: list[str] = Field(description="List of files changed")
    operation_time: float = Field(description="Time taken for operation in seconds")


class GitPushResult(BaseModel):
    """Result of a git push operation."""

    success: bool = Field(description="Whether push succeeded")
    error_message: str | None = Field(description="Error message if failed")
    retry_count: int = Field(description="Number of retries attempted")
    total_time: float = Field(description="Total time including retries in seconds")


class GitError(Exception):
    """Base exception for git operations."""

    def __init__(self, message: str, operation: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}


class GitRepositoryError(GitError):
    """Exception for git repository related errors."""


class GitCommitError(GitError):
    """Exception for git commit related errors."""


class GitPushError(GitError):
    """Exception for git push related errors."""
