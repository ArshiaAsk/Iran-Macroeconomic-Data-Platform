"""AppTest and composition tests for inflation and GDP pages.

The Inflation page (Task 13) owns the ``inflation`` domain and adds two emphasis
sections on top of the generic composition: the ten SCI household-expenditure
decile CPI series as one comparison, and the canonical chain-linked
national/urban/rural CPI series. The decile ids come from the connector registry
(never a hardcoded dashboard list), the deciles share one unit and one base year
so no normalization is applied, and the generic composition's widgets
(``inflation_indicators`` / ``inflation_chart_mode`` / ``inflation_derived``) stay
exactly as Tasks 14 and 15 left them.
"""

import pandas as pd

from dashboard.components.charts import (
    CHART_MODE_SMALL_MULTIPLES,
    build_scaled_time_series_chart,
    build_time_series_chart,
    shared_series_unit,
)
from dashboard.formatting import jalali_date_label
from dashboard.i18n import t
from dashboard.labels import indicator_label
from dashboard.navigation import PAGES
from dashboard.page_view import (
    SCI_CANONICAL_CPI_INDICATORS,
    SCI_DECILE_INDICATORS,
    chain_linked_catalog_ids,
    chain_linking_provenance,
    cpi_canonical_ids,
    cpi_decile_ids,
)
from src.connectors.sci_scraper import SCI_CANONICAL_INDICATORS, SCI_INDICATOR_REGISTRY
from tests.unit.dashboard.app_smoke import (
    IMF_FORECAST_TIMESTAMP,
    IMF_INDICATOR,
    SCI_CANONICAL_IDS,
    SCI_CPI_IDS,
    SCI_DECILE_IDS,
    app_test,
    inflation_catalog,
    inflation_series,
)

INFLATION_PAGE = "2_Inflation.py"


def _decile_series() -> pd.DataFrame:
    """Gold-shaped decile rows, as the page loads them."""
    series = inflation_series()
    return series[series["indicator_id"].isin(SCI_DECILE_IDS)]


def _canonical_series() -> pd.DataFrame:
    """Gold-shaped canonical chain-linked rows, as the page loads them."""
    series = inflation_series()
    return series[series["indicator_id"].isin(SCI_CANONICAL_IDS)]


def test_inflation_page_renders(fake_streamlit_connection) -> None:
    app = app_test(INFLATION_PAGE)
    app.run()

    assert not app.exception


def test_gdp_page_renders(fake_streamlit_connection) -> None:
    app = app_test("3_GDP_Economy.py")
    app.run()

    assert not app.exception


def test_future_dated_imf_row_renders_like_any_other_observation(
    fake_streamlit_connection,
) -> None:
    """A future-dated WEO row is stored and rendered without special handling.

    Forecast labeling is deferred, so the platform treats a forecast row exactly
    like any other observation; this pins that a future-dated row survives the
    Gold load and appears in the observations grid unchanged.
    """
    app = app_test("3_GDP_Economy.py")
    app.run()
    app.multiselect(key="gdp_economy_indicators").set_value([IMF_INDICATOR])
    app.run()

    assert not app.exception
    grid = next(
        frame.value for frame in app.dataframe if t("table.timestamp") in frame.value.columns
    )
    assert IMF_INDICATOR in set(grid[t("table.indicator_id")])
    # The stored future period end is rendered as its Jalali date, no filtering.
    assert jalali_date_label(IMF_FORECAST_TIMESTAMP) in set(grid[t("table.timestamp")])


def test_inflation_page_renders_the_cpi_decile_and_canonical_sections(
    fake_streamlit_connection,
) -> None:
    app = app_test(INFLATION_PAGE)
    app.run()

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.inflation")]
    subheaders = [subheader.value for subheader in app.subheader]
    assert t("section.cpi_deciles") in subheaders
    assert t("section.cpi_canonical") in subheaders
    # The generic composition stays reachable below the emphasis sections.
    assert t("section.inflation_all_indicators") in subheaders
    # The decile grid, the canonical comparison and the generic composition.
    assert len(app.get("plotly_chart")) == 3


def test_inflation_page_keeps_the_generic_composition_widgets(
    fake_streamlit_connection,
) -> None:
    """Task 14/15 wiring is preserved: the shared controls still exist."""
    app = app_test(INFLATION_PAGE)
    app.run()

    assert app.multiselect(key="inflation_indicators").value == ["FP.CPI.TOTL.ZG"]
    assert app.selectbox(key="inflation_chart_mode").value == "facets"
    # The derived-series toggle stays off by default (Task 14).
    assert app.checkbox(key="inflation_derived").value is False


def test_inflation_decile_selector_offers_every_decile_and_defaults_to_all(
    fake_streamlit_connection,
) -> None:
    app = app_test(INFLATION_PAGE)
    app.run()

    deciles = app.multiselect(key="inflation_deciles")
    # Options are the Persian display labels (format_func), in registry order...
    assert list(deciles.options) == [indicator_label(indicator) for indicator in SCI_DECILE_IDS]
    # ...and the selection is every decile by default ("D1…D10 or all").
    assert list(deciles.value) == list(SCI_DECILE_IDS)


