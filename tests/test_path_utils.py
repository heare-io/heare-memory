"""Tests for path validation and sanitization utilities."""

import tempfile
from pathlib import Path

import pytest

from heare_memory.config import Settings
from heare_memory.path_utils import (
    PathValidationError,
    ensure_parent_directory,
    extract_directory_path,
    get_relative_path,
    is_path_within_prefix,
    list_directory_paths,
    resolve_memory_path,
    sanitize_path,
    validate_path,
)


class TestPathValidation:
    """Test path validation functionality."""

    def test_validate_path_valid_cases(self):
        """Test validation of valid paths."""
        valid_paths = [
            "test.md",
            "folder/test.md",
            "deep/nested/path/file.md",
            "with-dashes.md",
            "with_underscores.md",
            "with.dots.md",
            "123numbers.md",
        ]

        for path in valid_paths:
            assert validate_path(path) is True

    def test_validate_path_invalid_cases(self):
        """Test validation of invalid paths."""
        invalid_cases = [
            ("", "Path cannot be empty"),
            ("no-extension", "Path must end with .md extension"),
            ("/absolute/path.md", "Path must be relative"),
            ("with/../traversal.md", "Path contains dangerous pattern"),
            ("with//double.md", "Path contains dangerous pattern"),
            ("with\\backslash.md", "Path contains dangerous pattern"),
            ("with\x00control.md", "Path contains control characters"),
            ("a" * 1025 + ".md", "Path too long"),
            ("./relative.md", "Path contains dangerous pattern"),
            ("../parent.md", "Path contains dangerous pattern"),
            ("folder/../other.md", "Path contains dangerous pattern"),
        ]

        for path, expected_error in invalid_cases:
            with pytest.raises(PathValidationError) as exc_info:
                validate_path(path)
            assert expected_error in str(exc_info.value)

    def test_validate_path_reserved_names(self):
        """Test validation rejects Windows reserved names."""
        reserved_names = ["CON.md", "PRN.md", "AUX.md", "NUL.md", "COM1.md", "LPT1.md"]

        for name in reserved_names:
            with pytest.raises(PathValidationError) as exc_info:
                validate_path(name)
            assert "reserved name" in str(exc_info.value)


class TestPathSanitization:
    """Test path sanitization functionality."""

    def test_sanitize_path_basic(self):
        """Test basic path sanitization."""
        assert sanitize_path("test") == "test.md"
        assert sanitize_path("test.md") == "test.md"
        assert sanitize_path("folder/test") == "folder/test.md"

    def test_sanitize_path_backslashes(self):
        """Test backslash conversion."""
        assert sanitize_path("folder\\test.md") == "folder/test.md"
        assert sanitize_path("deep\\nested\\path.md") == "deep/nested/path.md"

    def test_sanitize_path_double_slashes(self):
        """Test double slash removal."""
        assert sanitize_path("folder//test.md") == "folder/test.md"
        assert sanitize_path("deep///nested//path.md") == "deep/nested/path.md"

    def test_sanitize_path_leading_slash(self):
        """Test leading slash removal."""
        assert sanitize_path("/test.md") == "test.md"
        assert sanitize_path("/folder/test.md") == "folder/test.md"

    def test_sanitize_path_invalid_cases(self):
        """Test sanitization of paths that can't be made valid."""
        invalid_paths = [
            "",
            "folder/../other",
            "with\x00control",
        ]

        for path in invalid_paths:
            with pytest.raises(PathValidationError):
                sanitize_path(path)


