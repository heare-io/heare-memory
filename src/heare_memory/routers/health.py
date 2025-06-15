"""Health check router for service monitoring."""

from fastapi import APIRouter

from .. import __version__
from ..config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str | bool]:
    """Health check endpoint.

    Returns:
        dict: Health status information including service status,
              version, read-only mode, and git configuration.
    """
    return {
        "status": "healthy",
        "version": __version__,
        "service": "heare-memory",
        "read_only": settings.is_read_only,
        "git_configured": settings.git_remote_url is not None,
        "search_backend": "ripgrep",  # TODO: Detect actual backend
    }
