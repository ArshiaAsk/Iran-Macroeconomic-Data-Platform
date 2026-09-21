"""Shared dashboard filtering controls.

Labels and option values are Persian (the display layer), but the values a
:class:`FilterState` carries are always the raw catalog slugs, so the SQL is
unchanged: a display label is never a filter value.

Date selection keeps Streamlit's Gregorian ``st.date_input``. A selected day is
interpreted as a **Tehran** day (the display convention), so an evening UTC
observation lands on the day the analyst expects; the inclusive UTC bounds that
the repository filters on are echoed back. Jalali year/month presets and a Jalali
day text preset are convenience shortcuts that resolve to the same UTC bounds --
there is no custom Jalali date-entry widget.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

import jdatetime
import pandas as pd
import streamlit as st

from dashboard.formatting import (
    JALALI_MONTH_NAMES,
    gregorian_to_jalali,
    jalali_date_label,
    jalali_day_bounds,
    tehran_day_bounds,
    to_ascii_digits,
    to_persian_digits,
)
from dashboard.i18n import t
from dashboard.labels import domain_label, frequency_label, indicator_label, source_label
from src.utils.persian import iranian_year_end

#: Numeric Jalali date ``YYYY/MM/DD`` (``-`` and ``.`` separators accepted).
_JALALI_DAY_PATTERN = re.compile(r"(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})")


@dataclass(frozen=True)
class FilterState:
    """User-selected catalog and date filters."""

    indicator_ids: list[str]
    domains: list[str]
    frequencies: list[str]
    sources: list[str]
    start_date: datetime
    end_date: datetime


def unique_values(frame: pd.DataFrame, column: str) -> list[str]:
    """Return sorted non-null unique values from a catalog column."""
    if column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str)
    return sorted(values.unique().tolist())


def default_date_bounds(catalog: pd.DataFrame) -> tuple[datetime, datetime]:
    """Derive default bounds from observed catalog coverage."""
    start = catalog.get("availability_start", pd.Series(dtype="datetime64[ns, UTC]")).dropna()
    end = catalog.get("availability_end", pd.Series(dtype="datetime64[ns, UTC]")).dropna()
    start_value = start.min() if not start.empty else pd.Timestamp("1960-01-01", tz="UTC")
    end_value = end.max() if not end.empty else pd.Timestamp.now(tz="UTC")
    return start_value.to_pydatetime(), end_value.to_pydatetime()


def as_utc_datetime(value: date) -> datetime:
    """Convert a Streamlit date control value to a UTC datetime."""
    return datetime.combine(value, time.min, tzinfo=UTC)


def render_filters(
    catalog: pd.DataFrame,
    key_prefix: str,
    default_indicators: list[str] | None = None,
) -> FilterState:
    """Render common filters and return the exact user selection.

    Domain, frequency, source and indicator option values are shown through the
    label layer, while the underlying selection (and therefore
    :class:`FilterState`) keeps the raw catalog slugs. The date range defaults to
    the catalog coverage; a selected day means a Tehran day, and a Jalali preset
    (when chosen) takes over the range.

    Every ``st.multiselect``/``st.selectbox`` carries the Persian
    ``filter.placeholder`` (F4): Streamlit's own default for an empty widget is
    the English "Choose options", which must not appear in the Persian UI.
    """
    domains = unique_values(catalog, "domain")
    frequencies = unique_values(catalog, "frequency")
    sources = unique_values(catalog, "source_name")
    selected_domains = st.multiselect(
        t("filter.domain"),
        domains,
        format_func=domain_label,
        key=f"{key_prefix}_domains",
        placeholder=t("filter.placeholder"),
    )
    selected_frequencies = st.multiselect(
        t("filter.frequency"),
        frequencies,
        format_func=frequency_label,
        key=f"{key_prefix}_frequencies",
        placeholder=t("filter.placeholder"),
    )
    selected_sources = st.multiselect(
        t("filter.source"),
        sources,
        format_func=source_label,
        key=f"{key_prefix}_sources",
        placeholder=t("filter.placeholder"),
    )

    filtered = catalog
    if selected_domains:
        filtered = filtered[filtered["domain"].isin(selected_domains)]
    if selected_frequencies:
        filtered = filtered[filtered["frequency"].isin(selected_frequencies)]
    if selected_sources:
        filtered = filtered[filtered["source_name"].isin(selected_sources)]

    options = filtered["indicator_id"].tolist() if not filtered.empty else []
    defaults = [indicator for indicator in (default_indicators or []) if indicator in options]
    selected_indicators = st.multiselect(
        t("filter.indicators"),
        options=options,
        default=defaults,
        format_func=indicator_label,
        key=f"{key_prefix}_indicators",
        placeholder=t("filter.placeholder"),
    )
    default_start, default_end = default_date_bounds(catalog)
    preset_bounds = _render_jalali_presets(catalog, key_prefix)
    preset_active = preset_bounds is not None
    start_value = st.date_input(
        t("filter.start_date"),
        value=default_start.date(),
        key=f"{key_prefix}_start",
        disabled=preset_active,
    )
    end_value = st.date_input(
        t("filter.end_date"),
        value=default_end.date(),
        key=f"{key_prefix}_end",
        disabled=preset_active,
    )
    if preset_bounds is not None:
        start, end = preset_bounds
    else:
        start = tehran_day_bounds(start_value)[0]
        end = tehran_day_bounds(end_value)[1]
    _render_range_echo(start, end)
    if start > end:
        st.error(t("filter.start_after_end"))
    return FilterState(
        indicator_ids=selected_indicators,
        domains=selected_domains,
        frequencies=selected_frequencies,
        sources=selected_sources,
        start_date=start,
        end_date=end,
    )


def resolve_jalali_preset(
    year: int | None,
    month: int | None,
    day_text: str,
) -> tuple[datetime, datetime] | None:
    """Resolve a Jalali preset to the inclusive UTC bounds the repository expects.

    The most specific preset wins: a Jalali day, then a Jalali year + month, then
    a Jalali year. A day preset's bounds round-trip back to that same Jalali day,
    including a TGJU-style late-evening UTC instant (the day is a Tehran day).

    Args:
        year: Selected Jalali year, or ``None``
        month: Selected Jalali month (1-12), or ``None``
        day_text: Numeric Jalali day (``YYYY/MM/DD``), or an empty string

    Returns:
        ``(start, end)`` inclusive UTC bounds, or ``None`` when no preset is
        active

    Raises:
        ValueError: If ``day_text`` is present but is not a valid Jalali date

    Examples:
        >>> resolve_jalali_preset(1405, 6, "1405/06/18")[0].isoformat()
        '2026-09-08T20:30:00+00:00'
        >>> resolve_jalali_preset(None, None, "") is None
        True
    """
    day = _parse_jalali_day(day_text)
    if day is not None:
        return jalali_day_bounds(day)
    if year is None:
        return None
    if month is None:
        return _jalali_year_bounds(year)
    return _jalali_month_bounds(year, month)


def _parse_jalali_day(text: str) -> jdatetime.date | None:
    """Parse a numeric Jalali ``YYYY/MM/DD`` day, or ``None`` when blank."""
    normalized = to_ascii_digits(text.strip())
    if not normalized:
        return None
    match = _JALALI_DAY_PATTERN.fullmatch(normalized)
    if match is None:
        msg = f"Not a Jalali YYYY/MM/DD date: {text!r}"
        raise ValueError(msg)
    year, month, day = (int(part) for part in match.groups())
    try:
        return jdatetime.date(year, month, day)
    except ValueError as exc:
        msg = f"Invalid Jalali date: {text!r}"
        raise ValueError(msg) from exc


def _jalali_year_bounds(year: int) -> tuple[datetime, datetime]:
    """Inclusive UTC bounds of a whole Jalali year (Farvardin 1 .. Esfand 29/30)."""
    start = jalali_day_bounds(jdatetime.date(year, 1, 1))[0]
    end = jalali_day_bounds(gregorian_to_jalali(iranian_year_end(year)))[1]
    return start, end


def _jalali_month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Inclusive UTC bounds of one Jalali month."""
    last_day = _jalali_month_last_day(year, month)
    start = jalali_day_bounds(jdatetime.date(year, month, 1))[0]
    end = jalali_day_bounds(jdatetime.date(year, month, last_day))[1]
    return start, end


