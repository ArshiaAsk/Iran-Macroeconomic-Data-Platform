"""Streamlit entry point for the Iran Macroeconomic Data Platform.

The entrypoint owns page configuration and the navigation router; the individual
page modules under ``dashboard/pages/`` stay standalone-runnable so they can
still be driven directly by ``AppTest``.
"""

import streamlit as st

from dashboard.connection import get_connection
from dashboard.navigation import GROUPS, PAGES, PageSpec


def _build_page(spec: PageSpec) -> st.Page:
    """Build one router page from its registry entry."""
    return st.Page(spec.path, title=spec.title, icon=spec.icon, default=spec.is_default)


def build_navigation() -> dict[str, list[st.Page]]:
    """Group the registry's pages for ``st.navigation``, in declared group order."""
    grouped: dict[str, list[st.Page]] = {group: [] for group in GROUPS}
    for spec in PAGES:
        grouped[spec.group].append(_build_page(spec))
    return grouped


def render_database_status() -> None:
    """Render the database-status banner in the sidebar."""
    connection = get_connection()
    if connection.test_connection():
        st.success("Database connected")
    else:
        st.error("Database unavailable. Start PostgreSQL with `make db-up` and run migrations.")


def main() -> None:
    """Configure the shell and run the page selected by the router."""
    st.set_page_config(
        page_title="Iran Macroeconomic Data Platform",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    navigation = st.navigation(build_navigation(), position="sidebar")
    with st.sidebar:
        render_database_status()
    navigation.run()


if __name__ == "__main__":
    main()
