"""Composable page-rendering functions used by Streamlit page modules."""

import math
from collections.abc import Callable, Hashable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Final, NamedTuple

import pandas as pd
import streamlit as st

from dashboard.components.charts import (
    CHART_MODE_SMALL_MULTIPLES,
    CHART_MODES,
    SURVEY_YEAR_COLUMN,
    ScaledChart,
    build_chain_linking_chart,
    build_scaled_time_series_chart,
    build_survey_year_chart,
    build_time_series_chart,
)
from dashboard.components.exports import render_chart_downloads, render_data_downloads
from dashboard.components.filters import FilterState, render_filters, unique_values
from dashboard.components.html_table import (
    Cell,
    Dot,
    Ltr,
    Text,
    Tone,
    TwoLine,
    UnitChip,
    render_html_table,
)
from dashboard.components.layout import (
    BarRow,
    KpiCell,
    render_bar_list,
    render_callout,
    render_callout_stack,
    render_filter_bar,
    render_kpi_band,
    render_page_header,
    render_section_header,
    status_chip_cell,
)
from dashboard.components.quality import render_quality_summary, summarize_quality
from dashboard.components.states import render_empty
from dashboard.components.tables import (
    OBSERVATIONS_ROW_HEIGHT,
    cap_table_rows,
    localize_table_frame,
)
from dashboard.formatting import (
    RANGE_SEPARATOR,
    format_number,
    gregorian_to_jalali,
    jalali_date_label,
    jalali_year_label,
    range_label,
    relative_time_label,
    tehran_clock_label,
    tehran_timestamp_label,
    to_ascii_digits,
    to_persian_digits,
)
from dashboard.i18n import t
from dashboard.labels import (
    DERIVED_SUFFIX_LABELS,
    SOURCE_CALENDAR,
    derived_label,
    domain_label,
    frequency_label,
    indicator_label,
    source_expected_cadence,
    source_label,
)
from dashboard.queries import (
    cached_available_domains,
    cached_coverage_summary,
    cached_list_derived_ids,
    cached_list_indicators,
    cached_load_series,
    cached_series_inventory,
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
from src.connectors.sci_scraper import SCI_CANONICAL_INDICATORS, SCI_INDICATOR_REGISTRY
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

#: The SCI publication key whose members are the ten household-expenditure-decile
#: CPI series. The ids come from the connector's authoritative registry
#: (``src/connectors/sci_scraper.py``) rather than a list invented in the
#: dashboard, so a registry change is reflected without a page edit.
SCI_DECILE_PUBLICATION: Final[str] = "cpi_decile"

#: The ten expenditure-decile CPI ids (``SCI.CPI.DECILE.B2021.D1`` … ``D10``), in
#: the registry's order. They are ten separate catalog indicators with an
#: identical unit and a shared base year, which is why the Inflation page groups
#: them into one comparison instead of presenting ten unrelated series.
SCI_DECILE_INDICATORS: Final[tuple[str, ...]] = tuple(
    SCI_INDICATOR_REGISTRY[SCI_DECILE_PUBLICATION].member_ids
)

#: The canonical chain-linked CPI ids (national, urban, rural), in the registry's
#: order. The canonical ids -- not the inactive ``B<year>`` segments -- are what
#: Gold publishes and the catalog marks active.
SCI_CANONICAL_CPI_INDICATORS: Final[tuple[str, ...]] = tuple(SCI_CANONICAL_INDICATORS)

#: Default selection of the Inflation page's generic composition: the World Bank
#: headline CPI, exactly as before the decile view landed. The SCI decile and
#: canonical series have their own dedicated sections, so they are not selected
#: here by default.
INFLATION_DEFAULT_INDICATORS: Final[tuple[str, ...]] = ("FP.CPI.TOTL.ZG",)

#: The Inflation page's domain. Both the World Bank/IMF headline CPIs and the SCI
#: canonical and decile CPI series are catalog domain ``inflation``.
INFLATION_DOMAIN: Final[str] = "inflation"

#: Session-state keys of the catalog page's filter and search widgets. The
#: clear-filters button resets exactly these; the inactive-segment toggle is a view
#: control, not a filter, so it is deliberately not in the list.
CATALOG_FILTER_STATE_KEYS: Final[tuple[str, ...]] = (
    "catalog_domains",
    "catalog_frequencies",
    "catalog_sources",
    "catalog_indicators",
    "catalog_start",
    "catalog_end",
    "catalog_jalali_year",
    "catalog_jalali_month",
    "catalog_jalali_day",
    "catalog_search",
)


def render_domain_page(
    title_key: str,
    domains: Iterable[str],
    key_prefix: str,
    default_indicators: list[str] | None = None,
    repository: DashboardRepository | None = None,
) -> None:
    """Render a domain-specific Gold exploration page.

    The page opens with the shared page header (D11), so the two pages that use
    this composition -- GDP & Economy and Trade & Energy -- draw the same header
    shape as every other migrated page and the D11 guard can check them. Neither
    page has a caveat, so no callout is rendered; a page that needs one (FX & Gold,
    Labor) composes its own header through :func:`render_fx_gold_page` /
    :func:`render_labor_page`.

    Args:
        title_key: Catalog key of the page title (``page.<key>``), not a resolved
            string: :func:`render_page_header` resolves it
        domains: Catalog domains the page owns
        key_prefix: Widget-key prefix for the page's filters
        default_indicators: Ids selected by default, when any
        repository: Repository seam, or ``None`` for the cached query wrappers
    """
    render_page_header(title_key)
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

    The composition is the A2 archetype (D11): the shared filter set, then the
    chart, quality and observations sections through the shared components. Every
    empty case goes through :func:`dashboard.components.states.render_empty`, so a
    page never hand-rolls an informational alert.
    """
    domain_list = list(domains)
    if catalog is None:
        if repository is None:
            catalog = cached_list_indicators(domains=tuple(domain_list))
        else:
            catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        render_empty("empty.no_indicators_for_page")
        return
    if filters is None:
        filters = render_filters(catalog, key_prefix, default_indicators)
    selected_ids = list(filters.indicator_ids)
    if st.checkbox(t("filter.include_derived"), key=f"{key_prefix}_derived"):
        selected_ids.extend(
            derived_series_ids(filters.indicator_ids, repository, exclude=selected_ids)
        )
    if not selected_ids:
        render_empty("empty.select_indicators")
        return
    if filters.start_date > filters.end_date:
        return
    series = _load_series(selected_ids, filters.start_date, filters.end_date, repository)
    _render_series_section(series, key_prefix)


def render_inflation_page(repository: DashboardRepository | None = None) -> None:
    """Render the Inflation page: the CPI decile and canonical views, then Gold.

    The page owns the ``inflation`` domain. Two emphasis sections make the SCI
    CPI structure explicit -- the ten expenditure deciles (ten catalog indicators
    that share one unit and one base year, so a plain comparison is honest and
    needs no normalization) and the canonical chain-linked national/urban/rural
    series -- and the generic domain composition below them keeps the World
    Bank/IMF and every other inflation series reachable. Nothing is interpolated,
    normalized or resampled: Gold rows are drawn exactly as stored.

    The composition follows the D11 layout contract (Task 38): the page header,
    the shared section headers, and the shared empty/notice states. The filter
    set is unchanged (:func:`render_filters`), so the selection, the chart modes
    and every value are exactly as before.
    """
    render_page_header("page.inflation")
    if repository is None:
        catalog = cached_list_indicators(domains=(INFLATION_DOMAIN,))
    else:
        catalog = repository.list_indicators(domains=[INFLATION_DOMAIN])
    if catalog.empty:
        render_empty("empty.no_indicators_for_page")
        return
    filters = render_filters(catalog, "inflation", list(INFLATION_DEFAULT_INDICATORS))
    _render_cpi_decile_section(catalog, filters, repository)
    _render_cpi_canonical_section(catalog, filters, repository)
    _render_chain_linking_section(catalog, filters, repository)
    render_section_header("section.inflation_all_indicators")
    render_domain_body(
        (INFLATION_DOMAIN,),
        "inflation",
        list(INFLATION_DEFAULT_INDICATORS),
        repository=repository,
        catalog=catalog,
        filters=filters,
    )


def cpi_decile_ids(catalog: pd.DataFrame) -> list[str]:
    """The catalog's SCI expenditure-decile CPI ids, in registry order.

    The ids come from the connector registry (Task 13's metadata-driven rule),
    so the view never hardcodes the ten decile ids.
    """
    return _registered_ids(catalog, SCI_DECILE_INDICATORS)


def cpi_canonical_ids(catalog: pd.DataFrame) -> list[str]:
    """The catalog's canonical chain-linked CPI ids, in registry order."""
    return _registered_ids(catalog, SCI_CANONICAL_CPI_INDICATORS)


def _registered_ids(catalog: pd.DataFrame, registered: tuple[str, ...]) -> list[str]:
    """Registry ids that have a row in ``catalog``, in registry order (empty-safe)."""
    if catalog.empty or "indicator_id" not in catalog.columns:
        return []
    present = set(catalog["indicator_id"].astype(str))
    return [indicator_id for indicator_id in registered if indicator_id in present]


def _render_cpi_decile_section(
    catalog: pd.DataFrame,
    filters: FilterState,
    repository: DashboardRepository | None,
) -> None:
    """Render the ten expenditure-decile CPI series as one comparison.

    The deciles share a unit (an index) and a base year, so a plain comparison is
    honest and no normalization is applied. The comparison is drawn through the
    Task 15 small-multiples mode -- one unit-safe panel per decile -- rather than
    through the generic multi-indicator chart, which would force ten unrelated
    facets onto the page's main selection.
    """
    render_section_header("section.cpi_deciles")
    decile_ids = cpi_decile_ids(catalog)
    if not decile_ids:
        render_empty("empty.no_cpi_deciles")
        return
    selected = st.multiselect(
        t("filter.cpi_deciles"),
        options=decile_ids,
        default=decile_ids,
        format_func=indicator_label,
        key="inflation_deciles",
    )
    if not selected:
        render_callout("empty.select_indicators", tone="info", container_key="cpi-deciles")
        return
    series = _load_series(list(selected), filters.start_date, filters.end_date, repository)
    if series.empty:
        render_callout("empty.no_observations", tone="info", container_key="cpi-deciles")
        return
    render_callout("warn.cpi_deciles_shared_base", tone="info")
    scaled = build_scaled_time_series_chart(series, mode=CHART_MODE_SMALL_MULTIPLES)
    if scaled.notice:
        # The notice carries values, so its resolved text passes through ``body``
        # and the key is the container hook only. A distinct container key keeps
        # it from colliding with the generic composition's chart notice.
        render_callout(
            "chart.notice",
            tone="info",
            body=scaled.notice,
            container_key="cpi-deciles-chart-notice",
        )
    st.plotly_chart(scaled.figure, use_container_width=True)


def _render_cpi_canonical_section(
    catalog: pd.DataFrame,
    filters: FilterState,
    repository: DashboardRepository | None,
) -> None:
    """Render the canonical chain-linked national/urban/rural CPI comparison.

    The canonical series are the chain-linked Gold output (the inactive
    ``B<year>`` segments stay off the dashboard), drawn through
    :func:`build_time_series_chart` so each keeps its own panel and axis.
    """
    render_section_header("section.cpi_canonical")
    canonical_ids = cpi_canonical_ids(catalog)
    if not canonical_ids:
        render_empty("empty.no_cpi_canonical")
        return
    series = _load_series(canonical_ids, filters.start_date, filters.end_date, repository)
    if series.empty:
        render_callout("empty.no_observations", tone="info", container_key="cpi-canonical")
        return
    st.plotly_chart(build_time_series_chart(series), use_container_width=True)


def chain_linked_catalog_ids(catalog: pd.DataFrame) -> list[str]:
    """Catalog ids whose stored base-year flag marks them as chain-linked.

    The flag is the catalog's own ``has_base_year_changes`` column, read as
    stored: the dashboard never re-derives whether a series was chain-linked.
    """
    if catalog.empty or "has_base_year_changes" not in catalog.columns:
        return []
    flagged = catalog["has_base_year_changes"].fillna(False).astype(bool)
    return [str(indicator) for indicator in catalog.loc[flagged, "indicator_id"]]


def chain_linking_provenance(catalog: pd.DataFrame) -> pd.DataFrame:
    """Per chain-linked indicator: display name, base-year badge, years and segments.

    The badge is the catalog's stored ``has_base_year_changes`` flag, the nominal
    base years are the catalog's stored ``base_years`` value, and the segment
    ancestry comes from the connector registry
    (:data:`SCI_CANONICAL_INDICATORS`) rather than from a dashboard id list, so a
    registry change is reflected without a page edit. Nothing is recomputed.
    """
    columns = [
        t("table.name"),
        t("table.has_base_year_changes"),
        t("table.base_years"),
        t("table.base_year_segments"),
    ]
    rows: list[dict[str, str]] = []
    for row in catalog.to_dict("records"):
        indicator_id = str(row["indicator_id"])
        canonical = SCI_CANONICAL_INDICATORS.get(indicator_id)
        segments = (
            "، ".join(indicator_label(segment) for segment in canonical.segment_ids)
            if canonical is not None
            else ""
        )
        rows.append(
            {
                columns[0]: indicator_label(indicator_id, _catalog_name(row)),
                columns[1]: _flag_label(row.get("has_base_year_changes")),
                columns[2]: _base_years_text(row.get("base_years")),
                columns[3]: segments,
            }
        )
    return pd.DataFrame(rows, columns=columns)


class ChainLinkingProvenanceTable(NamedTuple):
    """The chain-linking provenance table ready for ``render_html_table``.

    Attributes:
        columns: Localized column headers, in
            :func:`chain_linking_provenance`'s order
        rows: One tuple of typed cells per chain-linked indicator
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


def build_chain_linking_provenance_rows(
    frame: pd.DataFrame,
) -> ChainLinkingProvenanceTable:
    """Build the provenance table as typed cells from the localized frame.

    The frame is the output of :func:`chain_linking_provenance`, whose cells are
    already Persian display text (the indicator label, the Persian yes/no flag,
    the Persian-digit base years and the joined segment ancestry). Each value
    therefore maps to a plain :class:`~dashboard.components.html_table.Text`
    cell, so the rendered table is byte-identical to the grid it replaces; a null
    (never produced today) falls back to the shared em-dash through ``Text(None)``.

    Args:
        frame: Frame from :func:`chain_linking_provenance`

    Returns:
        A :class:`ChainLinkingProvenanceTable`; an empty frame yields no columns
        and no rows
    """
    if frame.empty:
        return ChainLinkingProvenanceTable((), ())
    rows = tuple(
        tuple(_provenance_cell(value) for value in row)
        for row in frame.itertuples(index=False, name=None)
    )
    return ChainLinkingProvenanceTable(tuple(str(column) for column in frame.columns), rows)


def _provenance_cell(value: object) -> Cell:
    """One provenance cell: plain text, or the shared em-dash for a null."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return Text(None)
    return Text(str(value))


def _flag_label(value: object) -> str:
    """Display a stored boolean flag as the Persian yes/no, never inventing a yes."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return t("value.no")
    return t("value.yes") if bool(value) else t("value.no")


def _base_years_text(value: object) -> str:
    """Display a stored ``base_years`` value, or the unknown placeholder when absent."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return t("value.unknown")
    if isinstance(value, list | tuple):
        return "، ".join(to_persian_digits(str(year)) for year in value)
    return str(value)


def _render_chain_linking_section(
    catalog: pd.DataFrame,
    filters: FilterState,
    repository: DashboardRepository | None,
) -> None:
    """Surface the stored chain-linking provenance and the original-vs-linked panel.

    Everything shown is read from Gold as stored: the chart draws
    ``original_value`` against ``value`` for rows with ``is_chain_linked`` set,
    the provenance table shows the catalog's base-year flag and years plus the
    registry's segment ancestry, and the observations grid carries
    ``chain_linking_confidence`` and ``record_metadata`` unchanged. No value is
    recomputed, interpolated or normalized.
    """
    render_section_header("section.chain_linking")
    render_callout("warn.chain_linking_stored", tone="info")
    chain_ids = chain_linked_catalog_ids(catalog)
    if not chain_ids:
        render_empty("empty.no_chain_linked")
        return
    flagged = catalog[catalog["indicator_id"].isin(chain_ids)]
    provenance = build_chain_linking_provenance_rows(chain_linking_provenance(flagged))
    render_html_table(provenance.columns, provenance.rows, variant="coverage")
    render_callout("warn.chain_linking_overlap", tone="info")
    series = _load_series(chain_ids, filters.start_date, filters.end_date, repository)
    if series.empty:
        render_callout(
            "empty.no_chain_linked_observations",
            tone="info",
            container_key="chain-linking",
        )
        return
    figure = build_chain_linking_chart(series)
    if not figure.data:
        render_callout(
            "empty.no_chain_linked_observations",
            tone="info",
            container_key="chain-linking-figure",
        )
        return
    st.plotly_chart(figure, use_container_width=True)
    with st.expander(t("section.observations"), expanded=False):
        _render_capped_rows(series, "chain_linking")


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

    The composition follows the D11 layout contract (Task 40): the page header
    and the five TSETMC caveats through shared components (``render_page_header``
    + ``render_callout_stack``), the sessions metric through a small KPI band,
    the level section header through ``render_section_header``, and the empty
    states through shared callouts. The filter set is unchanged, so the selection
    and every value are exactly as before.
    """
    render_page_header("page.market")
    _render_market_notes()
    if repository is None:
        catalog = cached_list_indicators(domains=(MARKET_DOMAIN,))
    else:
        catalog = repository.list_indicators(domains=[MARKET_DOMAIN])
    if catalog.empty:
        render_empty("empty.no_indicators_for_page")
        return
    filters = render_filters(catalog, "market", list(catalog["indicator_id"]))
    if not filters.indicator_ids:
        render_callout("empty.select_indicators", tone="info", container_key="market-select")
        return
    if filters.start_date > filters.end_date:
        return
    series = _load_market_series(filters, repository)
    if series.empty:
        render_callout("empty.no_observations", tone="info", container_key="market-no-obs")
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
    """Render the TSETMC caveats: derivedness, absent sessions, warm-up, downsample.

    The five caveats are a ``render_callout_stack`` (one warning + four info
    callouts), so the page header's caveat block is the D11 shared component
    rather than five raw ``st.warning``/``st.info`` calls.
    """
    render_callout_stack(
        (
            ("warn.tsetmc_derived_not_official", "warn"),
            ("warn.tsetmc_trading_days_absent", "info"),
            ("warn.tsetmc_ma30_warmup", "info"),
            ("warn.tsetmc_month_end", "info"),
            ("warn.tsetmc_deferred_metrics", "info"),
        )
    )


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
    render_section_header("section.market_level")
    if level.empty:
        render_callout("empty.no_observations", tone="info", container_key="market-level")
        return
    render_kpi_band(
        [KpiCell("metric.market_sessions", format_number(len(level)))],
        key="market-level",
    )
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
        _render_capped_rows(series, key_prefix)
    render_data_downloads(series, f"iran-macro-{key_prefix}")
    render_chart_downloads(figure, f"iran-macro-{key_prefix}-chart")


def render_catalog_page(repository: DashboardRepository | None = None) -> None:
    """Render the searchable indicator catalog.

    The inactive-segment toggle re-queries with ``active_only=False`` so the four
    seeded SCI base-year segments are inspectable; search matches the catalog's
    own values (id, name, unit, source, domain) *and* the Persian display labels
    from :mod:`dashboard.labels`, because a Persian needle lives in the label
    layer rather than in the catalog. The SQL ``search`` path is exercised for
    catalog columns and unioned with the label-layer match, so neither path can
    hide a row the other would find.

    The page opens with ``render_page_header``. The filter bar hosts only the
    **three simple controls** — the search box, the inactive-segment toggle and the
    clear button — with proportional column weights that give the search field the
    widest column (Wave H P1); the shared filter set is a tall stack of widgets, so
    :func:`render_filters` returns to **full width** beneath the bar, in its
    original position. The toggle's current value is read from
    ``st.session_state`` **before** the bar renders (the Overview coverage bar's
    pattern), so the catalog frame the count and grid describe is the one the
    toggle describes in the same run; the controls write the same keys back. The
    toggle is rendered by the bar **before** the empty-catalog check, so it stays
    visible even when the catalog is empty (its pre-Task-44 behaviour). Every
    widget key, the clear button's ``on_click`` callback and the reset key list are
    unchanged. The matching count is a one-cell ``render_kpi_band``; the grid stays
    a native ``st.dataframe`` (D1, sortable, LTR grid) with the shared density
    ``row_height``; an empty search result is the shared ``render_empty`` state.
    """
    render_page_header("page.catalog")
    include_inactive = bool(st.session_state.get("catalog_include_inactive", False))
    active_only = not include_inactive
    catalog = _catalog_frame(repository, active_only=active_only)

    def search_control() -> None:
        st.text_input(t("filter.search"), key="catalog_search")

    def inactive_control() -> None:
        st.checkbox(
            t("filter.include_inactive_segments"),
            key="catalog_include_inactive",
        )

    def clear_control() -> None:
        st.button(t("filter.clear"), key="catalog_clear_filters", on_click=_clear_catalog_filters)

    # The bar carries only the three simple controls (Wave H P1). The search field
    # takes the widest column; the toggle and the clear button are narrower. The
    # bar renders before the empty-catalog check so the toggle is never hidden by
    # an empty catalog.
    render_filter_bar(
        [search_control, inactive_control, clear_control],
        key="catalog",
        weights=[3.0, 2.0, 1.0],
    )
    if catalog.empty:
        render_empty("empty.catalog_empty")
        return

    # The shared filter set is full width, in its original position beneath the bar.
    filters = render_filters(catalog, "catalog")
    needle = str(st.session_state.get("catalog_search", ""))
    result = _apply_catalog_filters(catalog, filters)
    if needle.strip():
        result = _apply_catalog_search(result, catalog, needle, repository, active_only)
    render_kpi_band(
        [KpiCell("metric.matching_indicators", format_number(len(result)))],
        key="catalog",
    )
    if needle.strip() and result.empty:
        render_empty("empty.search_no_match")
    st.dataframe(
        localize_table_frame(result),
        use_container_width=True,
        hide_index=True,
        row_height=OBSERVATIONS_ROW_HEIGHT,
    )


def _catalog_frame(
    repository: DashboardRepository | None,
    *,
    active_only: bool,
    search: str | None = None,
) -> pd.DataFrame:
    """Fetch the catalog through the repository seam (or its cached wrapper)."""
    if repository is None:
        return cached_list_indicators(search=search, active_only=active_only)
    return repository.list_indicators(search=search, active_only=active_only)


def _apply_catalog_filters(catalog: pd.DataFrame, filters: FilterState) -> pd.DataFrame:
    """Apply the shared filter state to the catalog frame (empty-safe)."""
    result = catalog
    if filters.domains:
        result = result[result["domain"].isin(filters.domains)]
    if filters.frequencies:
        result = result[result["frequency"].isin(filters.frequencies)]
    if filters.sources:
        result = result[result["source_name"].isin(filters.sources)]
    if filters.indicator_ids:
        result = result[result["indicator_id"].isin(filters.indicator_ids)]
    return result


def _apply_catalog_search(
    result: pd.DataFrame,
    catalog: pd.DataFrame,
    needle: str,
    repository: DashboardRepository | None,
    active_only: bool,
) -> pd.DataFrame:
    """Restrict ``result`` to the union of SQL and label-layer search matches."""
    matched = _indicator_id_set(search_catalog(catalog, needle))
    matched |= _indicator_id_set(_catalog_frame(repository, active_only=active_only, search=needle))
    if not matched:
        return result.iloc[0:0]
    return result[result["indicator_id"].isin(matched)]


def _indicator_id_set(frame: pd.DataFrame) -> set[str]:
    """Indicator ids of a frame as a set, empty when the column is absent."""
    if frame.empty or "indicator_id" not in frame.columns:
        return set()
    return {str(indicator) for indicator in frame["indicator_id"]}


def normalise_search_needle(text: str) -> str:
    """Normalize a search needle for matching, never rewriting stored data.

    Persian/Arabic-Indic digits become ASCII (so ``۱۴۰۰`` finds ``1400``), Arabic
    yeh/kaf fold to their Persian forms (so a keyboard variant still matches a
    Persian label), and the result is case-folded for ASCII catalog values. Only
    the needle is rewritten; stored values are compared as-is.

    Examples:
        >>> normalise_search_needle("۱۴۰۰")
        '1400'
        >>> normalise_search_needle("  Inflation  ")
        'inflation'
    """
    normalized = to_ascii_digits(text.strip())
    normalized = normalized.replace("ي", "ی").replace("ك", "ک")
    return normalized.casefold()


def search_catalog(frame: pd.DataFrame, needle: str) -> pd.DataFrame:
    """Catalog rows matching ``needle`` across catalog values and display labels.

    The match covers the indicator id, the Persian display name, the catalog
    (English) name, the unit, the source and the domain -- each in both its stored
    slug and its Persian label form -- plus a known derived-series suffix label.
    An empty needle returns the frame unchanged.
    """
    normalized = normalise_search_needle(needle)
    if not normalized or frame.empty:
        return frame
    matched = [
        any(normalized in candidate for candidate in _search_terms(row))
        for row in frame.to_dict("records")
    ]
    return frame[matched]


def _search_terms(row: Mapping[Hashable, Any]) -> tuple[str, ...]:
    """Case-folded searchable strings of one catalog row (labels included)."""
    indicator_id = str(row.get("indicator_id", ""))
    catalog_name = _catalog_name(row)
    source_name = str(row.get("source_name") or "")
    domain = str(row.get("domain") or "")
    terms = [
        indicator_id,
        catalog_name or "",
        indicator_label(indicator_id, catalog_name),
        str(row.get("unit") or ""),
        source_name,
        source_label(source_name),
        domain,
        domain_label(domain),
    ]
    suffix = indicator_id.rsplit(".", 1)[-1]
    if suffix in DERIVED_SUFFIX_LABELS:
        terms.append(derived_label(suffix))
    return tuple(term.casefold() for term in terms if term)


def _catalog_name(row: Mapping[Hashable, Any]) -> str | None:
    """A catalog row's ``name`` as stripped text, or ``None`` when absent."""
    value = row.get("name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _clear_catalog_filters() -> None:
    """Reset the catalog page's filter and search widgets (button callback)."""
    for key in CATALOG_FILTER_STATE_KEYS:
        st.session_state.pop(key, None)


def render_overview_page(repository: DashboardRepository | None = None) -> None:
    """Render platform-wide counts, per-domain ownership and source freshness.

    The Overview is an all-domain view, so it owns no domain itself: it reports
    counts and links into the page that owns each domain. The per-domain counts
    come from a single query (:meth:`DashboardRepository.available_domains`), and
    the Gold-only derived/orphan series -- which have no catalog row and would
    therefore be invisible to any catalog-driven view -- come from
    :meth:`DashboardRepository.series_inventory`. Freshness is the latest
    ``DataCollectionLog`` row per source, annotated with a staleness verdict
    against the presentation cadence map in :mod:`dashboard.labels` (the platform
    does not store an expected frequency, so this is a dashboard convention).
    """
    render_page_header(
        "page.overview",
        callout_key="warn.forecasts_indistinguishable",
        label_key="note.methodology_label",
    )
    catalog = repository.list_indicators() if repository else cached_list_indicators()
    if catalog.empty:
        render_callout("warn.catalog_empty")
        return
    coverage = repository.coverage_summary() if repository else cached_coverage_summary()
    freshness = repository.source_freshness() if repository else cached_source_freshness()
    domain_counts = repository.available_domains() if repository else cached_available_domains()
    inventory = repository.series_inventory() if repository else cached_series_inventory()

    observation_counts = coverage.get("observation_count")
    if observation_counts is None:
        total_observations = 0
    else:
        total_observations = int(pd.to_numeric(observation_counts, errors="coerce").fillna(0).sum())
    render_kpi_band(
        overview_kpi_cells(catalog, inventory, total_observations=total_observations),
        key="overview",
    )

    # One reference instant for the whole freshness section, so the verdict, the
    # summary and every relative age agree with each other.
    now = datetime.now(UTC)
    fresh, stale = freshness_summary(freshness, now=now)
    # The mockup's row: freshness in the wide column and the domain bars in the
    # narrow one. The keyed container declares `direction: rtl`, so the first
    # column is the rightmost, as in the mockup.
    with st.container(key="overview-row"):
        freshness_column, bars_column = st.columns([7, 5])
        with freshness_column:
            render_section_header(
                "section.source_freshness",
                trailing=(
                    None
                    if freshness.empty
                    else t(
                        "section.freshness_summary",
                        fresh=format_number(fresh),
                        stale=format_number(stale),
                    )
                ),
            )
            if freshness.empty:
                render_empty("empty.no_collection_runs")
            else:
                table = build_freshness_rows(freshness, now=now)
                render_html_table(table.columns, table.rows)
        with bars_column:
            render_section_header(
                "section.indicators_by_domain",
                trailing=t("table.indicator_count"),
            )
            _render_domain_counts(domain_counts)

    _render_coverage_section(coverage)


def series_inventory_counts(inventory: pd.DataFrame) -> tuple[int, int]:
    """Count the derived and catalog-less Gold series in a series inventory.

    Both are separate counts of the same ``series_inventory`` frame: the derived
    series are read from the ETL-written ``series_kind`` classification and the
    catalog-less series from ``has_catalog_metadata``. They are deliberately
    **not** deduplicated (D2) — a derived series normally has no catalog row, so
    the two sets overlap, and collapsing them would hide either signal.

    Returns:
        ``(derived, orphan)`` counts; both zero when the frame lacks the column
    """
    kinds = inventory.get("series_kind")
    has_catalog = inventory.get("has_catalog_metadata")
    derived = 0 if kinds is None else int((kinds == SERIES_KIND_DERIVED).sum())
    orphan = 0 if has_catalog is None else int((~has_catalog.astype(bool)).sum())
    return derived, orphan


def overview_kpi_cells(
    catalog: pd.DataFrame,
    inventory: pd.DataFrame,
    *,
    total_observations: int,
) -> list[KpiCell]:
    """The Overview's six KPI cells, in mockup order (right to left).

    Order matches the mockup: sources, domains, active indicators, Gold-layer
    observations, then the visually separated secondary group (derived series and
    series without a catalog row). The three annotated cells carry a data-agnostic
    tooltip, and the catalog-less cell carries the "نیازمند بررسی" tag.

    Args:
        catalog: The indicator catalog frame (its distinct domains and sources
            are the first two counts)
        inventory: The Gold series inventory frame
        total_observations: Catalog-linked Gold observation count, already summed
            by the caller

    Returns:
        One :class:`KpiCell` per band column, in display order
    """
    derived, orphan = series_inventory_counts(inventory)
    return [
        KpiCell("metric.sources", format_number(catalog["source_name"].nunique())),
        KpiCell("metric.domains", format_number(catalog["domain"].nunique())),
        KpiCell("metric.active_indicators", format_number(len(catalog))),
        KpiCell(
            "metric.gold_observations",
            format_number(total_observations),
            help_key="metric.gold_observations_help",
        ),
        KpiCell(
            "metric.derived_series",
            format_number(derived),
            help_key="metric.derived_series_help",
            tone="muted",
            secondary=True,
        ),
        KpiCell(
            "metric.orphan_series",
            format_number(orphan),
            help_key="metric.orphan_series_help",
            tone="muted",
            secondary=True,
            tag_key="metric.orphan_series_tag",
        ),
    ]


def ordered_domain_rows(domain_counts: pd.DataFrame) -> list[BarRow]:
    """Turn the ``available_domains`` frame into bar rows, count-descending.

    The mockup's bars are ordered by indicator count, largest first, and ties are
    broken by the domain's Persian display name ascending (the mockup's own tie
    order: ``تورم`` before ``رفاه`` at 15, ``ارز`` before ``بازار …`` at 1). A
    domain whose count is missing or non-numeric is treated as zero, never
    dropped, and the sort is stable so equal keys keep the frame's order.

    Args:
        domain_counts: Frame from ``available_domains`` with ``domain`` and
            ``indicator_count`` columns

    Returns:
        One :class:`BarRow` per domain, in display order
    """
    rows: list[BarRow] = []
    for row in domain_counts.itertuples(index=False):
        count = row.indicator_count
        rows.append(BarRow(str(row.domain), _domain_count(count)))
    rows.sort(key=lambda row: (-row.indicator_count, domain_label(row.domain)))
    return rows


def _domain_count(value: object) -> int:
    """A domain's indicator count as an int, treating a missing value as zero."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    if isinstance(value, float) and not math.isfinite(value):
        return 0
    return int(value)


def _render_domain_counts(domain_counts: pd.DataFrame) -> None:
    """Render the indicators-by-domain bar list, one row per domain.

    Rows come from ``available_domains`` through :func:`ordered_domain_rows`
    (count-descending, ties by domain display name ascending, as in the mockup).
    :func:`render_bar_list` reads each domain's owner from the navigation
    registry (:func:`page_for_domain`, the single declaration of domain ownership)
    and keeps it a native ``st.page_link`` beside the bar, so an owned domain stays
    navigable and visible to ``AppTest``; a domain without an owner stays visible
    as plain text rather than being dropped. The footer total is the sum of the
    row counts, computed from the data and formatted with Persian digits.
    """
    rows = ordered_domain_rows(domain_counts)
    total = sum(row.indicator_count for row in rows)
    render_bar_list(rows, t("metric.indicator_count", count=format_number(total)))


#: Session-state keys of the Overview coverage filter bar. The three filter keys
#: and the density key are read **before** the bar renders, so the frame the table
#: renders is the one the controls describe in the same run; the controls then
#: write the same keys back on the next interaction.
_COVERAGE_DOMAIN_KEY: Final[str] = "overview_coverage_domain"
_COVERAGE_SOURCE_KEY: Final[str] = "overview_coverage_source"
_COVERAGE_FREQUENCY_KEY: Final[str] = "overview_coverage_frequency"
_COVERAGE_DENSITY_KEY: Final[str] = "overview_coverage_density"

#: Row densities in the mockup's segmented-control order ("راحت" first). The
#: values are the HTML table's own density slugs, so the control's value passes
#: straight to ``render_html_table``; a test pins the pair against ``DENSITIES``.
_COVERAGE_DENSITIES: Final[tuple[str, ...]] = ("comfortable", "compact")


class CoverageTable(NamedTuple):
    """A coverage table ready for ``render_html_table``.

    Attributes:
        columns: Localized column headers, in mockup order
        rows: One tuple of typed cells per indicator, in the frame's order
        wrap_headers: The subset of ``columns`` the mockup renders on two lines
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]
    wrap_headers: tuple[str, ...]


def _optional_cell_text(value: object) -> str | None:
    """A stripped, non-empty string, or ``None`` for a null/blank/non-text value."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _optional_cell_number(value: Any) -> float | None:
    """A finite number, or ``None`` for a null, boolean or non-numeric value.

    ``value`` is typed ``Any`` because it arrives as an untyped pandas row
    attribute: a count is a Python ``int``, but ``avg``/``sum`` can come back as a
    ``Decimal``. ``pd.to_numeric`` is the same coercion the Overview's observation
    total uses, so a value the database returns as a ``Decimal`` or as a NumPy
    scalar is read as a number rather than silently rendered as missing.
    """
    if value is None or isinstance(value, bool):
        return None
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    number = float(numeric)
    return number if math.isfinite(number) else None


def _label_cell(value: object, label: Callable[[str], str]) -> Cell:
    """A text cell whose catalog slug is resolved through the label layer."""
    slug = _optional_cell_text(value)
    return Text(None if slug is None else label(slug))


def _exact_range_title(first: datetime, last: datetime) -> str:
    """The stored bounds as exact ISO dates, for a range cell's tooltip."""
    return f"{first.date().isoformat()}{RANGE_SEPARATOR}{last.date().isoformat()}"


def _coverage_range_cell(
    start: object,
    end: object,
    *,
    frequency: str,
    calendar: str,
) -> Cell:
    """One range cell: an ``Ltr`` for a Gregorian source, a ``Text`` for Jalali.

    This is the Task 13 bidi decision. A Gregorian range (``1960-2025``) is an LTR
    data token embedded in RTL text, so it is isolated in a ``bdi`` and cannot
    flip the row; a Jalali range is RTL text and stays a ``Text`` cell. A
    Gregorian cell also carries the exact stored bounds in its ``title``: the
    display is a bare year, so the tooltip is where the precise dates live, which
    is exactly what the section footnote promises. A daily Jalali range collapses
    to the mockup's compact same-month form (see
    :func:`dashboard.formatting.range_label`); every other frequency is unchanged.

    A missing bound renders the em-dash rather than a one-sided range.
    """
    first = _aware_utc(start)
    last = _aware_utc(end)
    if first is None or last is None:
        return Text(None)
    if calendar == "gregorian":
        return Ltr(
            range_label(first, last, frequency=frequency, calendar=calendar),
            title=_exact_range_title(first, last),
            num=True,
        )
    return Text(
        range_label(first, last, frequency=frequency, calendar=calendar, compact=True),
        num=True,
    )


def _coverage_count_cell(value: object) -> Cell:
    """A numeric coverage cell, or the em-dash when the value is unknown."""
    number = _optional_cell_number(value)
    return Text(None if number is None else format_number(number), num=True)


def build_coverage_rows(
    frame: pd.DataFrame,
    *,
    calendar_map: Mapping[str, str] = SOURCE_CALENDAR,
) -> CoverageTable:
    """Build the Overview coverage table as typed cells, in the frame's order.

    One row per catalog indicator, exactly the rows
    :meth:`DashboardRepository.coverage_summary` returns. The cells are:

    - indicator — :class:`TwoLine`: the display name above the raw id, which the
      mockup sets in its own block-level ``idl`` line
    - domain / source / frequency — :class:`Text` through the label layer
    - unit — :class:`UnitChip`
    - coverage range / observed range — the catalog bounds and the observed
      bounds, each labelled by :func:`range_label`. A Gregorian source's range is
      an :class:`Ltr` cell carrying the exact dates in its tooltip; a Jalali
      source's is a :class:`Text` cell (the Task 13 bidi decision)
    - observation count / chained rows / average confidence — numeric
      :class:`Text` cells, em-dash when unknown (never an invented zero)

    The three right-hand headers are the ones the mockup renders on two lines;
    they come back as ``wrap_headers`` so the caller never restates them. Row
    order is the frame's, which the repository owns; nothing is invented,
    re-sorted or recomputed.

    Args:
        frame: Coverage frame from ``coverage_summary()``
        calendar_map: Source slug -> display calendar. Defaults to the Task 13
            :data:`~dashboard.labels.SOURCE_CALENDAR`; inject an empty map to
            force every range into the Jalali form (tests, and any future
            opt-out). A source absent from the map keeps the Jalali default

    Returns:
        A :class:`CoverageTable`; an empty frame yields the headers with no rows
    """
    columns = (
        t("table.indicator"),
        t("table.domain"),
        t("table.source_name"),
        t("table.frequency"),
        t("table.unit"),
        t("table.coverage_range"),
        t("table.observed_range"),
        t("table.observation_count"),
        t("table.chained_rows"),
        t("table.average_confidence"),
    )
    wrap_headers = (
        t("table.observation_count"),
        t("table.chained_rows"),
        t("table.average_confidence"),
    )
    if frame.empty:
        return CoverageTable(columns, (), wrap_headers)
    rows: list[tuple[Cell, ...]] = []
    for row in frame.itertuples(index=False):
        indicator_id = _optional_cell_text(row.indicator_id)
        frequency = _optional_cell_text(row.frequency) or ""
        source_name = _optional_cell_text(row.source_name) or ""
        calendar = calendar_map.get(source_name, "jalali")
        if indicator_id is None:
            indicator: Cell = Text(None)
        else:
            indicator = TwoLine(
                indicator_label(indicator_id, _optional_cell_text(row.name)),
                (Ltr(indicator_id, mono_id=True),),
            )
        rows.append(
            (
                indicator,
                _label_cell(row.domain, domain_label),
                _label_cell(row.source_name, source_label),
                _label_cell(row.frequency, frequency_label),
                UnitChip(_optional_cell_text(row.unit)),
                _coverage_range_cell(
                    row.availability_start,
                    row.availability_end,
                    frequency=frequency,
                    calendar=calendar,
                ),
                _coverage_range_cell(
                    row.observed_start,
                    row.observed_end,
                    frequency=frequency,
                    calendar=calendar,
                ),
                _coverage_count_cell(row.observation_count),
                _coverage_count_cell(row.chain_linked_count),
                _coverage_count_cell(row.confidence),
            )
        )
    return CoverageTable(columns, tuple(rows), wrap_headers)


def filter_coverage_frame(
    frame: pd.DataFrame,
    *,
    domain: str | None = None,
    source: str | None = None,
    frequency: str | None = None,
) -> pd.DataFrame:
    """Apply the coverage filter bar's three selects to the loaded frame.

    The coverage frame holds one row per catalog indicator, so the filters run in
    memory and issue no extra query. ``None`` is the mockup's "همه" and matches
    every row; a column the frame does not carry is skipped rather than raising,
    so a partial frame still renders.

    Args:
        frame: Coverage frame from ``coverage_summary()``
        domain: Selected domain slug, or ``None`` for all
        source: Selected ``source_name`` slug, or ``None`` for all
        frequency: Selected frequency slug, or ``None`` for all

    Returns:
        The filtered frame, in the input order
    """
    filtered = frame
    for column, value in (
        ("domain", domain),
        ("source_name", source),
        ("frequency", frequency),
    ):
        if value is None or column not in filtered.columns:
            continue
        filtered = filtered[filtered[column] == value]
    return filtered


def _coverage_option_label(label: Callable[[str], str]) -> Callable[[str | None], str]:
    """An option formatter for a coverage select: "همه" for the no-filter value."""
    return lambda value: t("filter.all") if value is None else label(value)


def _render_coverage_section(coverage: pd.DataFrame) -> None:
    """Render the coverage section: filter bar, table, footnote.

    The bar is Task 21's :func:`render_filter_bar` with three ``st.selectbox``
    controls (domain / source / frequency) and two trailing ones — the mockup's
    row-count echo and its density segmented control. The three selections and the
    density are read from ``st.session_state`` **before** the bar renders, so the
    frame the table renders is the one the controls describe in the same run; the
    controls then write the same keys back.

    The table is the ``coverage`` variant (wide cells, two-line headers) at the
    selected density, and the footnote states the calendar rule the range cells
    implement: a Gregorian-calendar source shows a Gregorian year and the exact
    date is in each cell's tooltip (D3 opt-in).
    """
    selected_domain = st.session_state.get(_COVERAGE_DOMAIN_KEY)
    selected_source = st.session_state.get(_COVERAGE_SOURCE_KEY)
    selected_frequency = st.session_state.get(_COVERAGE_FREQUENCY_KEY)
    density = st.session_state.get(_COVERAGE_DENSITY_KEY, _COVERAGE_DENSITIES[0])
    if density not in _COVERAGE_DENSITIES:
        density = _COVERAGE_DENSITIES[0]
    filtered = filter_coverage_frame(
        coverage,
        domain=selected_domain,
        source=selected_source,
        frequency=selected_frequency,
    )

    def domain_control() -> None:
        st.selectbox(
            t("filter.domain"),
            options=[None, *unique_values(coverage, "domain")],
            format_func=_coverage_option_label(domain_label),
            key=_COVERAGE_DOMAIN_KEY,
        )

    def source_control() -> None:
        st.selectbox(
            t("filter.source"),
            options=[None, *unique_values(coverage, "source_name")],
            format_func=_coverage_option_label(source_label),
            key=_COVERAGE_SOURCE_KEY,
        )

    def frequency_control() -> None:
        st.selectbox(
            t("filter.frequency"),
            options=[None, *unique_values(coverage, "frequency")],
            format_func=_coverage_option_label(frequency_label),
            key=_COVERAGE_FREQUENCY_KEY,
        )

    def rows_control() -> None:
        st.markdown(t("filter.showing_rows", count=format_number(len(filtered))))

    def density_control() -> None:
        st.segmented_control(
            t("filter.density"),
            options=list(_COVERAGE_DENSITIES),
            default=_COVERAGE_DENSITIES[0],
            format_func=lambda value: t(f"filter.density_{value}"),
            key=_COVERAGE_DENSITY_KEY,
            label_visibility="collapsed",
        )

    with st.container(key="overview-coverage-section"):
        render_section_header("section.available_coverage")
        render_filter_bar(
            [domain_control, source_control, frequency_control],
            trailing=[rows_control, density_control],
            key="overview-coverage",
        )
        table = build_coverage_rows(filtered)
        if table.rows:
            render_html_table(
                table.columns,
                table.rows,
                density=density,
                variant="coverage",
                wrap_headers=table.wrap_headers,
            )
        else:
            render_empty("empty.no_coverage_rows")
        st.caption(t("table.coverage_footnote"))


class FreshnessTable(NamedTuple):
    """A freshness table ready for ``render_html_table``.

    Attributes:
        columns: Localized column headers, in mockup order
        rows: One tuple of typed cells per source, stale rows first
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


def _freshness_dot_tone(verdict: str) -> Tone:
    """Tone of the freshness dot: amber when stale, green when fresh, grey unknown.

    A source with no known cadence is reported as *unknown* and must not be
    dressed as either verdict, so it gets the neutral dot.
    """
    if verdict == t("value.stale"):
        return "warn"
    if verdict == t("value.fresh"):
        return "ok"
    return "neutral"


def build_freshness_rows(frame: pd.DataFrame, *, now: datetime) -> FreshnessTable:
    """Build the freshness table as typed cells, stale rows first.

    One row per source, exactly the latest ``DataCollectionLog`` run
    :meth:`DashboardRepository.source_freshness` returns. The cells are:

    - source — :class:`Text` through the label layer
    - freshness — :class:`Dot` (amber stale / green fresh / neutral unknown) with
      the verdict label, against the source's expected cadence
      (:func:`dashboard.labels.source_expected_cadence`)
    - last collection — :class:`TwoLine`: the Jalali date on the primary line,
      ``time · relative age`` on the secondary line. The relative age is the
      Task 11 formatter and the date is coloured by the verdict, as in the mockup
    - collected records — :class:`Text` with the formatted count (unknown, never
      an invented zero, when the source did not report one)
    - run status — :class:`StatusChip` from the shared slug mapping
      (:func:`dashboard.components.layout.status_chip_cell`)

    Ordering is the Task 12 semantics: stale rows first, and a stable sort keeps
    the input order within one verdict. Nothing is invented and no value is
    recomputed.

    Args:
        frame: Freshness frame from ``source_freshness()``
        now: Reference instant for the verdict and the relative ages. The caller
            captures it once per render and passes it in, so every verdict, age
            and the section summary agree; tests inject it.

    Returns:
        A :class:`FreshnessTable`; an empty frame yields the headers with no rows
    """
    columns = (
        t("table.source_name"),
        t("table.staleness"),
        t("table.last_collection"),
        t("table.records_collected"),
        t("table.run_status"),
    )
    if frame.empty:
        return FreshnessTable(columns, ())
    reference = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    stale_label = t("value.stale")
    ordered: list[tuple[bool, tuple[Cell, ...]]] = []
    for row in frame.itertuples(index=False):
        source_name = str(row.source_name)
        collected = _aware_utc(row.collection_timestamp)
        verdict = _staleness_label(source_name, collected, reference)
        if collected is None:
            date_text = time_text = age_text = t("value.unknown")
        else:
            date_text = jalali_date_label(collected)
            time_text = tehran_clock_label(collected)
            age_text = relative_time_label(collected, now=reference)
        ordered.append(
            (
                verdict != stale_label,
                (
                    Text(source_label(source_name)),
                    Dot(verdict, _freshness_dot_tone(verdict)),
                    TwoLine(
                        date_text,
                        (Text(time_text), Text(age_text)),
                        primary_tone=_freshness_dot_tone(verdict),
                    ),
                    Text(_count_label(row.records_collected)),
                    status_chip_cell(str(row.status)),
                ),
            )
        )
    ordered.sort(key=lambda item: item[0])
    return FreshnessTable(columns, tuple(cells for _, cells in ordered))


def freshness_display(frame: pd.DataFrame, *, now: datetime | None = None) -> pd.DataFrame:
    """Return the per-source freshness table with localized headers and staleness.

    One row per source, exactly the latest ``DataCollectionLog`` run
    :meth:`DashboardRepository.source_freshness` returns. ``status`` and the
    error text are data and stay verbatim; the source name is displayed through
    the label layer, and the collection instant is shown as a Tehran-local Jalali
    timestamp (storage stays UTC). The staleness verdict compares the last
    collection against the source's expected collection cadence
    (:func:`dashboard.labels.source_expected_cadence`); a source without a known
    cadence is reported as unknown rather than guessed fresh or stale.

    Args:
        frame: Freshness frame from ``source_freshness()``
        now: Reference instant for staleness; defaults to the current UTC time
            and is injectable so the verdict is deterministic under test

    Returns:
        A display frame with Persian headers, or an empty frame with those
        headers when there is no collection log
    """
    columns = [
        t("table.source_name"),
        t("table.collection_timestamp"),
        t("table.status"),
        t("table.records_collected"),
        t("table.error_message"),
        t("table.staleness"),
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    reference = now if now is not None else datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    rows: list[dict[str, str]] = []
    for row in frame.itertuples(index=False):
        source_name = str(row.source_name)
        collected = _aware_utc(row.collection_timestamp)
        staleness = _staleness_label(source_name, collected, reference)
        rows.append(
            {
                columns[0]: source_label(source_name),
                columns[1]: (
                    t("value.unknown") if collected is None else tehran_timestamp_label(collected)
                ),
                columns[2]: str(row.status),
                columns[3]: _count_label(row.records_collected),
                columns[4]: "" if row.error_message is None else str(row.error_message),
                columns[5]: staleness,
            }
        )
    # Stale rows sort first; stable sort keeps the original order for rows
    # with the same staleness verdict (fresh, unknown, etc.).
    rows.sort(key=lambda r: r[columns[5]] != t("value.stale"))
    return pd.DataFrame(rows)


def freshness_summary(frame: pd.DataFrame, *, now: datetime) -> tuple[int, int]:
    """Count fresh and stale sources in a freshness frame.

    Reuses :func:`_staleness_label` so the verdict matches
    :func:`freshness_display` exactly. Sources with no known cadence
    (``"unknown"``) are counted as neither fresh nor stale.

    Args:
        frame: Freshness frame from ``source_freshness()``
        now: Reference instant for staleness; injectable for determinism

    Returns:
        ``(fresh, stale)`` counts
    """
    if frame.empty:
        return (0, 0)
    reference = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    fresh = 0
    stale = 0
    fresh_label = t("value.fresh")
    stale_label = t("value.stale")
    for row in frame.itertuples(index=False):
        source_name = str(row.source_name)
        collected = _aware_utc(row.collection_timestamp)
        verdict = _staleness_label(source_name, collected, reference)
        if verdict == fresh_label:
            fresh += 1
        elif verdict == stale_label:
            stale += 1
    return (fresh, stale)


def _staleness_label(source_name: str, collected: datetime | None, now: datetime) -> str:
    """Verdict for one source: fresh, stale, or unknown when no cadence is known."""
    cadence = source_expected_cadence(source_name)
    if cadence is None or collected is None:
        return t("value.unknown")
    return t("value.stale") if (now - collected) > cadence else t("value.fresh")


def _aware_utc(value: Any) -> datetime | None:
    """Interpret a stored timestamp as timezone-aware UTC, or ``None`` if absent.

    ``value`` is typed ``Any`` because it arrives as an untyped pandas row
    attribute: it may be a ``Timestamp``, a ``datetime``, ``NaT`` or ``None``.
    """
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.to_pydatetime()


def _count_label(value: object) -> str:
    """Format a record count, showing unknown rather than inventing a zero."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return t("value.unknown")
    if not math.isfinite(value):
        return t("value.unknown")
    return format_number(int(value))


def render_fx_gold_page(repository: DashboardRepository | None = None) -> None:
    """Render the TGJU FX/gold page with snapshot limitations.

    The page header carries the snapshot caveat, so the title and the warning are
    one shared component (Task 18 + Task 17) instead of a raw ``st.title`` /
    ``st.warning``. The body composition is :func:`render_domain_body` rather than
    :func:`render_domain_page`, so the title cannot appear twice on the same page.
    """
    render_page_header("page.fx_gold", callout_key="warn.tgju_snapshot")
    render_domain_body(
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

    The composition follows the D11 layout contract (Task 39): the page header
    and the two HBSIR caveats through shared components, the shared section
    headers, and the survey-year panel as the shared RTL HTML table. The filter
    set is unchanged (:func:`render_filters`), so the selection and every value
    are exactly as before.
    """
    render_page_header("page.welfare")
    render_callout("warn.hbsir_relative_poverty", tone="warn", body=_relative_poverty_note())
    render_callout("warn.hbsir_computed_values", tone="info")
    domain_list = ["welfare"]
    if repository is None:
        catalog = cached_list_indicators(domains=tuple(domain_list))
    else:
        catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        render_empty("empty.no_indicators_for_page")
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
    render_section_header("section.welfare_other_indicators")
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

    The page header carries the SCI publication caveat (Task 18 + Task 17), so the
    title and the notice are one shared component rather than a raw ``st.title`` /
    ``st.info``.
    """
    render_page_header("page.labor", callout_key="warn.labor_publication", tone="info")
    domain_list = [LABOR_DOMAIN]
    if repository is None:
        catalog = cached_list_indicators(domains=tuple(domain_list))
    else:
        catalog = repository.list_indicators(domains=domain_list)
    if catalog.empty:
        render_empty("empty.no_indicators_for_page")
        return
    render_domain_body(
        domain_list,
        "labor",
        list(catalog["indicator_id"]),
        repository=repository,
        catalog=catalog,
    )


def render_correlation_page(repository: DashboardRepository | None = None) -> None:
    """Render exact-timestamp correlation diagnostics.

    The composition follows the D11 layout contract: the page opens with
    ``render_page_header``, every caveat (mixed frequencies, low overlap, exact
    join) is a ``render_callout`` with its own container key, the section title is
    a ``render_section_header``, and the empty/no-selection states are
    ``render_empty``. The join-count matrix and the overlap summary stay native
    ``st.dataframe`` tables (D1: a matrix and a sortable N-row table); only the
    overlap summary takes the shared density ``row_height``. The quality summary is
    the already-migrated ``render_quality_summary``. The suppression and
    exact-join logic in ``build_correlation_chart`` is untouched.
    """
    from dashboard.components.charts import build_correlation_chart

    render_page_header("page.correlation")
    catalog = repository.list_indicators() if repository else cached_list_indicators()
    if catalog.empty:
        render_empty("empty.catalog_empty")
        return
    filters = render_filters(catalog, "correlation")
    if not filters.indicator_ids:
        render_empty("empty.select_two_indicators")
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
        render_empty("empty.no_observations")
        return
    frequencies = set(series["frequency"].astype(str))
    if len(frequencies) > 1:
        render_callout("warn.mixed_frequencies")
    bundle = build_correlation_chart(series)
    if bundle.suppressed_pairs:
        # The message carries the suppressed-pair count and the overlap minimum,
        # so it passes its resolved text through ``body`` and uses the key for the
        # callout's container hook only.
        render_callout(
            "warn.correlation_low_overlap",
            body=t(
                "warn.correlation_low_overlap",
                count=format_number(len(bundle.suppressed_pairs)),
                minimum=format_number(bundle.min_overlap),
            ),
        )
    render_callout("warn.correlation_exact_join", tone="info")
    st.plotly_chart(bundle.figure, use_container_width=True)
    render_section_header("section.exact_join_counts")
    matrix_column, summary_column = st.columns(2)
    with matrix_column:
        st.dataframe(bundle.join_counts, use_container_width=True)
    with summary_column:
        st.dataframe(
            localize_table_frame(bundle.overlap_summary),
            use_container_width=True,
            hide_index=True,
            row_height=OBSERVATIONS_ROW_HEIGHT,
        )
    render_quality_summary(summarize_quality(series, filters.start_date, filters.end_date))
    render_data_downloads(series, "iran-macro-correlation")


def _render_series_section(series: pd.DataFrame, key_prefix: str) -> None:
    """Render the A2 archetype's chart, quality and observations sections.

    Order matches the archetype: the chart section (its mode control and the
    figure), then the quality summary, then the observations grid inside its
    expander, then the downloads. Nothing about the selection, the chart mode, the
    row cap or the values changes; only the composition and its section titles are
    shared components now.
    """
    if series.empty:
        render_empty("empty.no_observations")
        return
    start = series["timestamp"].min().to_pydatetime()
    end = series["timestamp"].max().to_pydatetime()
    quality = summarize_quality(series, start, end)
    render_section_header("section.chart")
    scaled = _render_scaled_chart(series, key_prefix)
    render_section_header("section.quality")
    render_quality_summary(quality)
    with st.expander(t("section.observations"), expanded=False):
        _render_capped_rows(series, key_prefix)
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
        # The notice carries values, so it passes its resolved text through
        # ``body`` and uses the key for the callout's container hook only.
        render_callout("chart.notice", tone="info", body=scaled.notice)
    st.plotly_chart(scaled.figure, use_container_width=True)
    return scaled


def _chart_mode_label(mode: str) -> str:
    """Persian label of a chart mode, keyed by the mode slug."""
    return t(f"chart.mode.{mode}")


def _render_capped_rows(series: pd.DataFrame, key_prefix: str) -> None:
    """Render the observations grid as a bounded preview with a truncation hint.

    The cap is presentation-only: it never changes a value, a column or the
    timezone-aware ``timestamp`` column, and the exports and the quality summary
    still describe the full selection. The grid is a large, scrollable table, so it
    stays a ``st.dataframe`` (D1) with ``row_height`` as its density control.

    ``key_prefix`` names the truncation callout's container: a page can render
    several grids (the Market page's level and one per derived series), and a
    repeated container key raises.
    """
    capped = cap_table_rows(series)
    if capped.truncated:
        render_callout(
            "table.rows_capped",
            tone="info",
            container_key=f"rows-capped-{key_prefix}",
            body=t(
                "table.rows_capped",
                shown=format_number(capped.shown_rows),
                total=format_number(capped.total_rows),
            ),
        )
    st.dataframe(
        localize_table_frame(capped.frame),
        use_container_width=True,
        hide_index=True,
        row_height=OBSERVATIONS_ROW_HEIGHT,
    )


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


class SurveyYearPanelTable(NamedTuple):
    """The survey-year panel ready for ``render_html_table``.

    Attributes:
        columns: Localized column headers, in :func:`survey_year_panel`'s order
        rows: One tuple of typed cells per survey year
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]


def build_survey_year_panel_rows(frame: pd.DataFrame) -> SurveyYearPanelTable:
    """Build the survey-year panel as typed cells from the localized frame.

    The frame is the output of :func:`survey_year_panel`, whose cells are already
    Persian display text (the Jalali survey-year label, the Esfand 29/30
    year-end, the Gregorian period end, and the formatted coverage counts). Each
    value therefore maps to a plain :class:`~dashboard.components.html_table.Text`
    cell, so the rendered table is byte-identical to the grid it replaces; a null
    (never produced today) falls back to the shared em-dash through ``Text(None)``.

    Args:
        frame: Frame from :func:`survey_year_panel`

    Returns:
        A :class:`SurveyYearPanelTable`; an empty frame yields no columns and no
        rows
    """
    if frame.empty:
        return SurveyYearPanelTable((), ())
    rows = tuple(
        tuple(_survey_year_cell(value) for value in row)
        for row in frame.itertuples(index=False, name=None)
    )
    return SurveyYearPanelTable(tuple(str(column) for column in frame.columns), rows)


def _survey_year_cell(value: object) -> Cell:
    """One survey-year cell: plain text, or the shared em-dash for a null."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return Text(None)
    return Text(str(value))


def _render_hbsir_sections(series: pd.DataFrame) -> None:
    """Render the HBSIR emphasis sections: trend, decile shares, survey years.

    Each section opens with a shared section header. An empty section renders the
    shared empty callout with a distinct ``container_key`` per section, because
    the same ``empty.no_hbsir_observations`` key can legitimately fire in more
    than one section on the same run. The survey-year panel is the shared RTL
    HTML table (:func:`render_html_table`) fed by the pure builder
    :func:`build_survey_year_panel_rows`; its values are byte-identical to the
    grid it replaces.
    """
    trend = _hbsir_subset(series, HBSIR_GINI_POVERTY_INDICATORS)
    render_section_header("section.hbsir_gini_poverty")
    if trend.empty:
        render_callout(
            "empty.no_hbsir_observations", tone="info", container_key="hbsir-gini-poverty"
        )
    else:
        st.plotly_chart(
            build_survey_year_chart(survey_year_frame(trend)),
            use_container_width=True,
        )

    deciles = _hbsir_subset(series, tuple(DECILE_INDICATORS))
    render_section_header("section.hbsir_deciles")
    if deciles.empty:
        render_callout("empty.no_hbsir_observations", tone="info", container_key="hbsir-deciles")
    else:
        st.plotly_chart(
            build_survey_year_chart(survey_year_frame(deciles), facet_indicators=False),
            use_container_width=True,
        )

    render_section_header("section.hbsir_survey_years")
    panel = survey_year_panel(_hbsir_subset(series, HBSIR_INDICATORS))
    if panel.empty:
        render_callout(
            "empty.no_hbsir_observations", tone="info", container_key="hbsir-survey-years"
        )
    else:
        table = build_survey_year_panel_rows(panel)
        render_html_table(table.columns, table.rows)


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
