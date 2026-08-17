"""
Unit tests for database schema models.

Note: `mapped_column(default=...)` is an *insert-time* default, so on an
un-flushed instance the attribute is still None. These unit tests therefore
assert the declared column default; the values actually written to the database
are covered by tests/integration/test_database.py.
"""

from datetime import UTC, datetime
from typing import Any

from src.database.schema import (
    Base,
    BronzeRaw,
    ChainLinkingLog,
    DataCollectionLog,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
    TransformationLog,
)


def column_default(model: type[Base], column_name: str) -> Any:
    """Return the declared insert-time default for a model column."""
    default = model.__table__.c[column_name].default
    return None if default is None else default.arg


def test_bronze_raw_model() -> None:
    """Test BronzeRaw model can be instantiated."""
    bronze = BronzeRaw(
        source_name="test_source",
        source_type="api",
        raw_data={"test": "data"},
        collection_timestamp=datetime.now(UTC),
    )
    assert bronze.source_name == "test_source"
    assert bronze.source_type == "api"
    assert bronze.raw_data == {"test": "data"}


def test_silver_cleaned_model() -> None:
    """Test SilverCleaned model can be instantiated."""
    silver = SilverCleaned(
        indicator_id="TEST_INDICATOR",
        timestamp=datetime.now(UTC),
        value=123.45,
        frequency="monthly",
        source_name="test_source",
    )
    assert silver.indicator_id == "TEST_INDICATOR"
    assert silver.value == 123.45
    assert silver.frequency == "monthly"
    assert column_default(SilverCleaned, "validation_status") == "valid"
    assert column_default(SilverCleaned, "is_outlier") is False


def test_gold_analytical_model() -> None:
    """Test GoldAnalytical model can be instantiated."""
    gold = GoldAnalytical(
        indicator_id="TEST_INDICATOR",
        timestamp=datetime.now(UTC),
        value=123.45,
        frequency="monthly",
        domain="gdp",
    )
    assert gold.indicator_id == "TEST_INDICATOR"
    assert gold.value == 123.45
    assert gold.domain == "gdp"
    assert column_default(GoldAnalytical, "is_chain_linked") is False


def test_indicator_catalog_model() -> None:
    """Test IndicatorCatalog model can be instantiated."""
    indicator = IndicatorCatalog(
        indicator_id="TEST_INDICATOR",
        name="Test Indicator",
        unit="percent",
        frequency="monthly",
        domain="gdp",
        source_name="test_source",
    )
    assert indicator.indicator_id == "TEST_INDICATOR"
    assert indicator.name == "Test Indicator"
    assert indicator.frequency == "monthly"
    assert column_default(IndicatorCatalog, "is_active") is True
    assert column_default(IndicatorCatalog, "has_base_year_changes") is False


def test_data_collection_log_model() -> None:
    """Test DataCollectionLog model can be instantiated."""
    log = DataCollectionLog(
        source_name="test_source",
        collection_timestamp=datetime.now(UTC),
        status="success",
        records_collected=100,
    )
    assert log.source_name == "test_source"
    assert log.status == "success"
    assert log.records_collected == 100


def test_transformation_log_model() -> None:
    """Test TransformationLog model can be instantiated."""
    log = TransformationLog(
        source_layer="bronze",
        target_layer="silver",
        transformation_type="cleaning",
        transformation_timestamp=datetime.now(UTC),
        records_processed=100,
        records_failed=5,
        status="partial",
    )
    assert log.source_layer == "bronze"
    assert log.target_layer == "silver"
    assert log.records_processed == 100
    assert log.records_failed == 5


def test_chain_linking_log_model() -> None:
    """Test ChainLinkingLog model can be instantiated."""
    log = ChainLinkingLog(
        indicator_id="TEST_INDICATOR",
        linking_timestamp=datetime.now(UTC),
        base_year_from=2011,
        base_year_to=2016,
        linking_method="splice",
        records_linked=50,
        status="success",
    )
    assert log.indicator_id == "TEST_INDICATOR"
    assert log.base_year_from == 2011
    assert log.base_year_to == 2016
    assert log.linking_method == "splice"
