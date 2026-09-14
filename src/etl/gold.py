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

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

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
from src.database.schema import (
    ChainLinkingLog,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
    utc_now,
)
from src.etl.frequency import to_month_end
from src.etl.lineage import (
    LAYER_GOLD,
    LAYER_SILVER,
    STATUS_SUCCESS,
    TransformResult,
    resolve_status,
    transformation,
)
from src.etl.silver import SilverSeries, load_silver_series
from src.utils.exceptions import ChainLinkingError
from src.utils.logging import get_logger, log_with_context
from src.utils.periods import FREQUENCY_MONTHLY, year_earlier

logger = get_logger(__name__)

TRANSFORMATION_TYPE = "chain_linking"

DERIVED_PREFIX = "WB"
DERIVED_YOY_SUFFIX = "YOY"
DERIVED_YOY_UNIT = "annual %"
DERIVED_METHOD = "year_over_year_percent_change"

# Daily metrics constants
DERIVED_RET1D_SUFFIX = "RET1D"
DERIVED_RET1D_UNIT = "%"
DERIVED_RET1D_METHOD = "daily_return"

DERIVED_MA30_SUFFIX = "MA30"
DERIVED_MA30_METHOD = "30day_moving_average"
MA30_WINDOW = 30

# Month-end downsample of a daily series (opt-in via ``include_monthly``)
DERIVED_MONTH_END_SUFFIX = "ME"
DERIVED_MONTH_END_METHOD = "month_end_from_daily"

DEFAULT_DOMAIN = "unclassified"
PERCENT = 100.0

# Base-year segments carry their base year in the indicator id (e.g. ``…B2016``)
# when the Silver row metadata does not. The suffix is Gregorian.
_BASE_YEAR_ID_PATTERN = re.compile(r"\.B(\d{4})$")


def _namespaced(indicator_id: str, prefix: str, suffix: str) -> str:
    """
    Build a derived indicator id without double-prefixing a namespaced source.

    Source indicator ids from namespaced connectors already carry their source
    prefix (e.g. ``TGJU.USD.FREE``). Prepending the prefix again would produce
    ``TGJU.TGJU.USD.FREE.RET1D``, so ids that already start with the namespace
    are left untouched.

    Args:
        indicator_id: Source indicator code, namespaced or bare
        prefix: Source namespace (e.g. ``WB`` or ``TGJU``)
        suffix: Derived-series suffix (e.g. ``YOY`` or ``RET1D``)

    Returns:
        e.g. ``WB.NY.GDP.MKTP.KD.YOY`` or ``TGJU.USD.FREE.RET1D``
    """
    if indicator_id.startswith(f"{prefix}."):
        return f"{indicator_id}.{suffix}"
    return f"{prefix}.{indicator_id}.{suffix}"


def derived_growth_indicator_id(indicator_id: str, prefix: str = DERIVED_PREFIX) -> str:
    """
    Namespaced id for an indicator's derived year-over-year growth series.

    Args:
        indicator_id: Source indicator code
        prefix: Source namespace (default: WB)

    Returns:
        e.g. ``WB.NY.GDP.MKTP.KD.YOY`` or ``TGJU.USD.FREE.YOY``
    """
    return _namespaced(indicator_id, prefix, DERIVED_YOY_SUFFIX)


def derived_ret1d_indicator_id(indicator_id: str, prefix: str) -> str:
    """
    Namespaced id for an indicator's derived daily return series.

    Args:
        indicator_id: Source indicator code
        prefix: Source namespace (e.g., TGJU)

    Returns:
        e.g. ``TGJU.USD.FREE.RET1D``
    """
    return _namespaced(indicator_id, prefix, DERIVED_RET1D_SUFFIX)


def derived_ma30_indicator_id(indicator_id: str, prefix: str) -> str:
    """
    Namespaced id for an indicator's derived 30-day moving average series.

    Args:
        indicator_id: Source indicator code
        prefix: Source namespace (e.g., TGJU)

    Returns:
        e.g. ``TGJU.USD.FREE.MA30``
    """
    return _namespaced(indicator_id, prefix, DERIVED_MA30_SUFFIX)


def derived_month_end_indicator_id(indicator_id: str, prefix: str) -> str:
    """
    Namespaced id for a derived month-end downsample series.

    Args:
        indicator_id: Source indicator code
        prefix: Source namespace (e.g., TSETMC)

    Returns:
        e.g. ``TSETMC.TEDPIX.ME``
    """
    return _namespaced(indicator_id, prefix, DERIVED_MONTH_END_SUFFIX)


