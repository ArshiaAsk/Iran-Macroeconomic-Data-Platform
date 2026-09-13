"""
Unit tests for the pure EIA v2 payload/row parser.

No network: rows are taken from the captured fixtures under
``tests/fixtures/eia`` or built inline for edge cases.
"""

from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from src.connectors.eia_parser import FRAME_COLUMNS, eia_parser, empty_frame
from src.utils.exceptions import ParsingError
from tests.conftest import load_eia_fixture

INDICATOR = "EIA.IRN.CRUDE_PRODUCTION"


def fixture_rows() -> list[dict[str, Any]]:
    """The ``response.data`` array of the captured crude-production payload."""
    return list(load_eia_fixture("CRUDE_PRODUCTION_normal")["response"]["data"])


def row(**overrides: Any) -> dict[str, Any]:
    """A minimal well-formed EIA observation, with per-test overrides."""
    base: dict[str, Any] = {
        "period": "2026-05",
        "value": "3430",
        "unitName": "thousand barrels per day",
        "dataFlagDescription": None,
        "dataFlagId": None,
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------ empty frame


def test_empty_rows_return_the_column_contract() -> None:
    """No observations is a valid answer with a stable schema."""
    frame = eia_parser([], INDICATOR)

    assert list(frame.columns) == list(FRAME_COLUMNS)
    assert frame.empty
    assert str(frame["timestamp"].dtype) == "datetime64[ns, UTC]"


def test_empty_frame_matches_parser_columns() -> None:
    """The exported helper is the same contract the parser uses."""
    assert list(empty_frame().columns) == list(FRAME_COLUMNS)


# ------------------------------------------------------------------ happy path


def test_parser_builds_the_silver_frame_contract() -> None:
    """Captured rows become one clean dataframe in the Silver schema."""
    rows = fixture_rows()

    frame = eia_parser(rows, INDICATOR)

    assert list(frame.columns) == list(FRAME_COLUMNS)
    assert len(frame) == len(rows)
    assert frame["indicator_id"].unique().tolist() == [INDICATOR]
    assert frame["value"].dtype == "float64"
    assert frame["value"].notna().all()
    assert set(frame["unit"].unique()) == {"thousand barrels per day"}


def test_period_is_stamped_at_month_end_utc() -> None:
    """``YYYY-MM`` becomes the last calendar day, timezone-aware (project rule)."""
    frame = eia_parser([row(period="2026-05")], INDICATOR)

    assert frame.loc[0, "timestamp"] == datetime(2026, 5, 31, tzinfo=UTC)


def test_february_period_end_handles_leap_years() -> None:
    """Month-end is calendar-aware, not a fixed 28/30/31."""
    frame = eia_parser(
        [row(period="2024-02"), row(period="2025-02")],
        INDICATOR,
    )

    assert list(frame["timestamp"]) == [
        datetime(2024, 2, 29, tzinfo=UTC),
        datetime(2025, 2, 28, tzinfo=UTC),
    ]


def test_parser_sorts_ascending() -> None:
    """Rows arrive newest-first in practice; the frame is always ascending."""
    frame = eia_parser(
        [row(period="2026-03"), row(period="2024-01"), row(period="2025-07")],
        INDICATOR,
    )

    assert list(frame["timestamp"]) == sorted(frame["timestamp"])


def test_value_string_is_coerced_to_float() -> None:
    """EIA stringifies every value; the platform stores numbers."""
    frame = eia_parser([row(value="3430.5")], INDICATOR)

    assert frame.loc[0, "value"] == pytest.approx(3430.5)


def test_unit_falls_back_when_a_row_has_none() -> None:
    """A missing ``unitName`` uses the discovered unit rather than blanking it."""
    frame = eia_parser([row(unitName=None)], INDICATOR, unit="barrels")

    assert frame.loc[0, "unit"] == "barrels"


# --------------------------------------------------------------- missing values


@pytest.mark.parametrize("bad_value", [None, "", "   "])
def test_blank_and_null_values_become_nan(bad_value: Any) -> None:
    """Honest nulls are preserved for the Silver null counter, not invented."""
    frame = eia_parser([row(value=bad_value)], INDICATOR)

    assert pd.isna(frame.loc[0, "value"])


def test_non_numeric_value_is_a_parsing_error() -> None:
    """A bogus string is a defect in the source, not a silent null."""
    with pytest.raises(ParsingError, match="non-numeric"):
        eia_parser([row(value="not-a-number")], INDICATOR)


def test_invalid_period_is_a_parsing_error() -> None:
    """A period outside ``YYYY-MM`` cannot be placed on the timeline."""
    with pytest.raises(ParsingError):
        eia_parser([row(period="2026/05")], INDICATOR)


def test_out_of_range_month_is_a_parsing_error() -> None:
    """Month 13 is rejected by the shared period helper."""
    with pytest.raises(ParsingError):
        eia_parser([row(period="2026-13")], INDICATOR)


# ------------------------------------------------------------- observation flag


def test_data_flag_description_becomes_obs_status() -> None:
    """EIA's human-readable flag is what auditors need, not the raw id."""
    frame = eia_parser([row(dataFlagId="F", dataFlagDescription="Forecast value")], INDICATOR)

    assert frame.loc[0, "obs_status"] == "Forecast value"


def test_data_flag_id_is_the_fallback_status() -> None:
    """When no description exists, keep the raw flag id."""
    frame = eia_parser([row(dataFlagId="NA", dataFlagDescription=None)], INDICATOR)

    assert frame.loc[0, "obs_status"] == "NA"


def test_unflagged_observations_have_no_status() -> None:
    """An unflagged row must not invent an observation status."""
    frame = eia_parser([row()], INDICATOR)

    assert frame.loc[0, "obs_status"] is None


# ----------------------------------------------------------------- misc shapes


def test_now_is_ignored() -> None:
    """EIA publishes no projections, so a future period is still parsed."""
    frame = eia_parser([row(period="2027-01")], INDICATOR, now=datetime(2026, 9, 12, tzinfo=UTC))

    assert len(frame) == 1


def test_fixture_and_inline_rows_agree_on_indicator_id() -> None:
    """The parser stamps the requested indicator id, never the API's code."""
    frame = eia_parser(fixture_rows(), "EIA.IRN.CUSTOM")

    assert set(frame["indicator_id"]) == {"EIA.IRN.CUSTOM"}
