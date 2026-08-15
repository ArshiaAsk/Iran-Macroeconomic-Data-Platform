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
from src.utils.exceptions import ConfigurationError


def test_database_config_defaults() -> None:
    """Test database config with default values."""
    with patch.dict(os.environ, {}, clear=True):
        config = DatabaseConfig()
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
        config = LoggingConfig()
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
        config = APIConfig()
        assert "worldbank.org" in config.world_bank_url
        assert "imf.org" in config.imf_url
        assert config.eia_api_key is None
