"""AppTest smoke test for the trade, welfare, and energy page."""

from tests.unit.dashboard.app_smoke import app_test


def test_trade_welfare_energy_page_renders(fake_streamlit_connection) -> None:
    app = app_test("4_Trade_Welfare_Energy.py")
    app.run()

    assert not app.exception
