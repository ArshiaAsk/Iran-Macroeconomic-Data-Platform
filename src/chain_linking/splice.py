"""
Base-year detection and chain-linking for macroeconomic series.

Iranian statistical agencies rebase index series every few years (1383, 1390,
1395, ...), which puts a level discontinuity in the middle of an otherwise
continuous history. Chain-linking removes the discontinuity while preserving the
period-to-period growth rates that carry the economic signal.

Everything here is a **pure function**: no database, no I/O, no globals. The
Gold transformer supplies frames and stores the results, which keeps the
algorithm testable in isolation and reusable by every future source.

Two linking methods
-------------------
``overlap``
    The rigorous method. Two series published on different bases report the same
    periods for a while; the scale factor is the mean ratio across that overlap.
    Requires at least :data:`MIN_OVERLAP_PERIODS_BY_FREQUENCY` shared periods.

``level_shift``
    Fallback when a *single* series contains a rebase and no overlap exists: the
    scale factor comes from the one junction observation. Growth within each
    segment is still preserved exactly, but the join is an assumption rather
    than a measurement, so confidence is capped low by design.

Invariant enforced on every link (AGENTS.md): within-segment growth rates must
be preserved to within :data:`GROWTH_TOLERANCE`, or :class:`ChainLinkingError`
is raised rather than silently emitting a distorted series.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd

from src.utils.exceptions import ChainLinkingError
from src.utils.logging import get_logger, log_with_context

logger = get_logger(__name__)

TIMESTAMP_COLUMN = "timestamp"
VALUE_COLUMN = "value"
ORIGINAL_VALUE_COLUMN = "original_value"
IS_LINKED_COLUMN = "is_linked"
SCALE_FACTOR_COLUMN = "scale_factor"

LINKING_METHOD_OVERLAP = "overlap"
LINKING_METHOD_LEVEL_SHIFT = "level_shift"

DETECTED_BY_METADATA = "metadata"
DETECTED_BY_LEVEL_SHIFT = "level_shift"

# AGENTS.md requires >=12 months of overlap; expressed per frequency.
MIN_OVERLAP_PERIODS_BY_FREQUENCY: Mapping[str, int] = {
    "annual": 3,
    "quarterly": 6,
    "monthly": 12,
    "daily": 12,
}
DEFAULT_MIN_OVERLAP_PERIODS = 3

MONTHS_PER_PERIOD: Mapping[str, int] = {
    "annual": 12,
    "quarterly": 3,
    "monthly": 1,
    "daily": 1,
}
DEFAULT_MONTHS_PER_PERIOD = 12

# Growth rates must survive linking to within +/-1%.
GROWTH_TOLERANCE = 0.01

# Confidence shaping: 36 months of overlap earns full marks, and even a
# zero-overlap level_shift link keeps a small floor so it is not reported as
# absolute nonsense -- it is a real, if weak, estimate.
CONFIDENCE_FULL_OVERLAP_MONTHS = 36.0
CONFIDENCE_OVERLAP_FLOOR = 0.2
CONFIDENCE_VARIANCE_WEIGHT = 50.0

# Statistical detection thresholds (only used when explicitly enabled).
DEFAULT_LEVEL_SHIFT_THRESHOLD = 0.20
DEFAULT_JUMP_MULTIPLE = 4.0

SCALE_EPSILON = 1e-12
MIN_ROWS_FOR_DETECTION = 4


@dataclass(frozen=True)
class BaseYearBreak:
    """One detected base-year change."""

    timestamp: datetime
    base_year_from: int
    base_year_to: int
    detected_by: str
    level_ratio: float | None = None


@dataclass
class ChainLinkResult:
    """Outcome of chain-linking one series, shaped for ``ChainLinkingLog``."""

    frame: pd.DataFrame
    is_chain_linked: bool
    breaks: list[BaseYearBreak] = field(default_factory=list)
    linking_method: str | None = None
    records_linked: int = 0
    avg_confidence_score: float | None = None
    overlap_period_months: int | None = None
    growth_rate_variance: float | None = None
    base_year_from: int | None = None
    base_year_to: int | None = None


def min_overlap_periods(frequency: str) -> int:
    """Minimum overlapping observations required to splice at ``frequency``."""
    return MIN_OVERLAP_PERIODS_BY_FREQUENCY.get(frequency, DEFAULT_MIN_OVERLAP_PERIODS)


def months_per_period(frequency: str) -> int:
    """Months spanned by one observation at ``frequency``."""
    return MONTHS_PER_PERIOD.get(frequency, DEFAULT_MONTHS_PER_PERIOD)


def normalise_series(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Sort, de-null, and reset a series so the algorithms can assume a clean input.

    Args:
        frame: Frame with ``timestamp`` and ``value`` columns

    Returns:
        A copy sorted ascending with null values removed

    Raises:
        ChainLinkingError: If the required columns are missing
    """
    missing = {TIMESTAMP_COLUMN, VALUE_COLUMN} - set(frame.columns)
    if missing:
        msg = f"series is missing required column(s): {sorted(missing)}"
        raise ChainLinkingError(msg)

    cleaned = frame.dropna(subset=[VALUE_COLUMN]).copy()
    cleaned = cleaned.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    cleaned[VALUE_COLUMN] = cleaned[VALUE_COLUMN].astype("float64")
    return cleaned


