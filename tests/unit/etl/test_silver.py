"""
Unit tests for the Bronze -> Silver transformation.

The cleaning rules are pure functions and are tested directly. Persistence is
exercised through :class:`tests.conftest.FakeSession`; the real upsert against
``uq_silver_indicator_timestamp`` is covered by the integration suite.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.database.schema import BronzeRaw, SilverCleaned, TransformationLog
from src.etl.bronze import wrap_envelope
from src.etl.lineage import LAYER_BRONZE, LAYER_SILVER, STATUS_PARTIAL, STATUS_SUCCESS
from src.etl.silver import (
    OUTLIER_NOTE,
    VALIDATION_STATUS_FLAGGED,
    VALIDATION_STATUS_VALID,
    _silver_records,
    bronze_to_silver,
    load_silver_series,
    prepare_silver_frame,
    write_silver,
)
from src.utils.exceptions import DataRetrievalError
from tests.conftest import FakeSession, compiled_sql, load_world_bank_fixture

GDP = "NY.GDP.MKTP.CD"
CPI = "FP.CPI.TOTL.ZG"
ENERGY = "EG.USE.PCAP.KG.OE"

EXPECTED_ANNUAL_ROWS = 66
ENERGY_NULLS = 32
BRONZE_ID = UUID("11111111-1111-1111-1111-111111111111")


def observation(year: str, value: float | None, indicator_id: str = GDP) -> dict[str, Any]:
    """One World Bank observation row, shaped as the API sends it."""
    return {
        "indicator": {"id": indicator_id, "value": indicator_id},
        "country": {"id": "IR", "value": "Iran, Islamic Rep."},
        "countryiso3code": "IRN",
        "date": year,
        "value": value,
        "unit": "",
        "obs_status": "",
        "decimal": 0,
    }


def fixture_rows(indicator_id: str) -> list[dict[str, Any]]:
    """The observation rows of a captured fixture."""
    return load_world_bank_fixture(f"{indicator_id}_normal")[1]


def seeded_bronze(session: FakeSession, indicator_id: str) -> None:
    """Put a Bronze row carrying ``indicator_id``'s fixture into the session."""
    row = BronzeRaw(
        source_name="world_bank",
        source_type="api",
        raw_data=wrap_envelope(load_world_bank_fixture(f"{indicator_id}_normal")),
    )
    row.id = BRONZE_ID
    session.seed(BronzeRaw, [row])


# ------------------------------------------------------- prepare_silver_frame


def test_prepare_keeps_every_usable_observation() -> None:
    """A complete series loses nothing during cleaning."""
    preparation = prepare_silver_frame(fixture_rows(GDP), GDP)

    assert preparation.records_processed == EXPECTED_ANNUAL_ROWS
    assert preparation.records_written == EXPECTED_ANNUAL_ROWS
    assert preparation.records_failed == 0
    assert preparation.frame["timestamp"].is_monotonic_increasing


def test_prepare_skips_nulls_and_counts_them() -> None:
    """``silver.value`` is NOT NULL, so a gap is dropped -- but never silently."""
    preparation = prepare_silver_frame(fixture_rows(ENERGY), ENERGY)

    assert preparation.null_records == ENERGY_NULLS
    assert preparation.records_written == EXPECTED_ANNUAL_ROWS - ENERGY_NULLS
    assert preparation.records_failed == ENERGY_NULLS
    assert preparation.frame["value"].notna().all()


def test_prepare_measures_nulls_against_the_source() -> None:
    """``null_percentage`` describes the payload, not the survivors."""
    preparation = prepare_silver_frame(fixture_rows(ENERGY), ENERGY)

    assert preparation.validation is not None
    assert preparation.validation.null_percentage == pytest.approx(
        ENERGY_NULLS / EXPECTED_ANNUAL_ROWS * 100
    )
    assert preparation.counters()["null_percentage"] > 0


def test_prepare_rejects_duplicate_periods() -> None:
    """One observation per (indicator, timestamp); the later value wins."""
    rows = [observation("2020", 1.0), observation("2020", 2.0), observation("2021", 3.0)]

    preparation = prepare_silver_frame(rows, GDP)

    assert preparation.duplicate_records == 1
    assert preparation.records_written == 2
    assert preparation.frame["value"].iloc[0] == 2.0


def test_prepare_flags_outliers_without_dropping_them() -> None:
    """Iran's 50%+ inflation swings are the phenomenon, not noise to discard."""
    rows = [observation(str(2000 + offset), 10.0) for offset in range(10)]
    rows.append(observation("2010", 900.0))

    preparation = prepare_silver_frame(rows, GDP)

    assert preparation.records_written == len(rows)
    assert preparation.outlier_count == 1
    flagged = preparation.frame[preparation.frame["is_outlier"]]
    assert flagged["value"].tolist() == [900.0]
    assert flagged["validation_status"].tolist() == [VALIDATION_STATUS_FLAGGED]
    assert flagged["validation_notes"].tolist() == [OUTLIER_NOTE]


