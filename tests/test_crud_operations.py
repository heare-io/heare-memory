"""Integration tests for CRUD operations with real services."""

from fastapi.testclient import TestClient

from .conftest import assert_error_response, assert_memory_node_equal


class TestCRUDIntegration:
    """Test complete CRUD workflows with real services."""

    def test_create_read_update_delete_cycle(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test complete CRUD cycle for a memory node."""
        path = "crud/test-cycle"
        initial_content = "# Initial Content\n\nThis is the initial content."
        updated_content = "# Updated Content\n\nThis content has been updated."

        # 1. Create (PUT) - should return 201 Created
        create_response = integration_client.put(
            f"/memory/{path}", json={"content": initial_content}
        )
        assert create_response.status_code == 201
        created_data = create_response.json()
        assert_memory_node_equal(created_data, f"{path}.md", initial_content)

        # Verify headers
        assert "X-Git-SHA" in create_response.headers
        assert "Last-Modified" in create_response.headers
        assert "ETag" in create_response.headers
        original_sha = create_response.headers["X-Git-SHA"]

        # 2. Read (GET) - should return the created content
        read_response = integration_client.get(f"/memory/{path}")
        assert read_response.status_code == 200
        read_data = read_response.json()
        assert read_data["content"] == initial_content
        assert read_data["path"] == f"{path}.md"
        assert read_data["metadata"]["sha"] == original_sha

        # 3. Update (PUT) - should return 200 OK
        update_response = integration_client.put(
            f"/memory/{path}", json={"content": updated_content}
        )
        assert update_response.status_code == 200  # Updated, not created
        updated_data = update_response.json()
        assert updated_data["content"] == updated_content
        assert updated_data["path"] == f"{path}.md"

        # SHA should be different after update
        new_sha = update_response.headers["X-Git-SHA"]
        assert new_sha != original_sha

        # 4. Read again to verify update
        read_updated_response = integration_client.get(f"/memory/{path}")
        assert read_updated_response.status_code == 200
        read_updated_data = read_updated_response.json()
        assert read_updated_data["content"] == updated_content
        assert read_updated_data["metadata"]["sha"] == new_sha

        # 5. Delete - should return 204 No Content
        delete_response = integration_client.delete(f"/memory/{path}")
        assert delete_response.status_code == 204
        assert delete_response.content == b""

        # 6. Verify deletion - GET should return 404
        get_deleted_response = integration_client.get(f"/memory/{path}")
        assert get_deleted_response.status_code == 404
        assert_error_response(get_deleted_response, 404, "NotFound")

        # 7. Delete again (idempotency) - should return 404
        delete_again_response = integration_client.delete(f"/memory/{path}")
        assert delete_again_response.status_code == 404
        assert_error_response(delete_again_response, 404, "NotFound")

    def test_nested_directory_creation_and_cleanup(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test automatic directory creation and cleanup."""
        # Create a deeply nested file
        nested_path = "deep/nested/directory/structure/file"
        content = "# Nested File\n\nThis file is deeply nested."

        # Create the file
        create_response = integration_client.put(
            f"/memory/{nested_path}", json={"content": content}
        )
        assert create_response.status_code == 201

        # Verify it can be read
        read_response = integration_client.get(f"/memory/{nested_path}")
        assert read_response.status_code == 200
        assert read_response.json()["content"] == content

        # Create another file in the same directory structure
        sibling_path = "deep/nested/directory/structure/sibling"
        sibling_content = "# Sibling File\n\nThis is a sibling file."

        sibling_response = integration_client.put(
            f"/memory/{sibling_path}", json={"content": sibling_content}
        )
        assert sibling_response.status_code == 201

        # Delete the first file
        delete_response = integration_client.delete(f"/memory/{nested_path}")
        assert delete_response.status_code == 204

        # Sibling should still exist
        sibling_read_response = integration_client.get(f"/memory/{sibling_path}")
        assert sibling_read_response.status_code == 200

        # Delete the sibling file (should clean up empty directories)
        delete_sibling_response = integration_client.delete(f"/memory/{sibling_path}")
        assert delete_sibling_response.status_code == 204

        # Both files should be gone
        assert integration_client.get(f"/memory/{nested_path}").status_code == 404
        assert integration_client.get(f"/memory/{sibling_path}").status_code == 404

    def test_path_sanitization_integration(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test that path sanitization works correctly in integration."""
        content = "# Sanitized Content\n\nThis content was created with a sanitized path."

        # Test various path formats that should be sanitized
        test_cases = [
            ("test/file", "test/file.md"),  # Add .md extension
            ("test\\windows\\path", "test/windows/path.md"),  # Convert backslashes
            ("/leading/slash", "leading/slash.md"),  # Remove leading slash
            ("double//slashes", "double/slashes.md"),  # Fix double slashes
        ]

        created_paths = []
        for input_path, expected_path in test_cases:
            # Create with potentially unsanitized path
            create_response = integration_client.put(
                f"/memory/{input_path}", json={"content": content}
            )
            assert create_response.status_code == 201

            # Verify the response shows the sanitized path
            created_data = create_response.json()
            assert created_data["path"] == expected_path
            created_paths.append(expected_path)

            # Verify we can read it back with the sanitized path
            read_response = integration_client.get(f"/memory/{input_path}")
            assert read_response.status_code == 200
            assert read_response.json()["path"] == expected_path

        # Clean up
        for path in created_paths:
            # Remove .md extension for delete request
            delete_path = path[:-3] if path.endswith(".md") else path
            delete_response = integration_client.delete(f"/memory/{delete_path}")
            assert delete_response.status_code == 204

    def test_read_only_mode_enforcement(
        self, integration_client: TestClient, mock_readonly_settings
    ):
        """Test that read-only mode prevents all write operations."""
        content = "# Test Content\n\nThis should not be created in read-only mode."

        # PUT should be forbidden
        put_response = integration_client.put("/memory/readonly/test", json={"content": content})
        assert put_response.status_code == 403
        assert_error_response(put_response, 403, "ReadOnlyMode")

        # DELETE should be forbidden
        delete_response = integration_client.delete("/memory/readonly/test")
        assert delete_response.status_code == 403
        assert_error_response(delete_response, 403, "ReadOnlyMode")

    def test_concurrent_different_files(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test concurrent operations on different files."""
        import concurrent.futures

        def create_file(path_suffix: int) -> dict:
            """Create a file and return the response data."""
            response = integration_client.put(
                f"/memory/concurrent/file_{path_suffix:03d}",
                json={"content": f"# File {path_suffix}\n\nContent for file {path_suffix}."},
            )
            return {
                "path_suffix": path_suffix,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 201 else None,
            }

        # Create 10 files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_file, i) for i in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert len(results) == 10
        for result in results:
            assert result["status_code"] == 201
            assert result["data"] is not None

        # Verify all files exist and have correct content
        for i in range(10):
            read_response = integration_client.get(f"/memory/concurrent/file_{i:03d}")
            assert read_response.status_code == 200
            data = read_response.json()
            assert f"Content for file {i}" in data["content"]

        # Clean up
        for i in range(10):
            delete_response = integration_client.delete(f"/memory/concurrent/file_{i:03d}")
            assert delete_response.status_code == 204

    def test_large_content_handling(self, integration_client: TestClient, mock_writable_settings):
        """Test handling of large content within limits."""
        # Create content that's large but within the 10MB limit
        large_content = "# Large Content\n\n" + ("This is a line of content.\n" * 100000)

        # Should be less than 10MB
        assert len(large_content.encode("utf-8")) < 10_000_000

        # Create large file
        create_response = integration_client.put(
            "/memory/large/content", json={"content": large_content}
        )
        assert create_response.status_code == 201

        # Read it back
        read_response = integration_client.get("/memory/large/content")
        assert read_response.status_code == 200
        read_data = read_response.json()
        assert read_data["content"] == large_content
        assert read_data["metadata"]["size"] == len(large_content.encode("utf-8"))

        # Update with different large content
        updated_large_content = "# Updated Large Content\n\n" + (
            "Updated line of content.\n" * 100000
        )
        update_response = integration_client.put(
            "/memory/large/content", json={"content": updated_large_content}
        )
        assert update_response.status_code == 200

        # Verify update
        read_updated_response = integration_client.get("/memory/large/content")
        assert read_updated_response.status_code == 200
        assert read_updated_response.json()["content"] == updated_large_content

        # Clean up
        delete_response = integration_client.delete("/memory/large/content")
        assert delete_response.status_code == 204

    def test_content_too_large_rejection(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test that content exceeding size limit is rejected."""
        # Create content larger than 10MB
        too_large_content = "x" * (10_000_001)  # Just over 10MB

        create_response = integration_client.put(
            "/memory/too/large", json={"content": too_large_content}
        )
        assert create_response.status_code == 400
        assert_error_response(create_response, 400, "ContentTooLarge")

    def test_unicode_content_handling(self, integration_client: TestClient, mock_writable_settings):
        """Test proper handling of Unicode content."""
        unicode_content = """# Unicode Test 🚀

This file contains various Unicode characters:

## Emoji
🎉 🎈 🎊 🎁 🎂 🎀 🎃 🎄 🎅 🎆

## Languages
- English: Hello World!
- Spanish: ¡Hola Mundo!
- French: Bonjour le Monde!
- German: Hallo Welt!
- Chinese: 你好世界！
- Japanese: こんにちは世界！
- Russian: Привет мир!
- Arabic: مرحبا بالعالم!

## Mathematical Symbols
∑ ∏ ∫ ∞ ≤ ≥ ≠ ≈ ± × ÷ √ ∂ ∇

## Greek Letters
α β γ δ ε ζ η θ ι κ λ μ ν ξ ο π ρ σ τ υ φ χ ψ ω

## Special Characters
""❝❞‚„…‰‱‹›«»‿⁀⁔⁗⁘⁙⁚⁛⁜⁝⁞
"""

        # Create file with Unicode content
        create_response = integration_client.put(
            "/memory/unicode/test", json={"content": unicode_content}
        )
        assert create_response.status_code == 201

        # Read it back and verify Unicode is preserved
        read_response = integration_client.get("/memory/unicode/test")
        assert read_response.status_code == 200
        read_data = read_response.json()
        assert read_data["content"] == unicode_content

        # Verify metadata reflects correct byte size (UTF-8 encoded)
        expected_size = len(unicode_content.encode("utf-8"))
        assert read_data["metadata"]["size"] == expected_size

        # Clean up
        delete_response = integration_client.delete("/memory/unicode/test")
        assert delete_response.status_code == 204

    def test_git_integration_workflow(self, integration_client: TestClient, mock_writable_settings):
        """Test that git operations work correctly."""
        content = "# Git Integration Test\n\nThis tests git integration."

        # Create file
        create_response = integration_client.put("/memory/git/test", json={"content": content})
        assert create_response.status_code == 201

        # Should have git SHA
        initial_sha = create_response.headers["X-Git-SHA"]
        assert initial_sha
        assert initial_sha != "uncommitted"
        assert initial_sha != "unknown"

        # Update file
        updated_content = "# Git Integration Test\n\nThis tests git integration with updates."
        update_response = integration_client.put(
            "/memory/git/test", json={"content": updated_content}
        )
        assert update_response.status_code == 200

        # Should have different git SHA
        updated_sha = update_response.headers["X-Git-SHA"]
        assert updated_sha
        assert updated_sha != initial_sha
        assert updated_sha != "uncommitted"
        assert updated_sha != "unknown"

        # ETags should be different
        initial_etag = create_response.headers["ETag"]
        updated_etag = update_response.headers["ETag"]
        assert initial_etag != updated_etag

        # Clean up
        delete_response = integration_client.delete("/memory/git/test")
        assert delete_response.status_code == 204
