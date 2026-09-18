"""Composable page-rendering functions used by Streamlit page modules."""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Final

import pandas as pd
import streamlit as st

from dashboard.components.charts import (
    CHART_MODES,
    SURVEY_YEAR_COLUMN,
    ScaledChart,
    build_scaled_time_series_chart,
    build_survey_year_chart,
    build_time_series_chart,
)
from dashboard.components.exports import render_chart_downloads, render_data_downloads
from dashboard.components.filters import FilterState, render_filters
from dashboard.components.quality import render_quality_summary, summarize_quality
from dashboard.components.tables import cap_table_rows
from dashboard.formatting import (
    format_number,
    gregorian_to_jalali,
    jalali_date_label,
    jalali_year_label,
)
from dashboard.i18n import t
from dashboard.labels import indicator_label
from dashboard.queries import (
    cached_coverage_summary,
    cached_list_derived_ids,
    cached_list_indicators,
    cached_load_series,
    cached_source_freshness,
)
from dashboard.repository import (
    SERIES_KIND_BASE,
    SERIES_KIND_DERIVED,
    DashboardRepository,
)
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

#: The Market page's domain. The level series has a catalog row; the platform's
#: derived series (``RET1D``/``MA30``/``.ME``) do not, which is why they are
#: discovered from Gold metadata rather than from the catalog or an id pattern.
MARKET_DOMAIN: Final[str] = "market"

#: Gold frequency of the ``.ME`` month-end downsample. The split between the
#: daily derived series and the downsample uses this stored value, never an id.
MARKET_MONTHLY_FREQUENCY: Final[str] = "monthly"

#: The Labor page's domain. SCI publishes the labour-force unemployment rate for
#: one quarter per release, so the domain is legitimately a single-observation
#: series and the page renders it without implying a trend.
LABOR_DOMAIN: Final[str] = "labor"


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
    if st.checkbox(t("filter.include_derived"), key=f"{key_prefix}_derived"):
        selected_ids.extend(
            derived_series_ids(filters.indicator_ids, repository, exclude=selected_ids)
        )
    if not selected_ids:
        st.info("Select one or more indicators to view Gold observations.")
        return
    if filters.start_date > filters.end_date:
        return
    series = _load_series(selected_ids, filters.start_date, filters.end_date, repository)
    _render_series_section(series, key_prefix)


def render_market_page(repository: DashboardRepository | None = None) -> None:
    """Render the Market (TSETMC) page: the index level plus its derived Gold series.

    Gold is the only analytical input. The level series comes from the catalog
    (domain ``market``); the platform-computed series (``RET1D``, ``MA30`` and the
    ``.ME`` month-end downsample) have no catalog row because
    ``connector.discover()`` never emits derived ids, so they are discovered from
    Gold's ``record_metadata["derived_from"]`` through the repository (Task 7) --
    never from a hardcoded id list and never from parsing an indicator id.

    Nothing is interpolated, forward-filled, resampled or zero-filled: an absent
    trading session is an absent observation, and the ``.ME`` rows are presented
    exactly as the ETL stamped them (calendar month end, monthly frequency).
    """
    st.title(t("page.market"))
    _render_market_notes()
    if repository is None:
        catalog = cached_list_indicators(domains=(MARKET_DOMAIN,))
    else:
        catalog = repository.list_indicators(domains=[MARKET_DOMAIN])
    if catalog.empty:
        st.info(t("empty.no_indicators_for_page"))
        return
    filters = render_filters(catalog, "market", list(catalog["indicator_id"]))
    if not filters.indicator_ids:
        st.info(t("empty.select_indicators"))
        return
    if filters.start_date > filters.end_date:
        return
    series = _load_market_series(filters, repository)
    if series.empty:
        st.info(t("empty.no_observations"))
        return
    level, daily_derived, month_end = market_series_groups(series)
    _render_market_level(level)
    _render_market_derived_panels(daily_derived, "market_derived")
    _render_market_derived_panels(month_end, "market_month_end")


