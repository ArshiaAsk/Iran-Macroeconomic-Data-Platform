"""
Transformation lineage logging shared by every ETL hop.

Every Bronze -> Silver and Silver -> Gold run writes exactly one
``metadata.transformation_log`` row, successes and failures alike.

Failure transaction boundary
----------------------------
A failed transformation must roll its data changes back but must still leave an
audit row behind. Those two requirements cannot share a transaction, so
:func:`transformation` writes the failure row through an **independent** session
obtained from ``failure_session_factory`` (by default
``get_db().get_session``), which commits on its own. Success rows are written in
the caller's session so they commit atomically with the data they describe.
"""

import time
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.database.schema import TransformationLog
from src.utils.logging import get_logger, log_with_context

logger = get_logger(__name__)

STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

LAYER_BRONZE = "bronze"
LAYER_SILVER = "silver"
LAYER_GOLD = "gold"


def resolve_status(records_written: int, records_failed: int) -> str:
    """
    Derive a transformation status from row counts.

    Args:
        records_written: Rows successfully persisted
        records_failed: Rows that could not be persisted (nulls, duplicates)

    Returns:
        ``success`` when nothing failed, ``partial`` when some rows survived,
        ``failed`` when nothing was written
    """
    if records_failed == 0:
        return STATUS_SUCCESS
    if records_written > 0:
        return STATUS_PARTIAL
    return STATUS_FAILED


@dataclass
class TransformResult:
    """Outcome of one ETL hop, returned by the Silver and Gold transformers."""

    source_layer: str
    target_layer: str
    records_processed: int
    records_failed: int
    records_written: int
    status: str
    log_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformationContext:
    """
    Mutable counters a transformation fills in while it runs.

    :func:`transformation` reads these when the block exits to build the audit
    row, so a partially-completed transformation still reports real numbers.
    """

    records_processed: int = 0
    records_failed: int = 0
    records_written: int = 0
    record_metadata: dict[str, Any] = field(default_factory=dict)
    log_id: UUID | None = None

    @property
    def status(self) -> str:
        """Status implied by the current counters."""
        return resolve_status(self.records_written, self.records_failed)


def record_transformation(
    session: Session,
    source_layer: str,
    target_layer: str,
    transformation_type: str,
    records_processed: int = 0,
    records_failed: int = 0,
    status: str = STATUS_SUCCESS,
    error_message: str | None = None,
    execution_time_seconds: float | None = None,
    record_metadata: dict[str, Any] | None = None,
) -> UUID:
    """
    Write one ``TransformationLog`` row in the caller's session.

    The row is flushed but not committed -- the caller owns the transaction.

    Args:
        session: Active SQLAlchemy session
        source_layer: Layer the data came from (bronze, silver)
        target_layer: Layer the data landed in (silver, gold)
        transformation_type: What the transformation did (cleaning, chain_linking)
        records_processed: Rows read from the source layer
        records_failed: Rows rejected during the transformation
        status: One of success, partial, failed
        error_message: Failure detail, when applicable
        execution_time_seconds: Wall-clock duration
        record_metadata: Extra lineage detail stored as JSONB

    Returns:
        Primary key of the inserted log row
    """
    entry = TransformationLog(
        source_layer=source_layer,
        target_layer=target_layer,
        transformation_type=transformation_type,
        records_processed=records_processed,
        records_failed=records_failed,
        status=status,
        error_message=error_message,
        execution_time_seconds=execution_time_seconds,
        record_metadata=record_metadata,
    )
    session.add(entry)
    session.flush()

    log_with_context(
        logger,
        "INFO",
        "transformation recorded",
        source_layer=source_layer,
        target_layer=target_layer,
        transformation_type=transformation_type,
        status=status,
        records_processed=records_processed,
        records_failed=records_failed,
    )
    return entry.id


def _default_failure_session_factory() -> AbstractContextManager[Session]:
    """Open an independent session so failure audit rows survive a rollback."""
    from src.database.connection import get_db  # local import avoids a cycle

    return get_db().get_session()


def _record_failure_out_of_band(
    factory: Callable[[], AbstractContextManager[Session]],
    source_layer: str,
    target_layer: str,
    transformation_type: str,
    context: TransformationContext,
    error_message: str,
    execution_time_seconds: float,
) -> None:
    """
    Persist a failure audit row through its own committing session.

    A problem writing the audit row must never mask the original failure, so
    every error here is logged and swallowed.
    """
    try:
        with factory() as audit_session:
            record_transformation(
                audit_session,
                source_layer=source_layer,
                target_layer=target_layer,
                transformation_type=transformation_type,
                records_processed=context.records_processed,
                records_failed=context.records_failed,
                status=STATUS_FAILED,
                error_message=error_message,
                execution_time_seconds=execution_time_seconds,
                record_metadata=context.record_metadata or None,
            )
    except Exception as audit_exc:  # - never mask the original failure
        log_with_context(
            logger,
            "ERROR",
            "failed to record transformation failure",
            source_layer=source_layer,
            target_layer=target_layer,
            transformation_type=transformation_type,
            original_error=error_message,
            audit_error=str(audit_exc),
        )


@contextmanager
def transformation(
    session: Session,
    source_layer: str,
    target_layer: str,
    transformation_type: str,
    failure_session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
) -> Generator[TransformationContext, None, None]:
    """
    Time a transformation and record its audit row on both paths.

    On success the row is written in ``session``. On failure it is written
    through ``failure_session_factory`` (an independent, self-committing
    session) and the original exception is re-raised.

    Args:
        session: Session owning the data changes
        source_layer: Layer the data came from
        target_layer: Layer the data lands in
        transformation_type: What the transformation does
        failure_session_factory: Override for the out-of-band failure session

    Yields:
        Counters for the transformation to update as it progresses
    """
    context = TransformationContext()
    started = time.monotonic()

    try:
        yield context
    except Exception as exc:
        factory = failure_session_factory or _default_failure_session_factory
        _record_failure_out_of_band(
            factory,
            source_layer=source_layer,
            target_layer=target_layer,
            transformation_type=transformation_type,
            context=context,
            error_message=str(exc),
            execution_time_seconds=time.monotonic() - started,
        )
        raise

    context.log_id = record_transformation(
        session,
        source_layer=source_layer,
        target_layer=target_layer,
        transformation_type=transformation_type,
        records_processed=context.records_processed,
        records_failed=context.records_failed,
        status=context.status,
        execution_time_seconds=time.monotonic() - started,
        record_metadata=context.record_metadata or None,
    )
