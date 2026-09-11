"""AppTest smoke test for the data catalog page."""

from tests.unit.dashboard.app_smoke import app_test


def test_catalog_page_renders(fake_streamlit_connection) -> None:
    app = app_test("7_Data_Catalog.py")
    app.run()

    assert not app.exception
