"""Search result models for memory content search."""

from pydantic import BaseModel, Field


class SearchMatch(BaseModel):
    """Represents a single match within a file."""

    line_number: int = Field(description="Line number where the match was found (1-indexed)")
    line_content: str = Field(description="Full content of the matching line")
    highlighted_content: str = Field(description="Line content with query highlighted")
    context_before: list[str] = Field(
        description="Lines before the match for context", default_factory=list
    )
    context_after: list[str] = Field(
        description="Lines after the match for context", default_factory=list
    )
    column_start: int | None = Field(
        description="Start column of the match (0-indexed)", default=None
    )
    column_end: int | None = Field(description="End column of the match (0-indexed)", default=None)


class SearchResult(BaseModel):
    """Represents search results for a single file."""

    path: str = Field(description="Full filesystem path to the file")
    relative_path: str = Field(description="Path relative to memory root")
    matches: list[SearchMatch] = Field(description="All matches found in this file")
    total_matches: int = Field(description="Total number of matches in the file")
    file_size: int | None = Field(description="Size of the file in bytes", default=None)


class SearchQuery(BaseModel):
    """Represents a search query with validation."""

    pattern: str = Field(description="Search pattern or regex")
    is_regex: bool = Field(
        description="Whether the pattern should be treated as regex", default=False
    )
    case_sensitive: bool = Field(description="Whether the search is case sensitive", default=False)
    whole_words: bool = Field(description="Whether to match whole words only", default=False)
    context_lines: int = Field(
        description="Number of context lines to include", default=2, ge=0, le=10
    )
    max_results: int = Field(
        description="Maximum number of file results to return", default=50, ge=1, le=1000
    )
    max_matches_per_file: int = Field(
        description="Maximum number of matches per file", default=10, ge=1, le=100
    )

    def validate_pattern(self) -> None:
        """Validate the search pattern for security and correctness."""
        if not self.pattern or not self.pattern.strip():
            raise ValueError("Search pattern cannot be empty")

        if len(self.pattern) > 1000:
            raise ValueError("Search pattern too long (max 1000 characters)")

        # Basic validation for dangerous patterns
        dangerous_chars = ["\x00", "\x01", "\x02", "\x03", "\x04", "\x05"]
        if any(char in self.pattern for char in dangerous_chars):
            raise ValueError("Search pattern contains invalid control characters")

        if self.is_regex:
            # Additional regex validation
            import re

            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}") from e


class SearchSummary(BaseModel):
    """Summary of search results across all files."""

    query: str = Field(description="The search query used")
    total_files_searched: int = Field(description="Total number of files searched")
    files_with_matches: int = Field(description="Number of files containing matches")
    total_matches: int = Field(description="Total number of matches across all files")
    search_time_ms: float = Field(description="Time taken for the search in milliseconds")
    backend_used: str = Field(description="Search backend used (ripgrep/grep)")
    results: list[SearchResult] = Field(description="Individual file results")
    truncated: bool = Field(
        description="Whether results were truncated due to limits", default=False
    )
