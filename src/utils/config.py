"""
Configuration management using Pydantic.

Loads and validates configuration from environment variables.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    host: str = Field(default="localhost", alias="DATABASE_HOST")
    port: int = Field(default=5432, alias="DATABASE_PORT")
    name: str = Field(default="iran_macro_db", alias="DATABASE_NAME")
    user: str = Field(default="iran_macro", alias="DATABASE_USER")
    password: str = Field(default="iran_macro_pass", alias="DATABASE_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow construction by field name as well as by env-var alias; without
        # this, DatabaseConfig(host="x") silently drops the argument.
        populate_by_name=True,
    )

    @property
    def url(self) -> str:
        """Get database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    format: Literal["json", "text"] = Field(default="json", alias="LOG_FORMAT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow construction by field name as well as by env-var alias; without
        # this, DatabaseConfig(host="x") silently drops the argument.
        populate_by_name=True,
    )


class CollectionConfig(BaseSettings):
    """Data collection configuration."""

    retry_max: int = Field(default=3, alias="COLLECTION_RETRY_MAX")
    timeout: int = Field(default=30, alias="COLLECTION_TIMEOUT")
    user_agent_rotation: bool = Field(default=True, alias="USER_AGENT_ROTATION")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow construction by field name as well as by env-var alias; without
        # this, DatabaseConfig(host="x") silently drops the argument.
        populate_by_name=True,
    )

    @field_validator("retry_max")
    @classmethod
    def validate_retry_max(cls, v: int) -> int:
        """Validate retry_max is positive."""
        if v < 0:
            msg = "retry_max must be non-negative"
            raise ValueError(msg)
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is positive."""
        if v <= 0:
            msg = "timeout must be positive"
            raise ValueError(msg)
        return v


class APIConfig(BaseSettings):
    """API configuration for external data sources."""

    world_bank_url: str = Field(default="https://api.worldbank.org/v2", alias="WORLD_BANK_API_URL")
    imf_url: str = Field(
        default="https://www.imf.org/external/datamapper/api/v1",
        alias="IMF_API_URL",
    )
    eia_api_key: str | None = Field(default=None, alias="EIA_API_KEY")
    eia_url: str = Field(default="https://api.eia.gov/v2", alias="EIA_API_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow construction by field name as well as by env-var alias; without
        # this, DatabaseConfig(host="x") silently drops the argument.
        populate_by_name=True,
    )


class AppConfig(BaseSettings):
    """Application-wide configuration."""

    env: Literal["development", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    debug: bool = Field(default=False, alias="DEBUG")

    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    collection: CollectionConfig = Field(default_factory=CollectionConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow construction by field name as well as by env-var alias; without
        # this, DatabaseConfig(host="x") silently drops the argument.
        populate_by_name=True,
    )


@lru_cache
def get_config() -> AppConfig:
    """
    Get cached application configuration.

    Returns:
        Application configuration instance
    """
    return AppConfig()
