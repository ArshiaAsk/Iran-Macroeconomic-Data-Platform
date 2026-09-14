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

    # Scraper-specific settings
    scraper_min_request_interval: float = Field(default=1.0, alias="SCRAPER_MIN_REQUEST_INTERVAL")
    scraper_page_timeout: int = Field(default=30, alias="SCRAPER_PAGE_TIMEOUT")
    scraper_download_timeout: int = Field(default=60, alias="SCRAPER_DOWNLOAD_TIMEOUT")
    scraper_max_download_bytes: int = Field(default=10_000_000, alias="SCRAPER_MAX_DOWNLOAD_BYTES")

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

    @field_validator("scraper_min_request_interval")
    @classmethod
    def validate_scraper_min_request_interval(cls, v: float) -> float:
        """Validate scraper_min_request_interval is non-negative."""
        if v < 0:
            msg = "scraper_min_request_interval must be non-negative"
            raise ValueError(msg)
        return v

    @field_validator("scraper_page_timeout")
    @classmethod
    def validate_scraper_page_timeout(cls, v: int) -> int:
        """Validate scraper_page_timeout is positive."""
        if v <= 0:
            msg = "scraper_page_timeout must be positive"
            raise ValueError(msg)
        return v

    @field_validator("scraper_download_timeout")
    @classmethod
    def validate_scraper_download_timeout(cls, v: int) -> int:
        """Validate scraper_download_timeout is positive."""
        if v <= 0:
            msg = "scraper_download_timeout must be positive"
            raise ValueError(msg)
        return v

    @field_validator("scraper_max_download_bytes")
    @classmethod
    def validate_scraper_max_download_bytes(cls, v: int) -> int:
        """Validate scraper_max_download_bytes is positive."""
        if v <= 0:
            msg = "scraper_max_download_bytes must be positive"
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
    tgju_base_url: str = Field(default="https://www.tgju.org", alias="TGJU_BASE_URL")
    sci_base_url: str = Field(default="https://www.amar.org.ir", alias="SCI_BASE_URL")
    # Optional CA bundle for SCI. The site serves an incomplete TLS chain, so a
    # pinned intermediate is shipped under src/connectors/certs/ and used unless
    # this override points elsewhere.
    sci_ca_bundle: str | None = Field(default=None, alias="SCI_CA_BUNDLE")
    # CBI TSD is gated (see docs/phase-5/VALIDATION.md); the URL exists so a
    # future connector reads it from config rather than hardcoding it.
    cbi_tsd_url: str = Field(default="https://tsd.cbi.ir", alias="CBI_TSD_URL")

    # Phase 6 — TSETMC (optional `tsetmc` extra, `finpy-tse`). The connector
    # wraps the package's index client, but the raw cdn base URL and request
    # timeout live here so nothing is hardcoded in the logic. `http` (not
    # `https`) is the endpoint verified during the Task 1 gate.
    tsetmc_base_url: str = Field(default="http://cdn.tsetmc.com/api", alias="TSETMC_BASE_URL")
    tsetmc_timeout: int = Field(default=30, alias="TSETMC_TIMEOUT")

    # Phase 6 — HBSIR (optional `hbsir` extra). The `hbsir` package loads survey
    # microdata from a local data directory it downloads into; data is annual
    # and loaded on demand (no scheduled run). The package version used for a
    # run is captured from `importlib.metadata` into Bronze provenance.
    hbsir_data_dir: str = Field(default="Data", alias="HBSIR_DATA_DIR")
    hbsir_download_timeout: int = Field(default=60, alias="HBSIR_DOWNLOAD_TIMEOUT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allow construction by field name as well as by env-var alias; without
        # this, DatabaseConfig(host="x") silently drops the argument.
        populate_by_name=True,
    )

    @field_validator("tsetmc_timeout")
    @classmethod
    def validate_tsetmc_timeout(cls, v: int) -> int:
        """Validate tsetmc_timeout is positive."""
        if v <= 0:
            msg = "tsetmc_timeout must be positive"
            raise ValueError(msg)
        return v

    @field_validator("hbsir_download_timeout")
    @classmethod
    def validate_hbsir_download_timeout(cls, v: int) -> int:
        """Validate hbsir_download_timeout is positive."""
        if v <= 0:
            msg = "hbsir_download_timeout must be positive"
            raise ValueError(msg)
        return v


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
