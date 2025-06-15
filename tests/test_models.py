"""Tests for all memory models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from heare_memory.models.file_metadata import FileMetadata
from heare_memory.models.memory import (
    MemoryNode,
    MemoryNodeMetadata,
)
from heare_memory.models.requests import (
    BatchOperation,
    BatchRequest,
    MemoryCreateRequest,
    MemoryListRequest,
    MemoryUpdateRequest,
    SearchRequest,
)
from heare_memory.models.responses import (
    BatchResponse,
    ErrorResponse,
    SearchResponse,
)


class TestMemoryNodeMetadata:
    """Test MemoryNodeMetadata model."""

    def test_create_metadata(self):
        """Test creating metadata from basic fields."""
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=1024,
            sha="abc123",
            exists=True,
        )

        assert metadata.created_at == now
        assert metadata.updated_at == now
        assert metadata.size == 1024
        assert metadata.sha == "abc123"
        assert metadata.exists is True

    def test_from_file_metadata(self):
        """Test creating metadata from FileMetadata."""
        now = datetime.now()
        file_meta = FileMetadata(
            path="test.md",
            size=512,
            created_at=now,
            modified_at=now,
            exists=True,
            is_directory=False,
            permissions="644",
        )

        metadata = MemoryNodeMetadata.from_file_metadata(file_meta, "sha456")

        assert metadata.created_at == now
        assert metadata.updated_at == now
        assert metadata.size == 512
        assert metadata.sha == "sha456"
        assert metadata.exists is True

    def test_negative_size_validation(self):
        """Test that negative size is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MemoryNodeMetadata(
                created_at=datetime.now(),
                updated_at=datetime.now(),
                size=-1,
                sha="abc123",
            )

        assert "greater than or equal to 0" in str(exc_info.value)

    def test_json_serialization(self):
        """Test JSON serialization and deserialization."""
        now = datetime.now()
        metadata = MemoryNodeMetadata(
            created_at=now,
            updated_at=now,
            size=1024,
            sha="abc123",
            exists=True,
        )

        # Serialize to JSON
        json_data = metadata.model_dump_json()
        parsed_data = json.loads(json_data)

        # Deserialize from JSON
        restored = MemoryNodeMetadata.model_validate(parsed_data)

        assert restored.size == metadata.size
        assert restored.sha == metadata.sha
        assert restored.exists == metadata.exists


class TestMemoryNode:
    """Test MemoryNode model."""

    def test_create_memory_node(self):
        """Test creating a memory node."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        node = MemoryNode(
            path="test/file.md",
            content="# Test\n\nThis is a test file.",
            metadata=metadata,
        )

        assert node.path == "test/file.md"
        assert node.content == "# Test\n\nThis is a test file."
        assert node.metadata == metadata

    def test_content_preview(self):
        """Test content preview computation."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        # Short content
        short_node = MemoryNode(
            path="short.md",
            content="Short content",
            metadata=metadata,
        )
        assert short_node.content_preview == "Short content"

        # Long content
        long_content = "A" * 300
        long_node = MemoryNode(
            path="long.md",
            content=long_content,
            metadata=metadata,
        )
        assert len(long_node.content_preview) == 200
        assert long_node.content_preview.endswith("...")

    def test_line_count(self):
        """Test line count computation."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        node = MemoryNode(
            path="multiline.md",
            content="Line 1\nLine 2\nLine 3",
            metadata=metadata,
        )

        assert node.line_count == 3

    def test_is_empty(self):
        """Test empty content detection."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=0,
            sha="abc123",
        )

        empty_node = MemoryNode(path="empty.md", content="", metadata=metadata)
        assert empty_node.is_empty is True

        whitespace_node = MemoryNode(path="whitespace.md", content="   \n  \t  ", metadata=metadata)
        assert whitespace_node.is_empty is True

        content_node = MemoryNode(path="content.md", content="# Content", metadata=metadata)
        assert content_node.is_empty is False

    def test_get_lines(self):
        """Test getting specific lines from content."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        node = MemoryNode(
            path="lines.md",
            content="Line 1\nLine 2\nLine 3\nLine 4\nLine 5",
            metadata=metadata,
        )

        # Get all lines
        all_lines = node.get_lines()
        assert len(all_lines) == 5
        assert all_lines[0] == "Line 1"

        # Get specific range
        range_lines = node.get_lines(2, 4)
        assert len(range_lines) == 3
        assert range_lines == ["Line 2", "Line 3", "Line 4"]

        # Get from start
        start_lines = node.get_lines(1, 3)
        assert len(start_lines) == 3
        assert start_lines == ["Line 1", "Line 2", "Line 3"]

        # Get from middle to end
        end_lines = node.get_lines(4)
        assert len(end_lines) == 2
        assert end_lines == ["Line 4", "Line 5"]

    def test_find_text(self):
        """Test finding text in content."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        node = MemoryNode(
            path="search.md",
            content="# Header\nThis is a Test\nAnother test line\nNo match here",
            metadata=metadata,
        )

        # Case insensitive search (default)
        matches = node.find_text("test")
        assert matches == [2, 3]

        # Case sensitive search
        matches_case = node.find_text("Test", case_sensitive=True)
        assert matches_case == [2]

        # No matches
        no_matches = node.find_text("nonexistent")
        assert no_matches == []


