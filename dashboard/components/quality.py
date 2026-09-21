"""Data-quality summaries for Gold observations.

The expectation primitive here answers one question, deterministically and
without a database or a repository read::

    indicator frequency + requested range + calendar rule
        -> expected observation periods (normalized keys) and their count

Actual observations stay the repository's responsibility: :func:`summarize_quality`
compares the rows it is *handed* against those expected periods, and nothing here
queries Gold, fills a gap or scores data quality.

Conventions:

- Ranges are inclusive -- ``[start_date, end_date]`` -- matching the dashboard
  date filters, so a date control bound covers the period it names.
- A reversed range is not silently swapped: it yields zero expected periods,
  the contract :func:`expected_observation_count` has always had.
- Naive datetimes are read as UTC (the storage convention); aware datetimes are
  converted to UTC before any calendar interpretation.
- Day-based frequencies (``daily``, ``weekly``) are interpreted in
  ``Asia/Tehran``, mirroring the display policy, so a stored late-evening UTC
  instant belongs to the Tehran day a human would see.
- Period-end frequencies (``monthly``, ``quarterly``, ``annual``) keep the
  storage convention and key off the UTC calendar date, which is unambiguous
  because the ETL stamps a period end at UTC midnight.
- Normalized keys: ``daily`` -> ``YYYY-MM-DD`` (Tehran day), ``weekly`` ->
  ``YYYY-Www`` (ISO week), ``monthly`` -> ``YYYY-MM``, ``quarterly`` ->
  ``YYYY-Qn``, ``annual`` -> ``YYYY``.
- ``daily`` has two rules. Snapshot sources (TGJU) publish every day, so every
  Tehran day in the range is expected. Trading sources (TSETMC) print only on
  exchange sessions, so their expectation is an *empirical session rate* applied
  to the range length and is reported as an estimate with no enumerable keys.
  That rule is deliberately **not** a trading calendar: it carries no session
  dates, encodes no weekday rule and knows no holidays, so it must never be
  presented as a session list -- a real calendar would need a holiday database
  this phase does not add.
"""

import zoneinfo
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal, NamedTuple

import pandas as pd
import streamlit as st

from dashboard.components.html_table import Cell, Ltr, Text, render_html_table
from dashboard.components.tables import NUMBER_COLUMNS, localize_table_frame
from dashboard.formatting import MISSING_VALUE, TEHRAN_TIMEZONE
from dashboard.i18n import t
from dashboard.labels import FREQUENCY_LABELS

__all__ = [
    "CALENDAR_CALENDAR",
    "CALENDAR_TRADING",
    "DAYS_PER_YEAR",
    "MISSING_PERIOD_WARNING_RATIO",
    "PERIODS_PER_YEAR",
    "SUPPORTED_FREQUENCIES",
    "TRADING_SESSION_SOURCES",
    "TRADING_SESSIONS_PER_YEAR",
    "ExpectedPeriods",
    "QualityTable",
    "build_quality_rows",
    "calendar_for_source",
    "expected_observation_count",
    "expected_periods",
    "render_quality_summary",
    "summarize_quality",
]

FrequencyCalendar = Literal["calendar", "trading"]
"""Calendar rule applied to a day-based frequency."""

CALENDAR_CALENDAR: Final[FrequencyCalendar] = "calendar"
"""Every calendar day of the range is an expected observation."""

CALENDAR_TRADING: Final[FrequencyCalendar] = "trading"
"""Session-rate rule: trading sources are expected only on exchange sessions.

An empirical estimate (see :data:`TRADING_SESSIONS_PER_YEAR`), not a trading
calendar: no session dates are known, so the expectation is a count with no
enumerable period keys.
"""

SUPPORTED_FREQUENCIES: Final[frozenset[str]] = frozenset(FREQUENCY_LABELS)
"""Frequencies the expectation primitive understands.

Derived from the presentation cadence registry in :mod:`dashboard.labels` rather
than re-declared, so a frequency cannot be displayable but unsupported here (or
the reverse). An indicator with any other frequency has no expectation at all.
"""

PERIODS_PER_YEAR: Final[dict[str, float]] = {
    "daily": 365.25,
    "weekly": 52.18,
    "monthly": 12,
    "quarterly": 4,
    "annual": 1,
}
"""Nominal periods per year, by frequency.

Reference rates only: month/quarter/year expectations are counted from the
calendar, and ``daily`` is either the calendar day count or the trading rate
below. Kept next to the trading constants because that is where the daily rate is
overridden.
"""

DAYS_PER_YEAR: Final[float] = PERIODS_PER_YEAR["daily"]
"""Mean Gregorian year length, the denominator of a sessions-per-year rate."""

