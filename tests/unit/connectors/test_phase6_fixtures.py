"""
Fixture-contract tests for the Phase 6 TSETMC and HBSIR sources.

The captured fixtures are the offline stand-ins for each live source: every
connector/parser unit test replays them, so their shape is a contract, not an
implementation detail. These tests pin that shape (and the capture manifest
checksums) so a silent fixture edit fails loudly here instead of skewing a
parser assertion elsewhere.

No test imports ``finpy-tse``/``hbsir`` or touches the network.
"""

import hashlib
import json

import pytest

from tests.conftest import (
    HBSIR_FIXTURES,
    TSETMC_FIXTURES,
    load_hbsir_csv,
    load_hbsir_json,
    load_tsetmc_fixture,
)

TEDPIX_INS_CODE = 32097828799138957
RAW_FIRST_SESSION = 20081204
RAW_LAST_SESSION = 20260913
RAW_SESSION_COUNT = 4283


# ------------------------------------------------------------------ TSETMC


def test_sources_note_is_committed_for_both_sources() -> None:
    """Each fixture directory documents provenance for auditors."""
    for root in (TSETMC_FIXTURES, HBSIR_FIXTURES):
        note = root / "SOURCES.md"
        assert note.is_file(), f"missing provenance note: {note}"
        assert len(note.read_text(encoding="utf-8").strip()) > 0


def test_tedpix_raw_fixture_is_a_stable_capture() -> None:
    """The raw payload covers the full TEDPIX history with monotonic sessions."""
    payload = load_tsetmc_fixture("tedpix_cwi_raw")

    assert set(payload) == {"indexB2"}
    rows = payload["indexB2"]
    assert len(rows) == RAW_SESSION_COUNT
    assert rows[0]["dEven"] == RAW_FIRST_SESSION
    assert rows[-1]["dEven"] == RAW_LAST_SESSION

    dates = [row["dEven"] for row in rows]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)

    expected_fields = {
        "insCode",
        "dEven",
        "xNivInuClMresIbs",
        "xNivInuPbMresIbs",
        "xNivInuPhMresIbs",
    }
    for row in rows:
        assert set(row) == expected_fields
        assert row["insCode"] == TEDPIX_INS_CODE
        assert isinstance(row["dEven"], int)
        assert isinstance(row["xNivInuClMresIbs"], int | float)


def test_tedpix_window_fixture_matches_the_package_output_contract() -> None:
    """The finpy-tse window fixture is a two-week Jalali J-Date/Adj Close CSV."""
    import pandas as pd

    frame = pd.read_csv(TSETMC_FIXTURES / "tedpix_window_1404-06.csv")

    assert list(frame.columns) == ["J-Date", "Adj Close"]
    assert len(frame) == 9
    assert frame["J-Date"].iloc[0] == "1404-06-01"
    assert frame["J-Date"].iloc[-1] == "1404-06-15"
    assert pd.api.types.is_numeric_dtype(frame["Adj Close"])


def test_marketwatch_fixture_documents_the_deferred_indicators() -> None:
    """Value/EPS/Market Cap exist per-symbol, but there is no historical P/E."""
    payload = load_tsetmc_fixture("marketwatch_columns")

    columns = payload["columns"]
    assert {"Value", "Market Cap", "EPS"}.issubset(columns)
    assert not any("P/E" in column or column == "PE" for column in columns)


def test_capture_manifest_checksums_match_the_committed_files() -> None:
    """A fixture edit without a manifest refresh fails this integrity check."""
    manifest = json.loads((TSETMC_FIXTURES / "_capture.json").read_text(encoding="utf-8"))

    names = {entry["fixture"] for entry in manifest}
    assert names == {
        "tedpix_cwi_raw.json",
        "tedpix_window_1404-06.csv",
        "marketwatch_columns.json",
    }
    for entry in manifest:
        path = TSETMC_FIXTURES / entry["fixture"]
        assert path.stat().st_size == entry["byte_length"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], f"{entry['fixture']} checksum drifted"


# ------------------------------------------------------------------- HBSIR


def test_hbsir_sample_extract_has_the_merged_columns() -> None:
    """The committed 1400 sample carries income, expenditure, and weights."""
    frame = load_hbsir_csv("income_expenditure_weight_1400_sample")

    assert list(frame.columns) == [
        "Year",
        "ID",
        "Income",
        "Gross_Expenditure",
        "Net_Expenditure",
        "Weight",
    ]
    assert set(frame["Year"]) == {1400}
    assert frame["ID"].is_unique
    assert frame["Weight"].notna().all()
    assert (frame["Weight"] > 0).all()
    assert len(frame) == 200


def test_hbsir_metrics_trend_is_a_four_year_reference() -> None:
    """The reference trend carries one record per probed survey year."""
    trend = load_hbsir_json("metrics_trend")

    assert [entry["year"] for entry in trend] == [1390, 1395, 1400, 1403]
    for entry in trend:
        assert set(entry) == {
            "year",
            "gini",
            "poverty_rate_pct",
            "poverty_line_rial",
            "poverty_line_rule",
            "n_households",
            "weighted_households",
            "decile_shares_pct",
            "columns",
        }
        assert 0.0 < entry["gini"] < 1.0
        assert 0.0 <= entry["poverty_rate_pct"] <= 100.0
        assert entry["poverty_line_rial"] > 0
        assert entry["poverty_line_rule"] == "50% of weighted median household income"
        assert entry["weighted_households"] > 0
        shares = entry["decile_shares_pct"]
        assert set(shares) == {str(index) for index in range(1, 11)}
        assert sum(shares.values()) == pytest.approx(100.0, abs=0.01)
        # Decile shares are non-decreasing up to sampling noise.
        assert shares["10"] > shares["1"]


def test_hbsir_manifest_records_package_and_survey_coverage() -> None:
    """The manifest documents the capture: package, mirror, and year span."""
    manifest = load_hbsir_json("_manifest")

    assert "hbsir" in manifest["package"]
    assert "bssir" in manifest["package"]
    assert manifest["survey_years_available"].startswith("1369")
    assert manifest["mirror"]
    assert manifest["data_dir"]