class TestRequestModels:
    """Test request models."""

    def test_memory_create_request(self):
        """Test MemoryCreateRequest validation."""
        # Valid request
        request = MemoryCreateRequest(content="# Valid Content")
        assert request.content == "# Valid Content"

        # Empty content
        with pytest.raises(ValidationError):
            MemoryCreateRequest(content="")

        # Whitespace only content
        with pytest.raises(ValidationError):
            MemoryCreateRequest(content="   \n  \t  ")

        # Content with null bytes
        with pytest.raises(ValidationError):
            MemoryCreateRequest(content="Content with\x00null byte")

    def test_memory_update_request(self):
        """Test MemoryUpdateRequest validation."""
        request = MemoryUpdateRequest(content="# Updated Content")
        assert request.content == "# Updated Content"

        # Same validation as create request
        with pytest.raises(ValidationError):
            MemoryUpdateRequest(content="")

    def test_memory_list_request(self):
        """Test MemoryListRequest validation."""
        # Default values
        request = MemoryListRequest()
        assert request.prefix is None
        assert request.recursive is True
        assert request.include_content is False
        assert request.limit is None

        # With valid prefix
        request_with_prefix = MemoryListRequest(prefix="docs/")
        assert request_with_prefix.prefix == "docs"  # Should strip trailing slash

        # With dangerous prefix
        with pytest.raises(ValidationError):
            MemoryListRequest(prefix="../escape")

        # With invalid limit
        with pytest.raises(ValidationError):
            MemoryListRequest(limit=0)

        with pytest.raises(ValidationError):
            MemoryListRequest(limit=2000)

    def test_search_request(self):
        """Test SearchRequest validation."""
        request = SearchRequest(query="test query")
        assert request.query == "test query"
        assert request.case_sensitive is False
        assert request.context_lines == 2
        assert request.limit == 100

        # Empty query
        with pytest.raises(ValidationError):
            SearchRequest(query="")

        # Query with null bytes
        with pytest.raises(ValidationError):
            SearchRequest(query="query\x00with null")

        # Invalid context lines
        with pytest.raises(ValidationError):
            SearchRequest(query="test", context_lines=-1)

        with pytest.raises(ValidationError):
            SearchRequest(query="test", context_lines=20)

    def test_batch_operation(self):
        """Test BatchOperation validation."""
        # Valid create operation
        create_op = BatchOperation(action="create", path="test.md", content="# Test Content")
        assert create_op.action == "create"
        assert create_op.path == "test.md"
        assert create_op.content == "# Test Content"

        # Valid delete operation
        delete_op = BatchOperation(action="delete", path="test.md")
        assert delete_op.action == "delete"
        assert delete_op.content is None

        # Invalid: create without content
        with pytest.raises(ValidationError):
            BatchOperation(action="create", path="test.md")

        # Invalid: delete with content
        with pytest.raises(ValidationError):
            BatchOperation(action="delete", path="test.md", content="content")

        # Invalid path
        with pytest.raises(ValidationError):
            BatchOperation(action="create", path="../escape.md", content="content")

    def test_batch_request(self):
        """Test BatchRequest validation."""
        operations = [
            BatchOperation(action="create", path="test1.md", content="Content 1"),
            BatchOperation(action="update", path="test2.md", content="Content 2"),
            BatchOperation(action="delete", path="test3.md"),
        ]

        request = BatchRequest(operations=operations)
        assert len(request.operations) == 3
        assert request.commit_message == "Batch update"  # Default

        # Custom commit message
        custom_request = BatchRequest(operations=operations, commit_message="Custom message")
        assert custom_request.commit_message == "Custom message"

        # Empty operations
        with pytest.raises(ValidationError):
            BatchRequest(operations=[])

        # Duplicate paths
        duplicate_ops = [
            BatchOperation(action="create", path="test.md", content="Content 1"),
            BatchOperation(action="update", path="test.md", content="Content 2"),
        ]
        with pytest.raises(ValidationError):
            BatchRequest(operations=duplicate_ops)

        # Too many operations
        too_many_ops = [
            BatchOperation(action="create", path=f"test{i}.md", content=f"Content {i}")
            for i in range(101)
        ]
        with pytest.raises(ValidationError):
            BatchRequest(operations=too_many_ops)


