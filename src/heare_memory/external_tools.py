"""External tool availability and validation."""

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class ToolCheck:
    """Result of checking an external tool."""

    name: str
    available: bool
    version: str | None = None
    error_message: str | None = None
    install_suggestion: str | None = None


@dataclass
class ToolsStatus:
    """Status of all external tools."""

    git: ToolCheck
    gh_cli: ToolCheck
    search_backend: ToolCheck
    all_required_available: bool


class ExternalToolChecker:
    """Checks availability and functionality of external tools."""

    def __init__(self):
        """Initialize the external tool checker."""

    def check_all_tools(self) -> ToolsStatus:
        """Check all required external tools.

        Returns:
            ToolsStatus: Status of all tools
        """
        git_check = self.check_git()
        gh_check = self.check_gh_cli()
        search_check = self.check_search_backend()

        # Git is the only truly required tool
        all_required = git_check.available

        return ToolsStatus(
            git=git_check,
            gh_cli=gh_check,
            search_backend=search_check,
            all_required_available=all_required,
        )

    def check_git(self) -> ToolCheck:
        """Check git availability and functionality.

        Returns:
            ToolCheck: Git tool status
        """
        if not shutil.which("git"):
            return ToolCheck(
                name="git",
                available=False,
                error_message="Git command not found",
                install_suggestion="Install git: https://git-scm.com/downloads",
            )

        try:
            # Check git version
            result = subprocess.run(  # noqa: S603
                ["git", "--version"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return ToolCheck(
                    name="git",
                    available=False,
                    error_message=f"Git command failed: {result.stderr}",
                )

            version = result.stdout.strip()

            # Test basic git functionality
            result = subprocess.run(  # noqa: S603
                ["git", "config", "--global", "--get", "user.name"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
            )

            return ToolCheck(
                name="git",
                available=True,
                version=version,
            )

        except subprocess.TimeoutExpired:
            return ToolCheck(
                name="git",
                available=False,
                error_message="Git command timed out",
            )
        except Exception as exc:
            return ToolCheck(
                name="git",
                available=False,
                error_message=f"Error checking git: {exc}",
            )

    def check_gh_cli(self) -> ToolCheck:
        """Check GitHub CLI availability.

        Returns:
            ToolCheck: GitHub CLI tool status
        """
        if not shutil.which("gh"):
            return ToolCheck(
                name="gh",
                available=False,
                error_message="GitHub CLI not found",
                install_suggestion="Install GitHub CLI: https://cli.github.com/",
            )

        try:
            # Check gh version
            result = subprocess.run(  # noqa: S603
                ["gh", "--version"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return ToolCheck(
                    name="gh",
                    available=False,
                    error_message=f"GitHub CLI command failed: {result.stderr}",
                )

            version = result.stdout.strip().split("\n")[0]

            return ToolCheck(
                name="gh",
                available=True,
                version=version,
            )

        except subprocess.TimeoutExpired:
            return ToolCheck(
                name="gh",
                available=False,
                error_message="GitHub CLI command timed out",
            )
        except Exception as exc:
            return ToolCheck(
                name="gh",
                available=False,
                error_message=f"Error checking GitHub CLI: {exc}",
            )

    def check_search_backend(self) -> ToolCheck:
        """Check search backend availability (ripgrep with grep fallback).

        Returns:
            ToolCheck: Search backend tool status
        """
        # First try ripgrep
        if shutil.which("rg"):
            try:
                result = subprocess.run(  # noqa: S603
                    ["rg", "--version"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    version = result.stdout.strip().split("\n")[0]
                    return ToolCheck(
                        name="ripgrep",
                        available=True,
                        version=version,
                    )

            except Exception:  # noqa: S110
                pass  # Fall through to grep check

        # Fall back to grep
        if shutil.which("grep"):
            try:
                result = subprocess.run(  # noqa: S603
                    ["grep", "--version"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    version = result.stdout.strip().split("\n")[0]
                    return ToolCheck(
                        name="grep",
                        available=True,
                        version=version,
                    )

            except Exception:  # noqa: S110
                pass

        return ToolCheck(
            name="search",
            available=False,
            error_message="Neither ripgrep nor grep found",
            install_suggestion="Install ripgrep: https://github.com/BurntSushi/ripgrep#installation",
        )

    def get_search_backend_name(self) -> str:
        """Get the name of the available search backend.

        Returns:
            str: 'ripgrep', 'grep', or 'none'
        """
        status = self.check_search_backend()
        if not status.available:
            return "none"
        return status.name


# Global instance
tool_checker = ExternalToolChecker()
