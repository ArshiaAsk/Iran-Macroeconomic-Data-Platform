"""
Unit tests for the IMF DataMapper parsing helpers.

Served entirely from captured fixtures in ``tests/fixtures/imf`` -- no network.
The quirks under test (empty-string values key, no server-side filtering,
future-dated projections) were all observed live on 2026-09-12.
"""

from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from src.connectors.imf_parser import (
    OBSERVATION_ACTUAL,
    OBSERVATION_ESTIMATE,
    OBSERVATION_FORECAST,
    empty_frame,
    flatten_values,
    imf_parser,
    observation_type,
    parse_indicator_metadata,
    vintage_year,
)
from src.utils.exceptions import DataRetrievalError, ParsingError
from tests.conftest import load_imf_fixture


def rpch_values() -> dict[str, Any]:
    """The ``values`` map from the captured real GDP growth payload."""
    return load_imf_fixture("NGDP_RPCH_normal")["values"]


# ----------------------------------------------------------- metadata / vintage


def test_parse_indicator_metadata_returns_the_code_map() -> None:
    """Discovery is driven by the /indicators payload, not a hand-kept list."""
    metadata = parse_indicator_metadata(load_imf_fixture("indicators"))

    assert "NGDP_RPCH" in metadata
    assert metadata["NGDP_RPCH"]["unit"] == "Annual percent change"
    assert metadata["NGDP_RPCH"]["source"] == "World Economic Outlook (April 2026)"


def test_parse_indicator_metadata_tolerates_a_missing_key() -> None:
    """A malformed payload yields no metadata rather than raising."""
    assert parse_indicator_metadata({"api": {"version": "1"}}) == {}


def test_vintage_year_parses_the_weo_label() -> None:
    """The vintage is the only place the API exposes projection semantics."""
    assert vintage_year("World Economic Outlook (April 2026)") == 2026
    assert vintage_year("World Economic Outlook (October 2025)") == 2025


@pytest.mark.parametrize("source", [None, "", "World Economic Outlook", 2026])
def test_vintage_year_returns_none_when_unparseable(source: Any) -> None:
    """An unknown vintage must not be guessed at."""
    assert vintage_year(source) is None


def test_observation_type_classifies_against_the_vintage() -> None:
    """Project convention: history=actual, vintage year=estimate, later=forecast."""
    assert observation_type(2025, 2026) == OBSERVATION_ACTUAL
    assert observation_type(2026, 2026) == OBSERVATION_ESTIMATE
    assert observation_type(2027, 2026) == OBSERVATION_FORECAST


def test_observation_type_is_unknown_without_a_vintage() -> None:
    """No vintage means no label, not a fabricated one."""
    assert observation_type(2027, None) is None


# ------------------------------------------------------------------ flattening


def test_flatten_values_selects_iran_and_skips_the_empty_key() -> None:
    """The API's ``""`` key maps to null and must not become an observation."""
    rows = flatten_values(rpch_values(), "NGDP_RPCH", "IRN", vintage=2026)

    assert [row["period"] for row in rows] == [str(year) for year in range(2010, 2032)]
    assert all(row["observation_type"] != "" for row in rows)


def test_flatten_values_sorts_ascending() -> None:
    """API dict ordering is not guaranteed; the parser sorts by year."""
    rows = flatten_values(rpch_values(), "NGDP_RPCH", "IRN", vintage=2026)

    assert [int(row["period"]) for row in rows] == sorted(int(row["period"]) for row in rows)


def test_flatten_values_labels_the_forecast_horizon() -> None:
    """2026 is the vintage estimate; 2027-2031 are WEO projections."""
    rows = flatten_values(rpch_values(), "NGDP_RPCH", "IRN", vintage=2026)
    labels = {row["period"]: row["observation_type"] for row in rows}

    assert labels["2025"] == OBSERVATION_ACTUAL
    assert labels["2026"] == OBSERVATION_ESTIMATE
    assert labels["2031"] == OBSERVATION_FORECAST


