"""
Silver -> Gold transformation: chain-linked levels plus derived growth rates.

Gold is the analysis-ready layer: one continuous series per indicator with base-
year discontinuities removed, the pre-link value retained alongside, and
year-over-year growth published as its own namespaced series.

Provenance rules
----------------
* ``original_value`` is **always** populated, linked or not, so any published
  number can be traced back to what the source actually said.
* ``is_chain_linked`` is per row: true only for observations whose level was
  actually rescaled. Rows already on the current base are not marked.
* ``chain_linking_confidence`` stays NULL when no link was performed -- a
  fabricated 1.0 would make unlinked data look independently verified.
* Derived growth rows are namespaced ``WB.<indicator>.YOY`` so they can never
  collide with a source indicator code, and they carry a non-null ``silver_id``
  by attributing the rate to the **later** of the two periods it spans.

Idempotency: Gold is a **refresh**. ``gold.gold_analytical`` has a composite
``(id, timestamp)`` primary key with a generated ``id``, so there is no natural
conflict target to upsert against (and TimescaleDB requires ``timestamp`` in any
unique index). The transformer therefore deletes the indicator's existing rows
and its derived rows, then re-inserts. Note for operations: once the
``compress_after = 6 months`` policy has compressed old chunks, this delete
requires a TimescaleDB version that permits DML on compressed chunks (2.11+).
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from src.chain_linking.splice import (
    IS_LINKED_COLUMN,
    ORIGINAL_VALUE_COLUMN,
    SCALE_EPSILON,
    SCALE_FACTOR_COLUMN,
    TIMESTAMP_COLUMN,
    VALUE_COLUMN,
    ChainLinkResult,
    chain_link,
)
from src.database.schema import ChainLinkingLog, GoldAnalytical, IndicatorCatalog, utc_now
from src.etl.lineage import (
    LAYER_GOLD,
    LAYER_SILVER,
    STATUS_SUCCESS,
    TransformResult,
    resolve_status,
    transformation,
)
from src.etl.silver import SilverSeries, load_silver_series
from src.utils.logging import get_logger, log_with_context

logger = get_logger(__name__)

TRANSFORMATION_TYPE = "chain_linking"

DERIVED_PREFIX = "WB"
DERIVED_YOY_SUFFIX = "YOY"
DERIVED_YOY_UNIT = "annual %"
DERIVED_METHOD = "year_over_year_percent_change"

DEFAULT_DOMAIN = "unclassified"
PERCENT = 100.0


def derived_growth_indicator_id(indicator_id: str) -> str:
    """
    Namespaced id for an indicator's derived year-over-year growth series.

    Args:
        indicator_id: Source indicator code

    Returns:
        e.g. ``WB.NY.GDP.MKTP.KD.YOY``
    """
    return f"{DERIVED_PREFIX}.{indicator_id}.{DERIVED_YOY_SUFFIX}"


def _resolve_catalog_entry(session: Session, indicator_id: str) -> IndicatorCatalog | None:
    """Look up an indicator's catalog row, if it has been seeded."""
    return session.get(IndicatorCatalog, indicator_id)


def _resolve_domain(catalog: IndicatorCatalog | None, indicator_id: str, domain: str | None) -> str:
    """
    Decide which analytical domain a Gold row belongs to.

    Precedence: explicit argument, then the seeded catalog, then a clearly
    labelled fallback -- never a silent guess.
    """
    if domain:
        return domain
    if catalog is not None and catalog.domain:
        return catalog.domain

    log_with_context(
        logger,
        "WARNING",
        "no domain found for indicator; tagging as unclassified",
        indicator_id=indicator_id,
        fallback_domain=DEFAULT_DOMAIN,
    )
    return DEFAULT_DOMAIN


