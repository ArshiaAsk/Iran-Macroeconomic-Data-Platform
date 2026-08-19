"""
Unit tests for transformation lineage logging.

The interesting behaviour is the failure path: a failed transformation rolls its
data changes back but must still leave an audit row behind, which means the row
has to be written through an *independent* session. That session is injected
here, so the split is verified without a database.
"""

from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from typing import Any
from uuid import UUID

import pytest

from src.database.schema import TransformationLog
from src.etl.lineage import (
    LAYER_BRONZE,
    LAYER_GOLD,
    LAYER_SILVER,
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SUCCESS,
    TransformationContext,
    record_transformation,
    resolve_status,
    transformation,
)
from tests.conftest import FakeSession

TRANSFORMATION_TYPE = "cleaning"


def factory_for(session: FakeSession) -> Any:
    """A failure-session factory that hands out ``session`` once."""

    @contextmanager
    def factory() -> Generator[Any, None, None]:
        yield session

    return factory


def only_log(session: FakeSession) -> TransformationLog:
    """The single transformation-log row staged on ``session``."""
    logs = session.added_of(TransformationLog)
    assert len(logs) == 1
    return logs[0]


def fail_inside(
    session: FakeSession,
    factory: Any,
    error: BaseException,
    source_layer: str = LAYER_BRONZE,
    target_layer: str = LAYER_SILVER,
    transformation_type: str = TRANSFORMATION_TYPE,
    **counters: Any,
) -> None:
    """
    Run a transformation that sets ``counters`` and then raises ``error``.

    Extracted so each failure test is a single statement inside
    ``pytest.raises``, which keeps the assertion scoped to the raise itself.
    """
    with transformation(
        session,  # type: ignore[arg-type]
        source_layer=source_layer,
        target_layer=target_layer,
        transformation_type=transformation_type,
        failure_session_factory=factory,
    ) as context:
        for name, value in counters.items():
            setattr(context, name, value)
        raise error


# --------------------------------------------------------------- resolve_status


def test_resolve_status_success_when_nothing_failed() -> None:
    """A clean run is a success even if it wrote nothing (an empty series)."""
    assert resolve_status(records_written=66, records_failed=0) == STATUS_SUCCESS
    assert resolve_status(records_written=0, records_failed=0) == STATUS_SUCCESS


def test_resolve_status_partial_when_some_rows_survived() -> None:
    """Sparse series lose their null observations but still land data."""
    assert resolve_status(records_written=34, records_failed=32) == STATUS_PARTIAL


def test_resolve_status_failed_when_nothing_was_written() -> None:
    """An all-null series produces no Silver rows at all."""
    assert resolve_status(records_written=0, records_failed=66) == STATUS_FAILED


def test_context_status_tracks_its_counters() -> None:
    """The context reports the status implied by whatever it holds right now."""
    context = TransformationContext()
    assert context.status == STATUS_SUCCESS

    context.records_written = 10
    context.records_failed = 2
    assert context.status == STATUS_PARTIAL


# --------------------------------------------------------- record_transformation


def test_record_transformation_stages_a_row(fake_session: FakeSession) -> None:
    """One log row per hop, flushed so its id can be returned."""
    log_id = record_transformation(
        fake_session,  # type: ignore[arg-type]
        source_layer=LAYER_BRONZE,
        target_layer=LAYER_SILVER,
        transformation_type=TRANSFORMATION_TYPE,
        records_processed=66,
        records_failed=0,
        record_metadata={"indicator_id": "NY.GDP.MKTP.CD"},
    )

    entry = only_log(fake_session)
    assert isinstance(log_id, UUID)
    assert entry.id == log_id
    assert entry.source_layer == LAYER_BRONZE
    assert entry.target_layer == LAYER_SILVER
    assert entry.transformation_type == TRANSFORMATION_TYPE
    assert entry.records_processed == 66
    assert entry.status == STATUS_SUCCESS
    assert entry.record_metadata == {"indicator_id": "NY.GDP.MKTP.CD"}


def test_record_transformation_does_not_commit(fake_session: FakeSession) -> None:
    """Success rows commit with the data they describe, not on their own."""
    record_transformation(
        fake_session,  # type: ignore[arg-type]
        source_layer=LAYER_SILVER,
        target_layer=LAYER_GOLD,
        transformation_type="chain_linking",
    )

    assert fake_session.flushes == 1
    assert fake_session.committed == 0


