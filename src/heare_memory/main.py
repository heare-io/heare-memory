"""Main FastAPI application for Heare Memory service."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .middleware.error_handler import ErrorHandlerMiddleware
from .routers import health, memory, schema

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown."""
    # Startup
    settings.setup_logging()
    logger.info("Starting Heare Memory service version %s", __version__)
    logger.info(
        "Configuration: read_only=%s, git_configured=%s",
        settings.is_read_only,
        settings.git_remote_url is not None,
    )

    # Ensure memory root directory exists
    settings.ensure_memory_root()
    logger.info("Memory root directory: %s", settings.memory_root)

    # TODO: Add git repository initialization and checks
    # TODO: Add external tool checks (git, gh, ripgrep)

    yield

    # Shutdown
    logger.info("Shutting down Heare Memory service")
    # TODO: Add cleanup code (close git connections, etc.)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan,
    )

    # Add error handling middleware
    app.add_middleware(ErrorHandlerMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(memory.router)
    app.include_router(schema.router)

    return app


def main() -> None:
    """Main entry point for the application."""
    app = create_app()
    uvicorn.run(
        app,
        host=settings.service_host,
        port=settings.service_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
