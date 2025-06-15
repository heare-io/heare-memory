"""Pytest configuration and fixtures for the memory service tests."""

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from git import Repo

from heare_memory.config import Settings
from heare_memory.dependencies import get_memory_service
from heare_memory.file_manager import FileManager
from heare_memory.git_manager import GitManager
from heare_memory.routers.memory import router
from heare_memory.services.memory_service import MemoryService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def temp_git_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository for testing."""
    repo_path = temp_dir / "test_repo"
    repo_path.mkdir()

    # Initialize git repository
    repo = Repo.init(repo_path)

    # Configure git user for commits
    with repo.config_writer() as git_config:
        git_config.set_value("user", "name", "Test User")
        git_config.set_value("user", "email", "test@example.com")

    # Create initial commit
    readme_file = repo_path / "README.md"
    readme_file.write_text("# Test Repository\n\nThis is a test repository.")
    repo.index.add([str(readme_file)])
    repo.index.commit("Initial commit")

    yield repo_path


@pytest.fixture
def test_settings(temp_git_repo: Path) -> Settings:
    """Create test settings with temporary directory."""
    return Settings(
        memory_root=temp_git_repo,
        git_remote_url=None,  # No remote for tests
        github_token=None,  # Read-only mode for tests
        log_level="DEBUG",
        debug=True,
    )


@pytest.fixture
async def file_manager(test_settings: Settings) -> FileManager:
    """Create a FileManager instance for testing."""
    # Mock the settings in file_manager module
    import heare_memory.file_manager

    original_settings = heare_memory.file_manager.settings
    heare_memory.file_manager.settings = test_settings

    try:
        yield FileManager()
    finally:
        # Restore original settings
        heare_memory.file_manager.settings = original_settings


@pytest.fixture
async def git_manager(test_settings: Settings) -> GitManager:
    """Create a GitManager instance for testing."""
    git_manager = GitManager(repository_path=test_settings.memory_root)
    # Initialize the repository if needed
    await git_manager.initialize_repository()
    return git_manager


@pytest.fixture
async def memory_service(file_manager: FileManager, git_manager: GitManager) -> MemoryService:
    """Create a MemoryService instance for testing."""
    return MemoryService(file_manager, git_manager)


@pytest.fixture
def app_with_real_service(memory_service: MemoryService) -> FastAPI:
    """Create FastAPI app with real memory service for integration testing."""
    app = FastAPI()
    app.include_router(router)

    # Override dependency with real service
    app.dependency_overrides[get_memory_service] = lambda: memory_service

    return app


@pytest.fixture
def integration_client(app_with_real_service: FastAPI) -> TestClient:
    """Create TestClient for integration testing with real services."""
    return TestClient(app_with_real_service)


@pytest.fixture
def mock_readonly_settings(monkeypatch) -> Mock:
    """Mock settings in read-only mode."""
    mock_settings = Mock()
    mock_settings.is_read_only = True
    monkeypatch.setattr("heare_memory.config.settings", mock_settings)
    return mock_settings


@pytest.fixture
def mock_writable_settings(monkeypatch) -> Mock:
    """Mock settings in writable mode."""
    mock_settings = Mock()
    mock_settings.is_read_only = False
    monkeypatch.setattr("heare_memory.config.settings", mock_settings)
    return mock_settings


# Sample test data
SAMPLE_MEMORY_CONTENT = {
    "simple": "# Simple Memory\n\nBasic content for testing.",
    "complex": """# Complex Memory

This is a more complex memory with:

