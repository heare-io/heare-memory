"""FastAPI dependencies for the memory service."""

from fastapi import Depends

from .file_manager import FileManager
from .git_manager import GitManager
from .services.memory_service import MemoryService
from .state import state


def get_file_manager() -> FileManager:
    """Get the FileManager instance."""
    if state.file_manager is None:
        state.file_manager = FileManager()
    return state.file_manager


def get_git_manager() -> GitManager:
    """Get the GitManager instance."""
    if state.git_manager is None:
        from .config import settings

        state.git_manager = GitManager(repository_path=settings.memory_root)
    return state.git_manager


def get_memory_service(
    file_manager: FileManager = Depends(get_file_manager),
    git_manager: GitManager = Depends(get_git_manager),
) -> MemoryService:
    """Get the MemoryService instance."""
    return MemoryService(file_manager=file_manager, git_manager=git_manager)
