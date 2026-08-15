"""
Unit tests for database schema models.
"""

from datetime import datetime

from src.database.schema import (
    BronzeRaw,
    ChainLinkingLog,
    DataCollectionLog,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
    TransformationLog,
)


def test_bronze_raw_model() -> None:
    """Test BronzeRaw model can be instantiated."""
    bronze = BronzeRaw(
        source_name="test_source",
        source_type="api",
        raw_data={"test": "data"},
        collection_timestamp=datetime.utcnow(),
    )
    assert bronze.source_name == "test_source"
    assert bronze.source_type == "api"
    assert bronze.raw_data == {"test": "data"}


def test_silver_cleaned_model() -> None:
    """Test SilverCleaned model can be instantiated."""
    silver = SilverCleaned(
        indicator_id="TEST_INDICATOR",
        timestamp=datetime.utcnow(),
        value=123.45,
        frequency="monthly",
        source_name="test_source",
    )
    assert silver.indicator_id == "TEST_INDICATOR"
    assert silver.value == 123.45
    assert silver.frequency == "monthly"
    assert silver.validation_status == "valid"
    assert silver.is_outlier is False


def test_gold_analytical_model() -> None:
    """Test GoldAnalytical model can be instantiated."""
    gold = GoldAnalytical(
        indicator_id="TEST_INDICATOR",
        timestamp=datetime.utcnow(),
        value=123.45,
        frequency="monthly",
        domain="gdp",
    )
    assert gold.indicator_id == "TEST_INDICATOR"
    assert gold.value == 123.45
    assert gold.domain == "gdp"
    assert gold.is_chain_linked is False


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
    assert indicator.is_active is True
    assert indicator.has_base_year_changes is False


def test_data_collection_log_model() -> None:
    """Test DataCollectionLog model can be instantiated."""
    log = DataCollectionLog(
        source_name="test_source",
        collection_timestamp=datetime.utcnow(),
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
        transformation_timestamp=datetime.utcnow(),
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
        linking_timestamp=datetime.utcnow(),
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