- **Bold text**
- *Italic text*
- `code snippets`
- [Links](https://example.com)

## Code Block

```python
def hello_world():
    print("Hello, World!")
```

## Lists

1. First item
2. Second item
3. Third item

- Bullet point 1
- Bullet point 2
- Bullet point 3
""",
    "unicode": "# Unicode Memory\n\n🚀 Rocket emoji\n中文 Chinese text\n🎉 Party emoji\nSpecial chars: αβγδε",  # noqa: E501
    "large": "# Large Memory\n\n" + "This is line {}\n".format("{}") * 1000,
    "markdown_features": """# Markdown Features Test

## Headers
### Sub Header
#### Sub Sub Header

## Text Formatting
**Bold**, *italic*, ***bold italic***, ~~strikethrough~~

## Lists
1. Ordered item 1
2. Ordered item 2
   - Nested unordered
   - Another nested item

## Links and Images
[Test Link](https://example.com)
![Alt text](https://example.com/image.png)

## Code
Inline `code` and blocks:

```javascript
function test() {
    return "Hello World";
}
```

## Tables
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |

## Blockquotes
> This is a blockquote
>
> With multiple lines

## Horizontal Rule
---

End of document.
""",
}


@pytest.fixture
def sample_content():
    """Provide sample content for testing."""
    return SAMPLE_MEMORY_CONTENT


@pytest.fixture(params=["simple", "complex", "unicode", "markdown_features"])
def sample_memory_node(request, sample_content):
    """Parametrized fixture providing different types of memory content."""
    content_key = request.param
    return {
        "path": f"test/{content_key}.md",
        "content": sample_content[content_key],
        "content_type": content_key,
    }


# Error testing fixtures
@pytest.fixture(
    params=[
        "../traversal",
        "../../escape",
        "/absolute/path",
        "path\\with\\backslashes",
        "path//with//doubles",
        "path\x00with\x00nulls",
        "con.md",  # Windows reserved name
        "a" * 1000,  # Very long path
    ]
)
def invalid_path(request):
    """Parametrized fixture providing invalid paths for testing."""
    return request.param


@pytest.fixture(
    params=[
        "",  # Empty content
        "\x00invalid\x00content",  # Null bytes
        "a" * (10_000_001),  # Content too large
    ]
)
def invalid_content(request):
    """Parametrized fixture providing invalid content for testing."""
    return request.param


# Performance testing fixtures
@pytest.fixture
def large_content():
    """Generate large content for performance testing."""
    return "# Large File\n\n" + "Line of content with some text. " * 100000


@pytest.fixture
def stress_test_paths():
    """Generate multiple paths for stress testing."""
    return [f"stress/test_{i:04d}.md" for i in range(100)]


# Async utilities
@pytest_asyncio.fixture
async def async_test_setup(memory_service: MemoryService, sample_content: dict):
    """Set up test data for async tests."""
    # Create some initial test files
    test_files = {
        "existing/file1.md": sample_content["simple"],
        "existing/file2.md": sample_content["complex"],
        "existing/nested/deep/file3.md": sample_content["unicode"],
    }

    created_files = []
    for path, content in test_files.items():
        try:
            memory_node = await memory_service.create_memory_node(path, content)
            created_files.append(memory_node.path)
        except Exception as e:
            # Log but don't fail - some tests might not need all files
            print(f"Warning: Could not create test file {path}: {e}")

    yield created_files

    # Cleanup is automatic since we're using temporary directories


# Helper functions for tests
def assert_memory_node_equal(actual, expected_path: str, expected_content: str):
    """Assert that a memory node matches expected values."""
    # Handle both MemoryNode objects and dict responses
    if hasattr(actual, "path"):
        # MemoryNode object
        assert actual.path == expected_path
        assert actual.content == expected_content
        assert actual.metadata.exists is True
        assert actual.metadata.size == len(expected_content.encode("utf-8"))
        assert actual.metadata.sha is not None
        assert actual.metadata.created_at is not None
        assert actual.metadata.updated_at is not None
    else:
        # Dict response
        assert actual["path"] == expected_path
        assert actual["content"] == expected_content
        assert actual["metadata"]["exists"] is True
        assert actual["metadata"]["size"] == len(expected_content.encode("utf-8"))
        assert actual["metadata"]["sha"] is not None
        assert actual["metadata"]["created_at"] is not None
        assert actual["metadata"]["updated_at"] is not None


def assert_error_response(response, expected_status: int, expected_error: str):
    """Assert that an error response matches expected values."""
    assert response.status_code == expected_status
    data = response.json()
    assert "detail" in data
    assert data["detail"]["error"] == expected_error
    assert "message" in data["detail"]
    assert "path" in data["detail"]
