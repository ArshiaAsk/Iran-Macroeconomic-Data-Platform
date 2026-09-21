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
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT, html_texts


def test_entrypoint_renders_the_default_page(fake_streamlit_connection: None) -> None:
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    default_key = next(spec.key for spec in PAGES if spec.is_default)
    # The in-page title and the sidebar label share the page's i18n key.
    assert [title.value for title in app.title] == [t(f"page.{default_key}")]
    assert t(f"page.{default_key}") == t(f"nav.{default_key}")


def test_database_status_renders_a_status_dot_not_an_alert(
    fake_streamlit_connection: None,
) -> None:
    """The DB status is the pinned status-dot component (Task 27), not a native
    ``st.success``/``st.error`` alert."""
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    html = " ".join(html_texts(app))
    assert "dot tone-ok" in html or "dot tone-err" in html
    assert t("app.db_status_online") in html or t("app.db_status_offline") in html


def test_brand_text_appears_in_the_injected_stylesheet(
    fake_streamlit_connection: None,
) -> None:
    """The sidebar brand is CSS-pinned (fallback 2): the brand text from
    ``t("app.brand")`` is interpolated into the stylesheet, not rendered by
    ``st.logo`` or a ``st.markdown`` brand call."""
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    styles = " ".join(m.value for m in app.markdown)
    assert t("app.brand") in styles


def test_top_bar_renders_breadcrumb_derived_from_registry(
    fake_streamlit_connection: None,
) -> None:
    """The top-bar breadcrumb is derived from ``PAGES``/``GROUPS`` (Task 28):
    the root, the default page's group label and the page title all appear."""
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    default_spec = next(spec for spec in PAGES if spec.is_default)
    fragments = html_texts(app)
    breadcrumb = next(f for f in fragments if "top-bar-breadcrumb" in f)
    assert t("shell.breadcrumb_root") in breadcrumb
    assert t(f"group.{default_spec.group}") in breadcrumb
    assert t(f"page.{default_spec.key}") in breadcrumb


def test_top_bar_renders_last_collection_stamp(
    fake_streamlit_connection: None,
) -> None:
    """The right-hand stamp carries the timezone label, always present."""
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    stamp = next(f for f in html_texts(app) if "top-bar-stamp" in f)
    assert t("shell.timezone") in stamp
