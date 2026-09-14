"""
Unit tests for the TSETMC ``indexB2`` parser.

The holiday-gap test reads the captured full payload
(``tests/fixtures/tsetmc/tedpix_cwi_raw.json``, 4,283 real sessions) and slices
a two-week window, so the "missing days stay missing" contract is checked
against the real exchange calendar rather than a synthetic one.
"""

from datetime import UTC, datetime

import pytest

from src.connectors.tsetmc_parser import (
    DEFAULT_UNIT,
    FRAME_COLUMNS,
    empty_frame,
    parse_session_date,
    tsetmc_parser,
)
from src.utils.exceptions import ParsingError
from tests.conftest import load_tsetmc_fixture

TEDPIX = "TSETMC.TEDPIX"

# Jalali 1404-06-01..1404-06-15 as Gregorian sessions. The exchange is closed
# Thu/Fri and on one holiday Monday, so six calendar days are absent.
WINDOW_START = 20250823
WINDOW_END = 20250906
EXPECTED_WINDOW = [
    ("2025-08-23", 2470967.7),
    ("2025-08-25", 2438038.8),
    ("2025-08-26", 2416298.1),
    ("2025-08-27", 2431039.4),
    ("2025-08-30", 2395694.7),
    ("2025-08-31", 2430150.3),
    ("2025-09-02", 2477159.1),
    ("2025-09-03", 2523539.2),
    ("2025-09-06", 2542851.1),
]
MISSING_WINDOW_DAYS = [
    "2025-08-24",  # Sunday
    "2025-08-28",  # Thursday
    "2025-08-29",  # Friday
    "2025-09-01",  # holiday Monday
    "2025-09-04",  # Thursday
    "2025-09-05",  # Friday
]


def window_rows() -> list[dict[str, object]]:
    """The captured TEDPIX payload sliced to the two-week Jalali window."""
    payload = load_tsetmc_fixture("tedpix_cwi_raw")
    return [row for row in payload["indexB2"] if WINDOW_START <= row["dEven"] <= WINDOW_END]


def make_row(day: int, close: float | None = 100.0) -> dict[str, object]:
    """One minimal ``indexB2`` record."""
    return {
        "insCode": 32097828799138957,
        "dEven": 20250100 + day,
        "xNivInuClMresIbs": close,
        "xNivInuPbMresIbs": close,
        "xNivInuPhMresIbs": close,
    }


def test_empty_rows_return_the_empty_frame_contract() -> None:
    """An empty payload yields an empty frame with the shared columns."""
    frame = tsetmc_parser([], TEDPIX)

    assert frame.empty
    assert tuple(frame.columns) == FRAME_COLUMNS
    assert tuple(empty_frame().columns) == FRAME_COLUMNS


def test_parses_sessions_sorted_with_utc_timestamps() -> None:
    """Rows parse into the Silver contract, ascending, stamped midnight UTC."""
    rows = [make_row(3, 300.0), make_row(1, 100.0), make_row(2, 200.0)]

    frame = tsetmc_parser(rows, TEDPIX, "index points")

    assert list(frame["value"]) == [100.0, 200.0, 300.0]
    assert list(frame["indicator_id"]) == [TEDPIX] * 3
    assert list(frame["unit"]) == ["index points"] * 3
    assert frame["timestamp"].dt.tz is not None
    assert frame["timestamp"].iloc[0].to_pydatetime() == datetime(2025, 1, 1, tzinfo=UTC)


def test_unit_falls_back_to_the_default() -> None:
    """A missing resolved unit uses the connector's index-points default."""
    frame = tsetmc_parser([make_row(1)], TEDPIX)

    assert frame["unit"].iloc[0] == DEFAULT_UNIT


def test_holiday_gaps_stay_absent_and_are_never_filled() -> None:
    """Missing sessions produce no row and no forward-filled value."""
    frame = tsetmc_parser(window_rows(), TEDPIX)

    observed = [ts.strftime("%Y-%m-%d") for ts in frame["timestamp"]]
    assert observed == [day for day, _ in EXPECTED_WINDOW]
    assert list(frame["value"]) == [value for _, value in EXPECTED_WINDOW]
    assert not set(MISSING_WINDOW_DAYS) & set(observed)
    assert len(frame) == 9


def test_window_values_match_the_package_output() -> None:
    """The raw-derived close matches ``finpy_tse``'s captured "Adj Close"."""
    frame = tsetmc_parser(window_rows(), TEDPIX)

    assert list(frame["value"]) == [value for _, value in EXPECTED_WINDOW]


def test_blank_level_is_preserved_as_null() -> None:
    """A blank level becomes None rather than being dropped by the parser."""
    frame = tsetmc_parser([make_row(1, None), make_row(2, ""), make_row(3, 200.0)], TEDPIX)

    assert frame["value"].isna().tolist() == [True, True, False]


def test_non_numeric_level_raises() -> None:
    """A genuinely non-numeric level is a parse failure, not silent loss."""
    with pytest.raises(ParsingError, match="non-numeric"):
        tsetmc_parser([make_row(1, "not-a-number")], TEDPIX)  # type: ignore[arg-type]


def test_invalid_session_date_raises() -> None:
    """A malformed ``dEven`` fails loudly."""
    with pytest.raises(ParsingError, match="eight-digit"):
        tsetmc_parser([{**make_row(1), "dEven": "2025-01"}], TEDPIX)


def test_future_session_is_dropped() -> None:
    """A session dated after ``now`` is dropped (no future rows emitted)."""
    now = datetime(2025, 1, 3, tzinfo=UTC)

    frame = tsetmc_parser(
        [make_row(1, 100.0), make_row(3, 300.0), make_row(4, 400.0)],
        TEDPIX,
        now=now,
    )

    assert list(frame["value"]) == [100.0, 300.0]


def test_parse_session_date_rejects_bad_values() -> None:
    """The date helper rejects non-numeric and impossible dates."""
    assert parse_session_date(20260913) == datetime(2026, 9, 13, tzinfo=UTC)
    with pytest.raises(ParsingError):
        parse_session_date("2026-09-13")
    with pytest.raises(ParsingError):
        parse_session_date(20261340)


def test_missing_session_date_raises() -> None:
    """A row without ``dEven`` is malformed, not silently dropped."""
    with pytest.raises(ParsingError, match="eight-digit"):
        tsetmc_parser([{"xNivInuClMresIbs": 100.0}], TEDPIX)


def test_missing_level_field_is_preserved_as_null() -> None:
    """A session with no close field keeps its row and a null value."""
    frame = tsetmc_parser([{"dEven": 20250101}], TEDPIX)

    assert len(frame) == 1
    assert frame["value"].isna().tolist() == [True]


def test_unknown_fields_are_ignored() -> None:
    """Extra cdn fields do not affect the normalized contract."""
    row = {**make_row(1, 100.0), "someNewField": "ignored", "another": 42}

    frame = tsetmc_parser([row], TEDPIX)

    assert list(frame.columns) == list(FRAME_COLUMNS)
    assert frame["value"].iloc[0] == 100.0


def test_all_blank_levels_stay_rows_with_nulls() -> None:
    """A payload of blanks yields null values rather than an empty frame."""
    frame = tsetmc_parser([make_row(1, None), make_row(2, "")], TEDPIX)

    assert len(frame) == 2
    assert frame["value"].isna().all()


def test_parse_session_date_accepts_a_numeric_string() -> None:
    """The cdn sometimes serializes ``dEven`` as a string."""
    assert parse_session_date("20260913") == datetime(2026, 9, 13, tzinfo=UTC)
