"""Configuration management for Heare Memory service."""

import logging
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service configuration
    service_host: str = Field(default="0.0.0.0", description="Service host address")
    service_port: int = Field(default=8000, description="Service port")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Memory storage configuration
    memory_root: Path = Field(
        default=Path("./memory"), description="Root directory for memory storage"
    )

    # Git configuration
    git_remote_url: str | None = Field(
        default=None, description="Git remote URL for memory repository"
    )
    github_token: str | None = Field(
        default=None, description="GitHub access token for git operations"
    )

    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )

    # API configuration
    api_title: str = Field(default="Heare Memory Global Service", description="API title")
    api_description: str = Field(
        default="A RESTful memory service with git-backed persistence for multi-agent environments",
        description="API description",
    )
    api_version: str = Field(default="0.1.0", description="API version")

    # CORS configuration
    cors_origins: list[str] = Field(default=["*"], description="List of origins allowed for CORS")
    cors_allow_credentials: bool = Field(
        default=True, description="Allow credentials in CORS requests"
    )

    @property
    def is_read_only(self) -> bool:
        """Check if the service should run in read-only mode."""
        return self.github_token is None

    def setup_logging(self) -> None:
        """Configure application logging."""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format=self.log_format,
        )

    def ensure_memory_root(self) -> None:
        """Ensure memory root directory exists."""
        self.memory_root.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
