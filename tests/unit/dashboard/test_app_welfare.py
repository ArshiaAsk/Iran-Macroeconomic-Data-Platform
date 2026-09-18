"""AppTest and presentation tests for the Welfare & Survey (HBSIR) page.

The page owns the whole ``welfare`` domain: HBSIR's Gini, relative-poverty and
income-decile series are emphasised in dedicated sections on a Jalali survey-year
axis, and the non-HBSIR members (World Bank population, IMF ``LUR``) render
through the generic domain composition. Survey years are stored as Gregorian
year-ends, so the label tests pin the Esfand 29/30 boundary explicitly.
"""

import jdatetime
import pandas as pd
import pytest

from dashboard.components.charts import SURVEY_YEAR_COLUMN, build_survey_year_chart
from dashboard.formatting import (
    format_number,
    gregorian_to_jalali,
    jalali_date_label,
    jalali_year_label,
    to_persian_digits,
)
from dashboard.i18n import t
from dashboard.navigation import PAGES
from dashboard.page_view import survey_year_frame, survey_year_panel
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    DEFAULT_POVERTY_LINE_K,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
)
from src.utils.persian import iranian_year_end
from tests.unit.dashboard.app_smoke import (
    REPOSITORY_ROOT,
    SURVEY_TIMESTAMPS,
    WELFARE_CONTEXT_ROWS,
    app_test,
    welfare_series,
)

WELFARE_PAGE = "8_Welfare_Survey.py"
TRADE_ENERGY_PAGE = "4_Trade_Welfare_Energy.py"
CONTEXT_INDICATORS = tuple(row[0] for row in WELFARE_CONTEXT_ROWS)

# (Jalali survey year, its Persian label, the last Esfand day of that year):
# 1402 is a common year, 1403 a leap year -- both stored at UTC midnight.
SURVEY_YEAR_CASES = [(1402, "۱۴۰۲", 29), (1403, "۱۴۰۳", 30)]


def _gold_frame(rows: list[tuple[str, object, float]]) -> pd.DataFrame:
    """A Gold-shaped frame of ``(indicator_id, timestamp, value)`` rows."""
    return pd.DataFrame(
        {
            "indicator_id": [indicator for indicator, _, _ in rows],
            "name": [indicator for indicator, _, _ in rows],
            "timestamp": [timestamp for _, timestamp, _ in rows],
            "value": [value for _, _, value in rows],
        }
    )


def _survey_frame() -> pd.DataFrame:
    """Gini, relative poverty and the ten decile shares over both survey years."""
    rows: list[tuple[str, object, float]] = []
    for period_end in SURVEY_TIMESTAMPS:
        rows.append((GINI_INDICATOR, period_end, 0.37))
        rows.append((POVERTY_INDICATOR, period_end, 16.0))
        rows.extend((decile, period_end, 10.0) for decile in DECILE_INDICATORS)
    return survey_year_frame(_gold_frame(rows))


def _expected_panel() -> pd.DataFrame:
    """The survey-year panel the page must render, from the shared fixture rows."""
    hbsir = welfare_series()
    return survey_year_panel(hbsir[hbsir["indicator_id"].isin(DEFAULT_INDICATORS)])


def test_welfare_page_renders_with_the_hbsir_sections(fake_streamlit_connection) -> None:
    app = app_test(WELFARE_PAGE)
    app.run()

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.welfare")]
    subheaders = [subheader.value for subheader in app.subheader]
    assert t("section.hbsir_gini_poverty") in subheaders
    assert t("section.hbsir_deciles") in subheaders
    assert t("section.hbsir_survey_years") in subheaders
    assert t("section.welfare_other_indicators") in subheaders
    # Two HBSIR emphasis charts (trend + decile shares) plus the generic
    # composition's chart for the population/LUR context selection.
    assert len(app.get("plotly_chart")) == 3
    # The survey-year metadata panel is rendered with the Jalali survey years.
    expected = _expected_panel()
    assert any(frame.value.equals(expected) for frame in app.dataframe)


def test_welfare_page_states_that_the_poverty_rate_is_relative(
    fake_streamlit_connection,
) -> None:
    app = app_test(WELFARE_PAGE)
    app.run()

    note = t(
        "warn.hbsir_relative_poverty",
        k=format_number(DEFAULT_POVERTY_LINE_K, digit_mode="fa"),
    )
    assert note in [warning.value for warning in app.warning]
    # The note names the multiplier, the weighted median and the official-line
    # disclaimer rather than implying a published poverty line.
    assert format_number(DEFAULT_POVERTY_LINE_K) == "۰٫۵"
    assert "میانه وزنی" in note
    assert t("warn.hbsir_computed_values") in [info.value for info in app.info]


def test_welfare_page_keeps_population_and_imf_lur_in_the_generic_composition(
    fake_streamlit_connection,
) -> None:
    app = app_test(WELFARE_PAGE)
    app.run()

    indicators = app.multiselect(key="welfare_indicators")
    # The generic composition defaults to the non-HBSIR members of the domain:
    # World Bank population and IMF LUR are never excluded from the page.
    assert set(indicators.value) == set(CONTEXT_INDICATORS)
    assert set(CONTEXT_INDICATORS).issubset(set(indicators.options))
    # The page owns the whole domain, so HBSIR stays selectable there too.
    assert set(DEFAULT_INDICATORS).issubset(set(indicators.options))


def test_welfare_page_owns_the_welfare_domain() -> None:
    specs = {spec.key: spec for spec in PAGES}

    assert [spec.key for spec in PAGES if "welfare" in spec.domains] == ["welfare"]
    assert specs["welfare"].domains == ("welfare",)
    assert (REPOSITORY_ROOT / "dashboard" / specs["welfare"].path).is_file()


