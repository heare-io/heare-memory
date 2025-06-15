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


@router.delete("/{path:path}")
async def delete_memory_node(path: str) -> None:
    """Delete a memory node.

    Args:
        path: The memory node path

    Raises:
        HTTPException: If memory node not found or operation fails
    """
    # TODO: Implement memory node deletion
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/")
async def list_memory_nodes(
    prefix: str | None = None,
    delimiter: str | None = None,
    recursive: bool = True,
    include_content: bool = False,
) -> dict[str, Any]:
    """List memory nodes with optional filtering.

    Args:
        prefix: Filter by path prefix
        delimiter: Delimiter for hierarchical listing
        recursive: Include subdirectories recursively
        include_content: Include node content in response

    Returns:
        dict: List of memory nodes
    """
    # TODO: Implement memory node listing
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/search")
async def search_memory_nodes(
    query: str,
    prefix: str | None = None,
    context_lines: int = 2,
    max_results: int = 50,
) -> dict[str, Any]:
    """Search memory node content.

    Args:
        query: Search query (grep pattern)
        prefix: Search within path prefix
        context_lines: Lines of context around matches
        max_results: Maximum number of results

    Returns:
        dict: Search results with highlighted matches
    """
    # TODO: Implement memory content search
    raise HTTPException(status_code=501, detail="Not implemented yet")