def _level_records(
    linked: pd.DataFrame,
    result: ChainLinkResult,
    series: SilverSeries,
    domain: str,
    stamped: datetime,
) -> list[dict[str, Any]]:
    """Build Gold rows for the chain-linked level series."""
    records: list[dict[str, Any]] = []

    for row in linked.itertuples(index=False):
        timestamp = pd.Timestamp(getattr(row, TIMESTAMP_COLUMN)).to_pydatetime()
        silver_id = series.silver_ids.get(timestamp)
        if silver_id is None:
            continue

        is_linked = bool(getattr(row, IS_LINKED_COLUMN))
        scale_factor = float(getattr(row, SCALE_FACTOR_COLUMN))

        records.append(
            {
                "id": uuid4(),
                "indicator_id": series.indicator_id,
                "timestamp": timestamp,
                "value": float(getattr(row, VALUE_COLUMN)),
                "original_value": float(getattr(row, ORIGINAL_VALUE_COLUMN)),
                "is_chain_linked": is_linked,
                "chain_linking_confidence": result.avg_confidence_score if is_linked else None,
                "unit": series.unit,
                "frequency": series.frequency,
                "domain": domain,
                "silver_id": silver_id,
                "record_metadata": (
                    {
                        "linking_method": result.linking_method,
                        "scale_factor": scale_factor,
                        "base_year_from": result.base_year_from,
                        "base_year_to": result.base_year_to,
                    }
                    if is_linked
                    else None
                ),
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
    return records


def _growth_records(
    linked: pd.DataFrame,
    result: ChainLinkResult,
    series: SilverSeries,
    domain: str,
    stamped: datetime,
) -> list[dict[str, Any]]:
    """
    Build derived year-over-year growth rows from the linked levels.

    ``original_value`` carries the growth rate implied by the *unlinked* values,
    which is why chain-linking matters: at a rebase junction the unlinked rate is
    meaningless, so it is left NULL there rather than published as a number.
    """
    derived_id = derived_growth_indicator_id(series.indicator_id)

    growth = linked[VALUE_COLUMN].pct_change(fill_method=None) * PERCENT
    original_growth = linked[ORIGINAL_VALUE_COLUMN].pct_change(fill_method=None) * PERCENT
    scale_changed = linked[SCALE_FACTOR_COLUMN].diff().abs() > SCALE_EPSILON

    records: list[dict[str, Any]] = []
    timestamps = linked[TIMESTAMP_COLUMN]

    for position in range(1, len(linked)):
        rate = growth.iloc[position]
        if not np.isfinite(rate):
            continue

        timestamp = pd.Timestamp(timestamps.iloc[position]).to_pydatetime()
        # Derived rates attribute to the later period's Silver row: it is the
        # observation that completes the comparison.
        silver_id = series.silver_ids.get(timestamp)
        if silver_id is None:
            continue

        previous = pd.Timestamp(timestamps.iloc[position - 1]).to_pydatetime()
        crossed_break = bool(scale_changed.iloc[position])
        raw_rate = original_growth.iloc[position]
        # A rate is chain-linked if either period it spans was rescaled. Scored
        # per row for the same reason levels are: a rate computed entirely on the
        # current base was never linked, so it carries no linking confidence.
        is_linked = bool(
            linked[IS_LINKED_COLUMN].iloc[position] or linked[IS_LINKED_COLUMN].iloc[position - 1]
        )

        records.append(
            {
                "id": uuid4(),
                "indicator_id": derived_id,
                "timestamp": timestamp,
                "value": float(rate),
                "original_value": (
                    None if crossed_break or not np.isfinite(raw_rate) else float(raw_rate)
                ),
                "is_chain_linked": is_linked,
                "chain_linking_confidence": result.avg_confidence_score if is_linked else None,
                "unit": DERIVED_YOY_UNIT,
                "frequency": series.frequency,
                "domain": domain,
                "silver_id": silver_id,
                "record_metadata": {
                    "derived_from": series.indicator_id,
                    "method": DERIVED_METHOD,
                    "from_period": previous.date().isoformat(),
                    "to_period": timestamp.date().isoformat(),
                    "spans_base_year_break": crossed_break,
                },
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
    return records


def _write_chain_linking_log(
    session: Session,
    indicator_id: str,
    result: ChainLinkResult,
) -> None:
    """Record a chain-linking audit row when a link was actually performed."""
    if not result.is_chain_linked:
        return
    if result.base_year_from is None or result.base_year_to is None:
        log_with_context(
            logger,
            "WARNING",
            "chain-link performed without identifiable base years; log row skipped",
            indicator_id=indicator_id,
            linking_method=result.linking_method,
        )
        return

    session.add(
        ChainLinkingLog(
            indicator_id=indicator_id,
            base_year_from=result.base_year_from,
            base_year_to=result.base_year_to,
            linking_method=result.linking_method or "unknown",
            records_linked=result.records_linked,
            avg_confidence_score=result.avg_confidence_score,
            overlap_period_months=result.overlap_period_months,
            growth_rate_variance=result.growth_rate_variance,
            status=STATUS_SUCCESS,
            record_metadata={
                "breaks": [
                    {
                        "timestamp": item.timestamp.date().isoformat(),
                        "base_year_from": item.base_year_from,
                        "base_year_to": item.base_year_to,
                        "detected_by": item.detected_by,
                        "level_ratio": item.level_ratio,
                    }
                    for item in result.breaks
                ]
            },
        )
    )
    session.flush()


def _replace_gold_rows(
    session: Session,
    indicator_ids: Sequence[str],
    records: Sequence[Mapping[str, Any]],
) -> int:
    """Delete the indicator's existing Gold rows and insert the new ones."""
    session.execute(delete(GoldAnalytical).where(GoldAnalytical.indicator_id.in_(indicator_ids)))
    if not records:
        return 0
    session.execute(insert(GoldAnalytical), list(records))
    return len(records)


def silver_to_gold(
    session: Session,
    indicator_id: str,
    domain: str | None = None,
    base_years: Sequence[int] | None = None,
    include_growth: bool = True,
    statistical_fallback: bool = False,
) -> TransformResult:
    """
    Chain-link one indicator's Silver history into Gold and derive growth rates.

    Args:
        session: Active session; the caller owns the transaction
        indicator_id: Indicator to transform
        domain: Analytical domain; resolved from the catalog when omitted
        base_years: Known base years; resolved from the catalog when omitted
        include_growth: Also publish the derived ``WB.<id>.YOY`` series
        statistical_fallback: Permit level-shift break detection without metadata

    Returns:
        Counts and status for the transformation

    Raises:
        ChainLinkingError: If linking would distort growth rates
    """
    with transformation(
        session,
        source_layer=LAYER_SILVER,
        target_layer=LAYER_GOLD,
        transformation_type=TRANSFORMATION_TYPE,
    ) as context:
        series = load_silver_series(session, indicator_id)
        catalog = _resolve_catalog_entry(session, indicator_id)
        resolved_domain = _resolve_domain(catalog, indicator_id, domain)
        resolved_base_years = base_years or (catalog.base_years if catalog else None)

        result = chain_link(
            series.frame,
            metadata={"base_years": resolved_base_years},
            frequency=series.frequency,
            statistical_fallback=statistical_fallback,
        )
        linked = result.frame
        stamped = utc_now()

        records = _level_records(linked, result, series, resolved_domain, stamped)
        growth_records = (
            _growth_records(linked, result, series, resolved_domain, stamped)
            if include_growth
            else []
        )

        targets = [indicator_id, derived_growth_indicator_id(indicator_id)]
        written = _replace_gold_rows(session, targets, [*records, *growth_records])
        _write_chain_linking_log(session, indicator_id, result)

        processed = int(len(series.frame))
        # Observations that reached Gold as levels; a missing Silver id is the
        # only way a row can be dropped here.
        failed = max(processed - len(records), 0)

        context.records_processed = processed
        context.records_failed = failed
        context.records_written = written
        context.record_metadata = {
            "indicator_id": indicator_id,
            "domain": resolved_domain,
            "level_rows": len(records),
            "growth_rows": len(growth_records),
            "is_chain_linked": result.is_chain_linked,
            "linking_method": result.linking_method,
            "records_linked": result.records_linked,
            "avg_confidence_score": result.avg_confidence_score,
            "base_year_from": result.base_year_from,
            "base_year_to": result.base_year_to,
            "idempotency": "delete-and-reinsert by indicator_id",
        }
        details = dict(context.record_metadata)

    log_with_context(
        logger,
        "INFO",
        "silver to gold complete",
        indicator_id=indicator_id,
        domain=resolved_domain,
        level_rows=len(records),
        growth_rows=len(growth_records),
        is_chain_linked=result.is_chain_linked,
    )

    return TransformResult(
        source_layer=LAYER_SILVER,
        target_layer=LAYER_GOLD,
        records_processed=processed,
        records_failed=failed,
        records_written=written,
        status=resolve_status(written, failed),
        log_id=context.log_id,
        details=details,
    )


def gold_indicator_ids(indicator_id: str) -> tuple[str, str]:
    """
    Every Gold indicator id derived from one source indicator.

    Args:
        indicator_id: Source indicator code

    Returns:
        Tuple of (level series id, derived growth series id)
    """
    return (indicator_id, derived_growth_indicator_id(indicator_id))


def load_gold_series(session: Session, indicator_id: str) -> pd.DataFrame:
    """
    Read one Gold series back, ascending -- used by tests and the dashboard.

    Args:
        session: Active session
        indicator_id: Gold indicator id (source or derived)

    Returns:
        Frame with timestamp, value, original_value, is_chain_linked, confidence
    """
    rows = (
        session.query(GoldAnalytical)
        .filter(GoldAnalytical.indicator_id == indicator_id)
        .order_by(GoldAnalytical.timestamp)
        .all()
    )
    return pd.DataFrame(
        [
            {
                "timestamp": row.timestamp,
                "value": row.value,
                "original_value": row.original_value,
                "is_chain_linked": row.is_chain_linked,
                "chain_linking_confidence": row.chain_linking_confidence,
                "unit": row.unit,
                "domain": row.domain,
            }
            for row in rows
        ]
    )
