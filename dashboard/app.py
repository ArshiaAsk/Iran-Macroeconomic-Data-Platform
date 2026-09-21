"""Streamlit entry point for the Iran Macroeconomic Data Platform.

The entrypoint owns page configuration and the navigation router; the individual
page modules under ``dashboard/pages/`` stay standalone-runnable so they can
still be driven directly by ``AppTest``.
"""

import streamlit as st

from dashboard.components.direction import inject_direction_css
from dashboard.components.layout import render_status_dot, render_top_bar
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
    """Render the database-status indicator in the sidebar's pinned footer.

    The indicator uses the shared status-dot component (Task 11) rather than a
    native ``st.success``/``st.error`` alert: the sidebar footer needs a compact
    dot + label, not a full alert banner. The tone is ``ok`` when the database
    is reachable and ``err`` when it is not. The label text resolves through
    :func:`dashboard.i18n.t`.
    """
    connection = get_connection()
    if connection.test_connection():
        render_status_dot(t("app.db_status_online"), tone="ok")
    else:
        render_status_dot(t("app.db_status_offline"), tone="err")


def _current_page_spec(selected_page: st.Page) -> PageSpec:
    """Find the registry spec matching the page currently selected by the router.

    ``st.navigation`` returns the current :class:`Page`, and ``Page.title`` is set
    to ``t(f"nav.{spec.key}")`` by :func:`_build_page`, so the selected page maps
    back to exactly one :class:`PageSpec`.

    Args:
        selected_page: The :class:`Page` returned by ``st.navigation``.

    Returns:
        The matching :class:`PageSpec` from the registry.

    Raises:
        RuntimeError: When the selected page title does not match any registry
            entry (this should never happen because the router builds its pages
            from the registry).
    """
    selected_title = selected_page.title
    for spec in PAGES:
        if t(f"nav.{spec.key}") == selected_title:
            return spec
    message = f"could not find PageSpec for selected page title: {selected_title!r}"
    raise RuntimeError(message)


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
        # The brand text is resolved here (not in the CSS module) and escaped
        # before interpolation by brand_sidebar_css().
        inject_direction_css(brand_text=t("app.brand"))
        render_database_status()

    spec = _current_page_spec(navigation)
    render_top_bar(
        group_label=t(f"group.{spec.group}"),
        page_label=t(f"page.{spec.key}"),
    )
    navigation.run()


if __name__ == "__main__":
    main()
