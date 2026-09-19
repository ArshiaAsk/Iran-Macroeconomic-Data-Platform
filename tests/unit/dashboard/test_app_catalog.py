"""AppTest coverage for the catalog page: grid, search and the inactive toggle."""

from streamlit.testing.v1 import AppTest

from dashboard.i18n import t
from tests.unit.dashboard.app_smoke import (
    INACTIVE_SEGMENT_IDS,
    INFLATION_INDICATOR,
    app_test,
)

GDP_INDICATOR = "NY.GDP.MKTP.CD"


def _grid(app: AppTest):
    """The catalog page's single localized data grid."""
    return app.dataframe[0].value


def _indicator_ids(app: AppTest) -> set[str]:
    return set(_grid(app)[t("table.indicator_id")])


def test_catalog_page_renders(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()

    assert not app.exception


def test_catalog_grid_uses_persian_headers(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()

    grid = _grid(app)
    assert t("table.indicator_id") in grid.columns
    assert t("table.name") in grid.columns
    assert t("table.availability_start") in grid.columns


def test_catalog_hides_inactive_base_year_segments_by_default(
    fake_streamlit_connection,
) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()

    assert not set(INACTIVE_SEGMENT_IDS) & _indicator_ids(app)


def test_catalog_inactive_toggle_exposes_the_base_year_segments(
    fake_streamlit_connection,
) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()
    app.checkbox(key="catalog_include_inactive").check()
    app.run()

    assert not app.exception
    assert set(INACTIVE_SEGMENT_IDS) <= _indicator_ids(app)


def test_catalog_search_matches_an_indicator_id(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()
    app.text_input(key="catalog_search").set_value("SCI.CPI.URBAN")
    app.run()

    assert _indicator_ids(app) == {"SCI.CPI.URBAN"}


def test_catalog_search_matches_a_persian_display_name(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()
    # "تورم" lives only in the label layer, never in the English catalog name.
    app.text_input(key="catalog_search").set_value("تورم")
    app.run()

    assert INFLATION_INDICATOR in _indicator_ids(app)


def test_catalog_search_matches_a_unit(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()
    app.text_input(key="catalog_search").set_value("current US$")
    app.run()

    ids = _indicator_ids(app)
    assert GDP_INDICATOR in ids
    assert INFLATION_INDICATOR not in ids


def test_catalog_search_without_matches_shows_the_empty_state(
    fake_streamlit_connection,
) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()
    app.text_input(key="catalog_search").set_value("zzzz-no-match")
    app.run()

    assert _indicator_ids(app) == set()
    assert t("empty.search_no_match") in {info.value for info in app.info}


def test_catalog_clear_filters_resets_the_search(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()
    app.text_input(key="catalog_search").set_value("SCI.CPI.URBAN")
    app.run()
    assert _indicator_ids(app) == {"SCI.CPI.URBAN"}

    app.button(key="catalog_clear_filters").click()
    app.run()

    assert not app.exception
    assert app.text_input(key="catalog_search").value == ""
    assert len(_indicator_ids(app)) > 1
