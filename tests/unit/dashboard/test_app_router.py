"""Router coverage for the dashboard entrypoint.

Per-page smoke tests keep targeting page files directly: Wave 0 showed that
``switch_page`` executes the page without re-running the entrypoint, so migrating
them would add churn without covering the router. This is the router's single
automatable coverage point.
"""

from streamlit.testing.v1 import AppTest

from dashboard.i18n import t
from dashboard.navigation import PAGES
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT


def test_entrypoint_renders_the_default_page(fake_streamlit_connection) -> None:
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    default_key = next(spec.key for spec in PAGES if spec.is_default)
    # The in-page title and the sidebar label share the page's i18n key.
    assert [title.value for title in app.title] == [t(f"page.{default_key}")]
    assert t(f"page.{default_key}") == t(f"nav.{default_key}")