class TestResponseModels:
    """Test response models."""

    def test_memory_node_list_response(self):
        """Test MemoryNodeListResponse."""
        from heare_memory.models.memory import MemoryNodeList

        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        nodes = [
            MemoryNode(path="test1.md", content="Content 1", metadata=metadata),
            MemoryNode(path="test2.md", content="Content 2", metadata=metadata),
        ]

        response = MemoryNodeList(
            nodes=nodes,
            total=2,
            prefix="test",
        )

        assert len(response.nodes) == 2
        assert response.total == 2

    def test_batch_response(self):
        """Test BatchResponse."""
        response = BatchResponse(
            success=True,
            commit_sha="abc123",
            commit_message="Test batch",
            results=[],
            completed=2,
            total=2,
        )

        assert response.success is True
        assert response.success_rate == 100.0

        # Partial success
        partial_response = BatchResponse(
            success=False,
            commit_sha=None,
            commit_message="Test batch",
            results=[],
            completed=1,
            total=2,
        )

        assert partial_response.success_rate == 50.0

    def test_error_response(self):
        """Test ErrorResponse."""
        error = ErrorResponse(
            error="ValidationError",
            message="Invalid input",
            details={"field": "content"},
            path="test.md",
        )

        assert error.error == "ValidationError"
        assert error.message == "Invalid input"
        assert error.path == "test.md"

        # From exception
        try:
            raise ValueError("Test error")
        except ValueError as e:
            error_from_exc = ErrorResponse.from_exception(e, "test.md")
            assert error_from_exc.error == "ValueError"
            assert error_from_exc.message == "Test error"
            assert error_from_exc.path == "test.md"

    def test_search_response(self):
        """Test SearchResponse."""
        response = SearchResponse(
            files=[],
            query="test",
            prefix=None,
            case_sensitive=False,
            total_files=0,
            total_matches=0,
            search_time_ms=15.5,
        )

        assert response.query == "test"
        assert response.has_results is False

        # With results
        response_with_results = SearchResponse(
            files=[],
            query="test",
            prefix=None,
            case_sensitive=False,
            total_files=1,
            total_matches=3,
            search_time_ms=25.0,
        )

        assert response_with_results.has_results is True


class TestModelIntegration:
    """Test model integration and edge cases."""

    def test_json_round_trip(self):
        """Test that models can be serialized and deserialized."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        node = MemoryNode(
            path="test.md",
            content="# Test Content\n\nThis is a test.",
            metadata=metadata,
        )

        # Serialize to JSON
        json_data = node.model_dump_json()

        # Deserialize from JSON
        parsed_data = json.loads(json_data)
        restored_node = MemoryNode.model_validate(parsed_data)

        assert restored_node.path == node.path
        assert restored_node.content == node.content
        assert restored_node.metadata.size == node.metadata.size

    def test_model_validation_edge_cases(self):
        """Test edge cases in model validation."""
        # Very long content
        long_content = "x" * 1_000_000
        request = MemoryCreateRequest(content=long_content)
        assert len(request.content) == 1_000_000

        # Content at max limit should work
        max_content = "x" * 10_000_000
        max_request = MemoryCreateRequest(content=max_content)
        assert len(max_request.content) == 10_000_000

        # Content over limit should fail
        with pytest.raises(ValidationError):
            MemoryCreateRequest(content="x" * 10_000_001)

    def test_computed_fields(self):
        """Test computed fields work correctly."""
        metadata = MemoryNodeMetadata(
            created_at=datetime.now(),
            updated_at=datetime.now(),
            size=100,
            sha="abc123",
        )

        node = MemoryNode(
            path="test.md",
            content="Line 1\nLine 2\nLine 3",
            metadata=metadata,
        )

        # Computed fields should be in serialized output
        serialized = node.model_dump()
        assert "content_preview" in serialized
        assert "line_count" in serialized
        assert "is_empty" in serialized

        assert serialized["line_count"] == 3
        assert serialized["is_empty"] is False
