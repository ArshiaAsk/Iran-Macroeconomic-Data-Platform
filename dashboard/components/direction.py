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

from dashboard.components.tokens import CHART_CATEGORICAL_COLORS, css_custom_properties, token

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
        # Shared-component hooks (Tasks 17-22). These are the keyed-container
        # classes Streamlit adds for `st.container(key=...)`: the class attribute
        # carries `st-key-<sanitized key>`, so an attribute substring selector
        # scopes a rule to one component without a hashed `st-emotion-cache-*`.
        "callout": '[class*="st-key-callout-"]',
        "kpi_band": '[class*="st-key-kpi-band-"]',
        "kpi_secondary_group": '[class*="st-key-kpi-"][class*="-secondary-0-tone-"]',
        "kpi_column": '[data-testid="stColumn"]',
        "kpi_value": '[data-testid="stMetricValue"]',
        "kpi_tone_muted": '[class*="st-key-kpi-"][class*="-tone-muted"]',
        "kpi_tone_ok": '[class*="st-key-kpi-"][class*="-tone-ok"]',
        "kpi_tone_warn": '[class*="st-key-kpi-"][class*="-tone-warn"]',
        "kpi_tone_err": '[class*="st-key-kpi-"][class*="-tone-err"]',
        "kpi_tone_accent": '[class*="st-key-kpi-"][class*="-tone-accent"]',
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

#: Component CSS for the RTL HTML table and its chip/dot/two-line cells (Task
#: 15). Emitted once by :func:`inject_direction_css` rather than a ``<style>`` per
#: table. Values mirror ``docs/design/phase-7.2/overview-redesign-mockup.html``
#: (``.dt``/``.chip``/``.dot``/``.unit``/``.ltr``) and read the design tokens, so
#: no literal colour appears here. Tone classes are ``tone-*``; the tone is
#: validated against a closed set in the component before it reaches a class name.
_TABLE_COMMENT: Final[str] = (
    "/* RTL HTML table + chip/dot/two-line cells (Task 15). Mirrors the mockup's "
    ".dt/.chip/.dot rules with design tokens; emitted once by "
    "inject_direction_css, never per table. */"
)

#: Table rules as complete CSS strings (class selectors, not data-testid hooks).
_TABLE_RULES: Final[tuple[str, ...]] = (
    ".dt-wrap { background: var(--surface); border: 1px solid var(--border); "
    "border-radius: var(--radius-lg); overflow-x: auto; }",
    ".dt { width: 100%; border-collapse: separate; border-spacing: 0; }",
    ".dt th { background: var(--surface-2); color: var(--text-2); "
    "font-size: 12.5px; font-weight: 600; text-align: start; padding: 9px 14px; "
    "border-bottom: 1px solid var(--border-strong); white-space: nowrap; "
    "line-height: 1.6; }",
    ".dt td { height: 52px; padding: 0 14px; "
    "border-bottom: 1px solid var(--border); white-space: nowrap; line-height: 1.5; }",
    ".dt tbody tr:last-child td { border-bottom: 0; }",
    ".dt tbody tr:hover td { background: var(--hover); }",
    ".dt.compact td { height: 40px; padding: 0 10px; font-size: 13.5px; " "line-height: 1.45; }",
    ".dt .num { font-variant-numeric: tabular-nums; }",
    ".dt .name { font-weight: 600; }",
    ".dt .sm { font-size: 12px; color: var(--text-3); display: block; }",
    ".dt .ltr { direction: ltr; unicode-bidi: isolate; "
    "font-family: var(--font-mono); font-size: 11.5px; display: inline-block; "
    "max-width: 24ch; overflow: hidden; text-overflow: ellipsis; "
    "vertical-align: bottom; }",
    ".dt .idl { display: block; color: var(--text-3); margin-top: 1px; }",
    ".unit { direction: ltr; unicode-bidi: isolate; display: inline-block; "
    "font-family: var(--font-mono); font-size: 11.5px; background: var(--neutral-bg); "
    "color: var(--text-2); padding: 1px 7px; border-radius: 4px; "
    "max-width: 20ch; overflow: hidden; text-overflow: ellipsis; }",
    ".na { color: var(--border-strong); }",
    ".chip { display: inline-flex; align-items: center; gap: 6px; padding: 0 8px; "
    "border-radius: 4px; font-size: 12px; font-weight: 500; line-height: 22px; }",
    '.chip::before { content: ""; width: 6px; height: 6px; border-radius: 50%; '
    "background: currentColor; }",
    ".dot { display: inline-flex; align-items: center; gap: 7px; font-size: 13px; "
    "font-weight: 500; }",
    '.dot::before { content: ""; width: 8px; height: 8px; border-radius: 50%; '
    "background: currentColor; }",
    ".tone-ok { color: var(--ok); }",
    ".tone-warn { color: var(--warn); }",
    ".tone-err { color: var(--err); }",
    ".tone-accent { color: var(--accent); }",
    ".tone-neutral { color: var(--text-2); }",
    ".chip.tone-ok { background: var(--ok-bg); }",
    ".chip.tone-warn { background: var(--warn-bg); }",
    ".chip.tone-err { background: var(--err-bg); }",
    ".chip.tone-accent { background: var(--accent-soft); }",
    ".chip.tone-neutral { background: var(--neutral-bg); }",
    ".tm { display: flex; gap: 0; }",
    '.tm > span + span::before { content: "·"; margin: 0 7px; }',
)

