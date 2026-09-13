"""
Unit tests for daily -> monthly month-end aggregation.

The rule (AGENTS.md) is end-of-month for price data and no forward-fill, so the
tests assert both the retained value and the absence of rows for empty months.
"""

from datetime import UTC, datetime

import pandas as pd
import pytest

from src.etl.frequency import MONTH_END, aggregate_to_monthly, to_month_end


def daily_frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """A daily Silver-shaped frame from ``(date, value)`` pairs."""
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime([date for date, _ in rows], utc=True),
            "value": [value for _, value in rows],
        }
    )


def test_to_month_end_keeps_the_last_observation_of_each_month() -> None:
    """The month's closing price is the last observation, not the first or mean."""
    frame = daily_frame(
        [
            ("2026-04-01", 10.0),
            ("2026-04-15", 20.0),
            ("2026-04-30", 30.0),
            ("2026-05-01", 40.0),
            ("2026-05-20", 50.0),
        ]
    )

    result = to_month_end(frame)

    assert result["timestamp"].tolist() == [
        datetime(2026, 4, 30, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
    ]
    assert result["value"].tolist() == [30.0, 50.0]


def test_to_month_end_does_not_fill_an_empty_month() -> None:
    """A month with no observation produces no row; a gap must stay visible."""
    frame = daily_frame([("2026-03-31", 1.0), ("2026-05-31", 3.0)])

    result = to_month_end(frame)

    assert result["timestamp"].tolist() == [
        datetime(2026, 3, 31, tzinfo=UTC),
        datetime(2026, 5, 31, tzinfo=UTC),
    ]


def test_to_month_end_sorts_unordered_input() -> None:
    """Bronze order is not guaranteed; the result is always ascending."""
    frame = daily_frame([("2026-05-10", 5.0), ("2026-04-10", 4.0)])

    result = to_month_end(frame)

    assert result["timestamp"].is_monotonic_increasing
    assert result["value"].tolist() == [4.0, 5.0]


def test_to_month_end_handles_leap_february() -> None:
    """The month-end stamp respects the calendar, including Feb 29."""
    frame = daily_frame([("2024-02-15", 1.0)])

    result = to_month_end(frame)

    assert result["timestamp"].tolist() == [datetime(2024, 2, 29, tzinfo=UTC)]


def test_to_month_end_returns_the_silver_column_contract() -> None:
    """Only timestamp and value survive; the frame is Gold-ready."""
    frame = daily_frame([("2026-04-30", 1.0)])[["value", "timestamp"]]

    result = to_month_end(frame)

    assert list(result.columns) == ["timestamp", "value"]


def test_aggregate_to_monthly_defaults_to_month_end() -> None:
    """The named seam must produce the same result as the direct helper."""
    frame = daily_frame([("2026-04-30", 1.0)])

    result = aggregate_to_monthly(frame)

    assert result["value"].tolist() == to_month_end(frame)["value"].tolist()


def test_aggregate_to_monthly_rejects_an_unknown_method() -> None:
    """An unimplemented aggregation must fail loudly rather than silently no-op."""
    frame = daily_frame([("2026-04-30", 1.0)])

    with pytest.raises(ValueError, match="unsupported monthly aggregation method"):
        aggregate_to_monthly(frame, method="mean")


def test_month_end_constant_is_the_supported_method() -> None:
    """Guard against a rename drifting away from the public default."""
    assert MONTH_END == "month_end"
