"""Health check router for service monitoring."""

from fastapi import APIRouter

from .. import __version__
from ..config import settings
from ..state import get_startup_result

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str | bool]:
    """Health check endpoint.

    Returns:
        dict: Health status information including service status,
              version, read-only mode, and git configuration.
    """
    startup_result = get_startup_result()

    # Base health info
    health_info = {
        "status": "healthy",
        "version": __version__,
        "service": "heare-memory",
        "read_only": settings.is_read_only,
        "git_configured": settings.git_remote_url is not None,
    }

    # Add startup-specific information if available
    if startup_result:
        health_info["search_backend"] = startup_result.search_backend
        health_info["read_only"] = startup_result.read_only_mode

        # Add detailed search backend status
        if startup_result.search_backend_status:
            health_info["search_backend_details"] = startup_result.search_backend_status

        # If there were startup warnings, mark as degraded
        if startup_result.warnings:
            health_info["status"] = "degraded"
    else:
        health_info["search_backend"] = "unknown"

    return health_info
