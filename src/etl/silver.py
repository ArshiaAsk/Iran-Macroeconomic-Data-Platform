"""
Bronze -> Silver transformation: parse, clean, validate, and persist.

Cleaning rules (AGENTS.md)
--------------------------
* **Nulls are never filled.** ``silver.silver_cleaned.value`` is NOT NULL, so a
  genuine gap cannot be stored as a row; the observation is skipped and counted
  in ``records_failed`` so the loss is auditable rather than invisible.
* **Duplicates are rejected**, not merged: one observation per
  ``(indicator_id, timestamp)``, enforced by ``uq_silver_indicator_timestamp``.
* **Outliers are flagged, never dropped.** Iranian series contain real 50%+
  inflation swings; discarding them would erase the phenomenon under study.

Idempotency: **upsert**
-----------------------
Re-running a collection must not duplicate observations. This module uses
PostgreSQL ``INSERT ... ON CONFLICT (indicator_id, timestamp) DO UPDATE`` against
``uq_silver_indicator_timestamp``. Upsert was chosen over check-then-skip because
a re-run then also *corrects* revised values -- the World Bank restates history
on every release -- while check-then-skip would leave stale numbers behind. The
Bronze lineage pointer is updated too, so a Silver row always names the payload
it currently reflects.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.connectors.world_bank import FREQUENCY_ANNUAL, SOURCE_NAME, rows_to_frame
from src.database.schema import BronzeRaw, SilverCleaned, utc_now
from src.etl.bronze import extract_rows
from src.etl.lineage import (
    LAYER_BRONZE,
    LAYER_SILVER,
    TransformResult,
    resolve_status,
    transformation,
)
from src.utils.exceptions import DataRetrievalError
from src.utils.logging import get_logger, log_with_context
from src.utils.validation import ValidationResult, detect_outliers_iqr, validate_data_quality

logger = get_logger(__name__)

TRANSFORMATION_TYPE = "cleaning"

VALIDATION_STATUS_VALID = "valid"
VALIDATION_STATUS_FLAGGED = "flagged"
OUTLIER_NOTE = "value outside 1.5x IQR bounds; retained and flagged for review"


@dataclass
class SilverPreparation:
    """Cleaned observations plus the counts that make the cleaning auditable."""

    frame: pd.DataFrame
    records_processed: int = 0
    null_records: int = 0
    duplicate_records: int = 0
    future_records: int = 0
    outlier_count: int = 0
    validation: ValidationResult | None = None

    @property
    def records_written(self) -> int:
        """Observations that will reach Silver."""
        return int(len(self.frame))

    @property
    def records_failed(self) -> int:
        """Observations that could not be represented in Silver."""
        return self.null_records + self.duplicate_records + self.future_records

    def counters(self) -> dict[str, Any]:
        """Counts and validation findings for the transformation log."""
        return {
            "records_processed": self.records_processed,
            "records_written": self.records_written,
            "nulls_skipped": self.null_records,
            "duplicates_rejected": self.duplicate_records,
            "future_periods_skipped": self.future_records,
            "outliers_flagged": self.outlier_count,
            "null_percentage": (
                round(self.validation.null_percentage, 4) if self.validation else None
            ),
            "validation_warnings": list(self.validation.warnings) if self.validation else [],
            "validation_errors": list(self.validation.errors) if self.validation else [],
        }


def prepare_silver_frame(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,
) -> SilverPreparation:
    """
    Clean raw Bronze observation rows into Silver-ready records.

    Pure function: no database access, no mutation of ``rows``.

    Args:
        rows: Observation objects from the stored Bronze payload
        indicator_id: Indicator being transformed
        unit: Resolved unit to stamp on each observation
        now: Clock override for the future-period cutoff

    Returns:
        The cleaned frame plus null, duplicate, and outlier counts
    """
    relevant = [row for row in rows if _row_indicator(row) in (None, indicator_id)]
    parsed = rows_to_frame(relevant, indicator_id, unit, now=now)

    processed = len(relevant)
    future_records = max(processed - int(len(parsed)), 0)

    if parsed.empty:
        return SilverPreparation(
            frame=parsed,
            records_processed=processed,
            future_records=future_records,
            validation=validate_data_quality(parsed),
        )

    # Validate before dropping nulls so null_percentage describes the source.
    validation = validate_data_quality(parsed)

    non_null = parsed.dropna(subset=["value"])
    null_records = int(len(parsed) - len(non_null))

    deduplicated = non_null.drop_duplicates(subset=["indicator_id", "timestamp"], keep="last")
    duplicate_records = int(len(non_null) - len(deduplicated))

    cleaned = deduplicated.reset_index(drop=True)
    outliers = detect_outliers_iqr(cleaned, "value")
    cleaned["is_outlier"] = outliers.to_numpy()
    cleaned["validation_status"] = cleaned["is_outlier"].map(
        {True: VALIDATION_STATUS_FLAGGED, False: VALIDATION_STATUS_VALID}
    )
    cleaned["validation_notes"] = cleaned["is_outlier"].map({True: OUTLIER_NOTE, False: None})

    return SilverPreparation(
        frame=cleaned,
        records_processed=processed,
        null_records=null_records,
        duplicate_records=duplicate_records,
        future_records=future_records,
        outlier_count=int(outliers.sum()),
        validation=validation,
    )


def _row_indicator(row: Mapping[str, Any]) -> str | None:
    """Extract the indicator code from a World Bank observation row."""
    indicator = row.get("indicator")
    if isinstance(indicator, Mapping):
        code = indicator.get("id")
        return str(code) if code else None
    return None


def _silver_records(
    preparation: SilverPreparation,
    indicator_id: str,
    source_name: str,
    bronze_id: UUID,
    frequency: str,
    unit: str | None,
) -> list[dict[str, Any]]:
    """Build fully-specified insert dicts (no reliance on column defaults)."""
    stamped = utc_now()
    records: list[dict[str, Any]] = []

    # ``to_dict("records")`` (rather than ``itertuples``) keeps the per-cell types
    # loose enough to coerce explicitly, which is what the columns require.
    for row in preparation.frame.to_dict("records"):
        obs_status = row.get("obs_status") or None
        records.append(
            {
                "id": uuid4(),
                "indicator_id": indicator_id,
                "timestamp": pd.Timestamp(row["timestamp"]).to_pydatetime(),
                "value": float(row["value"]),
                "unit": unit if unit is not None else row.get("unit"),
                "frequency": frequency,
                "source_name": source_name,
                "bronze_id": bronze_id,
                "validation_status": row["validation_status"],
                "validation_notes": row["validation_notes"],
                "is_outlier": bool(row["is_outlier"]),
                "record_metadata": {"obs_status": obs_status} if obs_status else None,
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
    return records


def write_silver(session: Session, records: Sequence[Mapping[str, Any]]) -> int:
    """
    Upsert Silver observations, keyed on ``uq_silver_indicator_timestamp``.

    Args:
        session: Active session; the caller owns the transaction
        records: Fully-specified row dicts from :func:`_silver_records`

    Returns:
        Number of rows submitted (inserted or refreshed)
    """
    if not records:
        return 0

    statement = pg_insert(SilverCleaned).values(list(records))
    statement = statement.on_conflict_do_update(
        constraint="uq_silver_indicator_timestamp",
        set_={
            "value": statement.excluded.value,
            "unit": statement.excluded.unit,
            "frequency": statement.excluded.frequency,
            "source_name": statement.excluded.source_name,
            "bronze_id": statement.excluded.bronze_id,
            "validation_status": statement.excluded.validation_status,
            "validation_notes": statement.excluded.validation_notes,
            "is_outlier": statement.excluded.is_outlier,
            # Both sides of this pair are SQL column names, not Python
            # attributes: the mapped attribute ``record_metadata`` is stored in
            # the column ``metadata``, and ``set_`` targets columns directly.
            "metadata": statement.excluded["metadata"],
            "updated_at": statement.excluded.updated_at,
        },
    )
    session.execute(statement)
    return len(records)


def bronze_to_silver(
    session: Session,
    bronze_id: UUID,
    indicator_id: str,
    source_name: str = SOURCE_NAME,
    frequency: str = FREQUENCY_ANNUAL,
    unit: str | None = None,
    now: datetime | None = None,
) -> TransformResult:
    """
    Transform one Bronze payload into cleaned Silver observations.

    Args:
        session: Active session; the caller owns the transaction
        bronze_id: Bronze row to read
        indicator_id: Indicator to extract from the payload
        source_name: Connector identity recorded on each Silver row
        frequency: Observation frequency
        unit: Resolved unit; falls back to the value parsed from the payload
        now: Clock override for the future-period cutoff

    Returns:
        Counts and status for the transformation

    Raises:
        DataRetrievalError: If the Bronze row does not exist
    """
    with transformation(
        session,
        source_layer=LAYER_BRONZE,
        target_layer=LAYER_SILVER,
        transformation_type=TRANSFORMATION_TYPE,
    ) as context:
        bronze_row = session.get(BronzeRaw, bronze_id)
        if bronze_row is None:
            msg = f"bronze row {bronze_id} not found"
            raise DataRetrievalError(msg)

        rows = extract_rows(bronze_row.raw_data)
        preparation = prepare_silver_frame(rows, indicator_id, unit, now=now)

        records = _silver_records(
            preparation,
            indicator_id=indicator_id,
            source_name=source_name,
            bronze_id=bronze_id,
            frequency=frequency,
            unit=unit,
        )
        written = write_silver(session, records)

        context.records_processed = preparation.records_processed
        context.records_failed = preparation.records_failed
        context.records_written = written
        context.record_metadata = {
            "indicator_id": indicator_id,
            "bronze_id": str(bronze_id),
            "idempotency": "upsert on uq_silver_indicator_timestamp",
            **preparation.counters(),
        }

    log_with_context(
        logger,
        "INFO",
        "bronze to silver complete",
        indicator_id=indicator_id,
        records_processed=preparation.records_processed,
        records_written=written,
        records_failed=preparation.records_failed,
        outliers_flagged=preparation.outlier_count,
    )

    return TransformResult(
        source_layer=LAYER_BRONZE,
        target_layer=LAYER_SILVER,
        records_processed=preparation.records_processed,
        records_failed=preparation.records_failed,
        records_written=written,
        status=resolve_status(written, preparation.records_failed),
        log_id=context.log_id,
        details=preparation.counters(),
    )


@dataclass
class SilverSeries:
    """A Silver series loaded for the Gold transformer."""

    indicator_id: str
    frame: pd.DataFrame
    unit: str | None = None
    frequency: str = FREQUENCY_ANNUAL
    silver_ids: dict[datetime, UUID] = field(default_factory=dict)


def load_silver_series(session: Session, indicator_id: str) -> SilverSeries:
    """
    Read one indicator's Silver history, ascending, with row ids for lineage.

    Args:
        session: Active session
        indicator_id: Indicator to load

    Returns:
        Frame with ``timestamp`` and ``value`` plus a timestamp -> Silver id map
    """
    rows = (
        session.query(SilverCleaned)
        .filter(SilverCleaned.indicator_id == indicator_id)
        .order_by(SilverCleaned.timestamp)
        .all()
    )

    frame = pd.DataFrame(
        {
            "timestamp": pd.Series([row.timestamp for row in rows], dtype="object"),
            "value": pd.Series([row.value for row in rows], dtype="float64"),
        }
    )
    if not frame.empty:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)

    return SilverSeries(
        indicator_id=indicator_id,
        frame=frame,
        unit=rows[0].unit if rows else None,
        frequency=rows[0].frequency if rows else FREQUENCY_ANNUAL,
        silver_ids={row.timestamp: row.id for row in rows},
    )
