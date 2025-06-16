"""Startup checks and service initialization."""

import logging
from dataclasses import dataclass
from typing import Any

from .config import settings
from .external_tools import tool_checker
from .git_manager import GitManager
from .search_backend import search_backend

logger = logging.getLogger(__name__)


@dataclass
class StartupResult:
    """Result of startup checks."""

    success: bool
    git_manager: GitManager | None = None
    read_only_mode: bool = False
    search_backend: str = "none"
    search_backend_status: dict[str, Any] | None = None
    error_messages: list[str] | None = None
    warnings: list[str] | None = None


class StartupError(Exception):
    """Exception raised when startup checks fail."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


async def run_startup_checks() -> StartupResult:
    """Run all startup checks and initialize the service.

    Returns:
        StartupResult: Result of startup checks

    Raises:
        StartupError: If critical startup checks fail
    """
    errors = []
    warnings = []

    logger.info("Starting heare-memory service initialization")

    # 1. Check external tools
    logger.info("Checking external tool availability...")
    tools_status = tool_checker.check_all_tools()

    if not tools_status.git.available:
        errors.append(f"Git not available: {tools_status.git.error_message}")
        if tools_status.git.install_suggestion:
            errors.append(f"Solution: {tools_status.git.install_suggestion}")

    if not tools_status.gh_cli.available:
        warnings.append(f"GitHub CLI not available: {tools_status.gh_cli.error_message}")
        if tools_status.gh_cli.install_suggestion:
            warnings.append(f"Optional: {tools_status.gh_cli.install_suggestion}")

    if not tools_status.search_backend.available:
        warnings.append(
            f"Search backend not available: {tools_status.search_backend.error_message}"
        )
        if tools_status.search_backend.install_suggestion:
            warnings.append(f"Recommended: {tools_status.search_backend.install_suggestion}")

    # Log tool status
    logger.info(
        "Tool availability: git=%s, gh=%s, search=%s",
        tools_status.git.available,
        tools_status.gh_cli.available,
        tools_status.search_backend.available,
    )

    if tools_status.git.available:
        logger.info("Git version: %s", tools_status.git.version)
    if tools_status.gh_cli.available:
        logger.info("GitHub CLI version: %s", tools_status.gh_cli.version)
    if tools_status.search_backend.available:
        logger.info(
            "Search backend: %s (%s)",
            tools_status.search_backend.name,
            tools_status.search_backend.version,
        )

    # Fail fast if git is not available
    if not tools_status.git.available:
        raise StartupError(
            "Git is required but not available", {"errors": errors, "warnings": warnings}
        )

    # 2. Check and create memory root directory
    logger.info("Checking memory root directory: %s", settings.memory_root)

    try:
        settings.ensure_memory_root()
        logger.info("Memory root directory ready: %s", settings.memory_root)
    except Exception as exc:
        errors.append(f"Failed to create memory root directory: {exc}")
        raise StartupError(
            f"Memory root directory setup failed: {exc}",
            {"errors": errors, "warnings": warnings},
        ) from exc

    # 3. Initialize git repository
    logger.info("Initializing git repository...")

    try:
        git_manager = GitManager()
        await git_manager.initialize_repository()
        logger.info("Git repository initialized successfully")
    except Exception as exc:
        errors.append(f"Git repository initialization failed: {exc}")
        raise StartupError(
            f"Git repository setup failed: {exc}",
            {"errors": errors, "warnings": warnings},
        ) from exc

    # 4. Check read-only mode
    read_only_mode = settings.is_read_only
    if read_only_mode:
        logger.warning("Running in read-only mode: no GITHUB_TOKEN configured")
        warnings.append("Service running in read-only mode - write operations disabled")
    else:
        logger.info("Write mode enabled with GitHub token authentication")

    # 5. Validate git remote configuration if specified
    if settings.git_remote_url:
        logger.info("Git remote URL configured: %s", settings.git_remote_url)

        try:
            repo_status = await git_manager.get_repository_status()
            if repo_status.remote_url and repo_status.remote_url != settings.git_remote_url:
                error_msg = (
                    f"Git remote URL mismatch: configured={settings.git_remote_url}, "
                    f"actual={repo_status.remote_url}"
                )
                errors.append(error_msg)
                raise StartupError(
                    "Git remote URL mismatch prevents startup to avoid repository confusion",
                    {"errors": errors, "warnings": warnings},
                )

            logger.info("Git remote configuration validated")
        except StartupError:
            raise  # Re-raise startup errors
        except Exception as exc:
            warnings.append(f"Could not validate git remote configuration: {exc}")

    # 6. Test git operations if not in read-only mode
    if not read_only_mode:
        logger.info("Testing git operations...")
        try:
            # Test that we can create commits (but don't push)
            test_result = await git_manager.commit_file(
                "_test_startup.md", "# Startup test\n\nThis is a test file created during startup."
            )
            if test_result.success:
                # Clean up test file
                await git_manager.delete_file("_test_startup.md", "Clean up startup test file")
                logger.info("Git operations test passed")
            else:
                warnings.append(f"Git operations test failed: {test_result.error_message}")
        except Exception as exc:
            warnings.append(f"Git operations test failed: {exc}")

    # 7. Detect search backends
    logger.info("Detecting search backends...")
    try:
        search_backends = await search_backend.detect_backends()
        search_status = search_backend.get_backend_status()
        logger.info(f"Search backends detected: {search_backends}")
    except Exception as e:
        logger.warning(f"Failed to detect search backends: {e}")
        search_status = {
            "ripgrep_available": False,
            "grep_available": False,
            "preferred_backend": None,
            "backends_detected": False,
        }

    # 8. Final status
    search_backend_name = tool_checker.get_search_backend_name()

    logger.info("Startup checks completed successfully")
    logger.info(
        "Configuration: read_only=%s, search_backend=%s, git_remote=%s",
        read_only_mode,
        search_backend_name,
        bool(settings.git_remote_url),
    )

    if warnings:
        logger.warning("Startup warnings: %s", "; ".join(warnings))

    return StartupResult(
        success=True,
        git_manager=git_manager,
        read_only_mode=read_only_mode,
        search_backend=search_backend_name,
        search_backend_status=search_status,
        warnings=warnings if warnings else None,
    )


def format_startup_error(error: StartupError) -> str:
    """Format a startup error for display.

    Args:
        error: The startup error

    Returns:
        str: Formatted error message
    """
    lines = [f"Startup failed: {error}"]

    if error.details.get("errors"):
        lines.append("Errors:")
        for err in error.details["errors"]:
            lines.append(f"  - {err}")

    if error.details.get("warnings"):
        lines.append("Warnings:")
        for warn in error.details["warnings"]:
            lines.append(f"  - {warn}")

    return "\n".join(lines)
