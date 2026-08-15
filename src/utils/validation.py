"""
Data validation utilities.

Provides schema validation, data quality checks, and outlier detection.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from src.utils.exceptions import ValidationError


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    null_percentage: float
    outlier_count: int
    record_count: int


def validate_schema(
    df: pd.DataFrame, required_columns: list[str]
) -> tuple[bool, list[str]]:
    """
    Validate DataFrame has required columns.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")

    return len(errors) == 0, errors


def validate_date_range(
    df: pd.DataFrame, date_column: str, min_date: datetime | None = None, max_date: datetime | None = None
) -> tuple[bool, list[str]]:
    """
    Validate dates are within acceptable range.

    Args:
        df: DataFrame to validate
        date_column: Name of date column
        min_date: Minimum acceptable date (optional)
        max_date: Maximum acceptable date (optional)

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    if date_column not in df.columns:
        errors.append(f"Date column '{date_column}' not found")
        return False, errors

    try:
        dates = pd.to_datetime(df[date_column])
    except Exception as e:
        errors.append(f"Failed to parse dates: {e}")
        return False, errors

    # Check for future dates
    if (dates > datetime.now()).any():
        errors.append("Found dates in the future")

    # Check min date
    if min_date and (dates < min_date).any():
        errors.append(f"Found dates before minimum date {min_date}")

    # Check max date
    if max_date and (dates > max_date).any():
        errors.append(f"Found dates after maximum date {max_date}")

    return len(errors) == 0, errors


def calculate_null_percentage(df: pd.DataFrame, column: str) -> float:
    """
    Calculate percentage of null values in column.

    Args:
        df: DataFrame
        column: Column name

    Returns:
        Percentage of null values (0-100)
    """
    if column not in df.columns:
        raise ValidationError(f"Column '{column}' not found")

    null_count = df[column].isnull().sum()
    total_count = len(df)

    if total_count == 0:
        return 0.0

    return (null_count / total_count) * 100


def detect_outliers_iqr(
    df: pd.DataFrame, column: str, multiplier: float = 1.5
) -> pd.Series:
    """
    Detect outliers using Interquartile Range (IQR) method.

    Args:
        df: DataFrame
        column: Column name to check for outliers
        multiplier: IQR multiplier (default 1.5 for standard outliers)

    Returns:
        Boolean Series indicating outliers (True = outlier)
    """
    if column not in df.columns:
        raise ValidationError(f"Column '{column}' not found")

    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1

    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR

    return (df[column] < lower_bound) | (df[column] > upper_bound)


def validate_data_quality(
    df: pd.DataFrame,
    value_column: str = "value",
    date_column: str = "timestamp",
    null_threshold: float = 5.0,
) -> ValidationResult:
    """
    Comprehensive data quality validation.

    Args:
        df: DataFrame to validate
        value_column: Name of value column
        date_column: Name of date column
        null_threshold: Maximum acceptable null percentage (default 5%)

    Returns:
        ValidationResult with validation details
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check if DataFrame is empty
    if df.empty:
        errors.append("DataFrame is empty")
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            null_percentage=0.0,
            outlier_count=0,
            record_count=0,
        )

    # Validate schema
    required_columns = [value_column, date_column]
    schema_valid, schema_errors = validate_schema(df, required_columns)
    errors.extend(schema_errors)

    if not schema_valid:
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            null_percentage=0.0,
            outlier_count=0,
            record_count=len(df),
        )

    # Check null percentage
    null_pct = calculate_null_percentage(df, value_column)
    if null_pct > null_threshold:
        warnings.append(
            f"High null percentage: {null_pct:.2f}% (threshold: {null_threshold}%)"
        )

    # Validate date range
    date_valid, date_errors = validate_date_range(df, date_column)
    errors.extend(date_errors)

    # Detect outliers
    outliers = detect_outliers_iqr(df, value_column)
    outlier_count = outliers.sum()

    if outlier_count > 0:
        outlier_pct = (outlier_count / len(df)) * 100
        warnings.append(
            f"Found {outlier_count} outliers ({outlier_pct:.2f}% of data)"
        )

    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        null_percentage=null_pct,
        outlier_count=int(outlier_count),
        record_count=len(df),
    )
