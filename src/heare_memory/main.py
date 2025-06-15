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
from .startup import StartupError, format_startup_error, run_startup_checks
from .state import set_git_manager, set_startup_result

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown."""
    # Startup
    settings.setup_logging()
    logger.info("Starting Heare Memory service version %s", __version__)

    try:
        # Run comprehensive startup checks
        startup_result = await run_startup_checks()

        # Store results in global state
        set_git_manager(startup_result.git_manager)
        set_startup_result(startup_result)

        logger.info("Service initialized successfully")
        if startup_result.warnings:
            for warning in startup_result.warnings:
                logger.warning("Startup warning: %s", warning)

    except StartupError as exc:
        error_details = format_startup_error(exc)
        logger.error("Startup failed:\n%s", error_details)
        raise RuntimeError(f"Service startup failed: {exc}") from exc
    except Exception as exc:
        logger.error("Unexpected startup error: %s", exc)
        raise RuntimeError(f"Unexpected startup error: {exc}") from exc

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