def test_flatten_values_keeps_nulls_for_honest_counting() -> None:
    """A null observation is dropped by Silver, but counted, not hidden here."""
    values = {"CODE": {"IRN": {"2020": 1.0, "2021": None}}, "": None}

    rows = flatten_values(values, "CODE", "IRN", vintage=2026)

    assert rows[1]["value"] is None


def test_flatten_values_raises_for_a_missing_indicator() -> None:
    """An invalid code returns HTTP 200 without values; treat it as an error."""
    with pytest.raises(DataRetrievalError, match="no values"):
        flatten_values({"": None}, "NOTAREALCODE")


def test_flatten_values_raises_for_a_missing_country() -> None:
    """A country the indicator does not cover is a retrieval failure."""
    with pytest.raises(DataRetrievalError, match="no IRN series"):
        flatten_values({"CODE": {"USA": {"2020": 1.0}}}, "CODE", "IRN")


def test_flatten_values_skips_non_year_keys() -> None:
    """Defensive: only four-digit year keys become observations."""
    values = {"CODE": {"IRN": {"2020": 1.0, "latest": 2.0}}}

    rows = flatten_values(values, "CODE", "IRN", vintage=2026)

    assert [row["period"] for row in rows] == ["2020"]


# ---------------------------------------------------------------------- parser


def test_imf_parser_builds_the_silver_frame_contract() -> None:
    """Timestamps are period ends and every Silver column is present."""
    rows = flatten_values(rpch_values(), "NGDP_RPCH", "IRN", vintage=2026)

    frame = imf_parser(rows, "NGDP_RPCH", "Annual percent change")

    assert list(frame.columns) == [
        "timestamp",
        "value",
        "indicator_id",
        "unit",
        "obs_status",
        "observation_type",
    ]
    assert frame["timestamp"].iloc[0] == datetime(2010, 12, 31, tzinfo=UTC)
    assert frame["timestamp"].is_monotonic_increasing
    assert frame["value"].dtype == "float64"


def test_imf_parser_keeps_future_dated_forecasts() -> None:
    """The parser ignores ``now``: WEO projections are intentionally future-dated."""
    rows = flatten_values(rpch_values(), "NGDP_RPCH", "IRN", vintage=2026)

    frame = imf_parser(rows, "NGDP_RPCH", now=datetime(2020, 6, 30, tzinfo=UTC))

    assert frame["timestamp"].max() == datetime(2031, 12, 31, tzinfo=UTC)
    assert (frame["observation_type"] == OBSERVATION_FORECAST).sum() == 5


def test_imf_parser_stamps_the_unit() -> None:
    """The unit comes from /indicators and reaches every row."""
    rows = [{"period": "2020", "value": 1.0, "observation_type": OBSERVATION_ACTUAL}]

    frame = imf_parser(rows, "NGDPD", "Billions of U.S. dollars")

    assert frame["unit"].tolist() == ["Billions of U.S. dollars"]


def test_imf_parser_maps_nulls_to_not_a_number() -> None:
    """Silver's NOT NULL column is protected by dropna, so NaN must survive here."""
    rows = [{"period": "2020", "value": None, "observation_type": OBSERVATION_ACTUAL}]

    frame = imf_parser(rows, "NGDPD")

    assert pd.isna(frame["value"].iloc[0])


def test_imf_parser_rejects_a_non_numeric_value() -> None:
    """A string where a number belongs is a parsing defect, not a null."""
    rows = [{"period": "2020", "value": "not-a-number", "observation_type": OBSERVATION_ACTUAL}]

    with pytest.raises(ParsingError, match="non-numeric"):
        imf_parser(rows, "NGDPD")


def test_imf_parser_handles_no_rows() -> None:
    """An empty series keeps the column contract for downstream code."""
    frame = imf_parser([], "NGDPD")

    assert frame.empty
    assert list(frame.columns) == list(empty_frame().columns)
