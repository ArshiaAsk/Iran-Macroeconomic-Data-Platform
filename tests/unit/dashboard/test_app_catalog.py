"""AppTest smoke test for the data catalog page."""

from dashboard.i18n import t
from tests.unit.dashboard.app_smoke import app_test


def test_catalog_page_renders(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()

    assert not app.exception


def test_catalog_grid_uses_persian_headers(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()

    grid = app.dataframe[0].value
    assert t("table.indicator_id") in grid.columns
    assert t("table.name") in grid.columns
    assert t("table.availability_start") in grid.columns
