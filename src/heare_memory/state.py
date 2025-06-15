"""Global application state."""

from .git_manager import GitManager

# Global state for git manager and startup results
_git_manager: GitManager | None = None
_startup_result = None


def set_git_manager(git_manager: GitManager | None) -> None:
    """Set the global git manager instance."""
    global _git_manager
    _git_manager = git_manager


def get_git_manager() -> GitManager | None:
    """Get the global git manager instance.

    Returns:
        GitManager | None: The git manager or None if not initialized
    """
    return _git_manager


def set_startup_result(startup_result) -> None:
    """Set the startup result."""
    global _startup_result
    _startup_result = startup_result


def get_startup_result():
    """Get the startup result.

    Returns:
        StartupResult | None: The startup result or None if not initialized
    """
    return _startup_result
