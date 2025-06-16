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
                git_sha = commit_result.commit_sha
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
                git_sha = commit_result.commit_sha
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
                git_sha = commit_result.commit_sha
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

    async def list_memory_nodes(
        self,
        prefix: str | None = None,
        delimiter: str | None = None,
        recursive: bool = True,
        include_content: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> dict:
        """
        List memory nodes with optional filtering and pagination.

        Args:
            prefix: Filter nodes by path prefix
            delimiter: Delimiter for hierarchical listing (e.g., "/" for directories)
            recursive: Include subdirectories recursively
            include_content: Include file content in response
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            Dict containing nodes list and metadata

        Raises:
            MemoryServiceError: If there's an error listing files
            PathValidationError: If the prefix path is invalid
        """
        try:
            # Get all memory files from file manager
            directory_listing = await self.file_manager.list_files(
                prefix=prefix or "", recursive=recursive
            )
            all_files = directory_listing.files

            # Apply delimiter filtering if specified
            if delimiter:
                all_files = self._apply_delimiter_filtering(all_files, prefix, delimiter, recursive)

            # Sort files for consistent ordering
            all_files.sort()

            # Apply pagination
            total_count = len(all_files)
            if limit is not None:
                end_index = offset + limit
                paginated_files = all_files[offset:end_index]
            else:
                paginated_files = all_files[offset:]

            # Build response nodes
            nodes = []
            for file_path in paginated_files:
                try:
                    if include_content:
                        # Get full memory node with content
                        memory_node = await self.get_memory_node(file_path)
                        nodes.append(
                            {
                                "path": memory_node.path,
                                "content": memory_node.content,
                                "metadata": {
                                    "created_at": memory_node.metadata.created_at.isoformat(),
                                    "updated_at": memory_node.metadata.updated_at.isoformat(),
                                    "size": memory_node.metadata.size,
                                    "sha": memory_node.metadata.sha,
                                    "exists": memory_node.metadata.exists,
                                },
                            }
                        )
                    else:
                        # Get metadata only
                        metadata = await self.get_memory_metadata(file_path)
                        nodes.append(
                            {
                                "path": file_path,
                                "metadata": {
                                    "created_at": metadata.created_at.isoformat(),
                                    "updated_at": metadata.updated_at.isoformat(),
                                    "size": metadata.size,
                                    "sha": metadata.sha,
                                    "exists": metadata.exists,
                                },
                            }
                        )
                except MemoryNotFoundError:
                    # File was deleted between listing and access, skip it
                    logger.debug(f"File {file_path} no longer exists, skipping")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing file {file_path}: {e}")
                    continue

            return {
                "nodes": nodes,
                "total_count": total_count,
                "returned_count": len(nodes),
                "prefix": prefix,
                "delimiter": delimiter,
                "recursive": recursive,
                "include_content": include_content,
                "limit": limit,
                "offset": offset,
            }

        except FileManagerError as e:
            logger.error(f"File manager error listing files: {e}")
            raise MemoryServiceError(f"Failed to list memory nodes: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error listing memory nodes: {e}")
            raise MemoryServiceError(f"Internal error listing memory nodes: {e}") from e

    def _apply_delimiter_filtering(
        self, files: list[str], prefix: str | None, delimiter: str, recursive: bool
    ) -> list[str]:
        """
        Apply delimiter-based filtering for hierarchical listing.

        Args:
            files: List of file paths
            prefix: Path prefix filter
            delimiter: Delimiter character for hierarchy
            recursive: Whether to include subdirectories

        Returns:
            Filtered list of file paths
        """
        if not delimiter:
            return files

        filtered_files = []
        seen_prefixes = set()

        for file_path in files:
            # Remove .md extension for processing
            working_path = file_path
            if working_path.endswith(".md"):
                working_path = working_path[:-3]

            # Apply prefix filter if specified
            if prefix:
                if not working_path.startswith(prefix):
                    continue
                # Remove prefix for delimiter processing
                relative_path = working_path[len(prefix) :].lstrip(delimiter)
            else:
                relative_path = working_path

            # Handle delimiter-based hierarchy
            if delimiter in relative_path:
                if recursive:
                    # Include all files in recursive mode
                    filtered_files.append(file_path)
                else:
                    # In non-recursive mode, show only immediate children
                    # Create a "directory" entry for the first delimiter
                    first_delimiter_index = relative_path.find(delimiter)
                    directory_name = relative_path[:first_delimiter_index]

                    if prefix:
                        if prefix.endswith(delimiter):
                            full_prefix = f"{prefix}{directory_name}"
                        else:
                            full_prefix = f"{prefix}{delimiter}{directory_name}"
                    else:
                        full_prefix = directory_name

                    if full_prefix not in seen_prefixes:
                        seen_prefixes.add(full_prefix)
                        # Add a synthetic directory entry
                        filtered_files.append(f"{full_prefix}/")
            else:
                # File is at the current level
                filtered_files.append(file_path)

        return filtered_files