# ------------------------------------------------------ transformation: success


def test_transformation_records_success_in_the_callers_session(
    fake_session: FakeSession,
) -> None:
    """The audit row lands in the same transaction as the data."""
    with transformation(
        fake_session,  # type: ignore[arg-type]
        source_layer=LAYER_BRONZE,
        target_layer=LAYER_SILVER,
        transformation_type=TRANSFORMATION_TYPE,
    ) as context:
        context.records_processed = 66
        context.records_written = 66
        context.record_metadata = {"indicator_id": "SP.POP.TOTL"}

    entry = only_log(fake_session)
    assert entry.status == STATUS_SUCCESS
    assert entry.records_processed == 66
    assert entry.execution_time_seconds is not None
    assert entry.execution_time_seconds >= 0.0
    assert context.log_id == entry.id


def test_transformation_records_a_partial_run(fake_session: FakeSession) -> None:
    """A discontinued series writes some rows and skips the rest."""
    with transformation(
        fake_session,  # type: ignore[arg-type]
        source_layer=LAYER_BRONZE,
        target_layer=LAYER_SILVER,
        transformation_type=TRANSFORMATION_TYPE,
    ) as context:
        context.records_processed = 66
        context.records_written = 34
        context.records_failed = 32

    assert only_log(fake_session).status == STATUS_PARTIAL


def test_transformation_omits_empty_metadata(fake_session: FakeSession) -> None:
    """An empty dict would store ``{}``; NULL is the honest representation."""
    with transformation(
        fake_session,  # type: ignore[arg-type]
        source_layer=LAYER_BRONZE,
        target_layer=LAYER_SILVER,
        transformation_type=TRANSFORMATION_TYPE,
    ) as context:
        context.records_written = 1

    assert only_log(fake_session).record_metadata is None


# ------------------------------------------------------ transformation: failure


def test_transformation_reraises_the_original_error(fake_session: FakeSession) -> None:
    """Audit logging must never swallow the failure it is describing."""
    audit_session = FakeSession()

    with pytest.raises(ValueError, match="boom"):
        fail_inside(
            fake_session,
            factory_for(audit_session),
            ValueError("boom"),
            records_processed=66,
        )


def test_transformation_records_failure_out_of_band(fake_session: FakeSession) -> None:
    """The failure row goes to the independent session, not the rolled-back one."""
    audit_session = FakeSession()

    with pytest.raises(RuntimeError):
        fail_inside(
            fake_session,
            factory_for(audit_session),
            RuntimeError("junction ratio is undefined"),
            source_layer=LAYER_SILVER,
            target_layer=LAYER_GOLD,
            transformation_type="chain_linking",
            records_processed=12,
            records_failed=12,
            record_metadata={"indicator_id": "FP.CPI.TOTL.ZG"},
        )

    entry = only_log(audit_session)
    assert entry.status == STATUS_FAILED
    assert entry.error_message == "junction ratio is undefined"
    assert entry.records_processed == 12
    assert entry.record_metadata == {"indicator_id": "FP.CPI.TOTL.ZG"}
    # Nothing was written where the data changes are about to be rolled back.
    assert fake_session.added_of(TransformationLog) == []


def test_transformation_failure_uses_the_counters_it_had(fake_session: FakeSession) -> None:
    """A transformation that dies halfway still reports the real numbers."""
    audit_session = FakeSession()

    with pytest.raises(ZeroDivisionError):
        fail_inside(
            fake_session,
            factory_for(audit_session),
            ZeroDivisionError("division by zero"),
            records_processed=40,
            records_written=40,
        )

    entry = only_log(audit_session)
    # Status is forced to failed regardless of the counters.
    assert entry.status == STATUS_FAILED
    assert entry.records_processed == 40


def test_transformation_survives_a_broken_audit_session(fake_session: FakeSession) -> None:
    """If the audit write itself fails, the original error still surfaces."""

    def broken_factory() -> AbstractContextManager[Any]:
        msg = "database unavailable"
        raise ConnectionError(msg)

    with pytest.raises(ValueError, match="original failure"):
        fail_inside(fake_session, broken_factory, ValueError("original failure"))
