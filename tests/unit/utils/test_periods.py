"""
Unit tests for shared period-end helpers.

These helpers define the timestamp contract every connector and transformer
relies on, so the tests pin the exact period ends (including leap years) rather
than asserting loosely.
"""

from datetime import UTC, datetime

import pytest

from src.utils.exceptions import ParsingError
from src.utils.periods import (
    annual_period_end,
    month_period_end,
    parse_period,
    year_earlier,
)


def test_annual_period_end_is_december_31_utc() -> None:
    """Annual observations are stamped at the end of the year, timezone-aware."""
    assert annual_period_end("2022") == datetime(2022, 12, 31, tzinfo=UTC)


def test_annual_period_end_accepts_an_integer_year() -> None:
    """A JSON payload may hand back a number rather than a string."""
    assert annual_period_end(2022) == datetime(2022, 12, 31, tzinfo=UTC)


@pytest.mark.parametrize("bad_value", ["2022-01", "22", "twenty", "", None])
def test_annual_period_end_rejects_non_annual_values(bad_value: object) -> None:
    """Anything but a bare four-digit year is a parsing failure, not a guess."""
    with pytest.raises(ParsingError, match="four-digit annual date"):
        annual_period_end(bad_value)  # type: ignore[arg-type]


def test_month_period_end_uses_the_last_calendar_day() -> None:
    """Month length varies; the helper never assumes 30 or 31."""
    assert month_period_end(2026, 4) == datetime(2026, 4, 30, tzinfo=UTC)


def test_month_period_end_handles_leap_february() -> None:
    """2024 is a leap year; 2023 is not."""
    assert month_period_end(2024, 2) == datetime(2024, 2, 29, tzinfo=UTC)
    assert month_period_end(2023, 2) == datetime(2023, 2, 28, tzinfo=UTC)


@pytest.mark.parametrize("month", [0, 13, -1])
def test_month_period_end_rejects_impossible_months(month: int) -> None:
    """A month outside 1-12 is a defect in the caller, not data to coerce."""
    with pytest.raises(ParsingError, match="month must be between"):
        month_period_end(2026, month)


def test_parse_period_routes_by_frequency() -> None:
    """The same helper handles both cadences the platform ingests today."""
    assert parse_period("2022", "annual") == datetime(2022, 12, 31, tzinfo=UTC)
    assert parse_period("2026-05", "monthly") == datetime(2026, 5, 31, tzinfo=UTC)


@pytest.mark.parametrize("bad_value", ["2026/05", "2026-5-1", "May 2026", ""])
def test_parse_period_rejects_malformed_monthly_values(bad_value: str) -> None:
    """EIA sends ``YYYY-MM``; anything else would silently mis-date an observation."""
    with pytest.raises(ParsingError, match="YYYY-MM monthly date"):
        parse_period(bad_value, "monthly")


def test_parse_period_rejects_an_unsupported_frequency() -> None:
    """A cadence the platform does not support must fail loudly."""
    with pytest.raises(ParsingError, match="unsupported frequency"):
        parse_period("2022", "weekly")


def test_year_earlier_matches_the_previous_period_exactly() -> None:
    """YoY alignment looks up the same period last year, not the prior row."""
    assert year_earlier(datetime(2026, 5, 31, tzinfo=UTC)) == datetime(2025, 5, 31, tzinfo=UTC)


def test_year_earlier_handles_leap_day() -> None:
    """Feb 29 maps to Feb 28 the year before, which is that month's period end."""
    assert year_earlier(datetime(2024, 2, 29, tzinfo=UTC)) == datetime(2023, 2, 28, tzinfo=UTC)


def test_year_earlier_snaps_a_non_leap_february_to_the_leap_period_end() -> None:
    """Feb 28 2025's prior-year period is Feb 29 2024, or monthly YoY would gap."""
    assert year_earlier(datetime(2025, 2, 28, tzinfo=UTC)) == datetime(2024, 2, 29, tzinfo=UTC)
