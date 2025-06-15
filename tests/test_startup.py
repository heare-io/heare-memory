"""Tests for startup checks."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heare_memory.external_tools import ExternalToolChecker, ToolCheck
from heare_memory.startup import StartupError, run_startup_checks


class TestExternalToolChecker:
    """Test suite for ExternalToolChecker."""

    def test_check_git_available(self):
        """Test git availability check when git is available."""
        checker = ExternalToolChecker()

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run") as mock_run,
        ):
            # Mock successful git version command
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "git version 2.34.1"

            result = checker.check_git()

            assert result.available
            assert result.name == "git"
            assert "git version 2.34.1" in result.version

    def test_check_git_not_available(self):
        """Test git availability check when git is not available."""
        checker = ExternalToolChecker()

        with patch("shutil.which", return_value=None):
            result = checker.check_git()

            assert not result.available
            assert result.name == "git"
            assert "not found" in result.error_message
            assert result.install_suggestion is not None

    def test_check_gh_cli_available(self):
        """Test GitHub CLI availability check when available."""
        checker = ExternalToolChecker()

        with patch("shutil.which", return_value="/usr/bin/gh"), patch("subprocess.run") as mock_run:
            # Mock successful gh version command
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "gh version 2.4.0"

            result = checker.check_gh_cli()

            assert result.available
            assert result.name == "gh"
            assert "gh version 2.4.0" in result.version

    def test_check_search_backend_ripgrep(self):
        """Test search backend check when ripgrep is available."""
        checker = ExternalToolChecker()

        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            # Mock ripgrep available
            mock_which.side_effect = lambda cmd: "/usr/bin/rg" if cmd == "rg" else None
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ripgrep 13.0.0"

            result = checker.check_search_backend()

            assert result.available
            assert result.name == "ripgrep"

    def test_check_search_backend_grep_fallback(self):
        """Test search backend check with grep fallback."""
        checker = ExternalToolChecker()

        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            # Mock ripgrep not available, grep available
            def which_side_effect(cmd):
                if cmd == "rg":
                    return None
                elif cmd == "grep":
                    return "/usr/bin/grep"
                return None

            mock_which.side_effect = which_side_effect
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "grep (GNU grep) 3.7"

            result = checker.check_search_backend()

            assert result.available
            assert result.name == "grep"

    def test_check_all_tools(self):
        """Test checking all tools."""
        checker = ExternalToolChecker()

        with (
            patch.object(checker, "check_git") as mock_git,
            patch.object(checker, "check_gh_cli") as mock_gh,
            patch.object(checker, "check_search_backend") as mock_search,
        ):
            # Mock all tools available
            mock_git.return_value = ToolCheck("git", True, "git version 2.34.1")
            mock_gh.return_value = ToolCheck("gh", True, "gh version 2.4.0")
            mock_search.return_value = ToolCheck("ripgrep", True, "ripgrep 13.0.0")

            status = checker.check_all_tools()

            assert status.all_required_available
            assert status.git.available
            assert status.gh_cli.available
            assert status.search_backend.available

    def test_get_search_backend_name(self):
        """Test getting search backend name."""
        checker = ExternalToolChecker()

        with patch.object(checker, "check_search_backend") as mock_check:
            mock_check.return_value = ToolCheck("ripgrep", True, "ripgrep 13.0.0")

            assert checker.get_search_backend_name() == "ripgrep"


class TestStartupChecks:
    """Test suite for startup checks."""

    @pytest.fixture
    async def temp_settings(self):
        """Create temporary settings for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock settings
            with patch("heare_memory.startup.settings") as mock_settings:
                mock_settings.memory_root = temp_path / "memory"
                mock_settings.git_remote_url = None
                mock_settings.is_read_only = True
                mock_settings.ensure_memory_root = MagicMock()

                yield mock_settings

    async def test_startup_checks_success(self, temp_settings):
        """Test successful startup checks."""
        # Mock external tools as available
        with (
            patch("heare_memory.startup.tool_checker") as mock_checker,
            patch("heare_memory.startup.GitManager") as mock_git_manager,
        ):
            # Mock tool checks
            mock_checker.check_all_tools.return_value = MagicMock(
                git=ToolCheck("git", True, "git version 2.34.1"),
                gh_cli=ToolCheck("gh", True, "gh version 2.4.0"),
                search_backend=ToolCheck("ripgrep", True, "ripgrep 13.0.0"),
                all_required_available=True,
            )
            mock_checker.get_search_backend_name.return_value = "ripgrep"

            # Mock git manager
            mock_git_instance = AsyncMock()
            mock_git_manager.return_value = mock_git_instance

            result = await run_startup_checks()

            assert result.success
            assert result.git_manager is not None
            assert result.search_backend == "ripgrep"

    async def test_startup_checks_git_not_available(self, temp_settings):
        """Test startup checks when git is not available."""
        with patch("heare_memory.startup.tool_checker") as mock_checker:
            # Mock git not available
            mock_checker.check_all_tools.return_value = MagicMock(
                git=ToolCheck("git", False, error_message="Git not found"),
                gh_cli=ToolCheck("gh", True),
                search_backend=ToolCheck("ripgrep", True),
                all_required_available=False,
            )

            with pytest.raises(StartupError) as exc_info:
                await run_startup_checks()

            assert "Git is required" in str(exc_info.value)

    async def test_startup_checks_directory_creation_failure(self, temp_settings):
        """Test startup checks when directory creation fails."""
        with patch("heare_memory.startup.tool_checker") as mock_checker:
            # Mock tools available
            mock_checker.check_all_tools.return_value = MagicMock(
                git=ToolCheck("git", True),
                all_required_available=True,
            )

            # Mock directory creation failure
            temp_settings.ensure_memory_root.side_effect = PermissionError("Permission denied")

            with pytest.raises(StartupError) as exc_info:
                await run_startup_checks()

            assert "Memory root directory setup failed" in str(exc_info.value)

    async def test_startup_checks_git_remote_mismatch(self, temp_settings):
        """Test startup checks with git remote URL mismatch."""
        temp_settings.git_remote_url = "https://github.com/example/repo.git"

        with (
            patch("heare_memory.startup.tool_checker") as mock_checker,
            patch("heare_memory.startup.GitManager") as mock_git_manager,
        ):
            # Mock tools available
            mock_checker.check_all_tools.return_value = MagicMock(
                git=ToolCheck("git", True),
                all_required_available=True,
            )

            # Mock git manager with mismatched remote
            mock_git_instance = AsyncMock()
            mock_git_instance.get_repository_status.return_value = MagicMock(
                remote_url="https://github.com/different/repo.git"
            )
            mock_git_manager.return_value = mock_git_instance

            with pytest.raises(StartupError) as exc_info:
                await run_startup_checks()

            assert "Git remote URL mismatch" in str(exc_info.value)

    async def test_startup_checks_with_warnings(self, temp_settings):
        """Test startup checks that succeed with warnings."""
        with (
            patch("heare_memory.startup.tool_checker") as mock_checker,
            patch("heare_memory.startup.GitManager") as mock_git_manager,
        ):
            # Mock git available, gh not available
            mock_checker.check_all_tools.return_value = MagicMock(
                git=ToolCheck("git", True, "git version 2.34.1"),
                gh_cli=ToolCheck("gh", False, error_message="GitHub CLI not found"),
                search_backend=ToolCheck("search", False, error_message="No search backend"),
                all_required_available=True,  # Git is available
            )
            mock_checker.get_search_backend_name.return_value = "none"

            # Mock git manager
            mock_git_instance = AsyncMock()
            mock_git_manager.return_value = mock_git_instance

            result = await run_startup_checks()

            assert result.success
            assert result.warnings is not None
            assert len(result.warnings) > 0