def test_inflation_decile_selector_accepts_a_subset(fake_streamlit_connection) -> None:
    app = app_test(INFLATION_PAGE)
    app.run()
    app.multiselect(key="inflation_deciles").set_value(list(SCI_DECILE_IDS[:3]))
    app.run()

    assert not app.exception
    assert list(app.multiselect(key="inflation_deciles").value) == list(SCI_DECILE_IDS[:3])


def test_inflation_page_states_that_the_deciles_share_a_unit_and_base_year(
    fake_streamlit_connection,
) -> None:
    app = app_test(INFLATION_PAGE)
    app.run()

    assert t("warn.cpi_deciles_shared_base") in [caption.value for caption in app.caption]


def test_decile_comparison_is_a_capped_small_multiples_grid() -> None:
    deciles = _decile_series()

    scaled = build_scaled_time_series_chart(deciles, mode=CHART_MODE_SMALL_MULTIPLES)

    assert scaled.mode == CHART_MODE_SMALL_MULTIPLES
    # One panel per decile, no truncation (the grid caps at 12; there are 10).
    assert len(scaled.figure.data) == len(SCI_DECILE_IDS)
    assert scaled.notice is None


def test_deciles_share_one_unit_so_no_normalization_is_needed() -> None:
    """The rationale for a plain comparison: a single shared unit."""
    assert shared_series_unit(_decile_series()) == "index"


def test_canonical_comparison_uses_the_chain_linked_canonical_ids() -> None:
    canonical = _canonical_series()

    figure = build_time_series_chart(canonical)

    assert set(canonical["indicator_id"]) == set(SCI_CANONICAL_CPI_INDICATORS)
    assert len(figure.data) == len(SCI_CANONICAL_CPI_INDICATORS)


def test_cpi_ids_come_from_the_connector_registry_not_a_dashboard_list() -> None:
    registry_deciles = tuple(SCI_INDICATOR_REGISTRY["cpi_decile"].member_ids)
    registry_canonical = tuple(SCI_CANONICAL_INDICATORS)

    assert registry_deciles == SCI_DECILE_INDICATORS
    assert registry_canonical == SCI_CANONICAL_CPI_INDICATORS


def test_cpi_helpers_return_catalog_registry_ids_in_registry_order() -> None:
    catalog = inflation_catalog()

    assert cpi_decile_ids(catalog) == list(SCI_DECILE_IDS)
    assert cpi_canonical_ids(catalog) == list(SCI_CANONICAL_IDS)
    # The full SCI CPI set is exactly the deciles plus the canonicals.
    assert set(catalog["indicator_id"]) == set(SCI_CPI_IDS)


def test_cpi_helpers_are_empty_safe() -> None:
    assert cpi_decile_ids(pd.DataFrame()) == []
    assert cpi_canonical_ids(pd.DataFrame()) == []
    assert cpi_decile_ids(pd.DataFrame({"indicator_id": ["unrelated"]})) == []


def test_inflation_domain_is_still_owned_by_exactly_one_page() -> None:
    specs = {spec.key: spec for spec in PAGES}

    assert [spec.key for spec in PAGES if "inflation" in spec.domains] == ["inflation"]
    assert specs["inflation"].domains == ("inflation",)
    assert specs["inflation"].path == "pages/2_Inflation.py"


def test_chain_linked_catalog_ids_read_the_stored_base_year_flag() -> None:
    catalog = inflation_catalog()

    assert set(chain_linked_catalog_ids(catalog)) == set(SCI_CANONICAL_IDS)


def test_chain_linked_catalog_ids_are_empty_safe() -> None:
    assert chain_linked_catalog_ids(pd.DataFrame()) == []
    assert chain_linked_catalog_ids(pd.DataFrame({"indicator_id": ["x"]})) == []


def test_chain_linking_provenance_lists_base_years_and_segment_ancestry() -> None:
    catalog = inflation_catalog()
    flagged = catalog[catalog["indicator_id"].isin(chain_linked_catalog_ids(catalog))]

    table = chain_linking_provenance(flagged)
    urban = table[table[t("table.name")] == indicator_label("SCI.CPI.URBAN")]

    assert list(table.columns) == [
        t("table.name"),
        t("table.has_base_year_changes"),
        t("table.base_years"),
        t("table.base_year_segments"),
    ]
    assert len(urban) == 1
    assert urban.iloc[0][t("table.has_base_year_changes")] == t("value.yes")
    segments = urban.iloc[0][t("table.base_year_segments")]
    assert indicator_label("SCI.CPI.URBAN.B2016") in segments
    assert indicator_label("SCI.CPI.URBAN.B2021") in segments


def test_inflation_page_renders_the_chain_linking_section(
    fake_streamlit_connection,
) -> None:
    app = app_test(INFLATION_PAGE)
    app.run()

    assert not app.exception
    assert t("section.chain_linking") in {subheader.value for subheader in app.subheader}
    assert t("warn.chain_linking_stored") in {caption.value for caption in app.caption}
    assert t("warn.chain_linking_overlap") in {caption.value for caption in app.caption}
