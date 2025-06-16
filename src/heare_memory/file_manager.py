"""Async file system operations manager for memory service."""

import asyncio
import contextlib
import logging
import tempfile
from pathlib import Path

import aiofiles
import aiofiles.os

from .config import settings
from .models.file_metadata import (
    DirectoryListing,
    FileMetadata,
    FileOperation,
    FileOperationResult,
)
from .path_utils import (
    PathValidationError,
    ensure_parent_directory,
    get_relative_path,
    list_directory_paths,
    resolve_memory_path,
    sanitize_path,
    validate_path,
)

logger = logging.getLogger(__name__)


class FileManagerError(Exception):
    """Base exception for file manager operations."""


class FileManager:
    """
    Async file system operations manager with security and atomicity guarantees.

    Provides safe file operations within the memory root directory with
    path validation, atomic writes, and concurrent access safety.
    """

    def __init__(self):
        """Initialize the file manager."""
        self._lock = asyncio.Lock()

    async def read_file(self, path: str) -> str:
        """
        Read content from a memory file.

        Args:
            path: Memory path to read

        Returns:
            File content as string

        Raises:
            FileManagerError: If file cannot be read
            PathValidationError: If path is invalid
        """
        # Validate and resolve path
        validated_path = sanitize_path(path)
        file_path = resolve_memory_path(validated_path)

        try:
            if not await aiofiles.os.path.exists(str(file_path)):
                raise FileManagerError(f"File not found: {validated_path}")

            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()

            logger.debug(f"Read file: {validated_path} ({len(content)} bytes)")
            return content

        except (OSError, UnicodeDecodeError) as e:
            raise FileManagerError(f"Failed to read file {validated_path}: {e}") from e

    async def write_file(self, path: str, content: str) -> FileMetadata:
        """
        Write content to a memory file atomically.

        Args:
            path: Memory path to write
            content: Content to write

        Returns:
            FileMetadata for the written file

        Raises:
            FileManagerError: If file cannot be written
            PathValidationError: If path is invalid
        """
        # Validate and resolve path
        validated_path = sanitize_path(path)
        file_path = resolve_memory_path(validated_path)

        # Ensure parent directory exists
        ensure_parent_directory(validated_path)

        # Use async lock for thread safety
        async with self._lock:
            try:
                # Write to temporary file first for atomicity
                temp_dir = file_path.parent
                temp_fd, temp_path = tempfile.mkstemp(
                    suffix=".tmp", prefix=f".{file_path.name}_", dir=temp_dir, text=True
                )

                try:
                    # Write content to temporary file
                    async with aiofiles.open(temp_fd, "w", encoding="utf-8", closefd=True) as f:
                        await f.write(content)

                    # Atomically move temporary file to final location
                    await aiofiles.os.rename(temp_path, str(file_path))

                    logger.debug(f"Wrote file: {validated_path} ({len(content)} bytes)")

                    # Return metadata for the written file
                    return FileMetadata.from_path(file_path, validated_path)

                except Exception:
                    # Clean up temporary file on error
                    with contextlib.suppress(OSError):
                        await aiofiles.os.unlink(temp_path)
                    raise

            except (OSError, UnicodeEncodeError) as e:
                raise FileManagerError(f"Failed to write file {validated_path}: {e}") from e

    async def delete_file(self, path: str) -> bool:
        """
        Delete a memory file.

        Args:
            path: Memory path to delete

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            FileManagerError: If file cannot be deleted
            PathValidationError: If path is invalid
        """
        # Validate and resolve path
        validated_path = sanitize_path(path)
        file_path = resolve_memory_path(validated_path)

        try:
            if not await aiofiles.os.path.exists(str(file_path)):
                return False

            await aiofiles.os.unlink(str(file_path))
            logger.debug(f"Deleted file: {validated_path}")

            # Clean up empty parent directories
            await self._cleanup_empty_directories(file_path.parent)

            return True

        except OSError as e:
            raise FileManagerError(f"Failed to delete file {validated_path}: {e}") from e

    async def file_exists(self, path: str) -> bool:
        """
        Check if a memory file exists.

        Args:
            path: Memory path to check

        Returns:
            True if file exists

        Raises:
            PathValidationError: If path is invalid
        """
        try:
            validated_path = sanitize_path(path)
            file_path = resolve_memory_path(validated_path)
            return await aiofiles.os.path.exists(str(file_path))
        except PathValidationError:
            return False

    async def get_file_metadata(self, path: str) -> FileMetadata:
        """
        Get metadata for a memory file.

        Args:
            path: Memory path to get metadata for

        Returns:
            FileMetadata instance

        Raises:
            PathValidationError: If path is invalid
        """
        validated_path = sanitize_path(path)
        file_path = resolve_memory_path(validated_path)
        return FileMetadata.from_path(file_path, validated_path)

    async def list_files(
        self, prefix: str | None = None, recursive: bool = True
    ) -> DirectoryListing:
        """
        List memory files within a prefix directory.

        Args:
            prefix: Directory prefix to search within
            recursive: Whether to search recursively

        Returns:
            DirectoryListing with found files

        Raises:
            PathValidationError: If prefix is invalid
        """
        if prefix and prefix.strip():
            # Validate prefix (treat as directory, so no .md extension required)
            try:
                validate_path(prefix + ".md")  # Temporary validation
                prefix = prefix.rstrip("/")
            except PathValidationError:
                # If validation fails, try without .md
                if ".." in prefix or prefix.startswith("/"):
                    raise PathValidationError(f"Invalid prefix: {prefix}") from None
        else:
            prefix = ""

        try:
            if recursive:
                # Get all files and filter by prefix
                all_paths = list_directory_paths()
                if prefix:
                    filtered_paths = [
                        p for p in all_paths if p.startswith(prefix + "/") or p == prefix + ".md"
                    ]
                else:
                    filtered_paths = all_paths
            else:
                # Only get files directly in the prefix directory
                memory_root = settings.memory_root.resolve()
                search_dir = memory_root / prefix if prefix else memory_root

                if not search_dir.exists():
                    filtered_paths = []
                else:
                    filtered_paths = []
                    for path in search_dir.glob("*.md"):
                        try:
                            relative_path = get_relative_path(path)
                            validate_path(relative_path)
                            filtered_paths.append(relative_path)
                        except PathValidationError:
                            continue

            return DirectoryListing.from_paths(prefix, filtered_paths)

        except Exception as e:
            raise FileManagerError(f"Failed to list files in {prefix}: {e}") from e

    async def ensure_directory(self, path: str) -> bool:
        """
        Ensure a directory exists within memory root.

        Args:
            path: Directory path to create

        Returns:
            True if directory was created or already exists

        Raises:
            FileManagerError: If directory cannot be created
        """
        try:
            # For directories, we'll validate as if it's a file path but ignore .md requirement
            directory_path = path.rstrip("/")
            if directory_path and not directory_path.endswith(".md"):
                # Validate the directory path by temporarily adding .md
                temp_path = directory_path + "/temp.md"
                validate_path(temp_path)

            memory_root = settings.memory_root.resolve()
            full_path = memory_root / directory_path if directory_path else memory_root

            # Ensure path is within memory root
            try:
                full_path.resolve().relative_to(memory_root)
            except ValueError:
                raise PathValidationError(f"Directory path outside memory root: {path}") from None

            full_path.mkdir(parents=True, exist_ok=True)
            return True

        except (OSError, PathValidationError) as e:
            raise FileManagerError(f"Failed to create directory {path}: {e}") from e

    async def _cleanup_empty_directories(self, directory: Path) -> None:
        """
        Recursively remove empty directories up to memory root.

        Args:
            directory: Directory to start cleanup from
        """
        memory_root = settings.memory_root.resolve()

        try:
            current = directory.resolve()

            while current != memory_root and current.exists():
                # Check if directory is empty
                try:
                    contents = list(current.iterdir())
                    if not contents:
                        await aiofiles.os.rmdir(str(current))
                        logger.debug(f"Cleaned up empty directory: {current}")
                        current = current.parent
                    else:
                        # Directory not empty, stop cleanup
                        break
                except OSError:
                    # Permission error or other issue, stop cleanup
                    break

        except Exception as e:
            # Don't fail the main operation if cleanup fails
            logger.warning(f"Failed to cleanup empty directories: {e}")

    async def perform_operation(self, operation: FileOperation) -> FileOperationResult:
        """
        Perform a file operation and return the result.

        Args:
            operation: FileOperation to perform

        Returns:
            FileOperationResult with operation outcome
        """
        if not operation.validate_action():
            return FileOperationResult.error_result(
                operation.path, operation.action, f"Invalid action: {operation.action}"
            )

        try:
            if operation.action == "read":
                content = await self.read_file(operation.path)
                metadata = await self.get_file_metadata(operation.path)
                return FileOperationResult.success_result(
                    operation.path, "read", content=content, metadata=metadata
                )

            elif operation.action == "write":
                if operation.content is None:
                    return FileOperationResult.error_result(
                        operation.path, "write", "Content required for write operation"
                    )
                metadata = await self.write_file(operation.path, operation.content)
                return FileOperationResult.success_result(
                    operation.path, "write", metadata=metadata
                )

            elif operation.action == "delete":
                deleted = await self.delete_file(operation.path)
                return FileOperationResult.success_result(
                    operation.path, "delete", content=str(deleted)
                )

            elif operation.action == "exists":
                exists = await self.file_exists(operation.path)
                return FileOperationResult.success_result(
                    operation.path, "exists", content=str(exists)
                )

            elif operation.action == "metadata":
                metadata = await self.get_file_metadata(operation.path)
                return FileOperationResult.success_result(
                    operation.path, "metadata", metadata=metadata
                )

            else:
                return FileOperationResult.error_result(
                    operation.path, operation.action, f"Unsupported action: {operation.action}"
                )

        except (FileManagerError, PathValidationError) as e:
            return FileOperationResult.error_result(operation.path, operation.action, str(e))
        except Exception as e:
            logger.error(f"Unexpected error in file operation: {e}")
            return FileOperationResult.error_result(
                operation.path, operation.action, f"Internal error: {e}"
            )
