"""Shared dashboard filtering controls."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

import pandas as pd
import streamlit as st


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
    """Render common filters and return the exact user selection."""
    domains = unique_values(catalog, "domain")
    frequencies = unique_values(catalog, "frequency")
    sources = unique_values(catalog, "source_name")
    selected_domains = st.multiselect("Domain", domains, key=f"{key_prefix}_domains")
    selected_frequencies = st.multiselect("Frequency", frequencies, key=f"{key_prefix}_frequencies")
    selected_sources = st.multiselect("Source", sources, key=f"{key_prefix}_sources")

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
        "Indicators",
        options=options,
        default=defaults,
        key=f"{key_prefix}_indicators",
    )
    default_start, default_end = default_date_bounds(catalog)
    start_value = st.date_input(
        "Start date",
        value=default_start.date(),
        key=f"{key_prefix}_start",
    )
    end_value = st.date_input(
        "End date",
        value=default_end.date(),
        key=f"{key_prefix}_end",
    )
    start = as_utc_datetime(start_value)
    end = as_utc_datetime(end_value).replace(hour=23, minute=59, second=59)
    if start > end:
        st.error("Start date must be on or before the end date.")
    return FilterState(
        indicator_ids=selected_indicators,
        domains=selected_domains,
        frequencies=selected_frequencies,
        sources=selected_sources,
        start_date=start,
        end_date=end,
    )
