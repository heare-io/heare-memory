"""Tests for the search endpoint implementation."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.heare_memory.models.search import SearchMatch, SearchResult, SearchSummary
from src.heare_memory.routers.memory import router
from src.heare_memory.services.memory_service import MemoryService, MemoryServiceError


@pytest.fixture
def test_app():
    """Create a test FastAPI app with the memory router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


@pytest.fixture
def mock_memory_service():
    """Create a mock memory service."""
    return Mock(spec=MemoryService)


class TestSearchEndpoint:
    """Test the GET /memory/search endpoint."""

    def test_search_basic_query(self, client, mock_memory_service):
        """Test basic search functionality."""
        # Create mock search results
        search_match = SearchMatch(
            line_number=5,
            line_content="This is a test line with query content",
            highlighted_content="This is a test line with <mark>query</mark> content",
            context_before=["line 3", "line 4"],
            context_after=["line 6", "line 7"],
        )

        search_result = SearchResult(
            path="/memory/test/file.md",
            relative_path="test/file.md",
            matches=[search_match],
            total_matches=1,
            file_size=1024,
        )

        search_summary = SearchSummary(
            query="test",  # Changed to match the actual query
            total_files_searched=10,
            files_with_matches=1,
            total_matches=1,
            search_time_ms=45.5,
            backend_used="ripgrep",
            results=[search_result],
            truncated=False,
        )

        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert data["query"] == "test"
        assert data["total_results"] == 1
        assert data["total_matches"] == 1
        assert data["search_time_ms"] == 45.5
        assert data["backend_used"] == "ripgrep"
        assert data["truncated"] is False

        # Check results
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["path"] == "test/file.md"
        assert result["absolute_path"] == "/memory/test/file.md"
        assert result["total_matches"] == 1
        assert result["file_size"] == 1024

        # Check matches
        assert len(result["matches"]) == 1
        match = result["matches"][0]
        assert match["line_number"] == 5
        assert match["line_content"] == "This is a test line with query content"
        assert match["highlighted_content"] == "This is a test line with <mark>query</mark> content"
        assert match["context_before"] == ["line 3", "line 4"]
        assert match["context_after"] == ["line 6", "line 7"]

        # Check parameters
        params = data["parameters"]
        assert params["context_lines"] == 2
        assert params["max_results"] == 50
        assert params["case_sensitive"] is False
        assert params["is_regex"] is False
        assert params["whole_words"] is False
        assert params["timeout"] == 30.0

    def test_search_with_all_parameters(self, client, mock_memory_service):
        """Test search with all query parameters."""
        search_summary = SearchSummary(
            query="test.*pattern",
            total_files_searched=5,
            files_with_matches=0,
            total_matches=0,
            search_time_ms=12.3,
            backend_used="grep",
            results=[],
            truncated=False,
        )

        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get(
                "/memory/search"
                "?query=test.*pattern"
                "&prefix=docs"
                "&context_lines=5"
                "&max_results=100"
                "&case_sensitive=true"
                "&is_regex=true"
                "&whole_words=true"
                "&timeout=60.0"
            )

        assert response.status_code == 200
        data = response.json()

        # Verify the memory service was called with correct parameters
        mock_memory_service.search_memory_content.assert_called_once_with(
            query="test.*pattern",
            prefix="docs",
            context_lines=5,
            max_results=100,
            case_sensitive=True,
            is_regex=True,
            whole_words=True,
            timeout_seconds=60.0,
        )

        # Check response
        assert data["query"] == "test.*pattern"
        assert data["prefix"] == "docs"
        assert data["total_results"] == 0
        assert data["backend_used"] == "grep"

        # Check parameters are reflected in response
        params = data["parameters"]
        assert params["context_lines"] == 5
        assert params["max_results"] == 100
        assert params["case_sensitive"] is True
        assert params["is_regex"] is True
        assert params["whole_words"] is True
        assert params["timeout"] == 60.0

    def test_search_empty_query(self, client, mock_memory_service):
        """Test search with empty query returns 400."""
        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=")

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidQuery"
        assert "empty" in data["detail"]["message"].lower()

    def test_search_missing_query(self, client, mock_memory_service):
        """Test search without query parameter returns 422."""
        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search")

        assert response.status_code == 422  # Pydantic validation error

    def test_search_invalid_context_lines(self, client, mock_memory_service):
        """Test search with invalid context_lines parameter."""
        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            # Test negative value
            response = client.get("/memory/search?query=test&context_lines=-1")
            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"] == "InvalidParameter"
            assert "context lines" in data["detail"]["message"].lower()

            # Test too large value
            response = client.get("/memory/search?query=test&context_lines=15")
            assert response.status_code == 400

    def test_search_invalid_max_results(self, client, mock_memory_service):
        """Test search with invalid max_results parameter."""
        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            # Test too small value
            response = client.get("/memory/search?query=test&max_results=0")
            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"] == "InvalidParameter"
            assert "max results" in data["detail"]["message"].lower()

            # Test too large value
            response = client.get("/memory/search?query=test&max_results=2000")
            assert response.status_code == 400

    def test_search_invalid_timeout(self, client, mock_memory_service):
        """Test search with invalid timeout parameter."""
        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            # Test too small value
            response = client.get("/memory/search?query=test&timeout=0.5")
            assert response.status_code == 400
            data = response.json()
            assert data["detail"]["error"] == "InvalidParameter"
            assert "timeout" in data["detail"]["message"].lower()

            # Test too large value
            response = client.get("/memory/search?query=test&timeout=200.0")
            assert response.status_code == 400

    def test_search_invalid_prefix(self, client, mock_memory_service):
        """Test search with invalid prefix parameter."""
        with (
            patch(
                "src.heare_memory.routers.memory.get_memory_service",
                return_value=mock_memory_service,
            ),
            patch("src.heare_memory.routers.memory.validate_path") as mock_validate,
        ):
            from src.heare_memory.path_utils import PathValidationError

            mock_validate.side_effect = PathValidationError("Invalid path format")

            response = client.get("/memory/search?query=test&prefix=../invalid")

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "InvalidPrefix"
        assert "invalid path format" in data["detail"]["message"].lower()

    def test_search_timeout_error(self, client, mock_memory_service):
        """Test search timeout handling."""
        mock_memory_service.search_memory_content = AsyncMock(
            side_effect=MemoryServiceError("Search timed out after 30 seconds")
        )

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test")

        assert response.status_code == 408
        data = response.json()
        assert data["detail"]["error"] == "SearchTimeout"
        assert "timed out" in data["detail"]["message"].lower()

    def test_search_service_error(self, client, mock_memory_service):
        """Test search service error handling."""
        mock_memory_service.search_memory_content = AsyncMock(
            side_effect=MemoryServiceError("Search backend failed")
        )

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "InternalError"
        assert "internal server error" in data["detail"]["message"].lower()

    def test_search_unexpected_error(self, client, mock_memory_service):
        """Test unexpected error handling."""
        mock_memory_service.search_memory_content = AsyncMock(
            side_effect=ValueError("Unexpected error")
        )

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test")

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "UnexpectedError"
        assert "unexpected error" in data["detail"]["message"].lower()

    def test_search_with_prefix_normalization(self, client, mock_memory_service):
        """Test that empty string prefix is normalized to None."""
        search_summary = SearchSummary(
            query="test",
            total_files_searched=0,
            files_with_matches=0,
            total_matches=0,
            search_time_ms=5.0,
            backend_used="ripgrep",
            results=[],
            truncated=False,
        )

        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test&prefix=")

        assert response.status_code == 200

        # Verify the service was called with None prefix
        mock_memory_service.search_memory_content.assert_called_once()
        call_args = mock_memory_service.search_memory_content.call_args
        assert call_args.kwargs["prefix"] is None

    def test_search_multiple_results(self, client, mock_memory_service):
        """Test search with multiple file results."""
        # Create multiple search results
        results = []
        for i in range(3):
            match = SearchMatch(
                line_number=i + 1,
                line_content=f"Line {i + 1} with test content",
                highlighted_content=f"Line {i + 1} with <mark>test</mark> content",
                context_before=[],
                context_after=[],
                column_start=10,
                column_end=14,
            )

            result = SearchResult(
                path=f"/memory/file{i + 1}.md",
                relative_path=f"file{i + 1}.md",
                matches=[match],
                total_matches=1,
                file_size=512 + i * 100,
            )
            results.append(result)

        search_summary = SearchSummary(
            query="test",
            total_files_searched=20,
            files_with_matches=3,
            total_matches=3,
            search_time_ms=89.2,
            backend_used="ripgrep",
            results=results,
            truncated=False,
        )

        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test")

        assert response.status_code == 200
        data = response.json()

        assert data["total_results"] == 3
        assert data["total_matches"] == 3
        assert len(data["results"]) == 3

        # Check each result
        for i, result in enumerate(data["results"]):
            assert result["path"] == f"file{i + 1}.md"
            assert result["absolute_path"] == f"/memory/file{i + 1}.md"
            assert result["file_size"] == 512 + i * 100
            assert len(result["matches"]) == 1

            match = result["matches"][0]
            assert match["column_start"] == 10
            assert match["column_end"] == 14

    def test_search_truncated_results(self, client, mock_memory_service):
        """Test search with truncated results."""
        search_summary = SearchSummary(
            query="test",
            total_files_searched=100,
            files_with_matches=50,
            total_matches=150,
            search_time_ms=2000.0,
            backend_used="grep",
            results=[],  # Empty for simplicity
            truncated=True,
        )

        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=test&max_results=50")

        assert response.status_code == 200
        data = response.json()

        assert data["truncated"] is True
        assert data["total_results"] == 50
        assert data["total_matches"] == 150

    def test_search_whitespace_query_handling(self, client, mock_memory_service):
        """Test that query whitespace is properly handled."""
        search_summary = SearchSummary(
            query="test query",
            total_files_searched=0,
            files_with_matches=0,
            total_matches=0,
            search_time_ms=5.0,
            backend_used="ripgrep",
            results=[],
            truncated=False,
        )

        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        with patch(
            "src.heare_memory.routers.memory.get_memory_service",
            return_value=mock_memory_service,
        ):
            response = client.get("/memory/search?query=  test query  ")

        assert response.status_code == 200

        # Verify the service was called with stripped query
        mock_memory_service.search_memory_content.assert_called_once()
        call_args = mock_memory_service.search_memory_content.call_args
        assert call_args.kwargs["query"] == "test query"


