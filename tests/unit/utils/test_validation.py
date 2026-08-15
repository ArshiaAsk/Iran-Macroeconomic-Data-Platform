"""
Unit tests for validation utilities.
"""

from datetime import datetime

import pandas as pd
import pytest

from src.utils.validation import (
    calculate_null_percentage,
    detect_outliers_iqr,
    validate_data_quality,
    validate_date_range,
    validate_schema,
)


def test_validate_schema_success() -> None:
    """Test schema validation with valid DataFrame."""
    df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
    is_valid, errors = validate_schema(df, ["col1", "col2"])
    assert is_valid is True
    assert len(errors) == 0


def test_validate_schema_missing_columns() -> None:
    """Test schema validation with missing columns."""
    df = pd.DataFrame({"col1": [1, 2, 3]})
    is_valid, errors = validate_schema(df, ["col1", "col2", "col3"])
    assert is_valid is False
    assert len(errors) == 1
    assert "Missing required columns" in errors[0]


def test_validate_date_range_success(sample_timeseries: pd.DataFrame) -> None:
    """Test date range validation with valid dates."""
    is_valid, errors = validate_date_range(
        sample_timeseries,
        "timestamp",
        min_date=datetime(2019, 1, 1),
        max_date=datetime(2025, 1, 1),
    )
    assert is_valid is True
    assert len(errors) == 0


def test_validate_date_range_future_dates() -> None:
    """Test date range validation rejects future dates."""
    df = pd.DataFrame(
        {"timestamp": [datetime(2050, 1, 1), datetime(2051, 1, 1)]}
    )
    is_valid, errors = validate_date_range(df, "timestamp")
    assert is_valid is False
    assert any("future" in error.lower() for error in errors)


def test_calculate_null_percentage_no_nulls(
    sample_timeseries: pd.DataFrame,
) -> None:
    """Test null percentage calculation with no nulls."""
    null_pct = calculate_null_percentage(sample_timeseries, "value")
    assert null_pct == 0.0


def test_calculate_null_percentage_with_nulls(
    sample_timeseries_with_nulls: pd.DataFrame,
) -> None:
    """Test null percentage calculation with nulls."""
    null_pct = calculate_null_percentage(sample_timeseries_with_nulls, "value")
    assert null_pct == pytest.approx(25.0, abs=0.1)  # 3 out of 12


def test_detect_outliers_iqr_no_outliers(
    sample_timeseries: pd.DataFrame,
) -> None:
    """Test outlier detection with no outliers."""
    outliers = detect_outliers_iqr(sample_timeseries, "value")
    assert outliers.sum() == 0


def test_detect_outliers_iqr_with_outliers(
    sample_timeseries_with_outliers: pd.DataFrame,
) -> None:
    """Test outlier detection with outliers."""
    outliers = detect_outliers_iqr(sample_timeseries_with_outliers, "value")
    assert outliers.sum() == 2  # 500.0 and 1000.0


def test_validate_data_quality_valid(sample_timeseries: pd.DataFrame) -> None:
    """Test comprehensive data quality validation with valid data."""
    result = validate_data_quality(sample_timeseries)
    assert result.is_valid is True
    assert len(result.errors) == 0
    assert result.null_percentage == 0.0
    assert result.outlier_count == 0
    assert result.record_count == 12


def test_validate_data_quality_empty_dataframe() -> None:
    """Test data quality validation with empty DataFrame."""
    df = pd.DataFrame()
    result = validate_data_quality(df)
    assert result.is_valid is False
    assert "empty" in result.errors[0].lower()


def test_validate_data_quality_with_warnings(
    sample_timeseries_with_nulls: pd.DataFrame,
) -> None:
    """Test data quality validation generates warnings for high null percentage."""
    result = validate_data_quality(
        sample_timeseries_with_nulls, null_threshold=5.0
    )
    assert result.is_valid is True  # Still valid, but has warnings
    assert len(result.warnings) > 0
    assert "null percentage" in result.warnings[0].lower()