def _resolve_catalog_entry(session: Session, indicator_id: str) -> IndicatorCatalog | None:
    """Look up an indicator's catalog row, if it has been seeded."""
    catalog = session.get(IndicatorCatalog, indicator_id)
    if catalog is not None:
        return catalog

    # A few Session-compatible adapters do not implement primary-key lookup
    # consistently, while still supporting the normal query interface.
    matches = (
        session.query(IndicatorCatalog).filter(IndicatorCatalog.indicator_id == indicator_id).all()
    )
    return matches[0] if matches else None


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
    prefix: str = DERIVED_PREFIX,
) -> list[dict[str, Any]]:
    """
    Build derived year-over-year growth rows from the linked levels.

    ``original_value`` carries the growth rate implied by the *unlinked* values,
    which is why chain-linking matters: at a rebase junction the unlinked rate is
    meaningless, so it is left NULL there rather than published as a number.

    Args:
        linked: Chain-linked DataFrame
        result: Chain-linking result
        series: Silver series metadata
        domain: Analytical domain
        stamped: Creation timestamp
        prefix: Namespace prefix for derived indicator (default: WB)

    Returns:
        List of Gold records for derived growth series
    """
    derived_id = derived_growth_indicator_id(series.indicator_id, prefix=prefix)

    # Year-over-year means the *same period one year earlier*, never the
    # previous row: for monthly and quarterly series a positional lag would
    # silently publish MoM/QoQ as YoY. Look-ups are keyed by exact timestamp,
    # so a missing prior-year period yields no rate instead of a fabricated one.
    timestamps = linked[TIMESTAMP_COLUMN]
    values = {
        pd.Timestamp(ts): value for ts, value in zip(timestamps, linked[VALUE_COLUMN], strict=True)
    }
    original_values = {
        pd.Timestamp(ts): value
        for ts, value in zip(timestamps, linked[ORIGINAL_VALUE_COLUMN], strict=True)
    }
    scale_factors = {
        pd.Timestamp(ts): value
        for ts, value in zip(timestamps, linked[SCALE_FACTOR_COLUMN], strict=True)
    }
    linked_flags = {
        pd.Timestamp(ts): bool(value)
        for ts, value in zip(timestamps, linked[IS_LINKED_COLUMN], strict=True)
    }

    records: list[dict[str, Any]] = []

    for position in range(len(linked)):
        current_ts = pd.Timestamp(timestamps.iloc[position])
        prior_ts = pd.Timestamp(year_earlier(current_ts))
        current_value = values[current_ts]
        prior_value = values.get(prior_ts)
        if prior_value is None or not np.isfinite(current_value) or not np.isfinite(prior_value):
            continue

        rate = (current_value / prior_value - 1) * PERCENT
        if not np.isfinite(rate):
            continue

        timestamp = current_ts.to_pydatetime()
        # Derived rates attribute to the later period's Silver row: it is the
        # observation that completes the comparison.
        silver_id = series.silver_ids.get(timestamp)
        if silver_id is None:
            continue

        previous = prior_ts.to_pydatetime()
        current_scale = scale_factors.get(current_ts)
        prior_scale = scale_factors.get(prior_ts)
        crossed_break = bool(
            current_scale is not None
            and prior_scale is not None
            and abs(current_scale - prior_scale) > SCALE_EPSILON
        )

        current_original = original_values.get(current_ts)
        prior_original = original_values.get(prior_ts)
        raw_rate = np.nan
        if (
            current_original is not None
            and prior_original is not None
            and np.isfinite(current_original)
            and np.isfinite(prior_original)
            and prior_original != 0
        ):
            raw_rate = (current_original / prior_original - 1) * PERCENT

        # A rate is chain-linked if either period it spans was rescaled. Scored
        # per row for the same reason levels are: a rate computed entirely on the
        # current base was never linked, so it carries no linking confidence.
        is_linked = bool(linked_flags.get(current_ts, False) or linked_flags.get(prior_ts, False))

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


