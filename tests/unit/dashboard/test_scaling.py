"""Page-level coverage of the Task 15 chart/table scaling wiring.

The pure builders are pinned in ``test_charts.py`` and the row cap in
``test_tables.py``; these tests drive the Streamlit pages to prove the controls
are opt-in, the default is unchanged, the mixed-unit fallback is visible, and the
observations grid is capped.
"""

from streamlit.testing.v1 import AppTest

from dashboard.components.charts import CHART_MODE_FACETS, CHART_MODES
from dashboard.components.tables import OBSERVATIONS_ROW_LIMIT
from dashboard.formatting import format_number
from dashboard.i18n import t
from tests.unit.dashboard.app_smoke import app_test

#: Every domain page that renders through the shared composition, with its
#: widget-key prefix (``<prefix>_indicators`` / ``<prefix>_chart_mode``).
DOMAIN_PAGES = (
    ("2_Inflation.py", "inflation"),
    ("3_GDP_Economy.py", "gdp_economy"),
    ("4_Trade_Welfare_Energy.py", "trade_energy"),
    ("5_FX_Gold.py", "fx_gold"),
    ("8_Welfare_Survey.py", "welfare"),
    ("10_Labor.py", "labor"),
)


def _render_capped_observations_app() -> None:
    """Render the shared capped observations grid with more rows than the cap."""
    import pandas as pd

    from dashboard.components.tables import OBSERVATIONS_ROW_LIMIT
    from dashboard.page_view import _render_capped_rows

    rows = OBSERVATIONS_ROW_LIMIT + 1
    frame = pd.DataFrame(
        {
            "indicator_id": ["i"] * rows,
            "timestamp": [pd.Timestamp("2020-01-01", tz="UTC")] * rows,
            "value": [float(index) for index in range(rows)],
        }
    )
    _render_capped_rows(frame, "capped-probe")


def _ensure_indicator_selected(app, prefix: str) -> None:
    """Select the first indicator when a page has no default selection."""
    choose = app.multiselect(key=f"{prefix}_indicators")
    if choose.value:
        return
    choose.select(choose.options[0])
    app.run()


def test_every_domain_page_defaults_to_facet_mode(fake_streamlit_connection) -> None:
    for page, prefix in DOMAIN_PAGES:
        app = app_test(page)
        app.run()
        _ensure_indicator_selected(app, prefix)

        assert not app.exception, page
        assert app.selectbox(key=f"{prefix}_chart_mode").value == CHART_MODE_FACETS, page


def test_chart_mode_control_offers_facets_overlay_and_small_multiples(
    fake_streamlit_connection,
) -> None:
    app = app_test("2_Inflation.py")
    app.run()

    assert tuple(app.selectbox(key="inflation_chart_mode").options) == tuple(
        t(f"chart.mode.{mode}") for mode in CHART_MODES
    )


def test_overlay_is_honoured_when_the_selection_shares_a_unit(
    fake_streamlit_connection,
) -> None:
    app = app_test("2_Inflation.py")
    app.run()
    app.selectbox(key="inflation_chart_mode").select("overlay")
    app.run()

    assert not app.exception
    assert t("chart.overlay_mixed_units") not in {info.value for info in app.info}


def test_overlay_falls_back_visibly_when_derived_rows_change_the_unit(
    fake_streamlit_connection,
) -> None:
    app = app_test("2_Inflation.py")
    app.run()
    # The parent is in percent; the derived YOY series is in annual percent.
    app.checkbox(key="inflation_derived").check()
    app.run()
    app.selectbox(key="inflation_chart_mode").select("overlay")
    app.run()

    assert not app.exception
    assert t("chart.overlay_mixed_units") in {info.value for info in app.info}


def test_small_multiples_is_selectable_without_error(fake_streamlit_connection) -> None:
    app = app_test("2_Inflation.py")
    app.run()
    app.selectbox(key="inflation_chart_mode").select("small_multiples")
    app.run()

    assert not app.exception
    assert app.selectbox(key="inflation_chart_mode").value == "small_multiples"


def test_capped_rows_render_the_limit_and_a_narrow_the_range_hint() -> None:
    app = AppTest.from_function(_render_capped_observations_app).run()

    assert not app.exception
    assert len(app.dataframe[0].value) == OBSERVATIONS_ROW_LIMIT
    assert app.info[0].value == t(
        "table.rows_capped",
        shown=format_number(OBSERVATIONS_ROW_LIMIT),
        total=format_number(OBSERVATIONS_ROW_LIMIT + 1),
    )
