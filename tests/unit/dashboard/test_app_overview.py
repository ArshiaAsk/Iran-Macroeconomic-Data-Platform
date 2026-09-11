"""AppTest smoke test for the overview page."""

from tests.unit.dashboard.app_smoke import app_test


def test_overview_page_renders(fake_streamlit_connection) -> None:
    app = app_test("1_Overview.py")
    app.run()

    assert not app.exception
