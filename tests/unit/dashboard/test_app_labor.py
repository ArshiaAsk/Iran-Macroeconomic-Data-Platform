"""AppTest and ownership tests for the Labor page (Task 11).

The page owns the whole ``labor`` domain -- SCI's quarterly labour-force
unemployment rate -- which today holds a single published quarter. These tests
pin the single-observation reality (one marker, one quality row, no implied
trend), the registry ownership, and the plan's rule that IMF ``LUR`` stays in the
``welfare`` domain rather than being merged onto this page.
"""

import pandas as pd

from dashboard.components.charts import build_time_series_chart
from dashboard.formatting import format_number, jalali_date_label
from dashboard.i18n import t
from dashboard.labels import frequency_label
from dashboard.navigation import GROUPS, PAGES
from tests.unit.dashboard.app_smoke import (
    LABOR_INDICATOR,
    LABOR_NAME,
    LABOR_TIMESTAMP,
    LABOR_VALUE,
    REPOSITORY_ROOT,
    FakeDashboardRepository,
    app_test,
    labor_series,
)

LABOR_PAGE = "10_Labor.py"


def _observations_frame(app) -> pd.DataFrame:
    """The localized observations grid: headers and cells are Persian."""
    return next(
        frame.value for frame in app.dataframe if t("table.timestamp") in frame.value.columns
    )


def _quality_frame(app) -> pd.DataFrame:
    return next(
        frame.value for frame in app.dataframe if t("table.rows_returned") in frame.value.columns
    )


def test_labor_page_renders_the_single_published_quarter(
    fake_streamlit_connection,
) -> None:
    app = app_test(LABOR_PAGE)
    app.run()

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.labor")]
    assert t("warn.labor_publication") in [info.value for info in app.info]
    # The domain's only indicator is selected by default, so the page is not an
    # empty selection waiting for the analyst.
    assert app.multiselect(key="labor_indicators").value == [LABOR_INDICATOR]
    assert len(app.get("plotly_chart")) == 1
    observations = _observations_frame(app)
    assert len(observations) == 1
    # The grid is localized: Persian headers, Persian digits and a Jalali date.
    assert observations[t("table.indicator_id")].tolist() == [LABOR_INDICATOR]
    assert observations[t("table.value")].tolist() == [format_number(LABOR_VALUE)]
    assert observations[t("table.timestamp")].tolist() == [jalali_date_label(LABOR_TIMESTAMP)]
    assert observations[t("table.frequency")].tolist() == [frequency_label("quarterly")]


def test_labor_page_does_not_imply_a_trend_from_one_quarter(
    fake_streamlit_connection,
) -> None:
    app = app_test(LABOR_PAGE)
    app.run()

    quality = _quality_frame(app)
    # One published quarter: the quality row reports exactly one returned row and
    # no missing periods, and the chart carries a single marker, not a line. The
    # grid is localized, so the counts render as Persian digits.
    assert quality[t("table.rows_returned")].tolist() == [format_number(1)]
    assert quality[t("table.missing_periods")].tolist() == [format_number(0)]
    figure = build_time_series_chart(labor_series())
    assert len(figure.data) == 1
    # Plotly stores the axis as timezone-naive UTC; the stored value is tz-aware.
    assert [pd.Timestamp(value) for value in figure.data[0].x] == [
        LABOR_TIMESTAMP.tz_localize(None)
    ]
    assert list(figure.data[0].y) == [LABOR_VALUE]


def test_labor_page_derived_toggle_is_inert_without_derived_rows(
    fake_streamlit_connection,
) -> None:
    app = app_test(LABOR_PAGE)
    app.run()
    app.checkbox(key="labor_derived").check()
    app.run()

    assert not app.exception
    # One observation cannot support a derived series, so the shared toggle
    # changes nothing and the page keeps rendering the same single quarter.
    assert _observations_frame(app)[t("table.indicator_id")].tolist() == [LABOR_INDICATOR]


def test_labor_page_is_registered_in_the_navigation_registry() -> None:
    specs = {spec.key: spec for spec in PAGES}
    labor = specs["labor"]

    assert labor.path == "pages/10_Labor.py"
    assert labor.domains == ("labor",)
    assert labor.group in GROUPS
    assert labor.is_default is False
    assert (REPOSITORY_ROOT / "dashboard" / labor.path).is_file()
    # The nav label and the in-page title share one key so they cannot drift.
    assert t("nav.labor") == t("page.labor")


def test_labor_domain_is_owned_by_exactly_one_page() -> None:
    assert [spec.key for spec in PAGES if "labor" in spec.domains] == ["labor"]


def test_imf_lur_stays_in_the_welfare_domain_not_labor() -> None:
    repository = FakeDashboardRepository()
    labor_ids = set(repository.list_indicators(domains=["labor"])["indicator_id"])
    welfare_ids = set(repository.list_indicators(domains=["welfare"])["indicator_id"])

    # IMF `LUR` is domain `welfare`; it is never merged onto the Labor page.
    assert "LUR" in welfare_ids
    assert "LUR" not in labor_ids
    assert labor_ids == {LABOR_INDICATOR}
    # The catalog keeps the auditable English name for the domain's indicator.
    assert set(repository.list_indicators(domains=["labor"])["name"]) == {LABOR_NAME}


def test_labor_page_leaves_every_other_page_ownership_unchanged() -> None:
    specs = {spec.key: spec for spec in PAGES}

    assert specs["inflation"].domains == ("inflation",)
    assert specs["gdp"].domains == ("gdp",)
    assert specs["trade_energy"].domains == ("trade", "energy")
    assert specs["welfare"].domains == ("welfare",)
    assert specs["fx_gold"].domains == ("fx", "gold")
    assert specs["market"].domains == ("market",)
    assert {spec.key for spec in PAGES if not spec.domains} == {
        "overview",
        "correlation",
        "catalog",
    }


def test_every_plan_domain_has_exactly_one_owner() -> None:
    plan_domains = {
        "gdp",
        "inflation",
        "trade",
        "welfare",
        "energy",
        "fx",
        "gold",
        "labor",
        "market",
    }
    owners = [domain for spec in PAGES for domain in spec.domains]

    assert set(owners) == plan_domains
    assert len(owners) == len(set(owners))
    assert "economy" not in owners
