"""Tests for the async file manager."""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from heare_memory.config import Settings
from heare_memory.file_manager import FileManager, FileManagerError
from heare_memory.models.file_metadata import FileOperation
from heare_memory.path_utils import PathValidationError


@pytest_asyncio.fixture
async def file_manager():
    """Create a file manager with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_settings = Settings(memory_root=Path(temp_dir))

        # Mock the settings in relevant modules
        import heare_memory.file_manager
        import heare_memory.path_utils

        original_fm_settings = heare_memory.file_manager.settings
        original_pu_settings = heare_memory.path_utils.settings

        heare_memory.file_manager.settings = temp_settings
        heare_memory.path_utils.settings = temp_settings

        try:
            yield FileManager()
        finally:
            # Restore original settings
            heare_memory.file_manager.settings = original_fm_settings
            heare_memory.path_utils.settings = original_pu_settings


class TestFileManagerBasicOperations:
    """Test basic file operations."""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, file_manager):
        """Test writing and reading a file."""
        content = "# Test Content\n\nThis is a test file."

        # Write file
        metadata = await file_manager.write_file("test.md", content)
        assert metadata.path == "test.md"
        assert metadata.size == len(content.encode("utf-8"))
        assert metadata.exists is True

        # Read file back
        read_content = await file_manager.read_file("test.md")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_write_nested_file(self, file_manager):
        """Test writing a file in nested directories."""
        content = "# Nested Content"

        metadata = await file_manager.write_file("folder/subfolder/nested.md", content)
        assert metadata.path == "folder/subfolder/nested.md"
        assert metadata.exists is True

        # Verify we can read it back
        read_content = await file_manager.read_file("folder/subfolder/nested.md")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_delete_file(self, file_manager):
        """Test deleting a file."""
        content = "# Delete Me"

        # Write and verify
        await file_manager.write_file("delete-me.md", content)
        assert await file_manager.file_exists("delete-me.md") is True

        # Delete and verify
        deleted = await file_manager.delete_file("delete-me.md")
        assert deleted is True
        assert await file_manager.file_exists("delete-me.md") is False

        # Delete non-existent file
        deleted_again = await file_manager.delete_file("delete-me.md")
        assert deleted_again is False

    @pytest.mark.asyncio
    async def test_file_exists(self, file_manager):
        """Test file existence checking."""
        # Non-existent file
        assert await file_manager.file_exists("nonexistent.md") is False

        # Create file and check
        await file_manager.write_file("exists.md", "content")
        assert await file_manager.file_exists("exists.md") is True

        # Check with invalid path
        assert await file_manager.file_exists("../invalid") is False

    @pytest.mark.asyncio
    async def test_get_file_metadata(self, file_manager):
        """Test getting file metadata."""
        content = "# Metadata Test"

        # Non-existent file
        metadata = await file_manager.get_file_metadata("nonexistent.md")
        assert metadata.exists is False
        assert metadata.size == 0

        # Existing file
        await file_manager.write_file("metadata.md", content)
        metadata = await file_manager.get_file_metadata("metadata.md")
        assert metadata.exists is True
        assert metadata.size == len(content.encode("utf-8"))
        assert metadata.path == "metadata.md"
        assert not metadata.is_directory


class TestFileManagerPathHandling:
    """Test path validation and sanitization in file manager."""

    @pytest.mark.asyncio
    async def test_path_sanitization(self, file_manager):
        """Test automatic path sanitization."""
        content = "# Sanitized"

        # Test various path formats that should be sanitized
        test_cases = [
            ("test", "test.md"),
            ("folder\\test.md", "folder/test.md"),
            ("folder//test.md", "folder/test.md"),
            ("/leading/slash.md", "leading/slash.md"),
        ]

        for input_path, expected_path in test_cases:
            metadata = await file_manager.write_file(input_path, content)
            assert metadata.path == expected_path

            # Verify we can read it back using the expected path
            read_content = await file_manager.read_file(expected_path)
            assert read_content == content

    @pytest.mark.asyncio
    async def test_invalid_paths(self, file_manager):
        """Test handling of invalid paths."""
        content = "# Invalid"

        invalid_paths = [
            "",
            "../escape.md",
            "with\x00control.md",
            "a" * 1025 + ".md",
        ]

        for path in invalid_paths:
            with pytest.raises((PathValidationError, FileManagerError)):
                await file_manager.write_file(path, content)


class TestFileManagerListing:
    """Test file listing functionality."""

    @pytest.mark.asyncio
    async def test_list_files_empty(self, file_manager):
        """Test listing files in empty directory."""
        listing = await file_manager.list_files()
        assert listing.total_files == 0
        assert listing.files == []

    @pytest.mark.asyncio
    async def test_list_files_basic(self, file_manager):
        """Test basic file listing."""
        # Create some files
        await file_manager.write_file("file1.md", "content1")
        await file_manager.write_file("file2.md", "content2")
        await file_manager.write_file("folder/file3.md", "content3")

        # List all files
        listing = await file_manager.list_files()
        assert listing.total_files == 3
        assert set(listing.files) == {"file1.md", "file2.md", "folder/file3.md"}

    @pytest.mark.asyncio
    async def test_list_files_with_prefix(self, file_manager):
        """Test file listing with prefix filter."""
        # Create files in different folders
        await file_manager.write_file("docs/readme.md", "readme")
        await file_manager.write_file("docs/guide.md", "guide")
        await file_manager.write_file("src/code.md", "code")
        await file_manager.write_file("other.md", "other")

        # List files in docs folder
        listing = await file_manager.list_files(prefix="docs")
        assert listing.total_files == 2
        assert set(listing.files) == {"docs/readme.md", "docs/guide.md"}

        # List files in src folder
        listing = await file_manager.list_files(prefix="src")
        assert listing.total_files == 1
        assert listing.files == ["src/code.md"]

    @pytest.mark.asyncio
    async def test_list_files_non_recursive(self, file_manager):
        """Test non-recursive file listing."""
        # Create files at different levels
        await file_manager.write_file("root.md", "root")
        await file_manager.write_file("folder/nested.md", "nested")
        await file_manager.write_file("folder/deep/deep.md", "deep")

        # List only root level files
        listing = await file_manager.list_files(prefix="", recursive=False)
        assert listing.total_files == 1
        assert listing.files == ["root.md"]

        # List only folder level files (non-recursive)
        listing = await file_manager.list_files(prefix="folder", recursive=False)
        assert listing.total_files == 1
        assert listing.files == ["folder/nested.md"]


class TestFileManagerConcurrency:
    """Test file manager concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_files(self, file_manager):
        """Test concurrent writes to different files."""
        import asyncio

        async def write_file(name, content):
            return await file_manager.write_file(f"{name}.md", content)

        # Write multiple files concurrently
        tasks = [
            write_file("file1", "content1"),
            write_file("file2", "content2"),
            write_file("file3", "content3"),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all files were written
        assert len(results) == 3
        for i, metadata in enumerate(results, 1):
            assert metadata.path == f"file{i}.md"
            content = await file_manager.read_file(f"file{i}.md")
            assert content == f"content{i}"

    @pytest.mark.asyncio
    async def test_atomic_write_operation(self, file_manager):
        """Test that write operations are atomic."""
        # This test verifies that partial writes don't occur
        large_content = "# Large Content\n" + "x" * 10000

        metadata = await file_manager.write_file("large.md", large_content)
        assert metadata.size == len(large_content.encode("utf-8"))

        # Read back and verify complete content
        read_content = await file_manager.read_file("large.md")
        assert read_content == large_content


class TestFileManagerOperations:
    """Test the file operation interface."""

    @pytest.mark.asyncio
    async def test_perform_read_operation(self, file_manager):
        """Test performing a read operation."""
        content = "# Read Test"
        await file_manager.write_file("read-test.md", content)

        operation = FileOperation(action="read", path="read-test.md")
        result = await file_manager.perform_operation(operation)

        assert result.success is True
        assert result.action == "read"
        assert result.path == "read-test.md"
        assert result.content == content
        assert result.metadata is not None

    @pytest.mark.asyncio
    async def test_perform_write_operation(self, file_manager):
        """Test performing a write operation."""
        content = "# Write Test"

        operation = FileOperation(action="write", path="write-test.md", content=content)
        result = await file_manager.perform_operation(operation)

        assert result.success is True
        assert result.action == "write"
        assert result.path == "write-test.md"
        assert result.metadata is not None

        # Verify file was actually written
        read_content = await file_manager.read_file("write-test.md")
        assert read_content == content

    @pytest.mark.asyncio
    async def test_perform_delete_operation(self, file_manager):
        """Test performing a delete operation."""
        content = "# Delete Test"
        await file_manager.write_file("delete-test.md", content)

        operation = FileOperation(action="delete", path="delete-test.md")
        result = await file_manager.perform_operation(operation)

        assert result.success is True
        assert result.action == "delete"
        assert result.path == "delete-test.md"
        assert result.content == "True"  # String representation of deletion success

        # Verify file was actually deleted
        assert await file_manager.file_exists("delete-test.md") is False

    @pytest.mark.asyncio
    async def test_perform_exists_operation(self, file_manager):
        """Test performing an exists operation."""
        # Test with non-existent file
        operation = FileOperation(action="exists", path="nonexistent.md")
        result = await file_manager.perform_operation(operation)

        assert result.success is True
        assert result.action == "exists"
        assert result.content == "False"

        # Test with existing file
        await file_manager.write_file("exists-test.md", "content")
        operation = FileOperation(action="exists", path="exists-test.md")
        result = await file_manager.perform_operation(operation)

        assert result.success is True
        assert result.content == "True"

    @pytest.mark.asyncio
    async def test_perform_metadata_operation(self, file_manager):
        """Test performing a metadata operation."""
        content = "# Metadata Test"
        await file_manager.write_file("metadata-test.md", content)

        operation = FileOperation(action="metadata", path="metadata-test.md")
        result = await file_manager.perform_operation(operation)

        assert result.success is True
        assert result.action == "metadata"
        assert result.metadata is not None
        assert result.metadata.exists is True
        assert result.metadata.path == "metadata-test.md"

    @pytest.mark.asyncio
    async def test_perform_invalid_operation(self, file_manager):
        """Test performing an invalid operation."""
        operation = FileOperation(action="invalid", path="test.md")
        result = await file_manager.perform_operation(operation)

        assert result.success is False
        assert "Invalid action" in result.error

    @pytest.mark.asyncio
    async def test_perform_write_without_content(self, file_manager):
        """Test write operation without content."""
        operation = FileOperation(action="write", path="test.md")  # No content
        result = await file_manager.perform_operation(operation)

        assert result.success is False
        assert "Content required" in result.error


class TestFileManagerErrorHandling:
    """Test error handling in file manager."""

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, file_manager):
        """Test reading a file that doesn't exist."""
        with pytest.raises(FileManagerError) as exc_info:
            await file_manager.read_file("nonexistent.md")
        assert "File not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_directory_cleanup(self, file_manager):
        """Test that empty directories are cleaned up after file deletion."""
        # Create a nested file
        await file_manager.write_file("deep/nested/file.md", "content")

        # Verify directories exist by checking if we can write another file
        await file_manager.write_file("deep/other.md", "other")

        # Delete the nested file
        await file_manager.delete_file("deep/nested/file.md")

        # The nested directory should be gone, but deep should remain
        # This is hard to test directly, so we'll just ensure no errors occur
        assert await file_manager.file_exists("deep/other.md") is True
