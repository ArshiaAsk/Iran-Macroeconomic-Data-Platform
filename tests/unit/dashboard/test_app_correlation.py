"""AppTest smoke test for exact-timestamp correlation."""

from tests.unit.dashboard.app_smoke import app_test


def test_correlation_page_renders(fake_streamlit_connection) -> None:
    app = app_test("6_Correlation.py")
    app.run()

    assert not app.exception