TRADING_SESSIONS_PER_YEAR: Final[float] = 241.0
"""Expected trading sessions in a year, calibrated against the observed live run.

The Phase 6 live run stored 4,285 sessions across 2008-12-04 .. 2026-09-15
(6,495 days, ~17.78 years), i.e. ~241 sessions/year. The value is calibrated from
that recorded observation rather than from an assumed round constant, and the
expectation it produces is still reported as an estimate: an exact session list
would need a holiday calendar this phase deliberately does not add.

The rate is date-agnostic -- it cannot say *which* days were sessions -- so it
feeds a count only and never a period-key list.
"""

TRADING_SESSION_SOURCES: Final[frozenset[str]] = frozenset({"tsetmc"})
"""``source_name`` slugs whose daily series follow exchange sessions.

Keyed by catalog provenance (which derived rows inherit), never by indicator id:
every other daily source in the catalog is a calendar-day snapshot. TSETMC has no
usable holiday calendar, so an estimated session rate replaces a session list.
"""

MISSING_PERIOD_WARNING_RATIO: Final[float] = 0.05
"""Gap share from which a missing-period warning is material.

A single missing month in a year is 8.3% and a missing quarter is 25%, while the
trading-session estimate for a TSETMC span leaves a residual well under 1%; 5%
therefore separates estimation noise from a real gap. The gate exists precisely
because the session rate is an estimate: ungated, its residual would still raise
the missing-period warning for every TSETMC series.
"""

_TEHRAN: Final[zoneinfo.ZoneInfo] = zoneinfo.ZoneInfo(TEHRAN_TIMEZONE)


@dataclass(frozen=True)
class ExpectedPeriods:
    """Expected observation periods for one indicator frequency and date range.

    ``period_keys`` holds the normalized periods themselves, so a later quality
    view can compare observed timestamps against expectation without reconstructing
    a calendar. When the rule is an estimate (trading sessions) the keys are empty
    and :attr:`estimated_count` carries the count instead, so a caller can tell
    "these are the periods" from "this is an estimate". An estimated count must
    never be expanded into periods or read as a session calendar.
    """

    frequency: str
    calendar: FrequencyCalendar
    start: datetime
    end: datetime
    period_keys: tuple[str, ...] = ()
    estimated_count: int | None = None

    @property
    def is_estimate(self) -> bool:
        """Whether the count is a session-rate estimate rather than enumerated periods."""
        return self.estimated_count is not None

    @property
    def count(self) -> int:
        """Number of expected periods: enumerated keys, or the estimate."""
        if self.estimated_count is not None:
            return self.estimated_count
        return len(self.period_keys)