def _daily_return_records(
    linked: pd.DataFrame,
    series: SilverSeries,
    domain: str,
    stamped: datetime,
    prefix: str,
) -> list[dict[str, Any]]:
    """
    Build derived daily return (RET1D) rows from the linked levels.

    Daily returns are simple percentage changes: (value_t / value_t-1 - 1) × 100.
    Each return is attributed to the **current day's** Silver row.

    Args:
        linked: Chain-linked DataFrame
        series: Silver series metadata
        domain: Analytical domain
        stamped: Creation timestamp
        prefix: Namespace prefix for derived indicator (e.g., TGJU)

    Returns:
        List of Gold records for derived daily return series
    """
    derived_id = derived_ret1d_indicator_id(series.indicator_id, prefix=prefix)

    # Daily percent change
    returns = linked[VALUE_COLUMN].pct_change(fill_method=None) * PERCENT
    timestamps = linked[TIMESTAMP_COLUMN]

    records: list[dict[str, Any]] = []

    # Skip position 0 (first day has no return)
    for position in range(1, len(linked)):
        ret = returns.iloc[position]
        if not np.isfinite(ret):
            continue

        timestamp = pd.Timestamp(timestamps.iloc[position]).to_pydatetime()
        silver_id = series.silver_ids.get(timestamp)
        if silver_id is None:
            continue

        previous = pd.Timestamp(timestamps.iloc[position - 1]).to_pydatetime()

        records.append(
            {
                "id": uuid4(),
                "indicator_id": derived_id,
                "timestamp": timestamp,
                "value": float(ret),
                "original_value": float(ret),  # No chain-linking for daily data
                "is_chain_linked": False,
                "chain_linking_confidence": None,
                "unit": DERIVED_RET1D_UNIT,
                "frequency": series.frequency,
                "domain": domain,
                "silver_id": silver_id,
                "record_metadata": {
                    "derived_from": series.indicator_id,
                    "method": DERIVED_RET1D_METHOD,
                    "from_period": previous.date().isoformat(),
                    "to_period": timestamp.date().isoformat(),
                },
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
    return records


def _moving_average_records(
    linked: pd.DataFrame,
    series: SilverSeries,
    domain: str,
    stamped: datetime,
    prefix: str,
) -> list[dict[str, Any]]:
    """
    Build derived 30-day moving average (MA30) rows from the linked levels.

    The MA is computed on the linked values. Each MA is attributed to the
    **current day's** Silver row.

    Args:
        linked: Chain-linked DataFrame
        series: Silver series metadata
        domain: Analytical domain
        stamped: Creation timestamp
        prefix: Namespace prefix for derived indicator (e.g., TGJU)

    Returns:
        List of Gold records for derived moving average series
    """
    derived_id = derived_ma30_indicator_id(series.indicator_id, prefix=prefix)

    # 30-day rolling mean
    ma = linked[VALUE_COLUMN].rolling(window=MA30_WINDOW, min_periods=MA30_WINDOW).mean()
    timestamps = linked[TIMESTAMP_COLUMN]

    records: list[dict[str, Any]] = []

    # Skip first 29 days (MA undefined)
    for position in range(MA30_WINDOW - 1, len(linked)):
        ma_value = ma.iloc[position]
        if not np.isfinite(ma_value):
            continue

        timestamp = pd.Timestamp(timestamps.iloc[position]).to_pydatetime()
        silver_id = series.silver_ids.get(timestamp)
        if silver_id is None:
            continue

        records.append(
            {
                "id": uuid4(),
                "indicator_id": derived_id,
                "timestamp": timestamp,
                "value": float(ma_value),
                "original_value": float(ma_value),  # No chain-linking for daily data
                "is_chain_linked": False,
                "chain_linking_confidence": None,
                "unit": series.unit,  # Same unit as source
                "frequency": series.frequency,
                "domain": domain,
                "silver_id": silver_id,
                "record_metadata": {
                    "derived_from": series.indicator_id,
                    "method": DERIVED_MA30_METHOD,
                    "window_days": MA30_WINDOW,
                },
                "created_at": stamped,
                "updated_at": stamped,
            }
        )
    return records


def _month_end_silver_ids(
    linked: pd.DataFrame, series: SilverSeries
) -> dict[tuple[int, int], UUID]:
    """
    Map ``(year, month)`` to the Silver id of that month's last observation.

    :func:`to_month_end` returns only the retained value and the period-end
    timestamp, so this recovers the Silver lineage link for the observation the
    downsample actually selected.
    """
    selected: dict[tuple[int, int], tuple[datetime, UUID]] = {}
    for row in linked.itertuples(index=False):
        timestamp = pd.Timestamp(getattr(row, TIMESTAMP_COLUMN)).to_pydatetime()
        silver_id = series.silver_ids.get(timestamp)
        if silver_id is None:
            continue
        key = (timestamp.year, timestamp.month)
        current = selected.get(key)
        if current is None or timestamp > current[0]:
            selected[key] = (timestamp, silver_id)
    return {key: value[1] for key, value in selected.items()}


def _month_end_records(
    linked: pd.DataFrame,
    series: SilverSeries,
    domain: str,
    stamped: datetime,
    prefix: str,
) -> list[dict[str, Any]]:
    """
    Build derived month-end (``.ME``) rows from the linked daily levels.

    The **last observation of each calendar month** is republished at the
    month-end timestamp via :func:`src.etl.frequency.to_month_end`. Months with
    no observation yield no row and are never forward-filled. Each row keeps the
    Silver lineage of the month's last observation.

    Args:
        linked: Chain-linked daily DataFrame
        series: Silver series metadata
        domain: Analytical domain
        stamped: Creation timestamp
        prefix: Namespace prefix for the derived indicator (e.g., TSETMC)

    Returns:
        List of Gold records for the derived month-end series
    """
    derived_id = derived_month_end_indicator_id(series.indicator_id, prefix=prefix)

    monthly = to_month_end(linked.loc[:, [TIMESTAMP_COLUMN, VALUE_COLUMN]])
    if monthly.empty:
        return []

    silver_by_month = _month_end_silver_ids(linked, series)

    records: list[dict[str, Any]] = []
    for row in monthly.itertuples(index=False):
        timestamp = pd.Timestamp(getattr(row, TIMESTAMP_COLUMN)).to_pydatetime()
        silver_id = silver_by_month.get((timestamp.year, timestamp.month))
        if silver_id is None:
            continue
        value = float(getattr(row, VALUE_COLUMN))
        records.append(
            {
                "id": uuid4(),
                "indicator_id": derived_id,
                "timestamp": timestamp,
                "value": value,
                "original_value": value,  # Republished aggregate; no new splice
                "is_chain_linked": False,
                "chain_linking_confidence": None,
                "unit": series.unit,
                "frequency": FREQUENCY_MONTHLY,
                "domain": domain,
                "silver_id": silver_id,
                "record_metadata": {
                    "derived_from": series.indicator_id,
                    "method": DERIVED_MONTH_END_METHOD,
                    "derivation": DERIVED_MONTH_END_METHOD,
                    "source_frequency": series.frequency,
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


@dataclass
class BaseYearSegment:
    """One published base-year series loaded for multi-segment linking."""

    indicator_id: str
    series: SilverSeries
    base_year: int | None = None


def base_year_from_indicator_id(indicator_id: str) -> int | None:
    """
    Gregorian base year encoded in a segment indicator id, if present.

    Segment ids follow ``<canonical>.B<year>`` (e.g. ``SCI.CPI.URBAN.B2016``).

    Args:
        indicator_id: Segment indicator id

    Returns:
        The base year, or ``None`` when the id does not carry one
    """
    match = _BASE_YEAR_ID_PATTERN.search(indicator_id)
    return int(match.group(1)) if match else None


def _segment_base_year(session: Session, indicator_id: str) -> int | None:
    """Base year recorded on a segment's Silver rows, falling back to its id."""
    rows = session.query(SilverCleaned).filter(SilverCleaned.indicator_id == indicator_id).all()
    years: set[int] = set()
    for row in rows:
        metadata = row.record_metadata
        if isinstance(metadata, Mapping) and metadata.get("base_year") is not None:
            years.add(int(metadata["base_year"]))
    if len(years) == 1:
        return years.pop()
    return base_year_from_indicator_id(indicator_id)


def order_base_year_segments(segments: Sequence[BaseYearSegment]) -> list[BaseYearSegment]:
    """
    Order segments oldest base first (the order ``chain_link`` expects).

    Falls back to the supplied order -- and warns -- when any segment's base
    year is unknown, because guessing would splice the wrong direction.

    Args:
        segments: Loaded base-year segments

    Returns:
        Segments sorted ascending by base year, or the input order when unknown
    """
    if not segments:
        return []
    if any(segment.base_year is None for segment in segments):
        log_with_context(
            logger,
            "WARNING",
            "segment base year(s) unknown; keeping supplied segment order",
            segments=[segment.indicator_id for segment in segments],
        )
        return list(segments)
    return sorted(segments, key=lambda segment: int(segment.base_year or 0))


def load_base_year_segments(
    session: Session,
    segment_indicator_ids: Sequence[str],
) -> list[BaseYearSegment]:
    """
    Load each published base-year segment from Silver, oldest base first.

    Args:
        session: Active session; the caller owns the transaction
        segment_indicator_ids: Segment ids (e.g. ``SCI.CPI.URBAN.B2016``)

    Returns:
        Segments ordered oldest base first
    """
    segments = [
        BaseYearSegment(
            indicator_id=segment_id,
            series=load_silver_series(session, segment_id),
            base_year=_segment_base_year(session, segment_id),
        )
        for segment_id in segment_indicator_ids
    ]
    return order_base_year_segments(segments)


def _merge_segment_series(
    indicator_id: str,
    segments: Sequence[BaseYearSegment],
) -> SilverSeries:
    """Present the linked segments as one series under the canonical id."""
    newest = segments[-1].series
    silver_ids: dict[datetime, UUID] = {}
    for segment in segments:
        silver_ids.update(segment.series.silver_ids)
    return SilverSeries(
        indicator_id=indicator_id,
        frame=newest.frame,
        unit=newest.unit,
        frequency=newest.frequency,
        silver_ids=silver_ids,
    )


@dataclass
class _DerivedSeries:
    """Derived Gold rows and published ids for one source indicator."""

    records: list[dict[str, Any]] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    growth_rows: int = 0
    month_end_rows: int = 0


def _derive_gold_series(
    linked: pd.DataFrame,
    result: ChainLinkResult,
    series: SilverSeries,
    domain: str,
    stamped: datetime,
    derived_prefix: str,
    derivation_strategy: str,
    *,
    include_growth: bool,
    include_monthly: bool,
    indicator_id: str,
) -> _DerivedSeries:
    """Build every derived Gold row/id for one indicator from its linked levels."""
    derived = _DerivedSeries()

    if include_growth:
        if derivation_strategy == "yoy":
            # Year-over-year growth for annual/quarterly/monthly data
            derived.records = _growth_records(
                linked, result, series, domain, stamped, prefix=derived_prefix
            )
            derived.ids = [derived_growth_indicator_id(indicator_id, prefix=derived_prefix)]
            derived.growth_rows = len(derived.records)
        elif derivation_strategy == "daily":
            # Daily returns + 30-day MA for daily data
            ret_records = _daily_return_records(
                linked, series, domain, stamped, prefix=derived_prefix
            )
            ma_records = _moving_average_records(
                linked, series, domain, stamped, prefix=derived_prefix
            )
            derived.records = [*ret_records, *ma_records]
            derived.ids = [
                derived_ret1d_indicator_id(indicator_id, prefix=derived_prefix),
                derived_ma30_indicator_id(indicator_id, prefix=derived_prefix),
            ]
        else:
            log_with_context(
                logger,
                "WARNING",
                f"unknown derivation strategy '{derivation_strategy}'; no derived metrics",
                indicator_id=indicator_id,
            )

    if include_monthly:
        month_end_records = _month_end_records(
            linked, series, domain, stamped, prefix=derived_prefix
        )
        derived.month_end_rows = len(month_end_records)
        derived.records = [*derived.records, *month_end_records]
        # Track the id even when no month is selected so a refresh clears stale
        # .ME rows from a previous run.
        derived.ids.append(derived_month_end_indicator_id(indicator_id, prefix=derived_prefix))

    return derived


def silver_to_gold(
    session: Session,
    indicator_id: str,
    domain: str | None = None,
    base_years: Sequence[int] | None = None,
    include_growth: bool = True,
    statistical_fallback: bool = False,
    derived_prefix: str = DERIVED_PREFIX,
    derivation_strategy: str = "yoy",
    include_monthly: bool = False,
    segment_indicator_ids: Sequence[str] | None = None,
) -> TransformResult:
    """
    Chain-link one indicator's Silver history into Gold and derive growth rates.

    Args:
        session: Active session; the caller owns the transaction
        indicator_id: Indicator to transform
        domain: Analytical domain; resolved from the catalog when omitted
        base_years: Known base years; resolved from the catalog when omitted
        include_growth: Also publish derived series
        statistical_fallback: Permit level-shift break detection without metadata
        derived_prefix: Namespace prefix for derived indicators (default: WB)
        derivation_strategy: Strategy for derived metrics - "yoy" or "daily"
        include_monthly: Also publish a month-end downsample of the linked
            series as ``<derived_id>.ME`` (opt-in; intended for daily sources).
            Months with no observation produce no row. Defaults to ``False`` so
            existing sources are unaffected.
        segment_indicator_ids: Published base-year segments to link into
            ``indicator_id`` (oldest base first is derived, not assumed). When
            supplied, ``indicator_id`` names the canonical series and its own
            Silver rows are not read.

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
        segment_ids = list(segment_indicator_ids or [])
        catalog = _resolve_catalog_entry(session, indicator_id)
        resolved_domain = _resolve_domain(catalog, indicator_id, domain)
        resolved_base_years = base_years or (catalog.base_years if catalog else None)

        if segment_ids:
            segments = load_base_year_segments(session, segment_ids)
            empty = [segment.indicator_id for segment in segments if segment.series.frame.empty]
            if not segments:
                msg = f"no base-year segments loaded for {indicator_id}"
                raise ChainLinkingError(msg)
            if empty:
                msg = (
                    f"cannot chain-link {indicator_id}: no Silver observations for "
                    f"{', '.join(empty)}"
                )
                raise ChainLinkingError(msg)
            series = _merge_segment_series(indicator_id, segments)
            newest = segments[-1]
            result = chain_link(
                newest.series.frame,
                metadata={
                    "segments": [segment.series.frame for segment in segments],
                    "base_years": resolved_base_years,
                },
                frequency=newest.series.frequency,
                statistical_fallback=statistical_fallback,
            )
            processed = sum(len(segment.series.frame) for segment in segments)
        else:
            series = load_silver_series(session, indicator_id)
            result = chain_link(
                series.frame,
                metadata={"base_years": resolved_base_years},
                frequency=series.frequency,
                statistical_fallback=statistical_fallback,
            )
            processed = int(len(series.frame))

        linked = result.frame
        stamped = utc_now()

        records = _level_records(linked, result, series, resolved_domain, stamped)

        derived = _derive_gold_series(
            linked,
            result,
            series,
            resolved_domain,
            stamped,
            derived_prefix,
            derivation_strategy,
            include_growth=include_growth,
            include_monthly=include_monthly,
            indicator_id=indicator_id,
        )

        targets = [indicator_id, *derived.ids]
        written = _replace_gold_rows(session, targets, [*records, *derived.records])
        _write_chain_linking_log(session, indicator_id, result)

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
            "growth_rows": derived.growth_rows,
            "derived_rows": len(derived.records),
            "month_end_rows": derived.month_end_rows,
            "derivation_strategy": derivation_strategy if include_growth else None,
            "is_chain_linked": result.is_chain_linked,
            "segments": segment_ids,
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
        growth_rows=derived.growth_rows,
        derived_rows=len(derived.records),
        derivation_strategy=derivation_strategy if include_growth else None,
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


def gold_indicator_ids(
    indicator_id: str,
    strategy: str = "yoy",
    prefix: str = DERIVED_PREFIX,
    include_monthly: bool = False,
) -> tuple[str, ...]:
    """
    Every Gold indicator id derived from one source indicator.

    Args:
        indicator_id: Source indicator code
        strategy: Derivation strategy ("yoy" or "daily")
        prefix: Namespace prefix (default: WB)
        include_monthly: Also include the derived month-end (``.ME``) series id

    Returns:
        Tuple of (level series id, derived indicator id(s))
        - yoy: (indicator_id, <prefix>.<indicator>.YOY)
        - daily: (indicator_id, <prefix>.<indicator>.RET1D, <prefix>.<indicator>.MA30)
        - include_monthly appends <prefix>.<indicator>.ME
    """
    ids: tuple[str, ...]
    if strategy == "daily":
        ids = (
            indicator_id,
            derived_ret1d_indicator_id(indicator_id, prefix=prefix),
            derived_ma30_indicator_id(indicator_id, prefix=prefix),
        )
    else:
        # Default to yoy
        ids = (indicator_id, derived_growth_indicator_id(indicator_id, prefix=prefix))
    if include_monthly:
        return (*ids, derived_month_end_indicator_id(indicator_id, prefix=prefix))
    return ids


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
