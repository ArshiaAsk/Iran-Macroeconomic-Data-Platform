"""Unit tests for the shared observations-table row cap (Task 15)."""

import pandas as pd
import pytest

from dashboard.components.tables import OBSERVATIONS_ROW_LIMIT, cap_table_rows


def _frame(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indicator_id": [f"i{index}" for index in range(rows)],
            "timestamp": [
                pd.Timestamp("2020-01-01", tz="UTC") + pd.Timedelta(days=index)
                for index in range(rows)
            ],
            "value": [float(index) for index in range(rows)],
        }
    )


def test_rows_under_the_limit_are_returned_untouched() -> None:
    frame = _frame(3)

    capped = cap_table_rows(frame)

    assert capped.truncated is False
    assert capped.total_rows == 3
    assert capped.shown_rows == 3
    assert capped.frame is frame


def test_rows_exactly_at_the_limit_are_not_truncated() -> None:
    capped = cap_table_rows(_frame(OBSERVATIONS_ROW_LIMIT))

    assert capped.truncated is False
    assert capped.shown_rows == OBSERVATIONS_ROW_LIMIT
    assert len(capped.frame) == OBSERVATIONS_ROW_LIMIT


def test_rows_over_the_limit_keep_the_first_rows() -> None:
    frame = _frame(OBSERVATIONS_ROW_LIMIT + 1)

    capped = cap_table_rows(frame)

    assert capped.truncated is True
    assert capped.total_rows == OBSERVATIONS_ROW_LIMIT + 1
    assert capped.shown_rows == OBSERVATIONS_ROW_LIMIT
    assert capped.frame["value"].tolist() == list(range(OBSERVATIONS_ROW_LIMIT))


def test_cap_keeps_timezone_aware_timestamps() -> None:
    frame = _frame(OBSERVATIONS_ROW_LIMIT + 1)

    capped = cap_table_rows(frame)

    assert isinstance(capped.frame["timestamp"].dtype, pd.DatetimeTZDtype)
    assert capped.frame["timestamp"].iloc[0] == frame["timestamp"].iloc[0]
    assert capped.frame["timestamp"].iloc[-1] == frame["timestamp"].iloc[OBSERVATIONS_ROW_LIMIT - 1]


def test_custom_limit_is_honoured() -> None:
    capped = cap_table_rows(_frame(10), limit=4)

    assert capped.truncated is True
    assert capped.shown_rows == 4
    assert capped.total_rows == 10


@pytest.mark.parametrize("limit", [0, -1])
def test_non_positive_limits_are_rejected(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        cap_table_rows(_frame(3), limit=limit)
