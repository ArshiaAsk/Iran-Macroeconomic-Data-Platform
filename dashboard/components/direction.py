"""RTL direction and Persian-capable typography for the dashboard.

Streamlit has no RTL mode, so this module owns the one place where the DOM is
touched: a small, deliberately scoped stylesheet plus a Plotly template. Two
rules keep that survivable across Streamlit releases:

- every DOM selector is declared once in :data:`CSS_SELECTORS`;
- rules stay narrow (sidebar, headings, markdown, metric blocks, form labels) and
  never flip the whole flex tree — flipping containers breaks Plotly's sizing, and
  the dataframe grid stays LTR by design (localized headers and Persian digits are
  applied later, but column order and the grid itself remain LTR and are
  documented as a known limitation rather than fought).

Phase 7.2 (D4, ratified) vendors Vazirmatn locally: the font is declared in
``.streamlit/config.toml`` via ``[[theme.fontFaces]]`` and served by Streamlit's
static serving from ``dashboard/static/`` at ``app/static/Vazirmatn.ttf`` (no CDN,
no webfont fetch). :data:`FONT_STACK` keeps a Persian-capable OS fallback after
``Vazirmatn`` so the UI still renders Persian if the vendored file is unavailable.

Nothing here localizes a chart. :func:`plotly_template` is the single helper later
chart work will inherit from; existing chart builders are untouched.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

import plotly.graph_objects as go
import streamlit as st
from plotly.basedatatypes import BaseFigure

from dashboard.components.tokens import css_custom_properties

__all__ = [
    "CSS_SELECTORS",
    "FONT_STACK",
    "apply_plotly_typography",
    "direction_css",
    "inject_direction_css",
    "plotly_template",
]

FONT_STACK: Final[str] = '"Vazirmatn", "IRANSans", "Tahoma", "Segoe UI", sans-serif'
"""Persian-capable stack; ``Vazirmatn`` is vendored and served by static serving,
the rest are OS fallbacks so the UI still renders Persian if the file is absent."""

PLOTLY_FONT_SIZE: Final[int] = 13
PLOTLY_TITLE_FONT_SIZE: Final[int] = 17

#: Every DOM selector this module styles. Streamlit's internal test ids are the
#: documented instability here, so they live in one mapping instead of being
#: scattered through rule strings.
CSS_SELECTORS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "sidebar": '[data-testid="stSidebar"]',
        "sidebar_content": '[data-testid="stSidebarContent"]',
        "sidebar_header": '[data-testid="stSidebarHeader"]',
        "sidebar_nav": '[data-testid="stSidebarNav"]',
        "sidebar_nav_link_active": '[data-testid="stSidebarNavLink"][aria-current="page"]',
        "sidebar_user_content": '[data-testid="stSidebarUserContent"]',
        "markdown": '[data-testid="stMarkdownContainer"]',
        "heading": '[data-testid="stHeading"], h1, h2, h3, h4, h5, h6',
        "metric": '[data-testid="stMetric"]',
        "metric_label": '[data-testid="stMetricLabel"]',
        "widget_label": '[data-testid="stWidgetLabel"]',
        "form_label": '[data-testid="stForm"] label',
        "dataframe": '[data-testid="stDataFrame"]',
        "plotly_chart": '[data-testid="stPlotlyChart"]',
        "main_block_container": '[data-testid="stMainBlockContainer"]',
    }
)

#: Scoped rules as ``(selector key, declarations)`` in stylesheet order.
_RULES: Final[tuple[tuple[str, str], ...]] = (
    ("sidebar", f"direction: rtl; text-align: right; font-family: {FONT_STACK};"),
    ("sidebar_nav", "direction: rtl; text-align: right;"),
    # Generous line-height keeps Persian ascenders/descenders and the mixed
    # Persian-digit runs readable in the RTL text blocks (Task 22 polish).
    (
        "markdown",
        f"direction: rtl; text-align: right; line-height: 1.9; font-family: {FONT_STACK};",
    ),
    ("heading", f"direction: rtl; text-align: right; line-height: 1.7; font-family: {FONT_STACK};"),
    ("metric", f"direction: rtl; text-align: right; font-family: {FONT_STACK};"),
    ("metric_label", "direction: rtl; text-align: right;"),
    ("widget_label", f"direction: rtl; text-align: right; font-family: {FONT_STACK};"),
    ("form_label", f"direction: rtl; text-align: right; font-family: {FONT_STACK};"),
    # Documented LTR posture: the dataframe grid and Plotly canvases keep their
    # left-to-right layout and sizing. Pinned explicitly so a future broad rule
    # cannot silently flip them.
    ("dataframe", "direction: ltr;"),
    ("plotly_chart", "direction: ltr;"),
)

#: Streamlit-chrome selectors verified on Streamlit 1.61.1
#: (``docs/phase-7.2/wave-0-spike.md`` §4.3/§4.4). Every hook here is a stable
#: ``data-testid`` or the ``[aria-current="page"]`` attribute; the hashed
#: ``st-emotion-cache-*`` active-link class is deliberately **not** used.
#: Widths need ``!important`` against Streamlit's inline styles. The native
#: ``[data-testid="stHeader"]`` is 60 px (the mockup's 48 px top bar is a new
#: element built in Task 28); the main container's top padding is intentionally
#: **not** touched here. Brand and top-bar rules land in Tasks 27/28.
_CHROME_COMMENT: Final[str] = (
    "/* Streamlit-chrome selectors — verified on Streamlit 1.61.1 "
    "(wave-0-spike.md §4.3/§4.4). Stable data-testid hooks + "
    '[aria-current="page"]; widths need !important. Native header '
    '[data-testid="stHeader"] is 60 px (mockup top bar 48 px → Task 28). '
    "Do not extend without re-running the selector probe. */"
)

#: Chrome rules as ``(selector key, declarations)`` in stylesheet order.
_CHROME_RULES: Final[tuple[tuple[str, str], ...]] = (
    ("sidebar", "width: 256px !important; min-width: 256px !important;"),
    ("sidebar_content", "display: flex !important; flex-direction: column;"),
    ("sidebar_header", "order: 0;"),
    ("sidebar_nav", "order: 1;"),
    ("sidebar_user_content", "order: 2; margin-top: auto;"),
    (
        "sidebar_nav_link_active",
        "background: var(--accent-soft); color: var(--accent); "
        "font-weight: 600; border-inline-start: 3px solid var(--accent);",
    ),
    ("main_block_container", "max-width: 1360px !important;"),
)


def direction_css() -> str:
    """Return the scoped RTL/typography/chrome stylesheet as a string.

    The stylesheet has three sections: the design-token ``:root`` block (the
    single source for the palette/radii/fonts), the RTL typography rules, and a
    comment-marked, version-named chrome block for the Streamlit shell selectors.
    """
    header = "/* dashboard RTL + Persian typography + chrome: dashboard/components/direction.py */"
    root_block = css_custom_properties()
    rules = [f"{CSS_SELECTORS[selector]} {{ {declarations} }}" for selector, declarations in _RULES]
    chrome_rules = [
        f"{CSS_SELECTORS[selector]} {{ {declarations} }}"
        for selector, declarations in _CHROME_RULES
    ]
    return "\n".join([header, root_block, *rules, _CHROME_COMMENT, *chrome_rules])


def inject_direction_css() -> None:
    """Inject the scoped stylesheet into the running app.

    The rules are wrapped in a ``<style>`` element: ``st.markdown`` renders a bare
    CSS string as visible page text, so without the wrapper the stylesheet source
    leaks into the DOM instead of styling it.

    Called once per script run by the entrypoint. It is intentionally not guarded
    by ``st.session_state``: Streamlit drops elements that a run does not re-emit,
    so a guard would remove the stylesheet on the next rerun.
    """
    st.markdown(f"<style>{direction_css()}</style>", unsafe_allow_html=True)


def plotly_template() -> go.layout.Template:
    """Build the shared Plotly typography template for dashboard figures.

    Returns:
        A template carrying only font/typography settings, so chart builders keep
        their own sizing, axes and trace layout.
    """
    template = go.layout.Template()
    template.layout.font = {
        "family": FONT_STACK,
        "size": PLOTLY_FONT_SIZE,
    }
    template.layout.title = {
        "font": {"family": FONT_STACK, "size": PLOTLY_TITLE_FONT_SIZE},
    }
    template.layout.legend = {"font": {"family": FONT_STACK}}
    template.layout.hoverlabel = {"font": {"family": FONT_STACK}}
    axis_typography = {
        "tickfont": {"family": FONT_STACK},
        "title": {"font": {"family": FONT_STACK}},
    }
    template.layout.xaxis = axis_typography
    template.layout.yaxis = axis_typography
    return template


def apply_plotly_typography(figure: BaseFigure) -> BaseFigure:
    """Apply the dashboard template to a figure and return it.

    Sizing and trace layout already set on the figure are left untouched: the
    template only supplies typography that the figure has not overridden.

    Args:
        figure: Plotly figure to style in place

    Returns:
        The same figure, for chaining
    """
    figure.update_layout(template=plotly_template())
    return figure
