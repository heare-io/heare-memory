"""Path validation and sanitization utilities for memory operations."""

import os
import re
from pathlib import Path, PurePosixPath

from .config import settings


class PathValidationError(Exception):
    """Raised when path validation fails."""


def validate_path(path: str) -> bool:
    """
    Validate a memory path for security and format requirements.

    Args:
        path: The path to validate

    Returns:
        True if path is valid

    Raises:
        PathValidationError: If path is invalid
    """
    if not path:
        raise PathValidationError("Path cannot be empty")

    if len(path) > 1024:  # Reasonable max path length
        raise PathValidationError("Path too long (max 1024 characters)")

    # Check for control characters and other dangerous characters
    if re.search(r"[\x00-\x1f\x7f]", path):
        raise PathValidationError("Path contains control characters")

    # Check for dangerous sequences
    dangerous_patterns = [
        "..",  # Directory traversal
        "//",  # Double slashes
        "\\",  # Backslashes (convert to forward slash instead)
        "./",  # Current directory reference
    ]

    for pattern in dangerous_patterns:
        if pattern in path:
            raise PathValidationError(f"Path contains dangerous pattern: {pattern}")

    # Ensure path ends with .md
    if not path.endswith(".md"):
        raise PathValidationError("Path must end with .md extension")

    # Validate path structure using PurePosixPath
    try:
        posix_path = PurePosixPath(path)

        # Check for absolute paths (should be relative)
        if posix_path.is_absolute():
            raise PathValidationError("Path must be relative (no leading /)")

        # Check each part of the path
        for part in posix_path.parts:
            if not part:  # Empty parts from double slashes
                raise PathValidationError("Path contains empty segments")

            if part in (".", ".."):
                raise PathValidationError(f"Path contains reserved segment: {part}")

            # Check for reserved Windows names (just in case)
            reserved_names = {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                "COM1",
                "COM2",
                "COM3",
                "COM4",
                "COM5",
                "COM6",
                "COM7",
                "COM8",
                "COM9",
                "LPT1",
                "LPT2",
                "LPT3",
                "LPT4",
                "LPT5",
                "LPT6",
                "LPT7",
                "LPT8",
                "LPT9",
            }
            if part.upper().split(".")[0] in reserved_names:
                raise PathValidationError(f"Path contains reserved name: {part}")

    except ValueError as e:
        raise PathValidationError(f"Invalid path format: {e}") from e

    return True


def sanitize_path(path: str) -> str:
    """
    Sanitize a path by converting backslashes and normalizing structure.

    Args:
        path: The path to sanitize

    Returns:
        Sanitized path string

    Raises:
        PathValidationError: If path cannot be sanitized to a valid format
    """
    if not path:
        raise PathValidationError("Cannot sanitize empty path")

    # Convert backslashes to forward slashes
    sanitized = path.replace("\\", "/")

    # Remove any double slashes
    while "//" in sanitized:
        sanitized = sanitized.replace("//", "/")

    # Remove leading slash if present
    sanitized = sanitized.lstrip("/")

    # Normalize using PurePosixPath
    try:
        posix_path = PurePosixPath(sanitized)
        sanitized = str(posix_path)
    except ValueError:
        raise PathValidationError(f"Cannot sanitize path: {path}") from None

    # Ensure .md extension
    if not sanitized.endswith(".md"):
        sanitized += ".md"

    # Validate the sanitized path
    validate_path(sanitized)

    return sanitized


def resolve_memory_path(path: str) -> Path:
    """
    Resolve a memory path to an absolute filesystem path within memory root.

    Args:
        path: The memory path to resolve

    Returns:
        Absolute Path object within memory root

    Raises:
        PathValidationError: If path is invalid or outside memory root
    """
    # Validate the path first
    validate_path(path)

    # Create absolute path within memory root
    memory_root = settings.memory_root.resolve()
    full_path = memory_root / path

    # Ensure the resolved path is still within memory root
    try:
        full_path.resolve().relative_to(memory_root)
    except ValueError:
        raise PathValidationError(f"Path resolves outside memory root: {path}") from None

    return full_path


def get_relative_path(absolute_path: Path) -> str:
    """
    Get the relative memory path from an absolute filesystem path.

    Args:
        absolute_path: Absolute filesystem path

    Returns:
        Relative memory path string

    Raises:
        PathValidationError: If path is not within memory root
    """
    memory_root = settings.memory_root.resolve()

    try:
        relative = absolute_path.resolve().relative_to(memory_root)
        return str(relative).replace(os.sep, "/")
    except ValueError:
        raise PathValidationError(f"Path is not within memory root: {absolute_path}") from None


def extract_directory_path(path: str) -> str:
    """
    Extract the directory portion of a memory path.

    Args:
        path: Memory path

    Returns:
        Directory path without filename
    """
    posix_path = PurePosixPath(path)
    return str(posix_path.parent) if posix_path.parent != PurePosixPath(".") else ""


def is_path_within_prefix(path: str, prefix: str) -> bool:
    """
    Check if a path is within a given prefix directory.

    Args:
        path: Path to check
        prefix: Prefix directory to check against

    Returns:
        True if path is within prefix
    """
    if not prefix:
        return True

    # Normalize both paths
    path_parts = PurePosixPath(path).parts
    prefix_parts = PurePosixPath(prefix).parts

    # Path must have at least as many parts as prefix
    if len(path_parts) < len(prefix_parts):
        return False

    # Check if all prefix parts match
    return path_parts[: len(prefix_parts)] == prefix_parts


def list_directory_paths(directory: str = "") -> list[str]:
    """
    List all valid memory paths within a directory.

    Args:
        directory: Directory to list (empty for root)

    Returns:
        List of memory paths found
    """
    memory_root = settings.memory_root.resolve()

    search_dir = memory_root / directory if directory else memory_root

    if not search_dir.exists():
        return []

    paths = []
    for path in search_dir.rglob("*.md"):
        try:
            relative_path = get_relative_path(path)
            # Validate the path (this will filter out any invalid files)
            validate_path(relative_path)
            paths.append(relative_path)
        except PathValidationError:
            # Skip invalid paths
            continue

    return sorted(paths)


def ensure_parent_directory(path: str) -> Path:
    """
    Ensure the parent directory exists for a given memory path.

    Args:
        path: Memory path

    Returns:
        Path to the parent directory
    """
    full_path = resolve_memory_path(path)
    parent_dir = full_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    return parent_dir
