"""Search backend implementation with ripgrep and grep support."""

import asyncio
import json
import logging
import re
import shlex
import time
from pathlib import Path
from typing import Any

from .config import settings
from .models.search import SearchMatch, SearchQuery, SearchResult, SearchSummary

logger = logging.getLogger(__name__)


class SearchBackendError(Exception):
    """Base exception for search backend operations."""


class SearchBackend:
    """
    Search backend that wraps ripgrep with grep fallback.

    Provides async content search across memory files with proper
    validation, security, and performance considerations.
    """

    def __init__(self):
        """Initialize the search backend."""
        self._ripgrep_available: bool | None = None
        self._grep_available: bool | None = None
        self._preferred_backend: str | None = None

    async def detect_backends(self) -> dict[str, bool]:
        """
        Detect available search backends.

        Returns:
            Dict with backend availability status
        """
        backends = {"ripgrep": False, "grep": False}

        # Check for ripgrep
        try:
            proc = await asyncio.create_subprocess_exec(
                "rg",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                backends["ripgrep"] = True
                logger.info("ripgrep detected and available")
        except (TimeoutError, FileNotFoundError, Exception) as e:
            logger.debug(f"ripgrep not available: {e}")

        # Check for grep
        try:
            proc = await asyncio.create_subprocess_exec(
                "grep",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                backends["grep"] = True
                logger.info("grep detected and available")
        except (TimeoutError, FileNotFoundError, Exception) as e:
            logger.debug(f"grep not available: {e}")

        self._ripgrep_available = backends["ripgrep"]
        self._grep_available = backends["grep"]

        # Set preferred backend
        if self._ripgrep_available:
            self._preferred_backend = "ripgrep"
        elif self._grep_available:
            self._preferred_backend = "grep"
        else:
            self._preferred_backend = None
            logger.warning("No search backends available")

        return backends

    def get_backend_status(self) -> dict[str, Any]:
        """
        Get current backend status information.

        Returns:
            Dict with backend status details
        """
        return {
            "ripgrep_available": self._ripgrep_available,
            "grep_available": self._grep_available,
            "preferred_backend": self._preferred_backend,
            "backends_detected": self._ripgrep_available is not None,
        }

    async def search_content(
        self,
        query: SearchQuery,
        search_root: Path | None = None,
        prefix: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> SearchSummary:
        """
        Search for content across memory files.

        Args:
            query: Validated search query
            search_root: Root directory to search (defaults to memory root)
            prefix: Path prefix to limit search scope
            timeout_seconds: Maximum time for search operation

        Returns:
            SearchSummary with results

        Raises:
            SearchBackendError: If search fails or no backends available
        """
        start_time = time.time()

        # Validate query
        query.validate_pattern()

        # Use memory root if not specified
        if search_root is None:
            search_root = settings.memory_root

        # Ensure backends are detected
        if self._preferred_backend is None:
            await self.detect_backends()

        if self._preferred_backend is None:
            raise SearchBackendError("No search backends available")

        try:
            if self._preferred_backend == "ripgrep":
                results = await self._search_with_ripgrep(
                    query, search_root, prefix, timeout_seconds
                )
            else:
                results = await self._search_with_grep(query, search_root, prefix, timeout_seconds)

            end_time = time.time()
            search_time_ms = (end_time - start_time) * 1000

            # Calculate summary statistics
            total_files_searched = 0  # This would need more sophisticated tracking
            files_with_matches = len(results)
            total_matches = sum(result.total_matches for result in results)

            return SearchSummary(
                query=query.pattern,
                total_files_searched=total_files_searched,
                files_with_matches=files_with_matches,
                total_matches=total_matches,
                search_time_ms=search_time_ms,
                backend_used=self._preferred_backend,
                results=results,
                truncated=len(results) >= query.max_results,
            )

        except TimeoutError:
            raise SearchBackendError(f"Search timed out after {timeout_seconds} seconds") from None
        except Exception as e:
            logger.error(f"Search failed with {self._preferred_backend}: {e}")
            raise SearchBackendError(f"Search operation failed: {e}") from e

    async def _search_with_ripgrep(
        self,
        query: SearchQuery,
        search_root: Path,
        prefix: str | None,
        timeout_seconds: float,
    ) -> list[SearchResult]:
        """Search using ripgrep with JSON output."""
        # Build ripgrep command
        cmd = ["rg"]

        # Add flags
        cmd.extend(
            [
                "--json",  # JSON output for easier parsing
                "--with-filename",
                "--line-number",
                "--no-heading",
            ]
        )

        # Case sensitivity
        if not query.case_sensitive:
            cmd.append("--ignore-case")

        # Word boundaries
        if query.whole_words:
            cmd.append("--word-regexp")

        # Context lines
        if query.context_lines > 0:
            cmd.extend(["--context", str(query.context_lines)])

        # Max count per file
        cmd.extend(["--max-count", str(query.max_matches_per_file)])

        # File pattern (only .md files)
        cmd.extend(["--glob", "*.md"])

        # Search pattern
        if query.is_regex:
            cmd.append(query.pattern)
        else:
            cmd.extend(["--fixed-strings", query.pattern])

        # Search directory
        search_dir = search_root
        if prefix:
            search_dir = search_root / prefix

        cmd.append(str(search_dir))

        logger.debug(f"Running ripgrep command: {' '.join(shlex.quote(arg) for arg in cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(search_root),
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)

            return self._parse_ripgrep_output(stdout.decode("utf-8"), search_root, query)

        except TimeoutError:
            # Kill the process if it's still running
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise

    async def _search_with_grep(
        self,
        query: SearchQuery,
        search_root: Path,
        prefix: str | None,
        timeout_seconds: float,
    ) -> list[SearchResult]:
        """Search using grep with text output."""
        # Build grep command
        cmd = ["grep"]

        # Add flags
        cmd.extend(
            [
                "--recursive",
                "--line-number",
                "--with-filename",
            ]
        )

        # Case sensitivity
        if not query.case_sensitive:
            cmd.append("--ignore-case")

        # Word boundaries
        if query.whole_words:
            cmd.append("--word-regexp")

        # Context lines
        if query.context_lines > 0:
            cmd.extend(["--context", str(query.context_lines)])

        # Include only .md files
        cmd.extend(["--include", "*.md"])

        # Max matches per file (not directly supported, handle in parsing)
        # cmd.extend(["--max-count", str(query.max_matches_per_file)])

        # Search pattern
        if query.is_regex:
            cmd.extend(["--extended-regexp", query.pattern])
        else:
            cmd.extend(["--fixed-strings", query.pattern])

        # Search directory
        search_dir = search_root
        if prefix:
            search_dir = search_root / prefix

        cmd.append(str(search_dir))

        logger.debug(f"Running grep command: {' '.join(shlex.quote(arg) for arg in cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(search_root),
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)

            # grep returns 1 when no matches found, which is not an error
            if proc.returncode not in (0, 1):
                error_msg = stderr.decode("utf-8").strip()
                logger.warning(f"grep command failed with code {proc.returncode}: {error_msg}")

            return self._parse_grep_output(stdout.decode("utf-8"), search_root, query)

        except TimeoutError:
            # Kill the process if it's still running
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise

    def _parse_ripgrep_output(
        self, output: str, search_root: Path, query: SearchQuery
    ) -> list[SearchResult]:
        """Parse ripgrep JSON output into SearchResult objects."""
        results_by_file: dict[str, list[dict]] = {}
        context_buffer: dict[str, list[dict]] = {}

        for line in output.strip().split("\n"):
            if not line:
                continue

            try:
                data = json.loads(line)
                msg_type = data.get("type")

                if msg_type == "match":
                    path_data = data.get("data", {}).get("path", {})
                    file_path = path_data.get("text", "")

                    if file_path not in results_by_file:
                        results_by_file[file_path] = []

                    results_by_file[file_path].append(data)

                elif msg_type == "context":
                    path_data = data.get("data", {}).get("path", {})
                    file_path = path_data.get("text", "")

                    if file_path not in context_buffer:
                        context_buffer[file_path] = []

                    context_buffer[file_path].append(data)

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse ripgrep JSON line: {line}")
                continue

        # Convert to SearchResult objects
        search_results = []
        for file_path, matches in results_by_file.items():
            if len(search_results) >= query.max_results:
                break

            relative_path = str(Path(file_path).relative_to(search_root))
            search_result = self._build_search_result_from_ripgrep(
                file_path, relative_path, matches, context_buffer.get(file_path, []), query
            )
            search_results.append(search_result)

        return search_results

    def _parse_grep_output(
        self, output: str, search_root: Path, query: SearchQuery
    ) -> list[SearchResult]:
        """Parse grep text output into SearchResult objects."""
        if not output.strip():
            return []

        results_by_file: dict[str, list[dict]] = {}

        for line in output.strip().split("\n"):
            if not line:
                continue

            # Parse grep output format: filename:line_number:content
            # or filename:line_number-content (for context lines)
            match = re.match(r"^([^:]+):(\d+)([-:])(.*)$", line)
            if not match:
                continue

            file_path, line_num, separator, content = match.groups()
            line_number = int(line_num)
            is_match = separator == ":"

            if file_path not in results_by_file:
                results_by_file[file_path] = []

            results_by_file[file_path].append(
                {
                    "line_number": line_number,
                    "content": content,
                    "is_match": is_match,
                }
            )

        # Convert to SearchResult objects
        search_results = []
        for file_path, lines in results_by_file.items():
            if len(search_results) >= query.max_results:
                break

            try:
                relative_path = str(Path(file_path).relative_to(search_root))
            except ValueError:
                # File is not within search_root, use absolute path
                relative_path = file_path

            search_result = self._build_search_result_from_grep(
                file_path, relative_path, lines, query
            )
            search_results.append(search_result)

        return search_results

    def _build_search_result_from_ripgrep(
        self,
        file_path: str,
        relative_path: str,
        matches: list[dict],
        context: list[dict],
        query: SearchQuery,
    ) -> SearchResult:
        """Build SearchResult from ripgrep data."""
        search_matches = []

        for match_data in matches[: query.max_matches_per_file]:
            line_data = match_data.get("data", {}).get("line", {})
            line_number = line_data.get("number", 0)
            line_content = line_data.get("text", "")

            # Create highlighted content
            highlighted_content = self._highlight_matches(line_content, query.pattern)

            search_match = SearchMatch(
                line_number=line_number,
                line_content=line_content,
                highlighted_content=highlighted_content,
                context_before=[],  # Would need more sophisticated context handling
                context_after=[],
            )
            search_matches.append(search_match)

        return SearchResult(
            path=file_path,
            relative_path=relative_path,
            matches=search_matches,
            total_matches=len(search_matches),
        )

    def _build_search_result_from_grep(
        self,
        file_path: str,
        relative_path: str,
        lines: list[dict],
        query: SearchQuery,
    ) -> SearchResult:
        """Build SearchResult from grep data."""
        search_matches = []
        matches_found = 0

        # Group lines to handle context
        current_match = None
        context_before = []

        for line_data in lines:
            if line_data["is_match"] and matches_found < query.max_matches_per_file:
                # This is a match line
                highlighted_content = self._highlight_matches(line_data["content"], query.pattern)

                search_match = SearchMatch(
                    line_number=line_data["line_number"],
                    line_content=line_data["content"],
                    highlighted_content=highlighted_content,
                    context_before=context_before.copy(),
                    context_after=[],  # Will be filled by subsequent context lines
                )
                search_matches.append(search_match)
                matches_found += 1
                context_before = []
                current_match = search_match

            else:
                # This is a context line
                if current_match and len(current_match.context_after) < query.context_lines:
                    current_match.context_after.append(line_data["content"])
                elif len(context_before) < query.context_lines:
                    context_before.append(line_data["content"])
                else:
                    context_before = context_before[1:] + [line_data["content"]]

        return SearchResult(
            path=file_path,
            relative_path=relative_path,
            matches=search_matches,
            total_matches=len(search_matches),
        )

    def _highlight_matches(self, content: str, pattern: str) -> str:
        """
        Add highlighting markers around matches in content.

        Args:
            content: Original content
            pattern: Search pattern

        Returns:
            Content with <mark>...</mark> tags around matches
        """
        if not pattern:
            return content

        try:
            # Simple highlighting - replace matches with marked version
            # For more sophisticated highlighting, would need to handle regex properly
            highlighted = re.sub(
                re.escape(pattern),
                f"<mark>{pattern}</mark>",
                content,
                flags=re.IGNORECASE,
            )
            return highlighted
        except Exception:
            # If highlighting fails, return original content
            return content


# Global search backend instance
search_backend = SearchBackend()
