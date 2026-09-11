"""AppTest smoke tests for inflation and GDP pages."""

from tests.unit.dashboard.app_smoke import app_test


def test_inflation_page_renders(fake_streamlit_connection) -> None:
    app = app_test("2_Inflation.py")
    app.run()

    assert not app.exception


def test_gdp_page_renders(fake_streamlit_connection) -> None:
    app = app_test("3_GDP_Economy.py")
    app.run()

    assert not app.exception
