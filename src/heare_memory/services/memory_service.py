"""Memory service for handling file operations with git integration."""

import logging

from ..file_manager import FileManager, FileManagerError
from ..git_manager import GitManager
from ..models.memory import MemoryNode, MemoryNodeMetadata

logger = logging.getLogger(__name__)


class MemoryServiceError(Exception):
    """Base exception for memory service operations."""


class MemoryNotFoundError(MemoryServiceError):
    """Raised when a requested memory node is not found."""


class MemoryService:
    """
    Service layer for memory operations combining file and git management.

    Provides high-level operations for memory nodes including file I/O,
    metadata generation, and git integration.
    """

    def __init__(self, file_manager: FileManager, git_manager: GitManager):
        """
        Initialize the memory service.

        Args:
            file_manager: FileManager instance for file operations
            git_manager: GitManager instance for git operations
        """
        self.file_manager = file_manager
        self.git_manager = git_manager

    async def get_memory_node(self, path: str) -> MemoryNode:
        """
        Get a memory node by path.

        Args:
            path: Memory path (with or without .md extension)

        Returns:
            MemoryNode with content and metadata

        Raises:
            MemoryNotFoundError: If the file doesn't exist
            MemoryServiceError: If there's an error reading the file
            PathValidationError: If the path is invalid
        """
        try:
            # Check if file exists first
            if not await self.file_manager.file_exists(path):
                raise MemoryNotFoundError(f"Memory node not found: {path}")

            # Read file content
            content = await self.file_manager.read_file(path)

            # Get file metadata
            file_metadata = await self.file_manager.get_file_metadata(path)

            # Get current git SHA for the file
            try:
                git_sha = await self.git_manager.get_file_sha(path)
                if git_sha is None:
                    # File not in git yet, use a placeholder
                    git_sha = "uncommitted"
            except Exception as e:
                logger.warning(f"Failed to get git SHA for {path}: {e}")
                git_sha = "unknown"

            # Create metadata
            metadata = MemoryNodeMetadata.from_file_metadata(file_metadata, git_sha)

            # Create and return memory node
            return MemoryNode(
                path=path,
                content=content,
                metadata=metadata,
            )

        except FileManagerError as e:
            logger.error(f"File manager error reading {path}: {e}")
            raise MemoryServiceError(f"Failed to read memory node: {e}") from e
        except (MemoryServiceError, MemoryNotFoundError):
            # Re-raise memory service exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading {path}: {e}")
            raise MemoryServiceError(f"Internal error reading memory node: {e}") from e

    async def create_memory_node(
        self, path: str, content: str, commit_message: str | None = None
    ) -> MemoryNode:
        """
        Create a new memory node.

        Args:
            path: Memory path for the new node
            content: Content to write
            commit_message: Optional git commit message

        Returns:
            MemoryNode representing the created node

        Raises:
            MemoryServiceError: If there's an error creating the file
            PathValidationError: If the path is invalid
        """
        try:
            # Write the file
            file_metadata = await self.file_manager.write_file(path, content)

            # Commit to git
            if commit_message is None:
                commit_message = f"Create {path}"

            try:
                commit_result = await self.git_manager.commit_file(path, commit_message)
                git_sha = commit_result.sha
            except Exception as e:
                logger.warning(f"Failed to commit {path} to git: {e}")
                git_sha = "uncommitted"

            # Create metadata
            metadata = MemoryNodeMetadata.from_file_metadata(file_metadata, git_sha)

            return MemoryNode(
                path=path,
                content=content,
                metadata=metadata,
            )

        except FileManagerError as e:
            logger.error(f"File manager error creating {path}: {e}")
            raise MemoryServiceError(f"Failed to create memory node: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating {path}: {e}")
            raise MemoryServiceError(f"Internal error creating memory node: {e}") from e

    async def update_memory_node(
        self, path: str, content: str, commit_message: str | None = None
    ) -> MemoryNode:
        """
        Update an existing memory node.

        Args:
            path: Memory path of the node to update
            content: New content
            commit_message: Optional git commit message

        Returns:
            MemoryNode representing the updated node

        Raises:
            MemoryNotFoundError: If the file doesn't exist
            MemoryServiceError: If there's an error updating the file
            PathValidationError: If the path is invalid
        """
        try:
            # Check if file exists
            if not await self.file_manager.file_exists(path):
                raise MemoryNotFoundError(f"Memory node not found: {path}")

            # Write the file
            file_metadata = await self.file_manager.write_file(path, content)

            # Commit to git
            if commit_message is None:
                commit_message = f"Update {path}"

            try:
                commit_result = await self.git_manager.commit_file(path, commit_message)
                git_sha = commit_result.sha
            except Exception as e:
                logger.warning(f"Failed to commit {path} to git: {e}")
                git_sha = "uncommitted"

            # Create metadata
            metadata = MemoryNodeMetadata.from_file_metadata(file_metadata, git_sha)

            return MemoryNode(
                path=path,
                content=content,
                metadata=metadata,
            )

        except FileManagerError as e:
            logger.error(f"File manager error updating {path}: {e}")
            raise MemoryServiceError(f"Failed to update memory node: {e}") from e
        except (MemoryServiceError, MemoryNotFoundError):
            # Re-raise memory service exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating {path}: {e}")
            raise MemoryServiceError(f"Internal error updating memory node: {e}") from e

    async def create_or_update_memory_node(
        self, path: str, content: str, commit_message: str | None = None
    ) -> tuple[MemoryNode, bool]:
        """
        Create or update a memory node, returning whether it was created.

        Args:
            path: Memory path for the node
            content: Content to write
            commit_message: Optional git commit message

        Returns:
            Tuple of (MemoryNode, is_new) where is_new indicates if the file was created

        Raises:
            MemoryServiceError: If there's an error with the operation
            PathValidationError: If the path is invalid
        """
        try:
            # Check if file exists
            file_exists = await self.file_manager.file_exists(path)

            # Write the file
            file_metadata = await self.file_manager.write_file(path, content)

            # Create appropriate commit message
            if commit_message is None:
                commit_message = f"Create {path}" if not file_exists else f"Update {path}"

            try:
                commit_result = await self.git_manager.commit_file(path, commit_message)
                git_sha = commit_result.sha
            except Exception as e:
                logger.warning(f"Failed to commit {path} to git: {e}")
                git_sha = "uncommitted"

            # Create metadata
            metadata = MemoryNodeMetadata.from_file_metadata(file_metadata, git_sha)

            memory_node = MemoryNode(
                path=path,
                content=content,
                metadata=metadata,
            )

            return memory_node, not file_exists

        except FileManagerError as e:
            logger.error(f"File manager error creating/updating {path}: {e}")
            raise MemoryServiceError(f"Failed to create/update memory node: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating/updating {path}: {e}")
            raise MemoryServiceError(f"Internal error creating/updating memory node: {e}") from e

    async def delete_memory_node(self, path: str, commit_message: str | None = None) -> bool:
        """
        Delete a memory node.

        Args:
            path: Memory path of the node to delete
            commit_message: Optional git commit message

        Returns:
            True if the file was deleted, False if it didn't exist

        Raises:
            MemoryServiceError: If there's an error deleting the file
            PathValidationError: If the path is invalid
        """
        try:
            # Delete the file
            deleted = await self.file_manager.delete_file(path)

            if deleted:
                # Commit to git
                if commit_message is None:
                    commit_message = f"Delete {path}"

                try:
                    await self.git_manager.delete_file(path, commit_message)
                except Exception as e:
                    logger.warning(f"Failed to commit deletion of {path} to git: {e}")

            return deleted

        except FileManagerError as e:
            logger.error(f"File manager error deleting {path}: {e}")
            raise MemoryServiceError(f"Failed to delete memory node: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error deleting {path}: {e}")
            raise MemoryServiceError(f"Internal error deleting memory node: {e}") from e

    async def memory_node_exists(self, path: str) -> bool:
        """
        Check if a memory node exists.

        Args:
            path: Memory path to check

        Returns:
            True if the memory node exists

        Raises:
            PathValidationError: If the path is invalid
        """
        try:
            return await self.file_manager.file_exists(path)
        except Exception as e:
            logger.error(f"Error checking existence of {path}: {e}")
            return False

    async def get_memory_metadata(self, path: str) -> MemoryNodeMetadata:
        """
        Get metadata for a memory node without reading content.

        Args:
            path: Memory path

        Returns:
            MemoryNodeMetadata for the node

        Raises:
            MemoryNotFoundError: If the file doesn't exist
            MemoryServiceError: If there's an error getting metadata
            PathValidationError: If the path is invalid
        """
        try:
            if not await self.file_manager.file_exists(path):
                raise MemoryNotFoundError(f"Memory node not found: {path}")

            # Get file metadata
            file_metadata = await self.file_manager.get_file_metadata(path)

            # Get current git SHA for the file
            try:
                git_sha = await self.git_manager.get_file_sha(path)
                if git_sha is None:
                    git_sha = "uncommitted"
            except Exception as e:
                logger.warning(f"Failed to get git SHA for {path}: {e}")
                git_sha = "unknown"

            return MemoryNodeMetadata.from_file_metadata(file_metadata, git_sha)

        except FileManagerError as e:
            logger.error(f"File manager error getting metadata for {path}: {e}")
            raise MemoryServiceError(f"Failed to get metadata: {e}") from e
        except (MemoryServiceError, MemoryNotFoundError):
            # Re-raise memory service exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting metadata for {path}: {e}")
            raise MemoryServiceError(f"Internal error getting metadata: {e}") from e
