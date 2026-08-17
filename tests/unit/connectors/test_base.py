"""
Unit tests for DataConnector abstract base class.
"""

from datetime import datetime

import pandas as pd
import pytest

from src.connectors.base import DataConnector, IndicatorMetadata
from src.utils.validation import ValidationResult


class ConcreteConnector(DataConnector):
    """Concrete implementation for testing."""

    def connect(self) -> bool:
        return True

    def discover(self) -> list[IndicatorMetadata]:
        return []

    def fetch(self, indicator_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        return pd.DataFrame()

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            null_percentage=0.0,
            outlier_count=0,
            record_count=0,
        )


def test_connector_initialization() -> None:
    """Test connector can be initialized."""
    connector = ConcreteConnector(source_name="test_source")
    assert connector.source_name == "test_source"


def test_connector_abstract_class_cannot_be_instantiated() -> None:
    """Test that abstract DataConnector cannot be instantiated."""
    with pytest.raises(TypeError):
        DataConnector(source_name="test")  # type: ignore


def test_connector_context_manager() -> None:
    """Test connector works as context manager."""
    with ConcreteConnector(source_name="test_source") as connector:
        assert connector.source_name == "test_source"


def test_indicator_metadata_creation(sample_indicator: IndicatorMetadata) -> None:
    """Test IndicatorMetadata can be created."""
    assert sample_indicator.indicator_id == "TEST_GDP"
    assert sample_indicator.name == "GDP Growth Rate"
    assert sample_indicator.frequency == "annual"
    assert sample_indicator.domain == "gdp"
    assert sample_indicator.has_base_year_changes is True
    assert sample_indicator.base_years == [1997, 2011, 2016]