#: Shared-component CSS (Tasks 17-22). Hooks are the keyed-container classes
#: (``.st-key-<key>``) and the stable alert ``data-testid``s, both probed on
#: Streamlit 1.61.1 and recorded in ``docs/phase-7.2/design-system.md``. Emitted
#: once by :func:`inject_direction_css`; no component emits its own ``<style>``.
_COMPONENT_COMMENT: Final[str] = (
    "/* Shared-component hooks (Tasks 17-22): keyed-container classes "
    "(.st-key-<key>) + stable alert data-testids, probed on Streamlit 1.61.1 "
    "(design-system.md). Emitted once by inject_direction_css, never per "
    "component. */"
)

#: KPI value tone -> design-token name (Task 19). ``default`` is deliberately
#: absent: it inherits the metric's own colour, so no rule is needed.
_KPI_TONE_TOKENS: Final[tuple[tuple[str, str], ...]] = (
    ("muted", "text-2"),
    ("ok", "ok"),
    ("warn", "warn"),
    ("err", "err"),
    ("accent", "accent"),
)

#: One rule per non-default KPI tone, colouring only the metric value.
_KPI_TONE_RULES: Final[tuple[str, ...]] = tuple(
    f'{CSS_SELECTORS[f"kpi_tone_{tone}"]} {CSS_SELECTORS["kpi_value"]} '
    f"{{ color: var(--{token_name}); }}"
    for tone, token_name in _KPI_TONE_TOKENS
)

#: Component rules as complete CSS strings, in stylesheet order. Each rule's
#: selector is built from the :data:`CSS_SELECTORS` registry so the hook has one
#: source (``_TABLE_RULES`` predates the registry and uses plain class selectors).
_COMPONENT_RULES: Final[tuple[str, ...]] = (
    # Callout (Task 17). The amber/blue/red tint and the text colour come from the
    # `[theme]` alert options; this adds only the mockup's left accent bar and the
    # info glyph. The native alert renders no icon element, so the glyph is a CSS
    # shape (a ring with the "i" dot and stem drawn as background layers) rather
    # than the mockup's inline SVG, which DOMPurify strips.
    f'{CSS_SELECTORS["callout"]} [data-testid="stAlertContainer"] {{ '
    "border-inline-start: 3px solid currentColor; border-radius: var(--radius); "
    "display: flex; align-items: flex-start; gap: 10px; }",
    f'{CSS_SELECTORS["callout"]} [data-testid="stAlertContainer"]::before {{ '
    'content: ""; flex: none; box-sizing: border-box; width: 15px; height: 15px; '
    "margin-block-start: 7px; border: 1.5px solid currentColor; border-radius: 50%; "
    "background: radial-gradient(circle, currentColor 0 1.1px, transparent 1.2px) "
    "50% 26% / 100% 100% no-repeat, "
    "linear-gradient(currentColor, currentColor) 50% 74% / 1.5px 5px no-repeat; }",
    # KPI band (Task 19): the mockup's larger corner radius, edge-to-edge columns,
    # a separator between every pair of cells and a stronger one at the start of
    # the secondary group. The `:has()` rule must follow the `+` rule: the two have
    # equal specificity, so source order decides the boundary cell.
    f'{CSS_SELECTORS["kpi_band"]} {{ border-radius: var(--radius-lg) !important; '
    "padding: 0 !important; }",
    f'{CSS_SELECTORS["kpi_band"]} {CSS_SELECTORS["kpi_column"]} '
    f'+ {CSS_SELECTORS["kpi_column"]} {{ border-inline-start: 1px solid var(--border); }}',
    f'{CSS_SELECTORS["kpi_band"]} {CSS_SELECTORS["kpi_column"]}'
    f':has({CSS_SELECTORS["kpi_secondary_group"]}) '
    "{ border-inline-start: 1px solid var(--border-strong); }",
    *_KPI_TONE_RULES,
)