def test_trade_energy_page_no_longer_owns_welfare() -> None:
    specs = {spec.key: spec for spec in PAGES}
    path = REPOSITORY_ROOT / "dashboard" / specs["trade_energy"].path

    assert specs["trade_energy"].domains == ("trade", "energy")
    # The page's executable body composes trade + energy only, so no HBSIR caveat
    # or welfare filter can leak onto it. Its module docstring records the split,
    # hence the check on the code that follows it.
    code = path.read_text("utf-8").split('"""', 2)[-1]
    assert '("trade", "energy")' in code
    assert "welfare" not in code
    assert "HBSIR" not in code


def test_reduced_trade_energy_page_still_renders(fake_streamlit_connection) -> None:
    app = app_test(TRADE_ENERGY_PAGE)
    app.run()

    assert not app.exception


def test_existing_page_ownership_is_unchanged() -> None:
    specs = {spec.key: spec for spec in PAGES}

    assert [spec.key for spec in PAGES] == [
        "overview",
        "correlation",
        "catalog",
        "inflation",
        "gdp",
        "trade_energy",
        "welfare",
        "fx_gold",
        # The Market page (Task 10) is appended: it claims only `market` and
        # leaves every page above exactly as the welfare split left it.
        "market",
        # The Labor page (Task 11) is appended: it claims only `labor`.
        "labor",
    ]
    assert specs["inflation"].domains == ("inflation",)
    assert specs["gdp"].domains == ("gdp",)
    assert specs["fx_gold"].domains == ("fx", "gold")
    assert specs["labor"].domains == ("labor",)
    assert {spec.key for spec in PAGES if not spec.domains} == {
        "overview",
        "correlation",
        "catalog",
    }


@pytest.mark.parametrize(("jalali_year", "label", "last_esfand_day"), SURVEY_YEAR_CASES)
def test_survey_year_label_round_trips_the_esfand_boundary(
    jalali_year: int,
    label: str,
    last_esfand_day: int,
) -> None:
    end = iranian_year_end(jalali_year)
    frame = survey_year_frame(_gold_frame([(GINI_INDICATOR, end, 0.37)]))

    assert frame[SURVEY_YEAR_COLUMN].tolist() == [label]
    assert frame[SURVEY_YEAR_COLUMN].tolist() == [jalali_year_label(end)]
    assert label == to_persian_digits(str(jalali_year))
    # The stored period end is midnight UTC, so the Tehran-local Jalali day stays
    # the survey year's last Esfand day: 29 in a common year, 30 in a leap year.
    assert gregorian_to_jalali(end) == jdatetime.date(jalali_year, 12, last_esfand_day)


def test_survey_year_frame_orders_rows_chronologically() -> None:
    frame = survey_year_frame(
        _gold_frame(
            [
                (GINI_INDICATOR, SURVEY_TIMESTAMPS[1], 0.35),
                (GINI_INDICATOR, SURVEY_TIMESTAMPS[0], 0.37),
            ]
        )
    )

    assert frame[SURVEY_YEAR_COLUMN].tolist() == ["۱۴۰۲", "۱۴۰۳"]
    assert frame["value"].tolist() == [0.37, 0.35]


def test_survey_year_chart_uses_the_jalali_survey_year_axis() -> None:
    trend = _survey_frame()
    trend = trend[trend["indicator_id"].isin([GINI_INDICATOR, POVERTY_INDICATOR])]

    figure = build_survey_year_chart(trend)

    assert list(figure.data[0].x) == ["۱۴۰۲", "۱۴۰۳"]
    # Gini (index) and poverty (percent) keep one panel each by default.
    assert len(figure.data) == 2


def test_survey_year_chart_overlays_series_that_share_a_unit() -> None:
    deciles = _survey_frame()
    deciles = deciles[deciles["indicator_id"].isin(DECILE_INDICATORS)]

    figure = build_survey_year_chart(deciles, facet_indicators=False)

    assert len(figure.data) == len(DECILE_INDICATORS)
    assert {tuple(trace.x) for trace in figure.data} == {("۱۴۰۲", "۱۴۰۳")}


def test_survey_year_panel_reports_the_year_end_and_coverage() -> None:
    panel = survey_year_panel(_survey_frame())

    assert list(panel.columns) == [
        t("table.survey_year"),
        t("table.survey_year_end"),
        t("table.period_end"),
        t("table.hbsir_indicators"),
        t("table.hbsir_observations"),
    ]
    assert panel[t("table.survey_year")].tolist() == ["۱۴۰۲", "۱۴۰۳"]
    assert panel[t("table.survey_year_end")].tolist() == [
        jalali_date_label(iranian_year_end(1402)),
        jalali_date_label(iranian_year_end(1403)),
    ]
    assert panel[t("table.survey_year_end")].tolist() == ["۲۹ اسفند ۱۴۰۲", "۳۰ اسفند ۱۴۰۳"]
    assert panel[t("table.period_end")].tolist() == ["2024-03-19", "2025-03-20"]
    assert panel[t("table.hbsir_indicators")].tolist() == [len(DEFAULT_INDICATORS)] * 2
    assert panel[t("table.hbsir_observations")].tolist() == [len(DEFAULT_INDICATORS)] * 2


def test_survey_year_panel_is_empty_rather_than_invented_without_observations() -> None:
    panel = survey_year_panel(pd.DataFrame())

    assert panel.empty
    assert t("table.survey_year") in panel.columns
