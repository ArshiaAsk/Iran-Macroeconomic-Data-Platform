"""
Period-end helpers for time-series ingestion.

Sources report a period, not an instant: annual series carry a bare year and
monthly series carry ``YYYY-MM``. The platform stores one timestamp per period
and the project convention (AGENTS.md) is the **end** of that period, always
timezone-aware UTC, so a monthly value and the annual value it rolls up into do
not collide and year-over-year alignment is an exact period comparison.

These helpers are pure: no I/O, no database, no logging. Connectors and the ETL
transformers share them so a period is parsed identically on every path.
"""

import calendar
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.utils.exceptions import ParsingError

FREQUENCY_ANNUAL = "annual"
FREQUENCY_MONTHLY = "monthly"

ANNUAL_DATE_LENGTH = 4
MONTHLY_DATE_PARTS = 2
MIN_MONTH = 1
MAX_MONTH = 12


def annual_period_end(year: int | str) -> datetime:
    """
    Convert a bare year to its period-end timestamp.

    Args:
        year: Year as reported by the source, e.g. ``"2022"`` or ``2022``

    Returns:
        December 31 of that year, timezone-aware in UTC

    Raises:
        ParsingError: If the value is not a bare four-digit year
    """
    text = str(year).strip()
    if len(text) != ANNUAL_DATE_LENGTH or not text.isdigit():
        msg = f"expected a four-digit annual date, got {year!r}"
        raise ParsingError(msg)
    return datetime(int(text), 12, 31, tzinfo=UTC)


def month_period_end(year: int, month: int) -> datetime:
    """
    Convert a year and month to the last calendar day of that month.

    Args:
        year: Calendar year
        month: Calendar month (1-12)

    Returns:
        Last day of the month, timezone-aware in UTC

    Raises:
        ParsingError: If the month is outside 1-12
    """
    if not MIN_MONTH <= month <= MAX_MONTH:
        msg = f"month must be between 1 and 12, got {month!r}"
        raise ParsingError(msg)
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, tzinfo=UTC)


def parse_period(value: Any, frequency: str) -> datetime:
    """
    Convert a source period to its period-end timestamp for a known frequency.

    Supported forms:
    * ``annual``: a bare year (``"2022"``)
    * ``monthly``: ``YYYY-MM`` (``"2026-05"``)

    Args:
        value: Period as reported by the source
        frequency: Observation frequency

    Returns:
        Period-end timestamp, timezone-aware in UTC

    Raises:
        ParsingError: If the value or frequency is not supported
    """
    if frequency == FREQUENCY_ANNUAL:
        return annual_period_end(value)

    if frequency == FREQUENCY_MONTHLY:
        text = str(value).strip()
        parts = text.split("-")
        if len(parts) != MONTHLY_DATE_PARTS or not parts[0].isdigit() or not parts[1].isdigit():
            msg = f"expected a YYYY-MM monthly date, got {value!r}"
            raise ParsingError(msg)
        return month_period_end(int(parts[0]), int(parts[1]))

    msg = f"unsupported frequency {frequency!r}"
    raise ParsingError(msg)


def year_earlier(timestamp: datetime) -> datetime:
    """
    Return the exact prior-year period for a period-end timestamp.

    ``pd.DateOffset(years=1)`` handles the leap-day input correctly (Feb 29 ->
    Feb 28), but the reverse case needs care: a Feb 28 period end in a
    non-leap year belongs to a year whose February ends on the 29th, so the
    prior-year period is Feb 29, not Feb 28. Month-end inputs are therefore
    snapped back to the prior month's end, which is what makes month-end YoY
    alignment exact rather than positional.

    Args:
        timestamp: Period-end timestamp

    Returns:
        The same period one year earlier, timezone preserved
    """
    current = pd.Timestamp(timestamp)
    prior = current - pd.DateOffset(years=1)
    if current.is_month_end:
        prior = prior + pd.offsets.MonthEnd(0)
    return prior.to_pydatetime()
