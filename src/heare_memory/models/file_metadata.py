"""File metadata models for memory operations."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class FileMetadata(BaseModel):
    """Metadata for a file in the memory system."""

    path: str = Field(description="Relative memory path")
    size: int = Field(description="File size in bytes")
    created_at: datetime = Field(description="File creation timestamp")
    modified_at: datetime = Field(description="File modification timestamp")
    exists: bool = Field(description="Whether the file exists")
    is_directory: bool = Field(description="Whether this is a directory")
    permissions: str = Field(description="File permissions in octal format")

    @classmethod
    def from_path(cls, file_path: Path, memory_path: str) -> "FileMetadata":
        """
        Create FileMetadata from a filesystem Path.

        Args:
            file_path: Absolute filesystem path
            memory_path: Relative memory path

        Returns:
            FileMetadata instance
        """
        if not file_path.exists():
            return cls(
                path=memory_path,
                size=0,
                created_at=datetime.now(),
                modified_at=datetime.now(),
                exists=False,
                is_directory=False,
                permissions="000",
            )

        stat = file_path.stat()

        return cls(
            path=memory_path,
            size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            exists=True,
            is_directory=file_path.is_dir(),
            permissions=oct(stat.st_mode)[-3:],
        )


class FileOperation(BaseModel):
    """Represents a file operation to be performed."""

    action: str = Field(description="Operation type: read, write, delete, list")
    path: str = Field(description="Memory path for the operation")
    content: str | None = Field(default=None, description="Content for write operations")
    recursive: bool = Field(default=False, description="Whether to operate recursively")

    def validate_action(self) -> bool:
        """Validate that the action is supported."""
        valid_actions = {"read", "write", "delete", "list", "exists", "metadata"}
        return self.action in valid_actions


class FileOperationResult(BaseModel):
    """Result of a file operation."""

    success: bool = Field(description="Whether the operation succeeded")
    path: str = Field(description="Memory path that was operated on")
    action: str = Field(description="Operation that was performed")
    content: str | None = Field(default=None, description="Content from read operations")
    metadata: FileMetadata | None = Field(default=None, description="File metadata")
    error: str | None = Field(default=None, description="Error message if operation failed")

    @classmethod
    def success_result(
        cls,
        path: str,
        action: str,
        content: str | None = None,
        metadata: FileMetadata | None = None,
    ) -> "FileOperationResult":
        """Create a successful operation result."""
        return cls(
            success=True,
            path=path,
            action=action,
            content=content,
            metadata=metadata,
        )

    @classmethod
    def error_result(cls, path: str, action: str, error: str) -> "FileOperationResult":
        """Create a failed operation result."""
        return cls(
            success=False,
            path=path,
            action=action,
            error=error,
        )


class DirectoryListing(BaseModel):
    """Result of listing a directory."""

    path: str = Field(description="Directory path that was listed")
    files: list[str] = Field(description="List of file paths found")
    directories: list[str] = Field(description="List of subdirectory paths found")
    total_files: int = Field(description="Total number of files")
    total_directories: int = Field(description="Total number of directories")

    @classmethod
    def from_paths(cls, directory_path: str, file_paths: list[str]) -> "DirectoryListing":
        """
        Create a DirectoryListing from a list of file paths.

        Args:
            directory_path: The directory that was listed
            file_paths: List of file paths found

        Returns:
            DirectoryListing instance
        """
        # Separate files and directories
        files = []
        directories = set()

        for path in file_paths:
            files.append(path)

            # Add all parent directories
            parts = Path(path).parts
            for i in range(len(parts) - 1):
                parent = "/".join(parts[: i + 1])
                if parent and parent != directory_path:
                    directories.add(parent)

        return cls(
            path=directory_path,
            files=sorted(files),
            directories=sorted(directories),
            total_files=len(files),
            total_directories=len(directories),
        )
