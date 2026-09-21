"""Streamlit entry point for the Iran Macroeconomic Data Platform.

The entrypoint owns page configuration and the navigation router; the individual
page modules under ``dashboard/pages/`` stay standalone-runnable so they can
still be driven directly by ``AppTest``.
"""

from typing import Protocol

import streamlit as st

from dashboard.components.direction import inject_direction_css
from dashboard.components.layout import render_status_dot, render_top_bar
from dashboard.connection import get_connection
from dashboard.i18n import t
from dashboard.navigation import GROUPS, PAGES, PageSpec


class _PageLike(Protocol):
    """The one attribute :func:`_current_page_spec` reads off a router page.

    A structural type (rather than ``st.Page``) keeps the lookup testable
    without a Streamlit script run, where ``st.Page`` degrades to a stub. The
    member is a read-only property because ``StreamlitPage.url_path`` is one,
    so a plain settable attribute would not match it structurally.
    """

    @property
    def url_path(self) -> str:
        ...


def _page_url_path(spec: PageSpec) -> str:
    """Return the ``url_path`` the registry gives a page's ``st.Page``.

    Each page is built with ``url_path=spec.key`` (see :func:`_build_page`), so
    the selected page maps back to its registry entry by a stable identifier
    instead of by display text. The one exception is the default page:
    ``StreamlitPage.url_path`` returns the empty string when ``default=True``,
    regardless of the value passed in.
    """
    return "" if spec.is_default else spec.key


def _default_page_spec() -> PageSpec:
    """Return the registry's default page (the safe fallback spec)."""
    return next(spec for spec in PAGES if spec.is_default)


def _build_page(spec: PageSpec) -> st.Page:
    """Build one router page from its registry entry.

    The nav label comes from the string catalog (``nav.<key>``), so the sidebar
    and the page's own ``st.title`` (``page.<key>``) share one translated value
    instead of a hardcoded literal. ``url_path`` is set to the registry key so
    the router's selected page can be mapped back to its :class:`PageSpec`
    without comparing display strings (Step 0c).
    """
    return st.Page(
        spec.path,
        title=t(f"nav.{spec.key}"),
        icon=spec.icon,
        url_path=_page_url_path(spec),
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


def _current_page_spec(selected_page: _PageLike) -> PageSpec:
    """Find the registry spec matching the page currently selected by the router.

    The match is on ``url_path``, which :func:`_build_page` sets to the registry
    key (:func:`_page_url_path`), so the lookup is derived from the registry's
    own identifiers and **never** from display text — a translated nav label
    cannot break the breadcrumb (Step 0c).

    A page that is not in the registry (or a stub without ``url_path``) falls
    back to the default page's spec instead of raising: the breadcrumb is
    chrome, and a missing label must not take down a page that otherwise
    renders.

    Args:
        selected_page: The page returned by ``st.navigation``.

    Returns:
        The matching :class:`PageSpec`, or the default page's spec on a miss.
    """
    selected_path = getattr(selected_page, "url_path", "")
    for spec in PAGES:
        if _page_url_path(spec) == selected_path:
            return spec
    return _default_page_spec()


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
