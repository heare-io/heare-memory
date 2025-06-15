"""Tests for GitManager."""

import tempfile
from pathlib import Path

import pytest

from heare_memory.git_manager import GitManager
from heare_memory.models.git import GitBatchOperation, GitOperation, GitOperationType


class TestGitManager:
    """Test suite for GitManager."""

    @pytest.fixture
    async def temp_repo_path(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    async def git_manager(self, temp_repo_path):
        """Create a GitManager instance for testing."""
        manager = GitManager(temp_repo_path)
        await manager.initialize_repository()
        return manager

    async def test_repository_initialization(self, temp_repo_path):
        """Test that repository initializes correctly."""
        manager = GitManager(temp_repo_path)
        await manager.initialize_repository()

        assert manager.repo is not None
        assert (temp_repo_path / ".git").exists()

    async def test_commit_file(self, git_manager):
        """Test committing a single file."""
        result = await git_manager.commit_file("test.md", "# Test Content")

        assert result.success
        assert result.commit_sha is not None
        assert result.files_changed == ["test.md"]
        assert result.operation_time > 0

    async def test_delete_file(self, git_manager):
        """Test deleting a file."""
        # First create a file
        await git_manager.commit_file("test.md", "# Test Content")

        # Then delete it
        result = await git_manager.delete_file("test.md")

        assert result.success
        assert result.files_changed == ["test.md"]

    async def test_delete_nonexistent_file(self, git_manager):
        """Test deleting a file that doesn't exist."""
        result = await git_manager.delete_file("nonexistent.md")

        assert result.success
        assert result.files_changed == []

    async def test_batch_commit(self, git_manager):
        """Test batch commit operations."""
        operations = [
            GitOperation(
                operation_type=GitOperationType.CREATE,
                file_path="file1.md",
                content="Content 1",
            ),
            GitOperation(
                operation_type=GitOperationType.CREATE,
                file_path="file2.md",
                content="Content 2",
            ),
        ]

        batch = GitBatchOperation(operations=operations, commit_message="Create multiple files")

        result = await git_manager.batch_commit(batch)

        assert result.success
        assert len(result.files_changed) == 2
        assert "file1.md" in result.files_changed
        assert "file2.md" in result.files_changed

    async def test_repository_status(self, git_manager):
        """Test getting repository status."""
        # Create a file first to have some history
        await git_manager.commit_file("test.md", "# Test")

        status = await git_manager.get_repository_status()

        assert status.path == str(git_manager.repository_path)
        assert status.is_clean
        assert not status.has_uncommitted_changes
        assert status.last_commit is not None
        assert status.last_commit.message.strip() == "Update test.md"

    async def test_push_without_token(self, git_manager):
        """Test push when no GitHub token is configured."""
        # This should succeed but do nothing
        result = await git_manager.push_changes()

        assert result.success
        assert result.retry_count == 0

    async def test_commit_file_creates_directories(self, git_manager):
        """Test that committing a file creates necessary directories."""
        result = await git_manager.commit_file("deep/nested/file.md", "# Nested Content")

        assert result.success
        assert (git_manager.repository_path / "deep" / "nested" / "file.md").exists()

    async def test_batch_commit_mixed_operations(self, git_manager):
        """Test batch commit with mixed create/update/delete operations."""
        # First create some files
        await git_manager.commit_file("file1.md", "Original content")
        await git_manager.commit_file("file2.md", "To be deleted")

        # Now perform mixed operations
        operations = [
            GitOperation(
                operation_type=GitOperationType.UPDATE,
                file_path="file1.md",
                content="Updated content",
            ),
            GitOperation(
                operation_type=GitOperationType.DELETE,
                file_path="file2.md",
            ),
            GitOperation(
                operation_type=GitOperationType.CREATE,
                file_path="file3.md",
                content="New file content",
            ),
        ]

        batch = GitBatchOperation(operations=operations, commit_message="Mixed operations batch")

        result = await git_manager.batch_commit(batch)

        assert result.success
        assert len(result.files_changed) == 3

        # Verify file states
        assert (git_manager.repository_path / "file1.md").read_text() == "Updated content"
        assert not (git_manager.repository_path / "file2.md").exists()
        assert (git_manager.repository_path / "file3.md").read_text() == "New file content"
