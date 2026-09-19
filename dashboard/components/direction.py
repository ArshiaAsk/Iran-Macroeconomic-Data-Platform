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

The dashboard is local-only, so there is no ``@font-face``, no CDN, no downloaded
font asset and no new dependency: the family stack falls back through whatever the
analyst's OS provides.

Nothing here localizes a chart. :func:`plotly_template` is the single helper later
chart work will inherit from; existing chart builders are untouched.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

import plotly.graph_objects as go
import streamlit as st
from plotly.basedatatypes import BaseFigure

__all__ = [
    "CSS_SELECTORS",
    "FONT_STACK",
    "apply_plotly_typography",
    "direction_css",
    "inject_direction_css",
    "plotly_template",
]

FONT_STACK: Final[str] = '"Vazirmatn", "IRANSans", "Tahoma", "Segoe UI", sans-serif'
"""OS-only Persian-capable stack; no webfont is fetched or vendored."""

PLOTLY_FONT_SIZE: Final[int] = 13
PLOTLY_TITLE_FONT_SIZE: Final[int] = 17

#: Every DOM selector this module styles. Streamlit's internal test ids are the
#: documented instability here, so they live in one mapping instead of being
#: scattered through rule strings.
CSS_SELECTORS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "sidebar": '[data-testid="stSidebar"]',
        "sidebar_nav": '[data-testid="stSidebarNav"]',
        "markdown": '[data-testid="stMarkdownContainer"]',
        "heading": '[data-testid="stHeading"], h1, h2, h3, h4, h5, h6',
        "metric": '[data-testid="stMetric"]',
        "metric_label": '[data-testid="stMetricLabel"]',
        "widget_label": '[data-testid="stWidgetLabel"]',
        "form_label": '[data-testid="stForm"] label',
        "dataframe": '[data-testid="stDataFrame"]',
        "plotly_chart": '[data-testid="stPlotlyChart"]',
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


def direction_css() -> str:
    """Return the scoped RTL/typography stylesheet as a string."""
    header = "/* dashboard RTL + Persian typography: dashboard/components/direction.py */"
    rules = [f"{CSS_SELECTORS[selector]} {{ {declarations} }}" for selector, declarations in _RULES]
    return "\n".join([header, *rules])


def inject_direction_css() -> None:
    """Inject the scoped stylesheet into the running app.

    Called once per script run by the entrypoint. It is intentionally not guarded
    by ``st.session_state``: Streamlit drops elements that a run does not re-emit,
    so a guard would remove the stylesheet on the next rerun.
    """
    st.markdown(direction_css(), unsafe_allow_html=True)


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