def calculate_confidence(overlap_months: float, growth_variance: float | None) -> float:
    """
    Score how trustworthy a chain-link is.

    Confidence rises with the length of the overlap used to estimate the scale
    factor and falls as the growth rates of the two segments disagree.

    Args:
        overlap_months: Months of overlap backing the scale factor
        growth_variance: Variance of the per-period ratio estimates, if known

    Returns:
        Score in ``[0, 1]``, rounded to 4 decimals
    """
    overlap_fraction = min(max(overlap_months, 0.0) / CONFIDENCE_FULL_OVERLAP_MONTHS, 1.0)
    overlap_score = CONFIDENCE_OVERLAP_FLOOR + (1.0 - CONFIDENCE_OVERLAP_FLOOR) * overlap_fraction

    variance = max(growth_variance or 0.0, 0.0)
    variance_score = 1.0 / (1.0 + CONFIDENCE_VARIANCE_WEIGHT * variance)

    return round(min(max(overlap_score * variance_score, 0.0), 1.0), 4)


def detect_base_year_breaks(
    frame: pd.DataFrame,
    base_years: Sequence[int] | None = None,
    statistical_fallback: bool = False,
    level_shift_threshold: float = DEFAULT_LEVEL_SHIFT_THRESHOLD,
    jump_multiple: float = DEFAULT_JUMP_MULTIPLE,
) -> list[BaseYearBreak]:
    """
    Locate base-year changes in a single series.

    Catalog metadata is authoritative: when ``base_years`` is supplied, each
    entry marks the first period expressed on that base. Statistical detection
    is available but **off by default** -- a level jump alone cannot distinguish
    a rebase from a genuine economic shock (Iranian series have plenty of the
    latter), so guessing would corrupt real data.

    Args:
        frame: Series with ``timestamp`` and ``value``, ascending
        base_years: Known base years from the indicator catalog
        statistical_fallback: Enable level-shift detection when metadata is absent
        level_shift_threshold: Minimum absolute period-on-period change to consider
        jump_multiple: How many times the typical absolute growth the jump must exceed

    Returns:
        Detected breaks, ordered oldest first
    """
    series = normalise_series(frame)
    if len(series) < 2:
        return []

    if base_years:
        return _breaks_from_metadata(series, base_years)
    if not statistical_fallback:
        return []
    return _breaks_from_level_shifts(series, level_shift_threshold, jump_multiple)


def _breaks_from_metadata(series: pd.DataFrame, base_years: Sequence[int]) -> list[BaseYearBreak]:
    """Turn catalog base years into breaks anchored on real observations."""
    ordered = sorted({int(year) for year in base_years})
    years = series[TIMESTAMP_COLUMN].dt.year.to_numpy()
    values = series[VALUE_COLUMN].to_numpy()

    breaks: list[BaseYearBreak] = []
    for previous_base, next_base in pairwise(ordered):
        positions = np.nonzero(years >= next_base)[0]
        if positions.size == 0 or positions[0] == 0:
            continue
        index = int(positions[0])
        breaks.append(
            BaseYearBreak(
                timestamp=series[TIMESTAMP_COLUMN].iloc[index].to_pydatetime(),
                base_year_from=previous_base,
                base_year_to=next_base,
                detected_by=DETECTED_BY_METADATA,
                level_ratio=_safe_ratio(values[index], values[index - 1]),
            )
        )
    return breaks


