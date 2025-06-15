"""OpenAPI schema router."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["schema"])


@router.get("/schema")
async def get_openapi_schema(request: Request) -> JSONResponse:
    """Get OpenAPI schema for the API.

    Args:
        request: FastAPI request object

    Returns:
        JSONResponse: OpenAPI schema as JSON
    """
    return JSONResponse(request.app.openapi())