class TestPathResolution:
    """Test path resolution functionality."""

    def test_resolve_memory_path(self):
        """Test memory path resolution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up temporary settings
            Path("./memory")
            temp_settings = Settings(memory_root=Path(temp_dir))

            # Mock the settings
            import heare_memory.path_utils

            original_settings = heare_memory.path_utils.settings
            heare_memory.path_utils.settings = temp_settings

            try:
                path = resolve_memory_path("test.md")
                expected = Path(temp_dir) / "test.md"
                assert path == expected

                nested_path = resolve_memory_path("folder/nested.md")
                expected_nested = Path(temp_dir) / "folder" / "nested.md"
                assert nested_path == expected_nested

            finally:
                # Restore original settings
                heare_memory.path_utils.settings = original_settings

    def test_resolve_memory_path_security(self):
        """Test path resolution security checks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_settings = Settings(memory_root=Path(temp_dir))

            import heare_memory.path_utils

            original_settings = heare_memory.path_utils.settings
            heare_memory.path_utils.settings = temp_settings

            try:
                # These should fail validation before resolution
                with pytest.raises(PathValidationError):
                    resolve_memory_path("../escape.md")

                with pytest.raises(PathValidationError):
                    resolve_memory_path("/absolute.md")

            finally:
                heare_memory.path_utils.settings = original_settings

    def test_get_relative_path(self):
        """Test getting relative path from absolute path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_settings = Settings(memory_root=Path(temp_dir))

            import heare_memory.path_utils

            original_settings = heare_memory.path_utils.settings
            heare_memory.path_utils.settings = temp_settings

            try:
                absolute_path = Path(temp_dir) / "folder" / "test.md"
                relative = get_relative_path(absolute_path)
                assert relative == "folder/test.md"

                # Test with file that's outside memory root
                with tempfile.TemporaryDirectory() as outside_dir:
                    outside_path = Path(outside_dir) / "outside.md"
                    with pytest.raises(PathValidationError):
                        get_relative_path(outside_path)

            finally:
                heare_memory.path_utils.settings = original_settings


class TestPathUtilities:
    """Test path utility functions."""

    def test_extract_directory_path(self):
        """Test directory path extraction."""
        assert extract_directory_path("test.md") == ""
        assert extract_directory_path("folder/test.md") == "folder"
        assert extract_directory_path("deep/nested/file.md") == "deep/nested"

    def test_is_path_within_prefix(self):
        """Test prefix matching."""
        # No prefix means all paths match
        assert is_path_within_prefix("any/path.md", "") is True

        # Exact prefix matches
        assert is_path_within_prefix("folder/file.md", "folder") is True
        assert is_path_within_prefix("folder/sub/file.md", "folder") is True
        assert is_path_within_prefix("folder/sub/file.md", "folder/sub") is True

        # Non-matches
        assert is_path_within_prefix("other/file.md", "folder") is False
        assert is_path_within_prefix("file.md", "folder") is False
        assert is_path_within_prefix("folder.md", "folder") is False

    def test_ensure_parent_directory(self):
        """Test parent directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_settings = Settings(memory_root=Path(temp_dir))

            import heare_memory.path_utils

            original_settings = heare_memory.path_utils.settings
            heare_memory.path_utils.settings = temp_settings

            try:
                # Create nested directory structure
                parent_dir = ensure_parent_directory("deep/nested/file.md")
                assert parent_dir.exists()
                assert parent_dir == Path(temp_dir) / "deep" / "nested"

                # Ensure it works for existing directories
                parent_dir2 = ensure_parent_directory("deep/other.md")
                assert parent_dir2.exists()
                assert parent_dir2 == Path(temp_dir) / "deep"

            finally:
                heare_memory.path_utils.settings = original_settings

    def test_list_directory_paths(self):
        """Test directory listing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_settings = Settings(memory_root=Path(temp_dir))

            import heare_memory.path_utils

            original_settings = heare_memory.path_utils.settings
            heare_memory.path_utils.settings = temp_settings

            try:
                # Create some test files
                (Path(temp_dir) / "test1.md").write_text("content1")
                (Path(temp_dir) / "folder").mkdir()
                (Path(temp_dir) / "folder" / "test2.md").write_text("content2")
                (Path(temp_dir) / "folder" / "sub").mkdir()
                (Path(temp_dir) / "folder" / "sub" / "test3.md").write_text("content3")

                # Create an invalid file (should be filtered out)
                (Path(temp_dir) / "invalid.txt").write_text("not markdown")

                paths = list_directory_paths()
                expected = ["folder/sub/test3.md", "folder/test2.md", "test1.md"]
                assert sorted(paths) == sorted(expected)

                # Test with specific directory
                folder_paths = list_directory_paths("folder")
                expected_folder = ["folder/sub/test3.md", "folder/test2.md"]
                assert sorted(folder_paths) == sorted(expected_folder)

            finally:
                heare_memory.path_utils.settings = original_settings

        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up temporary settings
            temp_settings = Settings(memory_root=Path(temp_dir))