def _as_utc(value: datetime) -> datetime:
    """Normalize a stored timestamp to timezone-aware UTC (naive is read as UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _tehran_date(value: datetime) -> date:
    """Return the Tehran-local calendar date of a stored timestamp."""
    return _as_utc(value).astimezone(_TEHRAN).date()


def _daily_keys(start: datetime, end: datetime) -> tuple[str, ...]:
    """One key per Tehran-local calendar day, inclusive."""
    day = _tehran_date(start)
    last = _tehran_date(end)
    keys: list[str] = []
    while day <= last:
        keys.append(day.isoformat())
        day += timedelta(days=1)
    return tuple(keys)


def _weekly_keys(start: datetime, end: datetime) -> tuple[str, ...]:
    """One key per ISO-8601 week, anchored on the Monday of the start week."""
    day = _tehran_date(start)
    last = _tehran_date(end)
    day -= timedelta(days=day.weekday())
    keys: list[str] = []
    while day <= last:
        iso = day.isocalendar()
        keys.append(f"{iso.year:04d}-W{iso.week:02d}")
        day += timedelta(days=7)
    return tuple(keys)


def _monthly_keys(start: datetime, end: datetime) -> tuple[str, ...]:
    """One key per calendar month of the storage (period-end) calendar."""
    first, last = start.date(), end.date()
    year, month = first.year, first.month
    keys: list[str] = []
    while (year, month) <= (last.year, last.month):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(keys)


def _quarterly_keys(start: datetime, end: datetime) -> tuple[str, ...]:
    """One key per calendar quarter of the storage (period-end) calendar."""
    first, last = start.date(), end.date()
    year, quarter = first.year, (first.month - 1) // 3 + 1
    last_key = (last.year, (last.month - 1) // 3 + 1)
    keys: list[str] = []
    while (year, quarter) <= last_key:
        keys.append(f"{year:04d}-Q{quarter}")
        year, quarter = (year + 1, 1) if quarter == 4 else (year, quarter + 1)
    return tuple(keys)


def _annual_keys(start: datetime, end: datetime) -> tuple[str, ...]:
    """One key per calendar year of the storage (period-end) calendar."""
    return tuple(f"{year:04d}" for year in range(start.year, end.year + 1))


_PERIOD_KEY_BUILDERS: Final[Mapping[str, Callable[[datetime, datetime], tuple[str, ...]]]] = {
    "daily": _daily_keys,
    "weekly": _weekly_keys,
    "monthly": _monthly_keys,
    "quarterly": _quarterly_keys,
    "annual": _annual_keys,
}


def _expected_sessions(start: datetime, end: datetime) -> int:
    """Estimate trading sessions for an inclusive range of Tehran-local days."""
    days = (_tehran_date(end) - _tehran_date(start)).days + 1
    return max(0, round(days * TRADING_SESSIONS_PER_YEAR / DAYS_PER_YEAR))


def calendar_for_source(source_name: str | None) -> FrequencyCalendar:
    """Return the calendar rule for a source's day-based series.

    Args:
        source_name: Catalog ``source_name`` slug (derived rows inherit it)

    Returns:
        ``"trading"`` for an exchange session source, else ``"calendar"``

    Examples:
        >>> calendar_for_source("tsetmc")
        'trading'
        >>> calendar_for_source("tgju")
        'calendar'
        >>> calendar_for_source(None)
        'calendar'
    """
    if source_name is not None and source_name in TRADING_SESSION_SOURCES:
        return CALENDAR_TRADING
    return CALENDAR_CALENDAR


def expected_periods(
    frequency: str | None,
    start_date: datetime,
    end_date: datetime,
    *,
    source_name: str | None = None,
    calendar: FrequencyCalendar | None = None,
) -> ExpectedPeriods | None:
    """Return the observation periods expected over an inclusive date range.

    Args:
        frequency: Catalog frequency (``daily``/``weekly``/``monthly``/
            ``quarterly``/``annual``)
        start_date: Inclusive range start (naive is read as UTC)
        end_date: Inclusive range end (naive is read as UTC)
        source_name: Catalog source slug, used to pick the daily calendar rule
        calendar: Explicit calendar rule, overriding ``source_name``

    Returns:
        The expected periods, or ``None`` when the frequency is missing or
        unsupported (no expectation is invented). A reversed range yields zero
        periods rather than being swapped or raising.

    Raises:
        ValueError: If ``calendar`` is not a known rule.

    Examples:
        >>> periods = expected_periods(
        ...     "monthly", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 31, tzinfo=UTC)
        ... )
        >>> periods.period_keys
        ('2024-01', '2024-02', '2024-03')
    """
    if frequency is None or frequency not in SUPPORTED_FREQUENCIES:
        return None
    rule = calendar if calendar is not None else calendar_for_source(source_name)
    if rule not in (CALENDAR_CALENDAR, CALENDAR_TRADING):
        msg = f"unsupported calendar rule {rule!r}"
        raise ValueError(msg)
    start = _as_utc(start_date)
    end = _as_utc(end_date)
    if start > end:
        return ExpectedPeriods(frequency=frequency, calendar=rule, start=start, end=end)
    if frequency == "daily" and rule == CALENDAR_TRADING:
        return ExpectedPeriods(
            frequency=frequency,
            calendar=rule,
            start=start,
            end=end,
            estimated_count=_expected_sessions(start, end),
        )
    return ExpectedPeriods(
        frequency=frequency,
        calendar=rule,
        start=start,
        end=end,
        period_keys=_PERIOD_KEY_BUILDERS[frequency](start, end),
    )


def expected_observation_count(
    frequency: str,
    start_date: datetime,
    end_date: datetime,
    *,
    source_name: str | None = None,
    calendar: FrequencyCalendar | None = None,
) -> int | None:
    """Return just the expected period count for a supported frequency.

    Thin wrapper over :func:`expected_periods` for callers that only need the
    number; ``None`` means "no expectation" for a missing/unsupported frequency.
    """
    periods = expected_periods(
        frequency, start_date, end_date, source_name=source_name, calendar=calendar
    )
    return None if periods is None else periods.count


def _first_text(frame: pd.DataFrame, column: str) -> str | None:
    """Return the first non-null value of a column as text, or ``None``."""
    if column not in frame.columns or frame.empty:
        return None
    value = frame[column].iloc[0]
    if value is None or pd.isna(value):
        return None
    return str(value)


def summarize_quality(
    series: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """Summarize coverage, gaps, and chain-linking quality without filling data.

    One row per indicator, always including ``expected_observations`` and
    ``missing_periods`` (``NaN`` when the frequency has no expectation).
    ``expected_is_estimated`` marks the rows whose expectation is a session-rate
    estimate rather than enumerated calendar periods -- the expectation counts
    something real, but the individual sessions are not known.
    """
    records: list[dict[str, object]] = []
    for indicator_id, frame in series.groupby("indicator_id", sort=False):
        frequency = str(frame["frequency"].iloc[0]) if not frame.empty else "unknown"
        expected = expected_periods(
            frequency,
            start_date,
            end_date,
            source_name=_first_text(frame, "source_name"),
        )
        records.append(
            {
                "indicator_id": indicator_id,
                "name": frame["name"].iloc[0] if "name" in frame else indicator_id,
                "rows_returned": int(len(frame)),
                "expected_observations": None if expected is None else expected.count,
                "expected_is_estimated": None if expected is None else expected.is_estimate,
                "missing_periods": (
                    None if expected is None else max(0, expected.count - len(frame))
                ),
                "observed_start": frame["timestamp"].min(),
                "observed_end": frame["timestamp"].max(),
                "chain_linked_rows": int(
                    frame.get("is_chain_linked", pd.Series(False, index=frame.index)).sum()
                ),
                "average_confidence": frame.get(
                    "chain_linking_confidence", pd.Series(dtype="float64")
                ).mean(),
                "frequency": frequency,
            }
        )
    return pd.DataFrame(records)


def _has_material_gap(quality: pd.DataFrame) -> bool:
    """Report whether any row misses a material share of its expected periods."""
    if "missing_periods" not in quality.columns or "expected_observations" not in quality.columns:
        return False
    missing = pd.to_numeric(quality["missing_periods"], errors="coerce")
    expected = pd.to_numeric(quality["expected_observations"], errors="coerce")
    ratio = (missing / expected).where(expected > 0)
    return bool((ratio >= MISSING_PERIOD_WARNING_RATIO).any())


class QualityTable(NamedTuple):
    """A quality summary ready for ``render_html_table``.

    Attributes:
        columns: Localized column headers, in ``summarize_quality``'s order
        rows: One tuple of typed cells per indicator, in the frame's order
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


