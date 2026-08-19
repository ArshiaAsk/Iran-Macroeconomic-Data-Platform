"""
Bronze layer writer: persist raw API and scraper payloads verbatim.

Bronze is immutable by contract (AGENTS.md): once written, a row is never
updated or deleted. Storing the untouched response means a parsing bug can be
fixed and the data re-derived without hitting the source again.

Envelope convention
-------------------
The World Bank Indicators API returns a two-element JSON *array*
``[metadata, rows]``, but ``bronze.bronze_raw.raw_data`` is JSONB typed as an
object. :func:`wrap_envelope` therefore stores it as
``{"meta": envelope[0], "rows": envelope[1]}`` -- lossless, and the shape every
downstream reader expects. Payloads that are already objects are stored as-is.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.database.schema import BronzeRaw, DataCollectionLog
from src.utils.exceptions import ParsingError
from src.utils.logging import get_logger, log_with_context

logger = get_logger(__name__)

META_KEY = "meta"
ROWS_KEY = "rows"

SOURCE_TYPE_API = "api"
SOURCE_TYPE_SCRAPER = "scraper"
SOURCE_TYPE_FILE = "file"

STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

# A World Bank envelope is exactly [meta, rows].
ENVELOPE_LENGTH = 2


def wrap_envelope(raw_envelope: Any) -> dict[str, Any]:
    """
    Normalise a source payload into the JSONB object shape Bronze stores.

    Args:
        raw_envelope: Parsed response -- a ``[meta, rows]`` list (World Bank
            style), or an object that is already keyed

    Returns:
        ``{"meta": ..., "rows": [...]}`` for list envelopes, the original
        mapping otherwise

    Raises:
        ParsingError: If the payload is neither a list nor a mapping
    """
    if isinstance(raw_envelope, dict):
        return raw_envelope

    if isinstance(raw_envelope, list):
        meta = raw_envelope[0] if raw_envelope else None
        rows = raw_envelope[1] if len(raw_envelope) >= ENVELOPE_LENGTH else None
        return {META_KEY: meta, ROWS_KEY: rows if rows is not None else []}

    msg = f"cannot store payload of type {type(raw_envelope).__name__} in Bronze"
    raise ParsingError(msg)


def extract_rows(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Read the observation rows back out of a stored Bronze payload.

    Args:
        raw_data: The ``raw_data`` value of a ``bronze.bronze_raw`` row

    Returns:
        List of observation objects (empty when the source returned no data)

    Raises:
        ParsingError: If ``rows`` is present but not a list of objects
    """
    rows = raw_data.get(ROWS_KEY)
    if rows is None:
        return []
    if not isinstance(rows, list):
        msg = f"Bronze payload 'rows' must be a list, got {type(rows).__name__}"
        raise ParsingError(msg)
    if not all(isinstance(row, dict) for row in rows):
        msg = "Bronze payload 'rows' must contain only objects"
        raise ParsingError(msg)
    return rows


def write_bronze(
    session: Session,
    source_name: str,
    source_type: str,
    raw_envelope: Any,
    request_url: str | None = None,
    http_status_code: int | None = None,
    record_metadata: dict[str, Any] | None = None,
    status: str = STATUS_SUCCESS,
    error_message: str | None = None,
    execution_time_seconds: float | None = None,
) -> UUID:
    """
    Store one raw payload in Bronze and log the collection in Metadata.

    ``collection_timestamp`` and ``created_at`` are left to their column
    defaults so the database, not the caller, stamps the write.

    Args:
        session: Active session; the caller owns the transaction
        source_name: Connector identity (world_bank, tgju, ...)
        source_type: One of api, scraper, file
        raw_envelope: Untouched parsed response
        request_url: Fully-resolved URL that produced the payload
        http_status_code: Status code of the response
        record_metadata: Extra provenance (indicator, pages fetched, ...)
        status: Collection outcome for the audit log
        error_message: Failure detail for the audit log
        execution_time_seconds: Wall-clock duration of the collection

    Returns:
        Primary key of the new Bronze row, usable as a Silver foreign key
    """
    raw_data = wrap_envelope(raw_envelope)
    row_count = len(extract_rows(raw_data))

    bronze_row = BronzeRaw(
        source_name=source_name,
        source_type=source_type,
        raw_data=raw_data,
        request_url=request_url,
        http_status_code=http_status_code,
        record_metadata=record_metadata,
    )
    session.add(bronze_row)
    # Flush (not commit) so the generated UUID is available to Silver while the
    # caller's transaction stays open.
    session.flush()

    session.add(
        DataCollectionLog(
            source_name=source_name,
            status=status,
            records_collected=row_count,
            error_message=error_message,
            execution_time_seconds=execution_time_seconds,
            record_metadata={
                **(record_metadata or {}),
                "bronze_id": str(bronze_row.id),
            },
        )
    )
    session.flush()

    log_with_context(
        logger,
        "INFO",
        "bronze payload stored",
        source_name=source_name,
        source_type=source_type,
        bronze_id=str(bronze_row.id),
        records_collected=row_count,
        http_status_code=http_status_code,
    )
    return bronze_row.id
