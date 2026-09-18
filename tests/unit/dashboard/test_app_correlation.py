"""AppTest smoke test for exact-timestamp correlation and its overlap guard."""

from dashboard.components.charts import MIN_CORRELATION_OVERLAP
from dashboard.formatting import format_number
from dashboard.i18n import t
from tests.unit.dashboard.app_smoke import (
    ENERGY_INDICATOR,
    MARKET_INDICATOR,
    app_test,
)


def test_correlation_page_renders(fake_streamlit_connection) -> None:
    app = app_test("6_Correlation.py")
    app.run()

    assert not app.exception


def test_correlation_page_warns_and_suppresses_a_low_overlap_pair(
    fake_streamlit_connection,
) -> None:
    app = app_test("6_Correlation.py")
    app.run()
    # The daily index and the monthly energy series share exactly one timestamp,
    # which is below the minimum overlap.
    app.multiselect(key="correlation_indicators").set_value([MARKET_INDICATOR, ENERGY_INDICATOR])
    app.run()

    assert not app.exception
    warnings = {warning.value for warning in app.warning}
    assert (
        t(
            "warn.correlation_low_overlap",
            count=format_number(1),
            minimum=format_number(MIN_CORRELATION_OVERLAP),
        )
        in warnings
    )
    assert t("warn.correlation_exact_join") in {caption.value for caption in app.caption}


def test_correlation_page_shows_the_matched_observation_summary(
    fake_streamlit_connection,
) -> None:
    app = app_test("6_Correlation.py")
    app.run()
    app.multiselect(key="correlation_indicators").set_value([MARKET_INDICATOR, ENERGY_INDICATOR])
    app.run()

    summary = next(
        frame.value
        for frame in app.dataframe
        if t("table.matched_observations") in frame.value.columns
    )
    assert summary[t("table.matched_observations")].tolist() == [format_number(1)]
    assert summary[t("table.meets_minimum_overlap")].tolist() == [t("value.no")]
