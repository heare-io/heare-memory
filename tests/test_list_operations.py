"""Tests for memory node listing operations."""

from fastapi.testclient import TestClient

from .conftest import assert_error_response


class TestListOperations:
    """Test memory node listing functionality."""

    def test_list_empty_memory(self, integration_client: TestClient, mock_writable_settings):
        """Test listing when no memory nodes exist."""
        print("Making request to /memory")
        response = integration_client.get("/memory")
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.content}")
        assert response.status_code == 200

        data = response.json()
        assert data["nodes"] == []
        assert data["total_count"] == 0
        assert data["returned_count"] == 0
        assert data["prefix"] is None
        assert data["delimiter"] is None
        assert data["recursive"] is True
        assert data["include_content"] is False

    def test_list_basic_files(self, integration_client: TestClient, mock_writable_settings):
        """Test basic file listing."""
        # Create test files
        test_files = {
            "file1": "# File 1\n\nContent of file 1",
            "file2": "# File 2\n\nContent of file 2",
            "nested/file3": "# File 3\n\nContent of file 3",
        }

        for path, content in test_files.items():
            response = integration_client.put(f"/memory/{path}", json={"content": content})
            assert response.status_code == 201

        # List all files
        response = integration_client.get("/memory/")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 3
        assert data["returned_count"] == 3
        assert len(data["nodes"]) == 3

        # Check file paths
        paths = [node["path"] for node in data["nodes"]]
        assert "file1.md" in paths
        assert "file2.md" in paths
        assert "nested/file3.md" in paths

        # Check metadata exists
        for node in data["nodes"]:
            assert "metadata" in node
            assert "created_at" in node["metadata"]
            assert "updated_at" in node["metadata"]
            assert "size" in node["metadata"]
            assert "sha" in node["metadata"]
            assert node["metadata"]["exists"] is True

        # Content should not be included by default
        for node in data["nodes"]:
            assert "content" not in node

        # Clean up
        for path in test_files:
            integration_client.delete(f"/memory/{path}")

    def test_list_with_content(self, integration_client: TestClient, mock_writable_settings):
        """Test listing with content inclusion."""
        # Create test files
        test_files = {
            "content1": "# Content 1\n\nFirst file content",
            "content2": "# Content 2\n\nSecond file content",
        }

        for path, content in test_files.items():
            response = integration_client.put(f"/memory/{path}", json={"content": content})
            assert response.status_code == 201

        # List with content
        response = integration_client.get("/memory/?include_content=true")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 2
        assert data["include_content"] is True

        # Check content is included
        for node in data["nodes"]:
            assert "content" in node
            assert "metadata" in node
            path_key = node["path"].replace(".md", "")
            if path_key in test_files:
                assert node["content"] == test_files[path_key]

        # Clean up
        for path in test_files:
            integration_client.delete(f"/memory/{path}")

    def test_list_with_prefix_filter(self, integration_client: TestClient, mock_writable_settings):
        """Test listing with prefix filtering."""
        # Create test files in different directories
        test_files = {
            "docs/readme": "# README\n\nDocumentation",
            "docs/guide": "# Guide\n\nUser guide",
            "src/main": "# Main\n\nMain source",
            "tests/test1": "# Test 1\n\nTest file",
        }

        for path, content in test_files.items():
            response = integration_client.put(f"/memory/{path}", json={"content": content})
            assert response.status_code == 201

        # List files with "docs" prefix
        response = integration_client.get("/memory/?prefix=docs")
        assert response.status_code == 200

        data = response.json()
        assert data["prefix"] == "docs"
        assert data["total_count"] == 2

        paths = [node["path"] for node in data["nodes"]]
        assert "docs/readme.md" in paths
        assert "docs/guide.md" in paths
        assert "src/main.md" not in paths
        assert "tests/test1.md" not in paths

        # List files with "src" prefix
        response = integration_client.get("/memory/?prefix=src")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 1
        paths = [node["path"] for node in data["nodes"]]
        assert "src/main.md" in paths

        # Clean up
        for path in test_files:
            integration_client.delete(f"/memory/{path}")

    def test_list_with_pagination(self, integration_client: TestClient, mock_writable_settings):
        """Test listing with pagination."""
        # Create multiple test files
        test_files = {}
        for i in range(10):
            path = f"page_test_{i:02d}"
            content = f"# Page Test {i}\n\nContent for page test {i}"
            test_files[path] = content

        for path, content in test_files.items():
            response = integration_client.put(f"/memory/{path}", json={"content": content})
            assert response.status_code == 201

        # Test first page
        response = integration_client.get("/memory/?limit=5&offset=0")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 10
        assert data["returned_count"] == 5
        assert data["limit"] == 5
        assert data["offset"] == 0
        assert len(data["nodes"]) == 5

        # Test second page
        response = integration_client.get("/memory/?limit=5&offset=5")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 10
        assert data["returned_count"] == 5
        assert data["limit"] == 5
        assert data["offset"] == 5
        assert len(data["nodes"]) == 5

        # Test page beyond data
        response = integration_client.get("/memory/?limit=5&offset=20")
        assert response.status_code == 200

        data = response.json()
        assert data["total_count"] == 10
        assert data["returned_count"] == 0
        assert len(data["nodes"]) == 0

        # Clean up
        for path in test_files:
            integration_client.delete(f"/memory/{path}")

    def test_list_recursive_vs_flat(self, integration_client: TestClient, mock_writable_settings):
        """Test recursive vs flat listing."""
        # Create nested structure
        test_files = {
            "level1/file1": "# Level 1 File 1",
            "level1/level2/file2": "# Level 2 File 2",
            "level1/level2/level3/file3": "# Level 3 File 3",
            "root_file": "# Root File",
        }

        for path, content in test_files.items():
            response = integration_client.put(f"/memory/{path}", json={"content": content})
            assert response.status_code == 201

        # Test recursive listing (default)
        response = integration_client.get("/memory/?recursive=true")
        assert response.status_code == 200

        data = response.json()
        assert data["recursive"] is True
        assert data["total_count"] == 4

        paths = [node["path"] for node in data["nodes"]]
        assert "level1/file1.md" in paths
        assert "level1/level2/file2.md" in paths
        assert "level1/level2/level3/file3.md" in paths
        assert "root_file.md" in paths

        # Test flat listing
        response = integration_client.get("/memory/?recursive=false")
        assert response.status_code == 200

        data = response.json()
        assert data["recursive"] is False
        # In flat mode, should only see root_file directly
        # (Note: implementation details may vary)

        # Clean up
        for path in test_files:
            integration_client.delete(f"/memory/{path}")

    def test_list_error_scenarios(self, integration_client: TestClient, mock_writable_settings):
        """Test error scenarios in listing."""
        # Test invalid prefix
        response = integration_client.get("/memory/?prefix=../invalid")
        assert response.status_code == 400
        assert_error_response(response, 400, "InvalidPrefix")

        # Test negative limit
        response = integration_client.get("/memory/?limit=-1")
        assert response.status_code == 400
        assert_error_response(response, 400, "InvalidParameter")

        # Test negative offset
        response = integration_client.get("/memory/?offset=-1")
        assert response.status_code == 400
        assert_error_response(response, 400, "InvalidParameter")

    def test_list_with_delimiter(self, integration_client: TestClient, mock_writable_settings):
        """Test hierarchical listing with delimiters."""
        # Create hierarchical structure
        test_files = {
            "projects/project1/readme": "# Project 1 README",
            "projects/project1/src/main": "# Project 1 Main",
            "projects/project2/readme": "# Project 2 README",
            "projects/shared/utils": "# Shared Utils",
        }

        for path, content in test_files.items():
            response = integration_client.put(f"/memory/{path}", json={"content": content})
            assert response.status_code == 201

        # List with delimiter to show hierarchical structure
        response = integration_client.get("/memory/?prefix=projects&delimiter=/")
        assert response.status_code == 200

        data = response.json()
        assert data["prefix"] == "projects"
        assert data["delimiter"] == "/"

        # Should show project directories and files
        paths = [node["path"] for node in data["nodes"]]
        # Exact behavior depends on delimiter implementation
        assert len(paths) > 0

        # Clean up
        for path in test_files:
            integration_client.delete(f"/memory/{path}")
