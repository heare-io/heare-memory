"""Simple tests for the search endpoint to verify implementation."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.heare_memory.models.search import SearchMatch, SearchResult, SearchSummary
from src.heare_memory.routers.memory import search_memory_nodes
from src.heare_memory.services.memory_service import MemoryService


class TestSearchEndpointFunction:
    """Test the search endpoint function directly."""

    @pytest.mark.asyncio
    async def test_search_function_basic(self):
        """Test the search function directly with mocked dependencies."""
        # Create mock search results
        search_match = SearchMatch(
            line_number=5,
            line_content="This is a test line with query content",
            highlighted_content="This is a test line with <mark>test</mark> content",
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
            query="test",
            total_files_searched=10,
            files_with_matches=1,
            total_matches=1,
            search_time_ms=45.5,
            backend_used="ripgrep",
            results=[search_result],
            truncated=False,
        )

        # Mock the memory service
        mock_memory_service = Mock(spec=MemoryService)
        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        # Mock request object
        mock_request = Mock()
        mock_request.client = "127.0.0.1:8000"

        # Call the function directly
        result = await search_memory_nodes(
            query="test",
            request=mock_request,
            prefix=None,
            context_lines=2,
            max_results=50,
            case_sensitive=False,
            is_regex=False,
            whole_words=False,
            timeout=30.0,
            memory_service=mock_memory_service,
        )

        # Verify the result
        assert result["query"] == "test"
        assert result["total_results"] == 1
        assert result["total_matches"] == 1
        assert result["search_time_ms"] == 45.5
        assert result["backend_used"] == "ripgrep"
        assert result["truncated"] is False

        # Check results structure
        assert len(result["results"]) == 1
        file_result = result["results"][0]
        assert file_result["path"] == "test/file.md"
        assert file_result["absolute_path"] == "/memory/test/file.md"
        assert file_result["total_matches"] == 1
        assert file_result["file_size"] == 1024

        # Check matches
        assert len(file_result["matches"]) == 1
        match = file_result["matches"][0]
        assert match["line_number"] == 5
        assert match["line_content"] == "This is a test line with query content"
        assert match["highlighted_content"] == "This is a test line with <mark>test</mark> content"
        assert match["context_before"] == ["line 3", "line 4"]
        assert match["context_after"] == ["line 6", "line 7"]

        # Check parameters
        params = result["parameters"]
        assert params["context_lines"] == 2
        assert params["max_results"] == 50
        assert params["case_sensitive"] is False
        assert params["is_regex"] is False
        assert params["whole_words"] is False
        assert params["timeout"] == 30.0

        # Verify the service was called correctly
        mock_memory_service.search_memory_content.assert_called_once_with(
            query="test",
            prefix=None,
            context_lines=2,
            max_results=50,
            case_sensitive=False,
            is_regex=False,
            whole_words=False,
            timeout_seconds=30.0,
        )

    @pytest.mark.asyncio
    async def test_search_function_with_prefix(self):
        """Test search function with prefix parameter."""
        # Mock empty results
        search_summary = SearchSummary(
            query="test query",
            total_files_searched=5,
            files_with_matches=0,
            total_matches=0,
            search_time_ms=12.3,
            backend_used="grep",
            results=[],
            truncated=False,
        )

        mock_memory_service = Mock(spec=MemoryService)
        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        mock_request = Mock()
        mock_request.client = "127.0.0.1:8000"

        # Test with prefix
        result = await search_memory_nodes(
            query="test query",
            request=mock_request,
            prefix="docs",
            context_lines=3,
            max_results=25,
            case_sensitive=True,
            is_regex=True,
            whole_words=True,
            timeout=60.0,
            memory_service=mock_memory_service,
        )

        # Verify the result
        assert result["query"] == "test query"
        assert result["prefix"] == "docs"
        assert result["total_results"] == 0
        assert result["backend_used"] == "grep"

        # Check parameters
        params = result["parameters"]
        assert params["context_lines"] == 3
        assert params["max_results"] == 25
        assert params["case_sensitive"] is True
        assert params["is_regex"] is True
        assert params["whole_words"] is True
        assert params["timeout"] == 60.0

        # Verify service call
        mock_memory_service.search_memory_content.assert_called_once_with(
            query="test query",
            prefix="docs",
            context_lines=3,
            max_results=25,
            case_sensitive=True,
            is_regex=True,
            whole_words=True,
            timeout_seconds=60.0,
        )

    @pytest.mark.asyncio
    async def test_search_function_validation_errors(self):
        """Test search function parameter validation."""
        from fastapi import HTTPException

        mock_memory_service = Mock(spec=MemoryService)
        mock_request = Mock()
        mock_request.client = "127.0.0.1:8000"

        # Test empty query - should raise HTTPException with 400 status
        with pytest.raises(HTTPException) as exc_info:
            await search_memory_nodes(
                query="",
                request=mock_request,
                memory_service=mock_memory_service,
            )

        # Now it should properly return 400 status
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "InvalidQuery"

        # Test invalid context_lines
        with pytest.raises(HTTPException) as exc_info:
            await search_memory_nodes(
                query="test",
                request=mock_request,
                context_lines=15,  # Too high
                memory_service=mock_memory_service,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "InvalidParameter"
        assert "context" in exc_info.value.detail["message"].lower()

        # Test invalid max_results
        with pytest.raises(HTTPException) as exc_info:
            await search_memory_nodes(
                query="test",
                request=mock_request,
                max_results=2000,  # Too high
                memory_service=mock_memory_service,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "InvalidParameter"
        assert "max results" in exc_info.value.detail["message"].lower()

    @pytest.mark.asyncio
    async def test_search_function_service_error_handling(self):
        """Test search function error handling."""
        from src.heare_memory.services.memory_service import MemoryServiceError

        mock_memory_service = Mock(spec=MemoryService)
        mock_request = Mock()
        mock_request.client = "127.0.0.1:8000"

        # Test timeout error
        mock_memory_service.search_memory_content = AsyncMock(
            side_effect=MemoryServiceError("Search timed out after 30 seconds")
        )

        with pytest.raises(Exception) as exc_info:
            await search_memory_nodes(
                query="test",
                request=mock_request,
                memory_service=mock_memory_service,
            )

        # Should be a timeout error (408)
        assert "SearchTimeout" in str(exc_info.value) or "timed out" in str(exc_info.value).lower()

        # Test general service error
        mock_memory_service.search_memory_content = AsyncMock(
            side_effect=MemoryServiceError("Backend failed")
        )

        with pytest.raises(Exception) as exc_info:
            await search_memory_nodes(
                query="test",
                request=mock_request,
                memory_service=mock_memory_service,
            )

        # Should be an internal error (500)
        assert "InternalError" in str(exc_info.value) or "internal" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_function_multiple_results(self):
        """Test search function with multiple file results."""
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

        mock_memory_service = Mock(spec=MemoryService)
        mock_memory_service.search_memory_content = AsyncMock(return_value=search_summary)

        mock_request = Mock()
        mock_request.client = "127.0.0.1:8000"

        result = await search_memory_nodes(
            query="test",
            request=mock_request,
            memory_service=mock_memory_service,
        )

        assert result["total_results"] == 3
        assert result["total_matches"] == 3
        assert len(result["results"]) == 3

        # Check each result
        for i, file_result in enumerate(result["results"]):
            assert file_result["path"] == f"file{i + 1}.md"
            assert file_result["absolute_path"] == f"/memory/file{i + 1}.md"
            assert file_result["file_size"] == 512 + i * 100
            assert len(file_result["matches"]) == 1

            match = file_result["matches"][0]
            assert match["column_start"] == 10
            assert match["column_end"] == 14