class TestSearchIntegration:
    """Integration tests for search functionality."""

    @pytest.mark.asyncio
    async def test_search_memory_service_integration(self):
        """Test search integration with memory service."""
        from src.heare_memory.services.memory_service import MemoryService

        # Create mock dependencies
        mock_file_manager = Mock()
        mock_git_manager = Mock()

        memory_service = MemoryService(mock_file_manager, mock_git_manager)

        # Mock the search backend
        with patch("src.heare_memory.services.memory_service.search_backend") as mock_backend:
            search_summary = SearchSummary(
                query="test",
                total_files_searched=1,
                files_with_matches=1,
                total_matches=1,
                search_time_ms=50.0,
                backend_used="ripgrep",
                results=[],
                truncated=False,
            )
            mock_backend.search_content = AsyncMock(return_value=search_summary)

            # Test the search method
            result = await memory_service.search_memory_content(
                query="test",
                prefix="docs",
                context_lines=3,
                max_results=25,
                case_sensitive=True,
                is_regex=False,
                whole_words=True,
                timeout_seconds=45.0,
            )

            assert result == search_summary

            # Verify backend was called correctly
            mock_backend.search_content.assert_called_once()
            call_args = mock_backend.search_content.call_args

            # Check SearchQuery was created with correct parameters
            search_query = call_args.kwargs["query"]
            assert search_query.pattern == "test"
            assert search_query.context_lines == 3
            assert search_query.max_results == 25
            assert search_query.case_sensitive is True
            assert search_query.is_regex is False
            assert search_query.whole_words is True

            assert call_args.kwargs["prefix"] == "docs"
            assert call_args.kwargs["timeout_seconds"] == 45.0
