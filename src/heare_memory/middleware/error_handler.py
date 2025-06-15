"""Error handling middleware."""

import logging
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle and format exceptions consistently."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Handle request and catch exceptions.

        Args:
            request: The incoming request
            call_next: The next middleware or endpoint

        Returns:
            Response: The response, possibly with error formatting
        """
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Re-raise HTTP exceptions to let FastAPI handle them
            raise
        except Exception as exc:
            logger.exception("Unhandled exception in request %s %s", request.method, request.url)

            # Return a structured error response
            details = {"type": type(exc).__name__} if logger.isEnabledFor(logging.DEBUG) else {}
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An internal server error occurred",
                    "details": details,
                },
            )