def market_series_groups(
    series: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split loaded market Gold rows into level, daily-derived and month-end groups.

    The split is metadata-driven and adds nothing: ``series_kind`` (which the
    repository derives from ``record_metadata["derived_from"]``) separates the
    collected level from the platform-computed rows, and the Gold ``frequency``
    column separates the ``.ME`` month-end downsample from the daily derived
    series. No indicator id is parsed, no row is filled, and no value is changed.

    Args:
        series: Gold observations as returned by the repository (or an empty
            frame, and frames without the classification columns)

    Returns:
        ``(level, daily_derived, month_end)`` frames, in that order
    """
    if series.empty:
        empty = pd.DataFrame()
        return empty, empty.copy(), empty.copy()
    kinds = series.get("series_kind", pd.Series(SERIES_KIND_BASE, index=series.index))
    frequencies = series.get("frequency", pd.Series("", index=series.index))
    derived = kinds == SERIES_KIND_DERIVED
    month_end = frequencies.astype(str) == MARKET_MONTHLY_FREQUENCY
    return (
        series[~derived].copy(),
        series[derived & ~month_end].copy(),
        series[derived & month_end].copy(),
    )


def _render_market_notes() -> None:
    """Render the TSETMC caveats: derivedness, absent sessions, warm-up, downsample."""
    st.warning(t("warn.tsetmc_derived_not_official"))
    st.info(t("warn.tsetmc_trading_days_absent"))
    st.info(t("warn.tsetmc_ma30_warmup"))
    st.info(t("warn.tsetmc_month_end"))
    st.info(t("warn.tsetmc_deferred_metrics"))


def _load_market_series(
    filters: FilterState,
    repository: DashboardRepository | None,
) -> pd.DataFrame:
    """Load the selected market levels plus every derived series Gold records."""
    parent_ids = list(filters.indicator_ids)
    derived_ids = derived_series_ids(parent_ids, repository, exclude=parent_ids)
    return _load_series(
        [*parent_ids, *derived_ids], filters.start_date, filters.end_date, repository
    )


def _render_market_level(level: pd.DataFrame) -> None:
    """Render the daily index level with the session expectation it defines."""
    st.subheader(t("section.market_level"))
    if level.empty:
        st.info(t("empty.no_observations"))
        return
    st.metric(t("metric.market_sessions"), format_number(len(level)))
    _render_market_figure_and_rows(level, "market_level")
    # The trading-session expectation describes the collection itself, so it is
    # computed on the level series only. A derived series legitimately starts
    # later (first-session return, moving-average warm-up, month-end downsample),
    # so comparing its row count against a session estimate would report a
    # construction artifact as missing data -- exactly what MA30 must not show.
    render_quality_summary(
        summarize_quality(
            level,
            level["timestamp"].min().to_pydatetime(),
            level["timestamp"].max().to_pydatetime(),
        )
    )


def _render_market_derived_panels(series: pd.DataFrame, key_prefix: str) -> None:
    """Render one labelled panel per platform-computed market series.

    The panel title comes from the presentation label layer and always names the
    parent series *and* the derivation, so a daily return, a moving average or a
    month-end downsample is never presented as the index level. Each series gets
    its own chart, and therefore its own y-axis, so a rate never shares an axis
    with a level.
    """
    for order, (_, rows) in enumerate(series.groupby("indicator_id", sort=False)):
        st.subheader(market_series_label(rows))
        _render_market_figure_and_rows(rows, f"{key_prefix}_{order}")


def market_series_label(series: pd.DataFrame) -> str:
    """Persian panel label of one loaded series, resolved by the label layer.

    Derivedness and the parent id come from the Gold row's ``derived_from``
    column (metadata-written), never from parsing the id: the id is only used to
    pick a suffix fragment for a row that is already known to be derived.

    Args:
        series: Rows of a single indicator (only the first row is read)

    Returns:
        The parent display name plus the derivation, or the level's own label
    """
    if series.empty:
        return ""
    row = series.iloc[0]
    return indicator_label(
        str(row["indicator_id"]),
        _optional_text(row, "name"),
        _optional_text(row, "derived_from"),
    )


def _optional_text(row: pd.Series, column: str) -> str | None:
    """Value of a row's column as text, or ``None`` when absent/null."""
    value = row.get(column)
    if value is None or not isinstance(value, str):
        return None
    return value.strip() or None


def _render_market_figure_and_rows(series: pd.DataFrame, key_prefix: str) -> None:
    """Chart one facet per indicator, then its observation table and downloads.

    :func:`build_time_series_chart` gives every indicator its own facet with its
    own y-axis, so a daily return or a moving average is never drawn on the index
    level's axis. The observation grid is a bounded preview (Task 15's row cap);
    the downloads keep every row.
    """
    figure = build_time_series_chart(series)
    st.plotly_chart(figure, use_container_width=True)
    with st.expander(t("section.observations"), expanded=False):
        _render_capped_rows(series)
    render_data_downloads(series, f"iran-macro-{key_prefix}")
    render_chart_downloads(figure, f"iran-macro-{key_prefix}-chart")


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


def render_labor_page(repository: DashboardRepository | None = None) -> None:
    """Render the Labor page, owner of the whole ``labor`` domain.

    SCI publishes the labour-force unemployment rate for one quarter per release,
    so the domain is legitimately sparse (the catalog observes a single spring
    1405 quarter). The composition therefore reads the whole domain from the
    catalog, defaults the selection to it, and renders through the shared Gold
    path: nothing is interpolated, extrapolated or zero-filled, and a lone
    quarter is presented as one marker with its quality row rather than an
    implied trend. The unemployment series carries no derived Gold rows today, so
    the "Include derived series" control is inert until the ETL publishes one --
    exactly as it behaves for every other domain without derived rows.
    """
    st.title(t("page.labor"))
    st.info(t("warn.labor_publication"))
    domain_list = [LABOR_DOMAIN]
    if repository is None:
        catalog = cached_list_indicators(domains=tuple(domain_list))
    else:
        catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        st.info(t("empty.no_indicators_for_page"))
        return
    render_domain_body(
        domain_list,
        "labor",
        list(catalog["indicator_id"]),
        repository=repository,
        catalog=catalog,
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
    scaled = _render_scaled_chart(series, key_prefix)
    render_quality_summary(quality)
    with st.expander("Observations", expanded=False):
        _render_capped_rows(series)
    render_data_downloads(series, f"iran-macro-{key_prefix}")
    render_chart_downloads(scaled.figure, f"iran-macro-{key_prefix}-chart")


def _render_scaled_chart(series: pd.DataFrame, key_prefix: str) -> ScaledChart:
    """Render the opt-in chart-mode control and the scaled figure.

    The default mode is per-indicator facets, so a page that never touches the
    control renders exactly as before. Overlay and small multiples are opt-in;
    the builder falls back to facets (with a visible notice) when an overlay
    would share an axis across different units, and caps the small-multiples
    grid at the documented series count.
    """
    mode = st.selectbox(
        t("chart.mode"),
        CHART_MODES,
        format_func=_chart_mode_label,
        key=f"{key_prefix}_chart_mode",
    )
    scaled = build_scaled_time_series_chart(series, mode=mode)
    if scaled.notice:
        st.info(scaled.notice)
    st.plotly_chart(scaled.figure, use_container_width=True)
    return scaled


def _chart_mode_label(mode: str) -> str:
    """Persian label of a chart mode, keyed by the mode slug."""
    return t(f"chart.mode.{mode}")


def _render_capped_rows(series: pd.DataFrame) -> None:
    """Render the observations grid as a bounded preview with a truncation hint.

    The cap is presentation-only: it never changes a value, a column or the
    timezone-aware ``timestamp`` column, and the exports and the quality summary
    still describe the full selection.
    """
    capped = cap_table_rows(series)
    if capped.truncated:
        st.info(
            t(
                "table.rows_capped",
                shown=format_number(capped.shown_rows),
                total=format_number(capped.total_rows),
            )
        )
    st.dataframe(capped.frame, use_container_width=True, hide_index=True)


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


def derived_series_ids(
    parent_ids: Iterable[str],
    repository: DashboardRepository | None,
    *,
    exclude: Iterable[str] = (),
) -> list[str]:
    """Discover the derived Gold ids of ``parent_ids`` from Gold metadata.

    Derivedness is read from the ETL-written ``record_metadata["derived_from"]``
    through the repository (or its cached query seam), so the discovery is
    independent of indicator-id prefixes and suffixes, of the suffix map and of
    the catalog: a derived series without a catalog row is still returned, and a
    new derivation strategy becomes visible without a dashboard change. Ids in
    ``exclude`` -- normally the caller's current selection -- are never returned,
    so a derived series cannot be appended twice.

    Args:
        parent_ids: Selected parent indicator ids (duplicates are ignored)
        repository: Repository seam, or ``None`` for the cached query wrapper
        exclude: Ids already selected, dropped from the result

    Returns:
        Derived Gold ids, in the repository's order, without duplicates
    """
    parents = list(dict.fromkeys(parent_ids))
    if not parents:
        return []
    discovered = (
        cached_list_derived_ids(tuple(parents))
        if repository is None
        else repository.list_derived_ids(parents)
    )
    excluded = set(exclude)
    return [indicator_id for indicator_id in discovered if indicator_id not in excluded]


def _display_timestamp(value: object) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, datetime | date | pd.Timestamp):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return str(value)
