"""Cached read-only query wrappers for Streamlit pages."""

from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.connection import repository_session


@st.cache_data(show_spinner=False)
def cached_list_indicators(
    search: str | None = None,
    domains: tuple[str, ...] = (),
    frequencies: tuple[str, ...] = (),
    sources: tuple[str, ...] = (),
    active_only: bool = True,
) -> pd.DataFrame:
    """Cache catalog query results with all filter values in the cache key."""
    with repository_session() as repository:
        return repository.list_indicators(
            search=search,
            domains=list(domains),
            frequencies=list(frequencies),
            sources=list(sources),
            active_only=active_only,
        )


@st.cache_data(show_spinner=False)
def cached_load_series(
    indicator_ids: tuple[str, ...],
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> pd.DataFrame:
    """Cache Gold query results with indicator and date selections in the key."""
    with repository_session() as repository:
        return repository.load_series(list(indicator_ids), start_date, end_date)


@st.cache_data(show_spinner=False)
def cached_coverage_summary(indicator_ids: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Cache coverage summaries by the selected indicator set."""
    with repository_session() as repository:
        return repository.coverage_summary(list(indicator_ids) if indicator_ids else None)


@st.cache_data(show_spinner=False)
def cached_list_derived_ids(parent_ids: tuple[str, ...]) -> list[str]:
    """Cache derived-series discovery by parent set.

    Derived Gold series have no catalog row, so they are discovered from
    ``record_metadata["derived_from"]`` rather than from a catalog query, a
    hardcoded id list or an id pattern.
    """
    with repository_session() as repository:
        return repository.list_derived_ids(list(parent_ids))


@st.cache_data(show_spinner=False)
def cached_source_freshness() -> pd.DataFrame:
    """Cache the latest collection result for each source."""
    with repository_session() as repository:
        return repository.source_freshness()


@st.cache_data(show_spinner=False)
def cached_available_domains() -> pd.DataFrame:
    """Cache active domain counts."""
    with repository_session() as repository:
        return repository.available_domains()
