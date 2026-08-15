"""
Pytest configuration and shared fixtures.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.connectors.base import IndicatorMetadata
from src.database.connection import DatabaseConnection


@pytest.fixture
def sample_indicator() -> IndicatorMetadata:
    """Fixture for sample indicator metadata."""
    return IndicatorMetadata(
        indicator_id="TEST_GDP",
        name="GDP Growth Rate",
        description="Annual GDP growth rate",
        unit="percent",
        frequency="annual",
        domain="gdp",
        source_name="test_source",
        source_url="https://example.com/data",
        availability_start=datetime(1970, 1, 1),
        availability_end=datetime(2023, 12, 31),
        has_base_year_changes=True,
        base_years=[1997, 2011, 2016],
    )


@pytest.fixture
def sample_timeseries() -> pd.DataFrame:
    """Fixture for sample time-series data."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2020-01-01", periods=12, freq="ME"),
            "value": [100.0, 102.5, 105.0, 103.2, 106.8, 108.5, 110.2, 112.0, 114.5, 116.8, 118.2, 120.0],
            "metadata": [{"source": "test"} for _ in range(12)],
        }
    )


@pytest.fixture
def sample_timeseries_with_nulls() -> pd.DataFrame:
    """Fixture for time-series data with null values."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2020-01-01", periods=12, freq="ME"),
            "value": [100.0, None, 105.0, 103.2, None, 108.5, 110.2, 112.0, None, 116.8, 118.2, 120.0],
        }
    )


@pytest.fixture
def sample_timeseries_with_outliers() -> pd.DataFrame:
    """Fixture for time-series data with outliers."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2020-01-01", periods=12, freq="ME"),
            "value": [100.0, 102.5, 105.0, 103.2, 500.0, 108.5, 110.2, 112.0, 114.5, 1000.0, 118.2, 120.0],  # 500.0 and 1000.0 are outliers
        }
    )


@pytest.fixture
def mock_db_connection() -> MagicMock:
    """Fixture for mocked database connection."""
    mock_db = MagicMock(spec=DatabaseConnection)
    mock_db.test_connection.return_value = True
    return mock_db


@pytest.fixture
def test_config() -> dict[str, str]:
    """Fixture for test configuration."""
    return {
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "test_db",
        "DATABASE_USER": "test_user",
        "DATABASE_PASSWORD": "test_pass",
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "text",
        "COLLECTION_RETRY_MAX": "3",
        "COLLECTION_TIMEOUT": "30",
    }
