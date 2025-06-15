"""Tests for error scenarios and edge cases."""

from fastapi.testclient import TestClient

from .conftest import assert_error_response


class TestErrorScenarios:
    """Test various error conditions and edge cases."""

    def test_invalid_paths(
        self, integration_client: TestClient, mock_writable_settings, invalid_path
    ):
        """Test handling of invalid paths."""
        content = "# Test Content\n\nThis should not be created with invalid path."

        # Test invalid path in PUT
        put_response = integration_client.put(f"/memory/{invalid_path}", json={"content": content})
        assert put_response.status_code == 400
        assert_error_response(put_response, 400, "InvalidPath")

        # Test invalid path in GET
        get_response = integration_client.get(f"/memory/{invalid_path}")
        assert get_response.status_code == 400
        assert_error_response(get_response, 400, "InvalidPath")

        # Test invalid path in DELETE
        delete_response = integration_client.delete(f"/memory/{invalid_path}")
        assert delete_response.status_code == 400
        assert_error_response(delete_response, 400, "InvalidPath")

    def test_invalid_content(
        self, integration_client: TestClient, mock_writable_settings, invalid_content
    ):
        """Test handling of invalid content."""
        if invalid_content == "":  # Empty content
            # Empty content should be rejected
            put_response = integration_client.put(
                "/memory/test/invalid", json={"content": invalid_content}
            )
            assert put_response.status_code == 400
            assert_error_response(put_response, 400, "InvalidRequest")

        elif "\x00" in invalid_content:  # Null bytes
            # This might be caught at different levels
            put_response = integration_client.put(
                "/memory/test/invalid", json={"content": invalid_content}
            )
            assert put_response.status_code in [400, 422]  # Could be validation or request error

        elif len(invalid_content) > 10_000_000:  # Too large
            put_response = integration_client.put(
                "/memory/test/invalid", json={"content": invalid_content}
            )
            assert put_response.status_code == 400
            assert_error_response(put_response, 400, "ContentTooLarge")

    def test_malformed_request_bodies(self, integration_client: TestClient, mock_writable_settings):
        """Test handling of malformed request bodies."""
        # Missing content field
        response1 = integration_client.put("/memory/test/malformed", json={})
        assert response1.status_code == 400
        assert_error_response(response1, 400, "InvalidRequest")

        # Content field with wrong type
        response2 = integration_client.put("/memory/test/malformed", json={"content": 123})
        assert response2.status_code == 400
        assert_error_response(response2, 400, "InvalidContent")

        # Content field with null value
        response3 = integration_client.put("/memory/test/malformed", json={"content": None})
        assert response3.status_code == 400
        assert_error_response(response3, 400, "InvalidContent")

        # Additional fields (should be ignored)
        response4 = integration_client.put(
            "/memory/test/malformed",
            json={
                "content": "# Valid Content\n\nThis is valid.",
                "extra_field": "ignored",
                "another_field": 123,
            },
        )
        assert response4.status_code == 201  # Should succeed, extra fields ignored

        # Clean up
        integration_client.delete("/memory/test/malformed")

    def test_invalid_json(self, integration_client: TestClient, mock_writable_settings):
        """Test handling of invalid JSON in request body."""
        import requests

        # Get the base URL from the test client
        base_url = integration_client.base_url

        # Send malformed JSON directly
        response = requests.put(
            f"{base_url}/memory/test/invalid-json",
            data='{"content": "incomplete json"',  # Missing closing brace
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert response.status_code == 422  # Unprocessable Entity for invalid JSON

    def test_non_existent_file_operations(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test operations on non-existent files."""
        non_existent_path = "does/not/exist"

        # GET non-existent file
        get_response = integration_client.get(f"/memory/{non_existent_path}")
        assert get_response.status_code == 404
        assert_error_response(get_response, 404, "NotFound")

        # DELETE non-existent file (should be idempotent)
        delete_response = integration_client.delete(f"/memory/{non_existent_path}")
        assert delete_response.status_code == 404
        assert_error_response(delete_response, 404, "NotFound")

    def test_path_edge_cases(self, integration_client: TestClient, mock_writable_settings):
        """Test edge cases in path handling."""
        # Very long but valid path
        long_path = "a" * 100 + "/" + "b" * 100 + "/" + "c" * 100
        content = "# Long Path Test\n\nThis tests a very long path."

        create_response = integration_client.put(f"/memory/{long_path}", json={"content": content})
        # Should either succeed or fail with appropriate error
        if create_response.status_code == 201:
            # If it succeeds, verify we can read and delete
            read_response = integration_client.get(f"/memory/{long_path}")
            assert read_response.status_code == 200

            delete_response = integration_client.delete(f"/memory/{long_path}")
            assert delete_response.status_code == 204
        else:
            # If it fails, should be due to path validation
            assert create_response.status_code == 400

        # Path with special characters (but valid)
        special_path = "test/special-chars_123.456"
        create_response = integration_client.put(
            f"/memory/{special_path}", json={"content": content}
        )
        assert create_response.status_code == 201

        # Clean up
        integration_client.delete(f"/memory/{special_path}")

    def test_content_edge_cases(self, integration_client: TestClient, mock_writable_settings):
        """Test edge cases in content handling."""
        # Whitespace-only content gets stripped and rejected as empty
        whitespace_only = "   \n  \t  \r\n  "
        response1 = integration_client.put(
            "/memory/test/whitespace", json={"content": whitespace_only}
        )
        # Should be rejected as empty after stripping
        assert response1.status_code == 400

        # Content with only newlines also gets stripped and rejected
        newlines_only = "\n\n\n\n\n"
        response2 = integration_client.put("/memory/test/newlines", json={"content": newlines_only})
        assert response2.status_code == 400

        # However, truly empty string should be rejected
        empty_content = ""
        response_empty = integration_client.put(
            "/memory/test/empty", json={"content": empty_content}
        )
        # Empty content should be rejected
        assert response_empty.status_code == 400

        # Content at size limit boundary
        at_limit_content = "x" * 10_000_000  # Exactly 10MB
        response3 = integration_client.put(
            "/memory/test/at-limit", json={"content": at_limit_content}
        )
        assert response3.status_code == 201

        # Clean up
        integration_client.delete("/memory/test/at-limit")

    def test_concurrent_access_same_file(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test concurrent access to the same file."""
        import concurrent.futures

        # Create initial file
        initial_content = "# Concurrent Test\n\nInitial content."
        create_response = integration_client.put(
            "/memory/concurrent/same-file", json={"content": initial_content}
        )
        assert create_response.status_code == 201

        def update_file(iteration: int) -> dict:
            """Update the same file with different content."""
            content = f"# Concurrent Test\n\nUpdate from iteration {iteration}."
            response = integration_client.put(
                "/memory/concurrent/same-file", json={"content": content}
            )
            return {
                "iteration": iteration,
                "status_code": response.status_code,
                "sha": response.headers.get("X-Git-SHA") if response.status_code == 200 else None,
            }

        # Try to update the same file concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(update_file, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All updates should succeed (last writer wins)
        assert len(results) == 5
        for result in results:
            assert result["status_code"] == 200
            assert result["sha"] is not None

        # Verify final state
        final_response = integration_client.get("/memory/concurrent/same-file")
        assert final_response.status_code == 200
        final_data = final_response.json()
        assert "Update from iteration" in final_data["content"]

        # Clean up
        integration_client.delete("/memory/concurrent/same-file")

    def test_rapid_operations_same_path(
        self, integration_client: TestClient, mock_writable_settings
    ):
        """Test rapid create/update/delete operations on the same path."""
        path = "rapid/operations"

        # Rapid sequence of operations
        for i in range(5):
            # Create
            create_response = integration_client.put(
                f"/memory/{path}", json={"content": f"# Rapid Test {i}\n\nIteration {i}."}
            )
            assert create_response.status_code in [200, 201]  # Could be create or update

            # Read
            read_response = integration_client.get(f"/memory/{path}")
            assert read_response.status_code == 200

            # Update
            update_response = integration_client.put(
                f"/memory/{path}",
                json={"content": f"# Rapid Test {i} Updated\n\nIteration {i} updated."},
            )
            assert update_response.status_code == 200  # Should be update

            # Delete
            delete_response = integration_client.delete(f"/memory/{path}")
            assert delete_response.status_code == 204

        # Final verification - should be gone
        final_response = integration_client.get(f"/memory/{path}")
        assert final_response.status_code == 404

    def test_stress_many_files(self, integration_client: TestClient, mock_writable_settings):
        """Test creating and managing many files."""
        file_count = 50
        content = "# Stress Test\n\nThis is a stress test file."

        # Create many files
        created_files = []
        for i in range(file_count):
            path = f"stress/file_{i:03d}"
            response = integration_client.put(
                f"/memory/{path}", json={"content": f"{content} File {i}."}
            )
            assert response.status_code == 201
            created_files.append(path)

        # Verify all files exist
        for path in created_files:
            response = integration_client.get(f"/memory/{path}")
            assert response.status_code == 200

        # Delete all files
        for path in created_files:
            response = integration_client.delete(f"/memory/{path}")
            assert response.status_code == 204

        # Verify all files are gone
        for path in created_files:
            response = integration_client.get(f"/memory/{path}")
            assert response.status_code == 404

    def test_headers_and_caching(self, integration_client: TestClient, mock_writable_settings):
        """Test proper HTTP headers and caching behavior."""
        content = "# Header Test\n\nThis tests HTTP headers."
        path = "headers/test"

        # Create file
        create_response = integration_client.put(f"/memory/{path}", json={"content": content})
        assert create_response.status_code == 201

        # Check required headers
        assert "X-Git-SHA" in create_response.headers
        assert "Last-Modified" in create_response.headers
        assert "ETag" in create_response.headers
        assert "Content-Type" in create_response.headers

        # ETag should be in correct format
        etag = create_response.headers["ETag"]
        assert etag.startswith('"') and etag.endswith('"')
        assert "-" in etag  # Should be "sha-size" format

        # Read and check headers match
        read_response = integration_client.get(f"/memory/{path}")
        assert read_response.status_code == 200
        assert read_response.headers["X-Git-SHA"] == create_response.headers["X-Git-SHA"]
        assert read_response.headers["ETag"] == create_response.headers["ETag"]
        assert read_response.headers["Last-Modified"] == create_response.headers["Last-Modified"]

        # Clean up
        integration_client.delete(f"/memory/{path}")