def _breaks_from_level_shifts(
    series: pd.DataFrame,
    level_shift_threshold: float,
    jump_multiple: float,
) -> list[BaseYearBreak]:
    """Flag isolated level jumps that dwarf the series' typical movement."""
    if len(series) < MIN_ROWS_FOR_DETECTION:
        return []

    growth = series[VALUE_COLUMN].pct_change(fill_method=None)
    magnitude = growth.abs()
    typical = float(magnitude.median(skipna=True))
    if not np.isfinite(typical):
        return []

    values = series[VALUE_COLUMN].to_numpy()
    timestamps = series[TIMESTAMP_COLUMN]

    breaks: list[BaseYearBreak] = []
    for index in range(1, len(series)):
        change = magnitude.iloc[index]
        if not np.isfinite(change) or change < level_shift_threshold:
            continue
        if typical > 0 and change < jump_multiple * typical:
            continue
        breaks.append(
            BaseYearBreak(
                timestamp=timestamps.iloc[index].to_pydatetime(),
                base_year_from=int(timestamps.iloc[index - 1].year),
                base_year_to=int(timestamps.iloc[index].year),
                detected_by=DETECTED_BY_LEVEL_SHIFT,
                level_ratio=_safe_ratio(values[index], values[index - 1]),
            )
        )
    return breaks


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    """Ratio guarded against division by zero and sign flips."""
    if denominator == 0 or not np.isfinite(denominator) or not np.isfinite(numerator):
        return None
    ratio = float(numerator) / float(denominator)
    if ratio <= 0:
        return None
    return ratio