def test_prepare_marks_ordinary_observations_valid() -> None:
    """A non-outlier carries no note, so reviewers only see real findings."""
    preparation = prepare_silver_frame([observation("2020", 1.0)], GDP)

    assert preparation.frame["validation_status"].iloc[0] == VALIDATION_STATUS_VALID
    assert preparation.frame["validation_notes"].iloc[0] is None
    assert bool(preparation.frame["is_outlier"].iloc[0]) is False


def test_prepare_counts_future_periods_as_failures() -> None:
    """A period that has not ended cannot be published; the loss is recorded."""
    rows = [observation("2020", 1.0), observation("2030", 2.0)]

    preparation = prepare_silver_frame(rows, GDP, now=datetime(2026, 6, 30, tzinfo=UTC))

    assert preparation.future_records == 1
    assert preparation.records_written == 1
    assert preparation.counters()["future_periods_skipped"] == 1


def test_prepare_ignores_rows_for_other_indicators() -> None:
    """One Bronze payload could carry several series; only ours is transformed."""
    rows = [observation("2020", 1.0), observation("2020", 99.0, indicator_id=CPI)]

    preparation = prepare_silver_frame(rows, GDP)

    assert preparation.records_written == 1
    assert preparation.frame["value"].iloc[0] == 1.0


def test_prepare_handles_an_all_null_series() -> None:
    """An indicator with no reported values yields nothing, and says so."""
    rows = [observation("2019", None), observation("2020", None)]

    preparation = prepare_silver_frame(rows, GDP)

    assert preparation.records_written == 0
    assert preparation.null_records == 2
    assert preparation.records_failed == 2


def test_prepare_handles_zero_observations() -> None:
    """An indicator the World Bank does not publish for Iran is not an error."""
    preparation = prepare_silver_frame([], GDP)

    assert preparation.records_processed == 0
    assert preparation.records_written == 0
    assert preparation.frame.empty
    assert preparation.counters()["records_written"] == 0


def test_counters_expose_every_cleaning_decision() -> None:
    """The transformation log has to explain each row that did not make it."""
    rows = [observation("2020", None), observation("2021", 1.0), observation("2021", 2.0)]

    counters = prepare_silver_frame(rows, GDP).counters()

    assert counters["records_processed"] == 3
    assert counters["records_written"] == 1
    assert counters["nulls_skipped"] == 1
    assert counters["duplicates_rejected"] == 1
    assert counters["outliers_flagged"] == 0
    assert isinstance(counters["validation_warnings"], list)


# ------------------------------------------------------------ _silver_records


def test_silver_records_carry_the_bronze_lineage_pointer() -> None:
    """Every Silver row names the payload it was derived from."""
    preparation = prepare_silver_frame(fixture_rows(GDP), GDP)

    records = _silver_records(
        preparation,
        indicator_id=GDP,
        source_name="world_bank",
        bronze_id=BRONZE_ID,
        frequency="annual",
        unit="current US$",
    )

    assert len(records) == EXPECTED_ANNUAL_ROWS
    assert {record["bronze_id"] for record in records} == {BRONZE_ID}
    assert {record["indicator_id"] for record in records} == {GDP}
    assert {record["unit"] for record in records} == {"current US$"}
    assert all(isinstance(record["id"], UUID) for record in records)


def test_silver_records_use_period_end_timestamps() -> None:
    """Annual observations are stamped at December 31, timezone-aware."""
    preparation = prepare_silver_frame([observation("2022", 5.0)], GDP)

    record = _silver_records(
        preparation,
        indicator_id=GDP,
        source_name="world_bank",
        bronze_id=BRONZE_ID,
        frequency="annual",
        unit=None,
    )[0]

    assert record["timestamp"] == datetime(2022, 12, 31, tzinfo=UTC)
    assert record["timestamp"].tzinfo is not None
    assert isinstance(record["value"], float)


def test_silver_records_keep_obs_status_as_provenance() -> None:
    """A provisional flag from the source is worth carrying; ``""`` is not."""
    rows = [observation("2020", 1.0), observation("2021", 2.0)]
    rows[0]["obs_status"] = "P"

    records = _silver_records(
        prepare_silver_frame(rows, GDP),
        indicator_id=GDP,
        source_name="world_bank",
        bronze_id=BRONZE_ID,
        frequency="annual",
        unit=None,
    )

    assert records[0]["record_metadata"] == {"obs_status": "P"}
    assert records[1]["record_metadata"] is None


def test_silver_records_fall_back_to_the_parsed_unit() -> None:
    """When discovery never ran, the unit parsed from the payload is used."""
    preparation = prepare_silver_frame([observation("2020", 1.0)], GDP, unit="current US$")

    record = _silver_records(
        preparation,
        indicator_id=GDP,
        source_name="world_bank",
        bronze_id=BRONZE_ID,
        frequency="annual",
        unit=None,
    )[0]

    assert record["unit"] == "current US$"


# --------------------------------------------------------------- write_silver


