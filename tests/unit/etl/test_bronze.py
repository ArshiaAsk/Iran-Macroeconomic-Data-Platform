"""
Unit tests for the Bronze layer writer.

The database is replaced by :class:`tests.conftest.FakeSession`, so these tests
prove the envelope wrapping and audit-logging contract without PostgreSQL. Real
persistence is covered by ``tests/integration/test_world_bank_pipeline.py``.
"""

from typing import Any
from uuid import UUID

import pytest

from src.database.schema import BronzeRaw, DataCollectionLog
from src.etl.bronze import (
    SOURCE_TYPE_API,
    STATUS_FAILED,
    extract_rows,
    wrap_envelope,
    write_bronze,
)
from src.utils.exceptions import ParsingError
from tests.conftest import FakeSession, load_world_bank_fixture

GDP = "NY.GDP.MKTP.CD"
EXPECTED_ANNUAL_ROWS = 66


def envelope() -> list[Any]:
    """A captured World Bank ``[meta, rows]`` response."""
    return load_world_bank_fixture(f"{GDP}_normal")


# --------------------------------------------------------------- wrap_envelope


def test_wrap_envelope_turns_the_list_into_an_object() -> None:
    """``raw_data`` is JSONB-as-object, but the API returns a JSON array."""
    wrapped = wrap_envelope([{"page": 1}, [{"date": "2020"}]])

    assert wrapped == {"meta": {"page": 1}, "rows": [{"date": "2020"}]}


def test_wrap_envelope_is_lossless_for_a_real_payload() -> None:
    """Nothing is dropped: Bronze must be able to re-derive Silver from this."""
    payload = envelope()

    wrapped = wrap_envelope(payload)

    assert wrapped["meta"] == payload[0]
    assert wrapped["rows"] == payload[1]
    assert len(wrapped["rows"]) == EXPECTED_ANNUAL_ROWS


def test_wrap_envelope_passes_a_mapping_through_untouched() -> None:
    """A source that already returns an object is stored as-is."""
    payload = {"data": [1, 2, 3]}

    assert wrap_envelope(payload) is payload


def test_wrap_envelope_handles_an_empty_list() -> None:
    """A zero-observation response is still storable."""
    assert wrap_envelope([]) == {"meta": None, "rows": []}


def test_wrap_envelope_handles_a_meta_only_list() -> None:
    """A truncated envelope yields an empty row list, not a KeyError."""
    assert wrap_envelope([{"page": 1}]) == {"meta": {"page": 1}, "rows": []}


@pytest.mark.parametrize("payload", ["a string", 42, None])
def test_wrap_envelope_rejects_unstorable_payloads(payload: Any) -> None:
    """Anything that is not a list or object cannot go into JSONB."""
    with pytest.raises(ParsingError, match="cannot store payload"):
        wrap_envelope(payload)


# ---------------------------------------------------------------- extract_rows


def test_extract_rows_reads_the_observations_back() -> None:
    """Silver reads its input through this function, so it must round-trip."""
    wrapped = wrap_envelope(envelope())

    assert len(extract_rows(wrapped)) == EXPECTED_ANNUAL_ROWS


def test_extract_rows_returns_empty_when_rows_are_absent() -> None:
    """A payload from another source shape yields no observations, not an error."""
    assert extract_rows({"meta": {}}) == []


def test_extract_rows_rejects_a_non_list_rows_value() -> None:
    """A corrupted payload must fail loudly rather than silently yield nothing."""
    with pytest.raises(ParsingError, match="must be a list"):
        extract_rows({"rows": {"not": "a list"}})


def test_extract_rows_rejects_non_object_rows() -> None:
    """Observations are objects; scalars cannot be parsed downstream."""
    with pytest.raises(ParsingError, match="only objects"):
        extract_rows({"rows": [{"date": "2020"}, "oops"]})


# ----------------------------------------------------------------- write_bronze


def test_write_bronze_returns_the_new_row_id(fake_session: FakeSession) -> None:
    """The returned UUID is what Silver stores as its lineage pointer."""
    bronze_id = write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=envelope(),
    )

    assert isinstance(bronze_id, UUID)
    assert fake_session.added_of(BronzeRaw)[0].id == bronze_id


def test_write_bronze_stores_the_wrapped_envelope(fake_session: FakeSession) -> None:
    """The stored payload keeps both halves of the API response."""
    write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=envelope(),
        request_url="https://api.worldbank.org/v2/country/IRN/indicator/NY.GDP.MKTP.CD",
        http_status_code=200,
        record_metadata={"indicator_id": GDP},
    )

    row = fake_session.added_of(BronzeRaw)[0]
    assert set(row.raw_data) == {"meta", "rows"}
    assert len(row.raw_data["rows"]) == EXPECTED_ANNUAL_ROWS
    assert row.http_status_code == 200
    assert row.record_metadata == {"indicator_id": GDP}
    assert row.source_type == SOURCE_TYPE_API


def test_write_bronze_leaves_timestamps_to_the_database(fake_session: FakeSession) -> None:
    """The database stamps the write, so the writer must not pre-fill them."""
    write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=envelope(),
    )

    row = fake_session.added_of(BronzeRaw)[0]
    assert row.collection_timestamp is None
    assert row.created_at is None


def test_write_bronze_writes_a_collection_log(fake_session: FakeSession) -> None:
    """Every collection is auditable, with the observation count recorded."""
    write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=envelope(),
        record_metadata={"indicator_id": GDP},
        execution_time_seconds=1.25,
    )

    log = fake_session.added_of(DataCollectionLog)[0]
    assert log.source_name == "world_bank"
    assert log.status == "success"
    assert log.records_collected == EXPECTED_ANNUAL_ROWS
    assert log.execution_time_seconds == 1.25
    # The log points back at the payload it describes.
    assert log.record_metadata["bronze_id"] == str(fake_session.added_of(BronzeRaw)[0].id)
    assert log.record_metadata["indicator_id"] == GDP


def test_write_bronze_records_a_failed_collection(fake_session: FakeSession) -> None:
    """A failed fetch still leaves an audit trail."""
    write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=[{"page": 1}, []],
        status=STATUS_FAILED,
        error_message="read timed out",
    )

    log = fake_session.added_of(DataCollectionLog)[0]
    assert log.status == STATUS_FAILED
    assert log.error_message == "read timed out"
    assert log.records_collected == 0


def test_write_bronze_flushes_so_the_id_is_available(fake_session: FakeSession) -> None:
    """Flush, never commit: the caller owns the transaction boundary."""
    write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=envelope(),
    )

    assert fake_session.flushes >= 1
    assert fake_session.committed == 0


def test_write_bronze_counts_zero_observations(fake_session: FakeSession) -> None:
    """An indicator with no data for Iran is a real, storable outcome."""
    write_bronze(
        fake_session,  # type: ignore[arg-type]
        source_name="world_bank",
        source_type=SOURCE_TYPE_API,
        raw_envelope=[{"page": 1, "total": 0}, []],
    )

    assert fake_session.added_of(DataCollectionLog)[0].records_collected == 0
    assert fake_session.added_of(BronzeRaw)[0].raw_data["rows"] == []
