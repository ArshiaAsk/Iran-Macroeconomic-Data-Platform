"""Streamlit entry point for the Iran Macroeconomic Data Platform.

The entrypoint owns page configuration and the navigation router; the individual
page modules under ``dashboard/pages/`` stay standalone-runnable so they can
still be driven directly by ``AppTest``.
"""

import streamlit as st

from dashboard.components.direction import inject_direction_css
from dashboard.connection import get_connection
from dashboard.i18n import t
from dashboard.navigation import GROUPS, PAGES, PageSpec


def _build_page(spec: PageSpec) -> st.Page:
    """Build one router page from its registry entry.

    The nav label comes from the string catalog (``nav.<key>``), so the sidebar
    and the page's own ``st.title`` (``page.<key>``) share one translated value
    instead of a hardcoded literal.
    """
    return st.Page(
        spec.path,
        title=t(f"nav.{spec.key}"),
        icon=spec.icon,
        default=spec.is_default,
    )


def build_navigation() -> dict[str, list[st.Page]]:
    """Group the registry's pages for ``st.navigation``, in declared group order."""
    grouped: dict[str, list[st.Page]] = {t(f"group.{key}"): [] for key in GROUPS}
    for spec in PAGES:
        grouped[t(f"group.{spec.group}")].append(_build_page(spec))
    return grouped


def render_database_status() -> None:
    """Render the database-status banner in the sidebar."""
    connection = get_connection()
    if connection.test_connection():
        st.success(t("app.db_connected"))
    else:
        st.error(t("app.db_unavailable"))


def main() -> None:
    """Configure the shell and run the page selected by the router."""
    st.set_page_config(
        page_title=t("app.title"),
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    navigation = st.navigation(build_navigation(), position="sidebar")
    with st.sidebar:
        # Injected in the sidebar so the (invisible) stylesheet element cannot
        # push page content down, and re-emitted every run so Streamlit keeps it.
        inject_direction_css()
        render_database_status()
    navigation.run()


if __name__ == "__main__":
    main()