def test_write_silver_upserts_on_the_unique_constraint(fake_session: FakeSession) -> None:
    """Re-running a collection must correct revised values, not duplicate them."""
    preparation = prepare_silver_frame(fixture_rows(GDP), GDP)
    records = _silver_records(
        preparation,
        indicator_id=GDP,
        source_name="world_bank",
        bronze_id=BRONZE_ID,
        frequency="annual",
        unit="current US$",
    )

    written = write_silver(fake_session, records)  # type: ignore[arg-type]

    assert written == EXPECTED_ANNUAL_ROWS
    statement, _ = fake_session.executed[0]
    sql = compiled_sql(statement)
    assert "ON CONFLICT" in sql
    assert "uq_silver_indicator_timestamp" in sql
    assert "DO UPDATE" in sql


def test_write_silver_skips_an_empty_batch(fake_session: FakeSession) -> None:
    """An all-null series must not emit a statement with no values."""
    assert write_silver(fake_session, []) == 0  # type: ignore[arg-type]
    assert fake_session.executed == []


# ------------------------------------------------------------ bronze_to_silver


def test_bronze_to_silver_transforms_a_stored_payload(fake_session: FakeSession) -> None:
    """The full hop reads Bronze, writes Silver, and reports what it did."""
    seeded_bronze(fake_session, GDP)

    result = bronze_to_silver(
        fake_session,  # type: ignore[arg-type]
        bronze_id=BRONZE_ID,
        indicator_id=GDP,
        unit="current US$",
    )

    assert result.source_layer == LAYER_BRONZE
    assert result.target_layer == LAYER_SILVER
    assert result.records_processed == EXPECTED_ANNUAL_ROWS
    assert result.records_written == EXPECTED_ANNUAL_ROWS
    assert result.records_failed == 0
    assert result.status == STATUS_SUCCESS
    assert len(fake_session.inserted(SilverCleaned)) == 0  # values(), not executemany
    assert fake_session.executed


def test_bronze_to_silver_writes_a_transformation_log(fake_session: FakeSession) -> None:
    """Lineage: one audit row per hop, carrying the cleaning counters."""
    seeded_bronze(fake_session, ENERGY)

    result = bronze_to_silver(
        fake_session,  # type: ignore[arg-type]
        bronze_id=BRONZE_ID,
        indicator_id=ENERGY,
    )

    logs = fake_session.added_of(TransformationLog)
    assert len(logs) == 1
    assert logs[0].status == STATUS_PARTIAL
    assert logs[0].records_failed == ENERGY_NULLS
    assert logs[0].record_metadata["bronze_id"] == str(BRONZE_ID)
    assert logs[0].record_metadata["nulls_skipped"] == ENERGY_NULLS
    assert logs[0].record_metadata["idempotency"].startswith("upsert")
    assert result.log_id == logs[0].id


def test_bronze_to_silver_reports_partial_for_a_sparse_series(
    fake_session: FakeSession,
) -> None:
    """Iran's energy series stops in 2014: some rows land, the rest are counted."""
    seeded_bronze(fake_session, ENERGY)

    result = bronze_to_silver(
        fake_session,  # type: ignore[arg-type]
        bronze_id=BRONZE_ID,
        indicator_id=ENERGY,
    )

    assert result.status == STATUS_PARTIAL
    assert result.records_written == EXPECTED_ANNUAL_ROWS - ENERGY_NULLS
    assert result.details["nulls_skipped"] == ENERGY_NULLS


def test_bronze_to_silver_raises_when_the_payload_is_missing(
    fake_session: FakeSession,
) -> None:
    """A dangling lineage pointer is a bug, not something to paper over."""
    with pytest.raises(DataRetrievalError, match="not found"):
        bronze_to_silver(
            fake_session,  # type: ignore[arg-type]
            bronze_id=uuid4(),
            indicator_id=GDP,
        )


# -------------------------------------------------------- load_silver_series


def test_load_silver_series_returns_an_ascending_frame(fake_session: FakeSession) -> None:
    """Gold reads its input here, with a timestamp -> row id map for lineage."""
    rows = []
    for offset in range(3):
        row = SilverCleaned(
            indicator_id=GDP,
            timestamp=datetime(2020 + offset, 12, 31, tzinfo=UTC),
            value=100.0 + offset,
            unit="current US$",
            frequency="annual",
            source_name="world_bank",
            bronze_id=BRONZE_ID,
        )
        row.id = uuid4()
        rows.append(row)
    fake_session.seed(SilverCleaned, rows)

    series = load_silver_series(fake_session, GDP)  # type: ignore[arg-type]

    assert series.indicator_id == GDP
    assert list(series.frame["value"]) == [100.0, 101.0, 102.0]
    assert series.frame["timestamp"].is_monotonic_increasing
    assert series.unit == "current US$"
    assert series.frequency == "annual"
    assert series.silver_ids[datetime(2021, 12, 31, tzinfo=UTC)] == rows[1].id


def test_load_silver_series_handles_an_indicator_with_no_rows(
    fake_session: FakeSession,
) -> None:
    """An indicator that never reached Silver yields an empty, typed frame."""
    series = load_silver_series(fake_session, GDP)  # type: ignore[arg-type]

    assert series.frame.empty
    assert series.unit is None
    assert series.silver_ids == {}
