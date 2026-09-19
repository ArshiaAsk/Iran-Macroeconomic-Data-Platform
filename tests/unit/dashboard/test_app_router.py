"""Router coverage for the dashboard entrypoint.

Per-page smoke tests now drive the router entrypoint through
``app_smoke.app_test`` (``AppTest.from_file(app).switch_page(...).run()``), which
is the path a real session takes. Wave 0 showed that ``switch_page`` executes the
page directly without re-running ``st.navigation``, so this test is still the
router's single automatable coverage point: an entrypoint run asserting the
default page. The direct-file fallback (``app_test(..., use_router=False)``)
remains available for pages that must be rendered standalone.
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
