"""Memory CRUD endpoints router."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..dependencies import get_memory_service
from ..models.memory import MemoryNode
from ..path_utils import PathValidationError, sanitize_path
from ..services.memory_service import MemoryNotFoundError, MemoryService, MemoryServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/")
async def list_memory_nodes(
    prefix: str | None = None,
    delimiter: str | None = None,
    recursive: bool = True,
    include_content: bool = False,
    limit: int | None = None,
    offset: int = 0,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict[str, Any]:
    """List memory nodes with optional filtering and pagination.

    Args:
        prefix: Filter by path prefix
        delimiter: Delimiter for hierarchical listing
        recursive: Include subdirectories recursively
        include_content: Include node content in response
        limit: Maximum number of results to return
        offset: Number of results to skip
        memory_service: Injected memory service

    Returns:
        dict: List of memory nodes with metadata
    """
    # Normalize empty string to None
    if prefix == "":
        prefix = None
    if delimiter == "":
        delimiter = None

    logger.info(f"GET /memory/ - prefix={prefix}, delimiter={delimiter}, recursive={recursive}")

    try:
        # Validate prefix if provided
        if prefix and prefix.strip():
            try:
                from ..path_utils import validate_path

                # Validate prefix by adding temporary .md extension
                test_path = f"{prefix}/temp.md" if not prefix.endswith("/") else f"{prefix}temp.md"
                validate_path(test_path)
            except PathValidationError as e:
                logger.warning(f"Invalid prefix provided: {prefix} - {e}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "InvalidPrefix",
                        "message": f"Invalid prefix format: {e}",
                        "prefix": prefix,
                    },
                ) from e

        # Validate pagination parameters
        if limit is not None and limit < 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidParameter",
                    "message": "Limit cannot be negative",
                    "limit": limit,
                },
            )

        if offset < 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidParameter",
                    "message": "Offset cannot be negative",
                    "offset": offset,
                },
            )

        # List memory nodes
        result = await memory_service.list_memory_nodes(
            prefix=prefix,
            delimiter=delimiter,
            recursive=recursive,
            include_content=include_content,
            limit=limit,
            offset=offset,
        )

        logger.info(f"Listed {result['returned_count']} of {result['total_count']} memory nodes")
        return result

    except PathValidationError as e:
        logger.warning(f"Path validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidPath",
                "message": f"Invalid path format: {e}",
                "prefix": prefix,
            },
        ) from e

    except MemoryServiceError as e:
        logger.error(f"Memory service error listing nodes: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": "Internal server error occurred",
                "prefix": prefix,
            },
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error listing memory nodes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UnexpectedError",
                "message": "An unexpected error occurred",
                "prefix": prefix,
            },
        ) from e


@router.get("/search")
async def search_memory_nodes(
    query: str,
    request: Request,
    prefix: str | None = None,
    context_lines: int = 2,
    max_results: int = 50,
    case_sensitive: bool = False,
    is_regex: bool = False,
    whole_words: bool = False,
    timeout: float = 30.0,
    memory_service: MemoryService = Depends(get_memory_service),
) -> dict[str, Any]:
    """Search memory node content across the repository.

    Args:
        query: Search query (pattern or regex)
        prefix: Search within path prefix (optional)
        context_lines: Lines of context around matches (0-10, default: 2)
        max_results: Maximum number of file results (1-1000, default: 50)
        case_sensitive: Whether search should be case sensitive (default: False)
        is_regex: Whether to treat query as regex pattern (default: False)
        whole_words: Whether to match whole words only (default: False)
        timeout: Maximum search time in seconds (default: 30.0)
        request: FastAPI request object
        memory_service: Injected memory service

    Returns:
        dict: Search results with highlighted matches and metadata

    Raises:
        HTTPException: 400 for invalid queries/parameters, 408 for timeouts, 500 for internal errors
    """
    logger.info(
        f"GET /memory/search - query='{query}', prefix={prefix}, "
        f"context_lines={context_lines}, max_results={max_results} - Request from {request.client}"
    )

    try:
        # Validate query parameter
        if not query or not query.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidQuery",
                    "message": "Search query cannot be empty",
                    "query": query,
                },
            )

        # Validate parameter ranges
        if context_lines < 0 or context_lines > 10:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidParameter",
                    "message": "Context lines must be between 0 and 10",
                    "context_lines": context_lines,
                },
            )

        if max_results < 1 or max_results > 1000:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidParameter",
                    "message": "Max results must be between 1 and 1000",
                    "max_results": max_results,
                },
            )

        if timeout < 1.0 or timeout > 120.0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidParameter",
                    "message": "Timeout must be between 1.0 and 120.0 seconds",
                    "timeout": timeout,
                },
            )

        # Normalize empty string prefix to None
        if prefix == "":
            prefix = None

        # Validate prefix if provided
        if prefix and prefix.strip():
            try:
                from ..path_utils import validate_path

                # Validate prefix by adding temporary .md extension
                test_path = f"{prefix}/temp.md" if not prefix.endswith("/") else f"{prefix}temp.md"
                validate_path(test_path)
            except PathValidationError as e:
                logger.warning(f"Invalid prefix provided: {prefix} - {e}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "InvalidPrefix",
                        "message": f"Invalid prefix format: {e}",
                        "prefix": prefix,
                    },
                ) from e

        # Perform the search
        search_summary = await memory_service.search_memory_content(
            query=query.strip(),
            prefix=prefix,
            context_lines=context_lines,
            max_results=max_results,
            case_sensitive=case_sensitive,
            is_regex=is_regex,
            whole_words=whole_words,
            timeout_seconds=timeout,
        )

        # Convert search summary to response format
        response_data = {
            "query": search_summary.query,
            "results": [],
            "total_results": search_summary.files_with_matches,
            "total_matches": search_summary.total_matches,
            "search_time_ms": search_summary.search_time_ms,
            "backend_used": search_summary.backend_used,
            "truncated": search_summary.truncated,
            "prefix": prefix,
            "parameters": {
                "context_lines": context_lines,
                "max_results": max_results,
                "case_sensitive": case_sensitive,
                "is_regex": is_regex,
                "whole_words": whole_words,
                "timeout": timeout,
            },
        }

        # Convert search results to response format
        for search_result in search_summary.results:
            result_data = {
                "path": search_result.relative_path,
                "absolute_path": search_result.path,
                "total_matches": search_result.total_matches,
                "matches": [],
            }

            # Add file size if available
            if search_result.file_size is not None:
                result_data["file_size"] = search_result.file_size

            # Convert matches
            for match in search_result.matches:
                match_data = {
                    "line_number": match.line_number,
                    "line_content": match.line_content,
                    "highlighted_content": match.highlighted_content,
                    "context_before": match.context_before,
                    "context_after": match.context_after,
                }

                # Add column information if available
                if match.column_start is not None:
                    match_data["column_start"] = match.column_start
                if match.column_end is not None:
                    match_data["column_end"] = match.column_end

                result_data["matches"].append(match_data)

            response_data["results"].append(result_data)

        logger.info(
            f"Search completed successfully: query='{query}', "
            f"files={search_summary.files_with_matches}, matches={search_summary.total_matches}, "
            f"time={search_summary.search_time_ms:.1f}ms"
        )

        return response_data

    except PathValidationError as e:
        logger.warning(f"Path validation error in search: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidPath",
                "message": f"Invalid path format: {e}",
                "prefix": prefix,
            },
        ) from e

    except MemoryServiceError as e:
        # Check if this is a timeout error
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
            logger.warning(f"Search timeout for query '{query}': {e}")
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "SearchTimeout",
                    "message": f"Search operation timed out: {e}",
                    "query": query,
                    "timeout": timeout,
                },
            ) from e
        else:
            logger.error(f"Memory service error during search: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "InternalError",
                    "message": "Internal server error during search",
                    "query": query,
                },
            ) from e

    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes
        raise
    except Exception as e:
        logger.error(f"Unexpected error during search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UnexpectedError",
                "message": "An unexpected error occurred during search",
                "query": query,
            },
        ) from e


@router.get("/{path:path}", response_model=MemoryNode)
async def get_memory_node(
    path: str,
    request: Request,
    response: Response,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryNode:
    """
    Get a memory node by path.

    Args:
        path: The memory node path (without .md extension)
        request: FastAPI request object
        response: FastAPI response object
        memory_service: Injected memory service

    Returns:
        MemoryNode with content and metadata

    Raises:
        HTTPException: 400 for invalid paths, 404 if not found, 500 for internal errors
    """
    logger.info(f"GET /memory/{path} - Request from {request.client}")

    try:
        # Sanitize the path to ensure it has .md extension and is safe
        sanitized_path = sanitize_path(path)
        logger.debug(f"Sanitized path: {path} -> {sanitized_path}")

        # Get the memory node
        memory_node = await memory_service.get_memory_node(sanitized_path)

        # Set HTTP headers
        response.headers["X-Git-SHA"] = memory_node.metadata.sha
        response.headers["Last-Modified"] = memory_node.metadata.updated_at.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

        # Create ETag from SHA and size
        etag = f'"{memory_node.metadata.sha}-{memory_node.metadata.size}"'
        response.headers["ETag"] = etag

        # Set content type for markdown
        response.headers["Content-Type"] = "application/json; charset=utf-8"

        logger.info(f"Successfully retrieved memory node: {sanitized_path}")
        return memory_node

    except PathValidationError as e:
        logger.warning(f"Invalid path provided: {path} - {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidPath",
                "message": f"Invalid path format: {e}",
                "path": path,
            },
        ) from e

    except MemoryNotFoundError as e:
        logger.info(f"Memory node not found: {path}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NotFound",
                "message": str(e),
                "path": path,
            },
        ) from e

    except MemoryServiceError as e:
        logger.error(f"Memory service error for {path}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": "Internal server error occurred",
                "path": path,
            },
        ) from e

    except Exception as e:
        logger.error(f"Unexpected error retrieving {path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UnexpectedError",
                "message": "An unexpected error occurred",
                "path": path,
            },
        ) from e


@router.put("/{path:path}", response_model=MemoryNode, status_code=200)
async def create_or_update_memory_node(
    path: str,
    request_body: dict[str, Any],
    request: Request,
    response: Response,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryNode:
    """
    Create or update a memory node.

    Args:
        path: The memory node path (without .md extension)
        request_body: JSON body with "content" field
        request: FastAPI request object
        response: FastAPI response object
        memory_service: Injected memory service

    Returns:
        MemoryNode with content and metadata

    Raises:
        HTTPException: 400 for invalid content, 403 for read-only mode, 500 for internal errors
    """
    logger.info(f"PUT /memory/{path} - Request from {request.client}")

    try:
        # Check if service is in read-only mode
        from ..config import settings

        if settings.is_read_only:
            logger.warning(f"Write attempt blocked - service in read-only mode: {path}")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "ReadOnlyMode",
                    "message": "Service is in read-only mode",
                    "path": path,
                },
            )

        # Validate request body
        if not isinstance(request_body, dict) or "content" not in request_body:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidRequest",
                    "message": "Request body must contain 'content' field",
                    "path": path,
                },
            )

        content = request_body["content"]
        if not isinstance(content, str):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidContent",
                    "message": "Content must be a string",
                    "path": path,
                },
            )

        # Basic content validation
        if len(content.strip()) == 0:  # Empty content after stripping
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidRequest",
                    "message": "Content cannot be empty",
                    "path": path,
                },
            )

        if len(content.encode("utf-8")) > 10_000_000:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "ContentTooLarge",
                    "message": "Content exceeds maximum size limit (10MB)",
                    "path": path,
                },
            )

        # Sanitize the path to ensure it has .md extension and is safe
        sanitized_path = sanitize_path(path)
        logger.debug(f"Sanitized path: {path} -> {sanitized_path}")

        # Create or update the memory node
        memory_node, is_new = await memory_service.create_or_update_memory_node(
            sanitized_path, content
        )

        # Set appropriate status code
        if is_new:
            response.status_code = 201
            logger.info(f"Created new memory node: {sanitized_path}")
        else:
            response.status_code = 200
            logger.info(f"Updated existing memory node: {sanitized_path}")

        # Set HTTP headers
        response.headers["X-Git-SHA"] = memory_node.metadata.sha
        response.headers["Last-Modified"] = memory_node.metadata.updated_at.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

        # Create ETag from SHA and size
        etag = f'"{memory_node.metadata.sha}-{memory_node.metadata.size}"'
        response.headers["ETag"] = etag

        # Set content type
        response.headers["Content-Type"] = "application/json; charset=utf-8"

        return memory_node

    except PathValidationError as e:
        logger.warning(f"Invalid path provided: {path} - {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidPath",
                "message": f"Invalid path format: {e}",
                "path": path,
            },
        ) from e

    except MemoryServiceError as e:
        logger.error(f"Memory service error for {path}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": "Internal server error occurred",
                "path": path,
            },
        ) from e

    except UnicodeDecodeError as e:
        logger.warning(f"Invalid UTF-8 content provided for {path}: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidEncoding",
                "message": "Content must be valid UTF-8",
                "path": path,
            },
        ) from e

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 for read-only mode)
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating/updating {path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UnexpectedError",
                "message": "An unexpected error occurred",
                "path": path,
            },
        ) from e


@router.delete("/{path:path}", status_code=204)
async def delete_memory_node(
    path: str,
    request: Request,
    response: Response,
    memory_service: MemoryService = Depends(get_memory_service),
) -> None:
    """
    Delete a memory node.

    Args:
        path: The memory node path (without .md extension)
        request: FastAPI request object
        response: FastAPI response object
        memory_service: Injected memory service

    Returns:
        None (204 No Content response)

    Raises:
        HTTPException: 404 if not found, 403 for read-only mode, 400 for invalid paths
    """
    logger.info(f"DELETE /memory/{path} - Request from {request.client}")

    try:
        # Check if service is in read-only mode
        from ..config import settings

        if settings.is_read_only:
            logger.warning(f"Delete attempt blocked - service in read-only mode: {path}")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "ReadOnlyMode",
                    "message": "Service is in read-only mode",
                    "path": path,
                },
            )

        # Sanitize the path to ensure it has .md extension and is safe
        sanitized_path = sanitize_path(path)
        logger.debug(f"Sanitized path: {path} -> {sanitized_path}")

        # Delete the memory node
        deleted = await memory_service.delete_memory_node(sanitized_path)

        if not deleted:
            # File didn't exist - return 404 for idempotency
            logger.info(f"Memory node not found for deletion: {sanitized_path}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NotFound",
                    "message": f"Memory node not found: {path}",
                    "path": path,
                },
            )

        # Success - file was deleted
        logger.info(f"Successfully deleted memory node: {sanitized_path}")
        response.status_code = 204

    except PathValidationError as e:
        logger.warning(f"Invalid path provided: {path} - {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "InvalidPath",
                "message": f"Invalid path format: {e}",
                "path": path,
            },
        ) from e

    except MemoryServiceError as e:
        logger.error(f"Memory service error deleting {path}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": "Internal server error occurred",
                "path": path,
            },
        ) from e

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 for read-only mode)
        raise

    except Exception as e:
        logger.error(f"Unexpected error deleting {path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UnexpectedError",
                "message": "An unexpected error occurred",
                "path": path,
            },
        ) from e