def _jalali_month_last_day(year: int, month: int) -> int:
    """Last day of a Jalali month, Esfand accounting for the leap year."""
    if month == 12:
        return 30 if jdatetime.date(year, 1, 1).isleap() else 29
    return int(jdatetime.j_days_in_month[month - 1])


def _render_jalali_presets(
    catalog: pd.DataFrame,
    key_prefix: str,
) -> tuple[datetime, datetime] | None:
    """Render the Jalali year/month/day presets, returning their resolved bounds."""
    none_label = t("filter.jalali_none")
    years = _jalali_year_options(catalog)
    with st.expander(t("filter.jalali_presets"), expanded=False):
        selected_year = st.selectbox(
            t("filter.jalali_year"),
            options=[None, *years],
            format_func=lambda year: (none_label if year is None else to_persian_digits(str(year))),
            key=f"{key_prefix}_jalali_year",
            placeholder=t("filter.placeholder"),
        )
        selected_month = st.selectbox(
            t("filter.jalali_month"),
            options=[None, *range(1, 13)],
            format_func=lambda month: (
                none_label if month is None else JALALI_MONTH_NAMES[month - 1]
            ),
            key=f"{key_prefix}_jalali_month",
            placeholder=t("filter.placeholder"),
        )
        day_text = st.text_input(t("filter.jalali_day"), key=f"{key_prefix}_jalali_day")
        if selected_year is None and not day_text.strip():
            return None
        try:
            bounds = resolve_jalali_preset(selected_year, selected_month, day_text)
        except ValueError:
            st.error(t("filter.jalali_day_invalid"))
            return None
        if bounds is not None:
            st.caption(t("filter.preset_active"))
        return bounds


def _jalali_year_options(catalog: pd.DataFrame) -> list[int]:
    """Jalali years spanned by the catalog's observed coverage, ascending."""
    start, end = default_date_bounds(catalog)
    first = gregorian_to_jalali(start).year
    last = gregorian_to_jalali(end).year
    if first > last:
        first, last = last, first
    return list(range(first, last + 1))


def _render_range_echo(start: datetime, end: datetime) -> None:
    """Echo the applied range as a Jalali label plus the UTC Gregorian bounds."""
    st.caption(
        t(
            "filter.applied_range",
            jalali_start=jalali_date_label(start),
            jalali_end=jalali_date_label(end),
            start=start.date().isoformat(),
            end=end.date().isoformat(),
        )
    )
