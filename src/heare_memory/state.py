"""Global application state management."""

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .file_manager import FileManager
    from .git_manager import GitManager

logger = logging.getLogger(__name__)


class ApplicationState:
    """Global application state container."""

    def __init__(self):
        """Initialize application state."""
        self.startup_time: float | None = None
        self.config: dict[str, Any] | None = None
        self.tools_status: dict[str, Any] | None = None
        self.file_manager: FileManager | None = None
        self.git_manager: GitManager | None = None

    def set_startup_time(self, startup_time: float) -> None:
        """Set the application startup time."""
        self.startup_time = startup_time
        logger.info(f"Application startup time set: {startup_time}")

    def set_config(self, config: dict[str, Any]) -> None:
        """Set the application configuration."""
        self.config = config
        logger.debug("Application configuration updated")

    def set_tools_status(self, tools_status: dict[str, Any]) -> None:
        """Set the external tools status."""
        self.tools_status = tools_status
        logger.debug("External tools status updated")

    @property
    def is_initialized(self) -> bool:
        """Check if the application state is fully initialized."""
        return (
            self.startup_time is not None
            and self.config is not None
            and self.tools_status is not None
        )


# Global state instance
state = ApplicationState()


# Legacy compatibility functions
def set_git_manager(git_manager: Optional["GitManager"]) -> None:
    """Set the global git manager instance (legacy compatibility)."""
    state.git_manager = git_manager


def get_git_manager() -> Optional["GitManager"]:
    """Get the global git manager instance (legacy compatibility)."""
    return state.git_manager


def set_startup_result(startup_result: Any) -> None:
    """Set the startup result (legacy compatibility)."""
    state.set_tools_status(startup_result)


def get_startup_result() -> Any:
    """Get the startup result (legacy compatibility)."""
    return state.tools_status
