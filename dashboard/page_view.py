"""Composable page-rendering functions used by Streamlit page modules."""

from collections.abc import Iterable
from datetime import date, datetime

import pandas as pd
import streamlit as st

from dashboard.components.charts import build_time_series_chart
from dashboard.components.exports import render_chart_downloads, render_data_downloads
from dashboard.components.filters import render_filters
from dashboard.components.quality import render_quality_summary, summarize_quality
from dashboard.queries import (
    cached_coverage_summary,
    cached_list_indicators,
    cached_load_series,
    cached_source_freshness,
)
from dashboard.repository import DashboardRepository


def render_domain_page(
    title: str,
    domains: Iterable[str],
    key_prefix: str,
    default_indicators: list[str] | None = None,
    repository: DashboardRepository | None = None,
) -> None:
    """Render a domain-specific Gold exploration page."""
    st.title(title)
    domain_list = list(domains)
    if repository is None:
        catalog = cached_list_indicators(domains=tuple(domain_list))
    else:
        catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        st.info("No active indicators are available for this page yet.")
        return
    filters = render_filters(catalog, key_prefix, default_indicators)
    selected_ids = list(filters.indicator_ids)
    if st.checkbox("Include derived series when available", key=f"{key_prefix}_derived"):
        selected_ids.extend(_derived_ids(catalog, filters.indicator_ids))
    if not selected_ids:
        st.info("Select one or more indicators to view Gold observations.")
        return
    if filters.start_date > filters.end_date:
        return
    if repository is None:
        series = cached_load_series(tuple(selected_ids), filters.start_date, filters.end_date)
    else:
        series = repository.load_series(selected_ids, filters.start_date, filters.end_date)
    _render_series_section(series, key_prefix)


def render_catalog_page(repository: DashboardRepository | None = None) -> None:
    """Render the searchable indicator catalog."""
    st.title("Data Catalog")
    catalog = repository.list_indicators() if repository else cached_list_indicators()
    if catalog.empty:
        st.info("The indicator catalog is empty.")
        return
    filters = render_filters(catalog, "catalog")
    result = catalog
    if filters.domains:
        result = result[result["domain"].isin(filters.domains)]
    if filters.frequencies:
        result = result[result["frequency"].isin(filters.frequencies)]
    if filters.sources:
        result = result[result["source_name"].isin(filters.sources)]
    if filters.indicator_ids:
        result = result[result["indicator_id"].isin(filters.indicator_ids)]
    st.metric("Matching indicators", len(result))
    display = result.copy()
    for column in ("availability_start", "availability_end"):
        display[column] = display[column].map(_display_timestamp)
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_overview_page(repository: DashboardRepository | None = None) -> None:
    """Render platform-wide coverage, counts, and freshness."""
    st.title("Overview")
    catalog = repository.list_indicators() if repository else cached_list_indicators()
    coverage = repository.coverage_summary() if repository else cached_coverage_summary()
    freshness = repository.source_freshness() if repository else cached_source_freshness()
    if catalog.empty:
        st.warning(
            "The indicator catalog is empty. Run an ETL pipeline before using the dashboard."
        )
        return
    observation_counts = coverage.get("observation_count")
    if observation_counts is None:
        total_observations = 0
    else:
        total_observations = int(pd.to_numeric(observation_counts, errors="coerce").fillna(0).sum())
    columns = st.columns(4)
    columns[0].metric("Active indicators", len(catalog))
    columns[1].metric("Gold observations", total_observations)
    columns[2].metric("Domains", catalog["domain"].nunique())
    columns[3].metric("Sources", catalog["source_name"].nunique())
    st.subheader("Indicators by domain")
    st.bar_chart(catalog.groupby("domain", observed=True).size())
    st.subheader("Available coverage")
    st.dataframe(coverage, use_container_width=True, hide_index=True)
    st.subheader("Source freshness")
    if freshness.empty:
        st.info("No collection runs have been logged yet.")
    else:
        st.dataframe(freshness, use_container_width=True, hide_index=True)
    st.subheader("Key indicators")
    st.dataframe(
        catalog[["indicator_id", "name", "domain", "frequency", "unit", "source_name"]],
        use_container_width=True,
        hide_index=True,
    )


def render_fx_gold_page(repository: DashboardRepository | None = None) -> None:
    """Render the TGJU FX/gold page with snapshot limitations."""
    st.title("FX & Gold")
    st.warning(
        "TGJU provides current-price snapshots, not a historical backfill. "
        "Daily scheduled collection gradually builds the time series."
    )
    render_domain_page(
        "FX & Gold",
        ("fx", "gold"),
        "fx_gold",
        repository=repository,
    )


def render_correlation_page(repository: DashboardRepository | None = None) -> None:
    """Render exact-timestamp correlation diagnostics."""
    from dashboard.components.charts import build_correlation_chart

    st.title("Comparison & Correlation")
    catalog = repository.list_indicators() if repository else cached_list_indicators()
    if catalog.empty:
        st.info("The indicator catalog is empty.")
        return
    filters = render_filters(catalog, "correlation")
    if not filters.indicator_ids:
        st.info("Select at least two indicators to compare.")
        return
    if filters.start_date > filters.end_date:
        return
    if repository is None:
        series = cached_load_series(
            tuple(filters.indicator_ids),
            filters.start_date,
            filters.end_date,
        )
    else:
        series = repository.load_series(
            filters.indicator_ids,
            filters.start_date,
            filters.end_date,
        )
    if series.empty:
        st.info("No observations match the selected indicators and dates.")
        return
    frequencies = set(series["frequency"].astype(str))
    if len(frequencies) > 1:
        st.warning(
            "Selected indicators use different frequencies. Correlation uses only exact timestamp matches; "
            "no values are forward-filled or interpolated."
        )
    bundle = build_correlation_chart(series)
    st.plotly_chart(bundle.figure, use_container_width=True)
    st.subheader("Exact timestamp join counts")
    st.dataframe(bundle.join_counts, use_container_width=True)
    render_quality_summary(summarize_quality(series, filters.start_date, filters.end_date))
    render_data_downloads(series, "iran-macro-correlation")


def _render_series_section(series: pd.DataFrame, key_prefix: str) -> None:
    if series.empty:
        st.info("No Gold observations match the selected indicators and dates.")
        return
    start = series["timestamp"].min().to_pydatetime()
    end = series["timestamp"].max().to_pydatetime()
    quality = summarize_quality(series, start, end)
    figure = build_time_series_chart(series)
    st.plotly_chart(figure, use_container_width=True)
    render_quality_summary(quality)
    with st.expander("Observations", expanded=False):
        st.dataframe(series, use_container_width=True, hide_index=True)
    render_data_downloads(series, f"iran-macro-{key_prefix}")
    render_chart_downloads(figure, f"iran-macro-{key_prefix}-chart")


def _derived_ids(catalog: pd.DataFrame, selected_ids: list[str]) -> list[str]:
    available = set(catalog["indicator_id"])
    derived: list[str] = []
    for indicator_id in selected_ids:
        candidates = (
            f"WB.{indicator_id}.YOY",
            f"TGJU.{indicator_id}.RET1D",
            f"TGJU.{indicator_id}.MA30",
        )
        derived.extend(candidate for candidate in candidates if candidate in available)
    return derived


def _display_timestamp(value: object) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, datetime | date | pd.Timestamp):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return str(value)
