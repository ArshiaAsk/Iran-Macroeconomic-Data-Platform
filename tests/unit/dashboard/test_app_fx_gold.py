"""AppTest smoke test for the FX and gold page."""

from tests.unit.dashboard.app_smoke import app_test


def test_fx_gold_page_renders_with_snapshot_warning(fake_streamlit_connection) -> None:
    app = app_test("5_FX_Gold.py")
    app.run()

    assert not app.exception
