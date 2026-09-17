"""Composable page-rendering functions used by Streamlit page modules."""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Final

import pandas as pd
import streamlit as st

from dashboard.components.charts import (
    SURVEY_YEAR_COLUMN,
    build_survey_year_chart,
    build_time_series_chart,
)
from dashboard.components.exports import render_chart_downloads, render_data_downloads
from dashboard.components.filters import FilterState, render_filters
from dashboard.components.quality import render_quality_summary, summarize_quality
from dashboard.formatting import (
    format_number,
    gregorian_to_jalali,
    jalali_date_label,
    jalali_year_label,
)
from dashboard.i18n import t
from dashboard.queries import (
    cached_coverage_summary,
    cached_list_indicators,
    cached_load_series,
    cached_source_freshness,
)
from dashboard.repository import DashboardRepository
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    DEFAULT_POVERTY_LINE_K,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
)
from src.utils.persian import iranian_year_end

#: HBSIR indicator ids the Welfare & Survey page emphasises. They come from the
#: connector's authoritative registry (``src/connectors/hbsir_parser.py``) rather
#: than a list invented in the dashboard: ``DEFAULT_INDICATORS`` is exactly Gini,
#: relative poverty and the ten income-decile shares.
HBSIR_INDICATORS: Final[tuple[str, ...]] = tuple(DEFAULT_INDICATORS)

#: The Gini and relative-poverty pair. They carry different units (an index and a
#: percentage), which is why the trend renders one panel per indicator.
HBSIR_GINI_POVERTY_INDICATORS: Final[tuple[str, ...]] = (GINI_INDICATOR, POVERTY_INDICATOR)


def render_domain_page(
    title: str,
    domains: Iterable[str],
    key_prefix: str,
    default_indicators: list[str] | None = None,
    repository: DashboardRepository | None = None,
) -> None:
    """Render a domain-specific Gold exploration page."""
    st.title(title)
    render_domain_body(
        domains,
        key_prefix,
        default_indicators,
        repository=repository,
    )


def render_domain_body(
    domains: Iterable[str],
    key_prefix: str,
    default_indicators: list[str] | None = None,
    repository: DashboardRepository | None = None,
    catalog: pd.DataFrame | None = None,
    filters: FilterState | None = None,
) -> None:
    """Render the generic domain composition: filters, selection and Gold series.

    Kept separate from :func:`render_domain_page` so a page that owns a whole
    domain can show its own emphasis sections around the same composition without
    drawing a second page title (see :func:`render_welfare_page`). ``catalog`` and
    ``filters`` are passed in when the caller has already rendered them, so the
    domain is never queried or filtered twice.
    """
    domain_list = list(domains)
    if catalog is None:
        if repository is None:
            catalog = cached_list_indicators(domains=tuple(domain_list))
        else:
            catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        st.info("No active indicators are available for this page yet.")
        return
    if filters is None:
        filters = render_filters(catalog, key_prefix, default_indicators)
    selected_ids = list(filters.indicator_ids)
    if st.checkbox("Include derived series when available", key=f"{key_prefix}_derived"):
        selected_ids.extend(_derived_ids(catalog, filters.indicator_ids))
    if not selected_ids:
        st.info("Select one or more indicators to view Gold observations.")
        return
    if filters.start_date > filters.end_date:
        return
    series = _load_series(selected_ids, filters.start_date, filters.end_date, repository)
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