def direction_css() -> str:
    """Return the scoped RTL/typography/chrome/table stylesheet as a string.

    The stylesheet has five sections: the design-token ``:root`` block (the
    single source for the palette/radii/fonts), the RTL typography rules, a
    comment-marked, version-named chrome block for the Streamlit shell selectors,
    the RTL HTML-table component rules, and the shared-component hook rules
    (emitted once, never per component).
    """
    header = "/* dashboard RTL + Persian typography + chrome: dashboard/components/direction.py */"
    root_block = css_custom_properties()
    rules = [f"{CSS_SELECTORS[selector]} {{ {declarations} }}" for selector, declarations in _RULES]
    chrome_rules = [
        f"{CSS_SELECTORS[selector]} {{ {declarations} }}"
        for selector, declarations in _CHROME_RULES
    ]
    component_rules = list(_COMPONENT_RULES)
    return "\n".join(
        [
            header,
            root_block,
            *rules,
            _CHROME_COMMENT,
            *chrome_rules,
            _TABLE_COMMENT,
            *_TABLE_RULES,
            _COMPONENT_COMMENT,
            *component_rules,
        ]
    )


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
    """Build the shared Plotly template for dashboard figures.

    The template carries typography, the categorical palette, token grid/border
    colours and RTL-friendly legend/title placement. Chart builders still own
    figure sizing (``width``/``height``/``autosize``) and margins.

    RTL decision (recorded in the Task 14 execution-log entry): the legend and
    title are aligned for right-to-left reading, but the **time axis is not
    reversed** — time flows left to right on the LTR plot canvas (the grid stays
    LTR per AGENTS.md), so only the chrome around the plot is RTL-aware.

    Returns:
        A template carrying palette, grid, legend/title placement and typography,
        so chart builders keep their own sizing, margins and trace layout.
    """
    template = go.layout.Template()
    template.layout.font = {
        "family": FONT_STACK,
        "size": PLOTLY_FONT_SIZE,
    }
    template.layout.title = {
        "font": {"family": FONT_STACK, "size": PLOTLY_TITLE_FONT_SIZE},
        # Right-aligned title reads naturally at the start of an RTL line.
        "x": 1,
        "xanchor": "right",
    }
    template.layout.legend = {
        "font": {"family": FONT_STACK},
        # Horizontal, above the plot, right-aligned: the RTL reading start.
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "right",
        "x": 1,
    }
    template.layout.hoverlabel = {"font": {"family": FONT_STACK}}
    template.layout.colorway = list(CHART_CATEGORICAL_COLORS)
    axis_layout = {
        "tickfont": {"family": FONT_STACK},
        "title": {"font": {"family": FONT_STACK}},
        "gridcolor": token("border"),
        "linecolor": token("border-strong"),
        "zerolinecolor": token("border-strong"),
    }
    template.layout.xaxis = axis_layout
    template.layout.yaxis = axis_layout
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