def _prepare_for_linking(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the linking bookkeeping columns if they are not present yet."""
    prepared = normalise_series(frame)
    if ORIGINAL_VALUE_COLUMN not in prepared.columns:
        prepared[ORIGINAL_VALUE_COLUMN] = prepared[VALUE_COLUMN]
    if SCALE_FACTOR_COLUMN not in prepared.columns:
        prepared[SCALE_FACTOR_COLUMN] = 1.0
    if IS_LINKED_COLUMN not in prepared.columns:
        prepared[IS_LINKED_COLUMN] = False
    return prepared


@dataclass
class _SpliceOutcome:
    """Internal result of splicing exactly two segments."""

    frame: pd.DataFrame
    scale_factor: float
    overlap_periods: int
    ratio_variance: float
    base_year_from: int
    base_year_to: int


def _splice_once(
    old: pd.DataFrame,
    new: pd.DataFrame,
    overlap: int | None,
    frequency: str,
) -> _SpliceOutcome:
    """
    Rescale ``old`` onto ``new``'s base using their overlapping periods.

    Raises:
        ChainLinkingError: If the overlap is too short or unusable
    """
    old_prepared = _prepare_for_linking(old)
    new_prepared = _prepare_for_linking(new)

    required = min_overlap_periods(frequency)
    shared = old_prepared.merge(
        new_prepared[[TIMESTAMP_COLUMN, VALUE_COLUMN]],
        on=TIMESTAMP_COLUMN,
        suffixes=("_old", "_new"),
    )
    if len(shared) < required:
        msg = (
            f"insufficient overlap to chain-link: {len(shared)} shared "
            f"{frequency} period(s), need at least {required}"
        )
        raise ChainLinkingError(msg)

    if overlap is not None:
        if overlap < required:
            msg = (
                f"requested overlap of {overlap} period(s) is below the "
                f"{required} required for {frequency} data"
            )
            raise ChainLinkingError(msg)
        shared = shared.tail(overlap)

    ratios = np.array(
        [
            ratio
            for ratio in (
                _safe_ratio(new_value, old_value)
                for old_value, new_value in zip(
                    shared[f"{VALUE_COLUMN}_old"], shared[f"{VALUE_COLUMN}_new"], strict=True
                )
            )
            if ratio is not None
        ]
    )
    if ratios.size < required:
        msg = (
            f"only {ratios.size} usable overlap ratio(s) after discarding zero "
            f"and sign-flipping observations; need {required}"
        )
        raise ChainLinkingError(msg)

    scale_factor = float(ratios.mean())
    ratio_variance = float(np.var(ratios / scale_factor, ddof=0))

    # The new series is authoritative from its first period onward.
    boundary = new_prepared[TIMESTAMP_COLUMN].min()
    rescaled = old_prepared[old_prepared[TIMESTAMP_COLUMN] < boundary].copy()
    rescaled[VALUE_COLUMN] = rescaled[VALUE_COLUMN] * scale_factor
    rescaled[SCALE_FACTOR_COLUMN] = rescaled[SCALE_FACTOR_COLUMN] * scale_factor
    rescaled[IS_LINKED_COLUMN] = True

    combined = pd.concat([rescaled, new_prepared], ignore_index=True)
    combined = combined.sort_values(TIMESTAMP_COLUMN).reset_index(drop=True)
    _assert_growth_preserved(combined)

    return _SpliceOutcome(
        frame=combined,
        scale_factor=scale_factor,
        overlap_periods=int(len(shared)),
        ratio_variance=ratio_variance,
        base_year_from=int(old_prepared[TIMESTAMP_COLUMN].iloc[-1].year),
        base_year_to=int(new_prepared[TIMESTAMP_COLUMN].iloc[0].year),
    )


def splice_series(
    old: pd.DataFrame,
    new: pd.DataFrame,
    overlap: int | None = None,
    frequency: str = "annual",
) -> pd.DataFrame:
    """
    Splice an older base-year series onto a newer one.

    Args:
        old: Series on the earlier base (``timestamp``, ``value``)
        new: Series on the current base, authoritative where both report
        overlap: Use only the most recent N shared periods; None uses all
        frequency: Observation frequency, controlling the overlap minimum

    Returns:
        One continuous series with ``value`` on the new base plus
        ``original_value``, ``scale_factor``, and ``is_linked`` bookkeeping

    Raises:
        ChainLinkingError: If the overlap is too short, unusable, or the link
            would distort within-segment growth rates
    """
    return _splice_once(old, new, overlap, frequency).frame


def _assert_growth_preserved(frame: pd.DataFrame, tolerance: float = GROWTH_TOLERANCE) -> None:
    """
    Verify that linking changed levels only, never within-segment growth.

    The junction itself is expected to move -- that is the point of linking --
    so rows where the scale factor changes are excluded from the comparison.

    Raises:
        ChainLinkingError: If any within-segment growth rate moved by more than
            ``tolerance``
    """
    if len(frame) < 2:
        return

    original_growth = frame[ORIGINAL_VALUE_COLUMN].pct_change(fill_method=None)
    linked_growth = frame[VALUE_COLUMN].pct_change(fill_method=None)
    scale_changed = frame[SCALE_FACTOR_COLUMN].diff().abs() > SCALE_EPSILON

    deviation = (linked_growth - original_growth).abs()
    comparable = (~scale_changed) & np.isfinite(deviation)
    if not bool(comparable.any()):
        return

    worst = float(deviation[comparable].max())
    if worst > tolerance:
        msg = (
            f"chain-linking altered growth rates by {worst:.4%}, exceeding the "
            f"{tolerance:.2%} tolerance"
        )
        raise ChainLinkingError(msg)


def _link_at_breaks(
    series: pd.DataFrame,
    breaks: Sequence[BaseYearBreak],
) -> tuple[pd.DataFrame, list[float]]:
    """
    Rescale each older segment of a single series onto the newest base.

    Segments are folded from the newest backwards, so scale factors compose
    transitively across three or more base years.

    Raises:
        ChainLinkingError: If a junction ratio cannot be computed
    """
    prepared = _prepare_for_linking(series)
    boundaries = [pd.Timestamp(item.timestamp) for item in breaks]

    # segment_index[i] = which segment row i belongs to (0 = oldest).
    segment_index = np.zeros(len(prepared), dtype=int)
    for boundary in boundaries:
        segment_index += (prepared[TIMESTAMP_COLUMN] >= boundary).to_numpy().astype(int)

    scales = [1.0] * (len(boundaries) + 1)
    cumulative = 1.0
    for position in range(len(boundaries), 0, -1):
        ratio = breaks[position - 1].level_ratio
        if ratio is None:
            msg = (
                "cannot chain-link across the break at "
                f"{breaks[position - 1].timestamp.date()}: junction ratio is undefined "
                "(zero, non-finite, or sign-flipping observation)"
            )
            raise ChainLinkingError(msg)
        cumulative *= ratio
        scales[position - 1] = cumulative

    factors = np.array([scales[index] for index in segment_index], dtype="float64")
    prepared[VALUE_COLUMN] = prepared[VALUE_COLUMN] * factors
    prepared[SCALE_FACTOR_COLUMN] = prepared[SCALE_FACTOR_COLUMN] * factors
    prepared[IS_LINKED_COLUMN] = np.abs(factors - 1.0) > SCALE_EPSILON

    _assert_growth_preserved(prepared)
    return prepared, scales


def _passthrough(series: pd.DataFrame) -> ChainLinkResult:
    """Build the no-break result: values untouched, nothing fabricated."""
    prepared = _prepare_for_linking(series)
    return ChainLinkResult(
        frame=prepared,
        is_chain_linked=False,
        breaks=[],
        linking_method=None,
        records_linked=0,
        # Deliberately None, not 1.0: no link was performed, so there is no
        # confidence to report.
        avg_confidence_score=None,
        overlap_period_months=None,
        growth_rate_variance=None,
    )


def chain_link(
    frame: pd.DataFrame,
    metadata: Mapping[str, Any] | None = None,
    frequency: str = "annual",
    statistical_fallback: bool = False,
) -> ChainLinkResult:
    """
    Produce a continuous, analysis-ready series from one indicator's history.

    Args:
        frame: Silver observations with ``timestamp`` and ``value``
        metadata: Catalog metadata; ``base_years`` and ``segments`` are honoured
        frequency: Observation frequency
        statistical_fallback: Allow level-shift detection when no base years are known

    Returns:
        Linked series plus the audit fields ``ChainLinkingLog`` needs

    Raises:
        ChainLinkingError: If a link would distort growth rates or cannot be made
    """
    info: Mapping[str, Any] = metadata or {}

    # Checked before ``frame`` is touched: when the caller supplies overlapping
    # published segments, they are the input and ``frame`` is unused.
    segments = info.get("segments")
    if segments:
        return _chain_link_segments(list(segments), frequency)

    series = normalise_series(frame)
    if series.empty:
        return _passthrough(series)

    base_years = info.get("base_years")
    breaks = detect_base_year_breaks(
        series,
        base_years=base_years,
        statistical_fallback=statistical_fallback,
    )
    if not breaks:
        return _passthrough(series)

    linked, _ = _link_at_breaks(series, breaks)
    variance = None
    confidence = calculate_confidence(0.0, variance)

    log_with_context(
        logger,
        "INFO",
        "series chain-linked across in-series break(s)",
        breaks=len(breaks),
        method=LINKING_METHOD_LEVEL_SHIFT,
        records_linked=int(linked[IS_LINKED_COLUMN].sum()),
        confidence=confidence,
    )

    return ChainLinkResult(
        frame=linked,
        is_chain_linked=True,
        breaks=list(breaks),
        linking_method=LINKING_METHOD_LEVEL_SHIFT,
        records_linked=int(linked[IS_LINKED_COLUMN].sum()),
        avg_confidence_score=confidence,
        # No overlapping publication exists in a single series.
        overlap_period_months=0,
        growth_rate_variance=variance,
        base_year_from=breaks[0].base_year_from,
        base_year_to=breaks[-1].base_year_to,
    )


def _chain_link_segments(segments: list[pd.DataFrame], frequency: str) -> ChainLinkResult:
    """
    Fold multiple overlapping base-year series into one linked history.

    Args:
        segments: Series ordered oldest base first, newest base last
        frequency: Observation frequency

    Returns:
        Linked result using the rigorous ``overlap`` method

    Raises:
        ChainLinkingError: If any pair lacks sufficient usable overlap
    """
    if len(segments) == 1:
        return _passthrough(segments[0])

    combined = _prepare_for_linking(segments[-1])
    overlaps: list[int] = []
    variances: list[float] = []
    confidences: list[float] = []
    base_years: list[tuple[int, int]] = []

    for older in reversed(segments[:-1]):
        outcome = _splice_once(older, combined, None, frequency)
        combined = outcome.frame
        overlaps.append(outcome.overlap_periods)
        variances.append(outcome.ratio_variance)
        confidences.append(
            calculate_confidence(
                outcome.overlap_periods * months_per_period(frequency),
                outcome.ratio_variance,
            )
        )
        base_years.append((outcome.base_year_from, outcome.base_year_to))

    total_overlap_months = sum(overlaps) * months_per_period(frequency)
    breaks = [
        BaseYearBreak(
            timestamp=pd.Timestamp(combined[TIMESTAMP_COLUMN].iloc[0]).to_pydatetime(),
            base_year_from=pair[0],
            base_year_to=pair[1],
            detected_by=DETECTED_BY_METADATA,
        )
        for pair in reversed(base_years)
    ]

    log_with_context(
        logger,
        "INFO",
        "segments chain-linked on overlap",
        segments=len(segments),
        method=LINKING_METHOD_OVERLAP,
        overlap_months=total_overlap_months,
    )

    return ChainLinkResult(
        frame=combined,
        is_chain_linked=True,
        breaks=breaks,
        linking_method=LINKING_METHOD_OVERLAP,
        records_linked=int(combined[IS_LINKED_COLUMN].sum()),
        avg_confidence_score=round(float(np.mean(confidences)), 4),
        overlap_period_months=total_overlap_months,
        growth_rate_variance=round(float(np.mean(variances)), 10),
        base_year_from=min(pair[0] for pair in base_years),
        base_year_to=max(pair[1] for pair in base_years),
    )