def render_welfare_page(repository: DashboardRepository | None = None) -> None:
    """Render the Welfare & Survey page, owner of the whole ``welfare`` domain.

    HBSIR's Gini, relative-poverty and income-decile series get dedicated sections
    on a Jalali survey-year axis (the survey year is the Jalali year containing the
    stored period end, so no Silver read is needed), plus the survey-year metadata
    panel. The remaining ``welfare`` members -- World Bank population and IMF
    ``LUR`` -- render through the generic domain composition, so the page owns
    everything the catalog assigns to the domain.
    """
    st.title(t("page.welfare"))
    st.warning(_relative_poverty_note())
    st.info(t("warn.hbsir_computed_values"))
    domain_list = ["welfare"]
    if repository is None:
        catalog = cached_list_indicators(domains=tuple(domain_list))
    else:
        catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        st.info(t("empty.no_indicators_for_page"))
        return
    hbsir_ids = [
        indicator for indicator in catalog["indicator_id"] if indicator in HBSIR_INDICATORS
    ]
    context_ids = [
        indicator for indicator in catalog["indicator_id"] if indicator not in HBSIR_INDICATORS
    ]
    filters = render_filters(catalog, "welfare", context_ids)
    series = _load_series(hbsir_ids, filters.start_date, filters.end_date, repository)
    _render_hbsir_sections(series)
    st.subheader(t("section.welfare_other_indicators"))
    render_domain_body(
        domain_list,
        "welfare",
        context_ids,
        repository=repository,
        catalog=catalog,
        filters=filters,
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


def survey_year_frame(series: pd.DataFrame) -> pd.DataFrame:
    """Add the Jalali survey-year label of each stored period end.

    HBSIR publishes one observation per survey year, stamped at the **true**
    Gregorian Iranian year end (Esfand 29 in a common year, Esfand 30 in a leap
    year). The survey year is therefore the Jalali year *containing that stored
    period end*: period ends are stored at UTC midnight, so under the Tehran
    display policy the Jalali day is stable and the label round-trips exactly at
    the 29/30 boundary without reading Silver for the year stored there.

    Args:
        series: Gold observations carrying a ``timestamp`` column

    Returns:
        A copy ordered by timestamp, with the ``survey_year`` label column added
    """
    frame = series.copy()
    if "timestamp" not in frame.columns:
        frame[SURVEY_YEAR_COLUMN] = pd.Series(dtype="object")
        return frame.reset_index(drop=True)
    frame[SURVEY_YEAR_COLUMN] = [
        jalali_year_label(timestamp) for timestamp in pd.to_datetime(frame["timestamp"], utc=True)
    ]
    return frame.sort_values("timestamp").reset_index(drop=True)


def survey_year_panel(series: pd.DataFrame) -> pd.DataFrame:
    """Summarise HBSIR coverage per Jalali survey year, in survey order.

    One row per survey year: its Jalali label, the year's canonical leap-aware
    Esfand 29/30 end, the Gregorian period end Gold actually stores (the
    auditable value), and how many HBSIR series and observations that year
    contributes.
    """
    columns = _survey_year_panel_columns()
    frame = survey_year_frame(series)
    if frame.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for label, group in frame.groupby(SURVEY_YEAR_COLUMN, sort=False):
        period_end = group["timestamp"].max().to_pydatetime()
        jalali_year = gregorian_to_jalali(period_end).year
        rows.append(
            {
                columns[0]: label,
                columns[1]: jalali_date_label(iranian_year_end(jalali_year)),
                columns[2]: period_end.date().isoformat(),
                columns[3]: int(group["indicator_id"].nunique()),
                columns[4]: len(group),
            }
        )
    return pd.DataFrame(rows)


def _survey_year_panel_columns() -> list[str]:
    """Column headers of :func:`survey_year_panel`, in display order."""
    return [
        t("table.survey_year"),
        t("table.survey_year_end"),
        t("table.period_end"),
        t("table.hbsir_indicators"),
        t("table.hbsir_observations"),
    ]


def _relative_poverty_note() -> str:
    """The relative-poverty note, with the pipeline's own multiplier in place.

    The multiplier is ``hbsir_parser.DEFAULT_POVERTY_LINE_K`` -- the value the ETL
    applies -- so the note cannot drift from the computed measure. The measure is
    explicitly *not* the official Iranian (calorie-based) poverty line.
    """
    return t(
        "warn.hbsir_relative_poverty",
        k=format_number(DEFAULT_POVERTY_LINE_K, digit_mode="fa"),
    )


def _render_hbsir_sections(series: pd.DataFrame) -> None:
    """Render the HBSIR emphasis sections: trend, decile shares, survey years."""
    trend = _hbsir_subset(series, HBSIR_GINI_POVERTY_INDICATORS)
    st.subheader(t("section.hbsir_gini_poverty"))
    if trend.empty:
        st.info(t("empty.no_hbsir_observations"))
    else:
        st.plotly_chart(
            build_survey_year_chart(survey_year_frame(trend)),
            use_container_width=True,
        )

    deciles = _hbsir_subset(series, tuple(DECILE_INDICATORS))
    st.subheader(t("section.hbsir_deciles"))
    if deciles.empty:
        st.info(t("empty.no_hbsir_observations"))
    else:
        st.plotly_chart(
            build_survey_year_chart(survey_year_frame(deciles), facet_indicators=False),
            use_container_width=True,
        )

    st.subheader(t("section.hbsir_survey_years"))
    panel = survey_year_panel(_hbsir_subset(series, HBSIR_INDICATORS))
    if panel.empty:
        st.info(t("empty.no_hbsir_observations"))
    else:
        st.dataframe(panel, use_container_width=True, hide_index=True)


def _hbsir_subset(series: pd.DataFrame, indicator_ids: tuple[str, ...]) -> pd.DataFrame:
    """Rows of a loaded frame restricted to the given ids (empty-safe)."""
    if series.empty or "indicator_id" not in series.columns:
        return pd.DataFrame()
    return series[series["indicator_id"].isin(indicator_ids)]


def _load_series(
    indicator_ids: list[str],
    start_date: datetime,
    end_date: datetime,
    repository: DashboardRepository | None,
) -> pd.DataFrame:
    """Load Gold observations for an id selection through the repository seam."""
    if not indicator_ids:
        return pd.DataFrame()
    if repository is None:
        return cached_load_series(tuple(indicator_ids), start_date, end_date)
    return repository.load_series(list(indicator_ids), start_date, end_date)


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
