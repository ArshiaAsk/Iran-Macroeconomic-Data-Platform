"""Unit tests for the shared observations-table row cap and localization."""

import pandas as pd
import pytest

from dashboard.components.tables import (
    OBSERVATIONS_ROW_LIMIT,
    cap_table_rows,
    localize_table_frame,
    localized_header,
)
from dashboard.formatting import format_number, jalali_date_label
from dashboard.i18n import t
from dashboard.labels import frequency_label, indicator_label


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


def _gold_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indicator_id": ["FP.CPI.TOTL.ZG"],
            "name": ["Inflation"],
            "timestamp": [pd.Timestamp("2024-01-01", tz="UTC")],
            "value": [12.5],
            "unit": ["%"],
            "frequency": ["annual"],
            "domain": ["inflation"],
            "source_name": ["world_bank"],
            "is_chain_linked": [True],
            "derived_from": [None],
        }
    )


def test_localize_table_frame_translates_headers_digits_and_dates() -> None:
    display = localize_table_frame(_gold_frame())

    assert list(display.columns) == [
        t("table.indicator_id"),
        t("table.name"),
        t("table.timestamp"),
        t("table.value"),
        t("table.unit"),
        t("table.frequency"),
        t("table.domain"),
        t("table.source_name"),
        t("table.is_chain_linked"),
        t("table.derived_from"),
    ]
    row = display.iloc[0]
    assert row[t("table.indicator_id")] == "FP.CPI.TOTL.ZG"
    assert row[t("table.name")] == indicator_label("FP.CPI.TOTL.ZG", "Inflation")
    assert row[t("table.timestamp")] == jalali_date_label(pd.Timestamp("2024-01-01", tz="UTC"))
    assert row[t("table.value")] == format_number(12.5)
    assert row[t("table.frequency")] == frequency_label("annual")
    assert row[t("table.is_chain_linked")] == t("value.yes")
    assert row[t("table.derived_from")] == "—"


def test_localize_table_frame_preserves_the_raw_frame() -> None:
    frame = _gold_frame()

    display = localize_table_frame(frame)

    # Localization is a display transform: the source frame keeps its values,
    # column names and dtypes for the exports and the quality logic.
    assert list(frame.columns) == list(_gold_frame().columns)
    assert frame["value"].iloc[0] == 12.5
    assert isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype)
    assert display is not frame


def test_localize_table_frame_is_empty_safe() -> None:
    display = localize_table_frame(pd.DataFrame({"value": pd.Series(dtype="float64")}))

    assert display.empty
    assert t("table.value") in display.columns


def test_localized_header_falls_back_to_the_raw_column_name() -> None:
    assert localized_header("value") == t("table.value")
    assert localized_header("custom_column") == "custom_column"
