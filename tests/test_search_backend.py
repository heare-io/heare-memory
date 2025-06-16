"""Tests for search backend functionality."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.heare_memory.models.search import SearchQuery, SearchSummary
from src.heare_memory.search_backend import SearchBackend, SearchBackendError


class TestSearchBackend:
    """Test search backend functionality."""

    @pytest.fixture
    def search_backend(self):
        """Create a SearchBackend instance for testing."""
        return SearchBackend()

    @pytest.fixture
    def sample_query(self):
        """Create a sample search query."""
        return SearchQuery(
            pattern="test content",
            is_regex=False,
            case_sensitive=False,
            context_lines=2,
            max_results=10,
        )

    @pytest.fixture
    def temp_search_root(self, tmp_path):
        """Create a temporary directory with test files for searching."""
        search_root = tmp_path / "search_test"
        search_root.mkdir()

        # Create test files
        (search_root / "file1.md").write_text(
            "# File 1\n\nThis contains test content for searching.\n\nAnother line."
        )
        (search_root / "file2.md").write_text(
            "# File 2\n\nDifferent content here.\n\nTest content is also here."
        )
        (search_root / "subdir").mkdir()
        (search_root / "subdir" / "file3.md").write_text(
            "# Nested File\n\nThis has test content in a subdirectory."
        )

        return search_root

    @pytest.mark.asyncio
    async def test_backend_detection_ripgrep_available(self, search_backend):
        """Test backend detection when ripgrep is available."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock ripgrep being available
            mock_proc_rg = AsyncMock()
            mock_proc_rg.returncode = 0
            mock_proc_rg.communicate.return_value = (b"ripgrep 13.0.0", b"")

            # Mock grep being available
            mock_proc_grep = AsyncMock()
            mock_proc_grep.returncode = 0
            mock_proc_grep.communicate.return_value = (b"grep (GNU grep) 3.7", b"")

            mock_subprocess.side_effect = [mock_proc_rg, mock_proc_grep]

            backends = await search_backend.detect_backends()

            assert backends["ripgrep"] is True
            assert backends["grep"] is True

            status = search_backend.get_backend_status()
            assert status["preferred_backend"] == "ripgrep"

    @pytest.mark.asyncio
    async def test_backend_detection_grep_only(self, search_backend):
        """Test backend detection when only grep is available."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock ripgrep not available
            mock_proc_rg = AsyncMock()
            mock_proc_rg.side_effect = FileNotFoundError()

            # Mock grep being available
            mock_proc_grep = AsyncMock()
            mock_proc_grep.returncode = 0
            mock_proc_grep.communicate.return_value = (b"grep (GNU grep) 3.7", b"")

            mock_subprocess.side_effect = [mock_proc_rg, mock_proc_grep]

            backends = await search_backend.detect_backends()

            assert backends["ripgrep"] is False
            assert backends["grep"] is True

            status = search_backend.get_backend_status()
            assert status["preferred_backend"] == "grep"

    @pytest.mark.asyncio
    async def test_backend_detection_none_available(self, search_backend):
        """Test backend detection when no backends are available."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            # Mock both tools not available
            mock_subprocess.side_effect = FileNotFoundError()

            backends = await search_backend.detect_backends()

            assert backends["ripgrep"] is False
            assert backends["grep"] is False

            status = search_backend.get_backend_status()
            assert status["preferred_backend"] is None

    def test_search_query_validation_valid(self):
        """Test search query validation with valid patterns."""
        query = SearchQuery(pattern="test", is_regex=False)
        query.validate_pattern()  # Should not raise

        regex_query = SearchQuery(pattern=r"test\d+", is_regex=True)
        regex_query.validate_pattern()  # Should not raise

    def test_search_query_validation_empty(self):
        """Test search query validation with empty pattern."""
        query = SearchQuery(pattern="", is_regex=False)
        with pytest.raises(ValueError, match="Search pattern cannot be empty"):
            query.validate_pattern()

        query2 = SearchQuery(pattern="   ", is_regex=False)
        with pytest.raises(ValueError, match="Search pattern cannot be empty"):
            query2.validate_pattern()

    def test_search_query_validation_too_long(self):
        """Test search query validation with too long pattern."""
        query = SearchQuery(pattern="x" * 1001, is_regex=False)
        with pytest.raises(ValueError, match="Search pattern too long"):
            query.validate_pattern()

    def test_search_query_validation_invalid_regex(self):
        """Test search query validation with invalid regex."""
        query = SearchQuery(pattern="[invalid", is_regex=True)
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            query.validate_pattern()

    def test_search_query_validation_control_chars(self):
        """Test search query validation with control characters."""
        query = SearchQuery(pattern="test\x00content", is_regex=False)
        with pytest.raises(ValueError, match="contains invalid control characters"):
            query.validate_pattern()

    @pytest.mark.asyncio
    async def test_search_no_backends_available(self, search_backend, sample_query):
        """Test search when no backends are available."""
        search_backend._preferred_backend = None

        with pytest.raises(SearchBackendError, match="No search backends available"):
            await search_backend.search_content(sample_query)

    def test_highlight_matches(self, search_backend):
        """Test match highlighting functionality."""
        content = "This is test content with test words"
        pattern = "test"

        highlighted = search_backend._highlight_matches(content, pattern)
        assert "<mark>test</mark>" in highlighted
        assert highlighted.count("<mark>test</mark>") == 2

    def test_highlight_matches_empty_pattern(self, search_backend):
        """Test match highlighting with empty pattern."""
        content = "This is test content"
        pattern = ""

        highlighted = search_backend._highlight_matches(content, pattern)
        assert highlighted == content
        assert "<mark>" not in highlighted

    @pytest.mark.asyncio
    async def test_search_with_ripgrep_mock(self, search_backend, sample_query, temp_search_root):
        """Test search using mocked ripgrep."""
        search_backend._preferred_backend = "ripgrep"

        # Mock ripgrep JSON output
        ripgrep_output = (
            '{"type":"match","data":{"path":{"text":"file1.md"},'
            '"lines":{"text":"This contains test content for searching."},'
            '"line_number":3,"absolute_offset":20,"submatches":'
            '[{"match":{"text":"test"},"start":14,"end":18}]}}\n'
            '{"type":"match","data":{"path":{"text":"file2.md"},'
            '"lines":{"text":"Test content is also here."},'
            '"line_number":4,"absolute_offset":45,"submatches":'
            '[{"match":{"text":"Test"},"start":0,"end":4}]}}'
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (ripgrep_output.encode(), b"")
            mock_subprocess.return_value = mock_proc

            result = await search_backend.search_content(sample_query, temp_search_root)

            assert isinstance(result, SearchSummary)
            assert result.backend_used == "ripgrep"
            assert result.files_with_matches >= 1
            assert len(result.results) >= 1
            assert result.search_time_ms > 0

    @pytest.mark.asyncio
    async def test_search_with_grep_mock(self, search_backend, sample_query, temp_search_root):
        """Test search using mocked grep."""
        search_backend._preferred_backend = "grep"

        # Mock grep text output
        grep_output = """file1.md:3:This contains test content for searching.
file2.md:4:Test content is also here."""

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (grep_output.encode(), b"")
            mock_subprocess.return_value = mock_proc

            result = await search_backend.search_content(sample_query, temp_search_root)

            assert isinstance(result, SearchSummary)
            assert result.backend_used == "grep"
            assert result.files_with_matches >= 1
            assert len(result.results) >= 1
            assert result.search_time_ms > 0

    @pytest.mark.asyncio
    async def test_search_timeout(self, search_backend, sample_query, temp_search_root):
        """Test search timeout handling."""
        search_backend._preferred_backend = "ripgrep"

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.communicate.side_effect = TimeoutError()
            mock_subprocess.return_value = mock_proc

            with pytest.raises(SearchBackendError, match="Search timed out"):
                await search_backend.search_content(
                    sample_query, temp_search_root, timeout_seconds=0.1
                )

    @pytest.mark.asyncio
    async def test_search_with_prefix(self, search_backend, sample_query, temp_search_root):
        """Test search with path prefix limitation."""
        search_backend._preferred_backend = "ripgrep"

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_proc

            await search_backend.search_content(sample_query, temp_search_root, prefix="subdir")

            # Verify that the command included the prefix path
            args, kwargs = mock_subprocess.call_args
            command_args = args
            assert str(temp_search_root / "subdir") in command_args

    @pytest.mark.asyncio
    async def test_search_max_results_limit(self, search_backend, temp_search_root):
        """Test search respects max results limit."""
        query = SearchQuery(pattern="test", max_results=1)
        search_backend._preferred_backend = "ripgrep"

        # Mock multiple results
        ripgrep_output = (
            '{"type":"match","data":{"path":{"text":"file1.md"},'
            '"lines":{"text":"test 1"},"line_number":1}}\n'
            '{"type":"match","data":{"path":{"text":"file2.md"},'
            '"lines":{"text":"test 2"},"line_number":1}}\n'
            '{"type":"match","data":{"path":{"text":"file3.md"},'
            '"lines":{"text":"test 3"},"line_number":1}}'
        )

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (ripgrep_output.encode(), b"")
            mock_subprocess.return_value = mock_proc

            result = await search_backend.search_content(query, temp_search_root)

            assert len(result.results) <= query.max_results
            assert result.truncated is True

    def test_parse_ripgrep_output_empty(self, search_backend, sample_query):
        """Test parsing empty ripgrep output."""
        result = search_backend._parse_ripgrep_output("", Path("/safe/path"), sample_query)
        assert result == []

    def test_parse_grep_output_empty(self, search_backend, sample_query):
        """Test parsing empty grep output."""
        result = search_backend._parse_grep_output("", Path("/safe/path"), sample_query)
        assert result == []

    def test_parse_grep_output_invalid_format(self, search_backend, sample_query):
        """Test parsing grep output with invalid format."""
        invalid_output = "invalid line format"
        result = search_backend._parse_grep_output(invalid_output, Path("/safe/path"), sample_query)
        assert result == []

    def test_build_search_result_from_ripgrep(self, search_backend, sample_query):
        """Test building search result from ripgrep data."""
        matches = [
            {
                "data": {
                    "line": {"number": 5, "text": "This is a test line"},
                }
            }
        ]

        result = search_backend._build_search_result_from_ripgrep(
            "/path/to/file.md", "file.md", matches, [], sample_query
        )

        assert result.path == "/path/to/file.md"
        assert result.relative_path == "file.md"
        assert len(result.matches) == 1
        assert result.matches[0].line_number == 5
        assert result.matches[0].line_content == "This is a test line"

    def test_build_search_result_from_grep(self, search_backend, sample_query):
        """Test building search result from grep data."""
        lines = [
            {"line_number": 5, "content": "This is a test line", "is_match": True},
            {"line_number": 6, "content": "Context line after", "is_match": False},
        ]

        result = search_backend._build_search_result_from_grep(
            "/path/to/file.md", "file.md", lines, sample_query
        )

        assert result.path == "/path/to/file.md"
        assert result.relative_path == "file.md"
        assert len(result.matches) == 1
        assert result.matches[0].line_number == 5
        assert result.matches[0].line_content == "This is a test line"


class TestSearchQueryModel:
    """Test SearchQuery model validation and functionality."""

    def test_default_values(self):
        """Test SearchQuery default values."""
        query = SearchQuery(pattern="test")

        assert query.pattern == "test"
        assert query.is_regex is False
        assert query.case_sensitive is False
        assert query.whole_words is False
        assert query.context_lines == 2
        assert query.max_results == 50
        assert query.max_matches_per_file == 10

    def test_validation_constraints(self):
        """Test SearchQuery validation constraints."""
        # Test context_lines constraints
        with pytest.raises(ValueError):
            SearchQuery(pattern="test", context_lines=-1)

        with pytest.raises(ValueError):
            SearchQuery(pattern="test", context_lines=11)

        # Test max_results constraints
        with pytest.raises(ValueError):
            SearchQuery(pattern="test", max_results=0)

        with pytest.raises(ValueError):
            SearchQuery(pattern="test", max_results=1001)

        # Test max_matches_per_file constraints
        with pytest.raises(ValueError):
            SearchQuery(pattern="test", max_matches_per_file=0)

        with pytest.raises(ValueError):
            SearchQuery(pattern="test", max_matches_per_file=101)
