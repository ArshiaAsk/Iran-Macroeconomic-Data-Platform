"""Unit tests for dashboard filter helpers."""

from datetime import UTC, date, datetime

import pandas as pd

from dashboard.components.filters import as_utc_datetime, default_date_bounds, unique_values


def test_unique_values_ignores_nulls_and_sorts() -> None:
    frame = pd.DataFrame({"domain": ["gdp", None, "inflation", "gdp"]})

    assert unique_values(frame, "domain") == ["gdp", "inflation"]
    assert unique_values(frame, "missing") == []


def test_default_bounds_use_catalog_coverage() -> None:
    frame = pd.DataFrame(
        {
            "availability_start": [
                pd.Timestamp("2000-01-01", tz="UTC"),
                pd.Timestamp("1990-01-01", tz="UTC"),
                None,
            ],
            "availability_end": [
                pd.Timestamp("2024-06-30", tz="UTC"),
                pd.Timestamp("2020-01-01", tz="UTC"),
                None,
            ],
        }
    )

    start, end = default_date_bounds(frame)

    assert start == datetime(1990, 1, 1, tzinfo=UTC)
    assert end == datetime(2024, 6, 30, tzinfo=UTC)


def test_date_control_is_converted_to_utc() -> None:
    assert as_utc_datetime(date(2024, 3, 15)) == datetime(2024, 3, 15, tzinfo=UTC)