def _quality_cell(value: object, *, numeric: bool, ltr: bool) -> Cell:
    """One quality cell: an LTR token, a tabular number, or plain text.

    The value arrives already localized, so the em-dash a null renders is the
    shared missing-value placeholder; it is passed through as ``None`` so the cell
    emits the same ``.na`` markup as every other RTL table.

    An id is an :class:`~dashboard.components.html_table.Ltr` cell, which the
    shared ``.dt .ltr`` rule caps at 24ch with an ellipsis; the cell therefore
    carries the full id as its ``title``, so the truncated token is still
    recoverable on hover (the same tooltip practice the coverage table's range
    cells use).
    """
    text = None if value is None or str(value) == MISSING_VALUE else str(value)
    if ltr:
        return Ltr(text, title=text)
    return Text(text, num=numeric)


def build_quality_rows(quality: pd.DataFrame) -> QualityTable:
    """Build the quality summary as typed cells, in the frame's order.

    One row per indicator and exactly the columns
    :func:`summarize_quality` returns. The values come from
    :func:`dashboard.components.tables.localize_table_frame` -- the same localizer
    the observation grid and the exports use -- so the HTML table cannot drift
    from the frame, and the em-dash a null renders is unchanged.

    The indicator id is an :class:`~dashboard.components.html_table.Ltr` cell (an
    LTR token isolated inside RTL text) and the columns in
    :data:`dashboard.components.tables.NUMBER_COLUMNS` are
    :class:`~dashboard.components.html_table.Text` cells with tabular figures;
    every other column is plain text.

    Args:
        quality: Frame from :func:`summarize_quality`

    Returns:
        A :class:`QualityTable`; an empty frame yields no columns and no rows
    """
    if quality.empty:
        return QualityTable((), ())
    display = localize_table_frame(quality)
    numeric = [str(column) in NUMBER_COLUMNS for column in quality.columns]
    ltr = [str(column) == "indicator_id" for column in quality.columns]
    rows = tuple(
        tuple(
            _quality_cell(value, numeric=numeric[index], ltr=ltr[index])
            for index, value in enumerate(row)
        )
        for row in display.itertuples(index=False, name=None)
    )
    return QualityTable(tuple(str(column) for column in display.columns), rows)


def render_quality_summary(quality: pd.DataFrame) -> None:
    """Display quality diagnostics, including zero-row and sparse-history cases.

    The summary is a small, static, presentation-only table, so it is the shared
    RTL HTML table (D1) rather than a ``st.dataframe``; the two warnings stay
    native alerts. Nothing about the frame changes: same columns, same values,
    same nulls.

    It is the ``coverage`` variant: the summary is as wide as the Overview
    coverage table (eleven columns), so it needs the same wrapping rules to fit
    the page instead of scrolling sideways inside its own box.
    """
    if quality.empty:
        st.info(t("empty.no_quality_rows"))
        return
    table = build_quality_rows(quality)
    render_html_table(table.columns, table.rows, variant="coverage")
    if (quality["rows_returned"] == 1).any():
        st.warning(t("warn.single_observation"))
    if _has_material_gap(quality):
        st.warning(t("warn.missing_periods"))
