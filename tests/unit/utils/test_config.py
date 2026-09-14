"""
Unit tests for configuration management.
"""

import os
from unittest.mock import patch

import pytest

from src.utils.config import (
    APIConfig,
    CollectionConfig,
    DatabaseConfig,
    LoggingConfig,
)


def test_database_config_defaults() -> None:
    """Test database config with default values."""
    # _env_file=None keeps the test hermetic: a developer's local .env must not
    # change the result.
    with patch.dict(os.environ, {}, clear=True):
        config = DatabaseConfig(_env_file=None)
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.name == "iran_macro_db"
        assert config.user == "iran_macro"


def test_database_config_url() -> None:
    """Test database URL generation."""
    config = DatabaseConfig(
        host="testhost",
        port=5433,
        name="testdb",
        user="testuser",
        password="testpass",
    )
    expected_url = "postgresql://testuser:testpass@testhost:5433/testdb"
    assert config.url == expected_url


def test_logging_config_defaults() -> None:
    """Test logging config with default values."""
    with patch.dict(os.environ, {}, clear=True):
        config = LoggingConfig(_env_file=None)
        assert config.level == "INFO"
        assert config.format == "json"


def test_collection_config_validation_retry_max() -> None:
    """Test collection config validates retry_max."""
    with pytest.raises(ValueError, match="retry_max must be non-negative"):
        CollectionConfig(retry_max=-1)


def test_collection_config_validation_timeout() -> None:
    """Test collection config validates timeout."""
    with pytest.raises(ValueError, match="timeout must be positive"):
        CollectionConfig(timeout=0)


def test_api_config_defaults() -> None:
    """Test API config with default values."""
    with patch.dict(os.environ, {}, clear=True):
        config = APIConfig(_env_file=None)
        assert "worldbank.org" in config.world_bank_url
        assert "imf.org" in config.imf_url
        assert config.eia_api_key is None


def test_api_config_sci_and_cbi_urls() -> None:
    """SCI is configured; CBI's URL exists even though the source is gated."""
    with patch.dict(os.environ, {}, clear=True):
        config = APIConfig(_env_file=None)
        assert "amar.org.ir" in config.sci_base_url
        assert "tsd.cbi.ir" in config.cbi_tsd_url


def test_api_config_phase6_defaults() -> None:
    """Phase 6 sources have sensible defaults and are optional."""
    with patch.dict(os.environ, {}, clear=True):
        config = APIConfig(_env_file=None)
        assert config.tsetmc_base_url == "http://cdn.tsetmc.com/api"
        assert config.tsetmc_timeout == 30
        assert config.hbsir_data_dir == "Data"
        assert config.hbsir_download_timeout == 60


def test_api_config_phase6_reads_aliases() -> None:
    """Phase 6 settings are overridable via their environment aliases."""
    with patch.dict(
        os.environ,
        {
            "TSETMC_BASE_URL": "http://tsetmc.test/api",
            "TSETMC_TIMEOUT": "45",
            "HBSIR_DATA_DIR": "/data/hbsir",
            "HBSIR_DOWNLOAD_TIMEOUT": "120",
        },
        clear=True,
    ):
        config = APIConfig(_env_file=None)
        assert config.tsetmc_base_url == "http://tsetmc.test/api"
        assert config.tsetmc_timeout == 45
        assert config.hbsir_data_dir == "/data/hbsir"
        assert config.hbsir_download_timeout == 120


def test_api_config_phase6_timeout_validation() -> None:
    """Non-positive Phase 6 timeouts are rejected."""
    with pytest.raises(ValueError, match="tsetmc_timeout must be positive"):
        APIConfig(tsetmc_timeout=0)
    with pytest.raises(ValueError, match="hbsir_download_timeout must be positive"):
        APIConfig(hbsir_download_timeout=-1)


def test_api_config_reads_aliases() -> None:
    """New URLs are overridable via their environment aliases."""
    with patch.dict(
        os.environ,
        {
            "SCI_BASE_URL": "https://sci.test",
            "CBI_TSD_URL": "https://cbi.test",
            "SCI_CA_BUNDLE": "/tmp/sci-ca.pem",
        },
        clear=True,
    ):
        config = APIConfig(_env_file=None)
        assert config.sci_base_url == "https://sci.test"
        assert config.cbi_tsd_url == "https://cbi.test"
        assert config.sci_ca_bundle == "/tmp/sci-ca.pem"


def test_collection_config_scraper_download_defaults() -> None:
    """Download timeout and size cap have sensible defaults."""
    with patch.dict(os.environ, {}, clear=True):
        config = CollectionConfig(_env_file=None)
        assert config.scraper_download_timeout == 60
        assert config.scraper_max_download_bytes == 10_000_000


def test_collection_config_validation_download_timeout() -> None:
    """A non-positive download timeout is rejected."""
    with pytest.raises(ValueError, match="scraper_download_timeout must be positive"):
        CollectionConfig(scraper_download_timeout=0)


def test_collection_config_validation_max_download_bytes() -> None:
    """A non-positive size cap is rejected."""
    with pytest.raises(ValueError, match="scraper_max_download_bytes must be positive"):
        CollectionConfig(scraper_max_download_bytes=0)
