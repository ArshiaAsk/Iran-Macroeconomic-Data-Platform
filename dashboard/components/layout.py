"""Shared, native-first layout components for the Phase 7.2 dashboard.

Every page composition in the dashboard draws its header, callouts, KPI cells,
section headers, filter bar and states from this module (the D11 layout contract).
The components are **native-first** (D13): they wrap ``st.warning``/``st.info``/
``st.error``, ``st.title``, ``st.subheader``, ``st.metric``,
``st.container(border=True)``, ``st.columns``, ``st.badge`` and ``st.page_link``,
so AppTest keeps seeing typed elements and the HTML-escaping surface stays small.
``st.html`` is used only where no native element exists (the bar itself inside a
bar-list row, and a standalone status dot).

Four rules are load-bearing:

- **All user-visible text resolves through** :func:`dashboard.i18n.t`. No
  component passes a Persian literal to a Streamlit display call, so
  ``test_literal_guard.py`` stays green.
- **A keyed container is the CSS hook.** Streamlit 1.61.1 adds the class
  ``st-key-<key>`` to the container's ``stVerticalBlock`` (probed and recorded in
  ``docs/phase-7.2/design-system.md``), so a component is styled by a scoped rule
  in :mod:`dashboard.components.direction` instead of a hashed
  ``st-emotion-cache-*`` class. Container keys must be unique within a run, so a
  component that can legitimately render twice derives its key from its argument
  and accepts an explicit override.
- **A tone is a closed set.** An unknown tone raises rather than reaching a class
  attribute, so a data value can never inject a CSS class.
- **A component establishes its own RTL context.** Streamlit's main block is
  ``dir: ltr``, so an inherited ``inline-start``/``flex-start`` is the *left*
  edge and a ``st.columns`` row reads left-to-right. Each component's container
  therefore declares ``direction: rtl`` in its scoped CSS, which is what makes a
  cell order, an accent bar or a bar fill land on the right edge as in the
  mockup. The Task 15 table does the same thing with ``dir="rtl"`` on its
  wrapper.
"""

from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Final, Literal, NamedTuple, TypeAlias

import streamlit as st

from dashboard.components.escaping import escape_html
from dashboard.components.html_table import TONES
from dashboard.formatting import format_number
from dashboard.i18n import t
from dashboard.labels import domain_label
from dashboard.navigation import page_for_domain
from src.etl.bronze import STATUS_FAILED, STATUS_PARTIAL, STATUS_SUCCESS

__all__ = [
    "CALLOUT_TONES",
    "KPI_TONES",
    "STATUS_CHIPS",
    "STATUS_CHIP_FALLBACK",
    "BarRow",
    "KpiCell",
    "render_bar_list",
    "render_callout",
    "render_kpi_band",
    "render_page_header",
    "render_status_chip",
    "render_status_dot",
]

BadgeColor: TypeAlias = Literal[
    "red", "orange", "yellow", "blue", "green", "violet", "gray", "grey", "primary"
]
"""The colours ``st.badge`` accepts; kept local so the mapping below is typed."""

CALLOUT_TONES: Final[frozenset[str]] = frozenset({"warn", "info", "error"})
"""Accepted callout tones; each maps to one native Streamlit alert element."""

KPI_TONES: Final[frozenset[str]] = frozenset({"default", "muted", "ok", "warn", "err", "accent"})
"""Accepted KPI value tones; each maps to a design token (see ``direction.py``).

``default`` inherits the metric's own colour and ``muted`` renders the secondary
text colour; the rest resolve to their token.
"""

STATUS_CHIPS: Final[Mapping[str, tuple[str, BadgeColor]]] = MappingProxyType(
    {
        STATUS_SUCCESS: ("value.status_success", "green"),
        STATUS_FAILED: ("value.status_failed", "red"),
        STATUS_PARTIAL: ("value.status_partial", "orange"),
    }
)
"""Collection-run status slug -> (catalog key, badge colour)."""

STATUS_CHIP_FALLBACK: Final[tuple[str, BadgeColor]] = ("value.status_unknown", "gray")
"""The chip for a slug outside :data:`STATUS_CHIPS`, so the mapping is total."""


class BarRow(NamedTuple):
    """One row of the indicators-by-domain bar list.

    Attributes:
        domain: Domain slug as stored in the catalog (``inflation``, ``fx``, …)
        indicator_count: Number of indicators in that domain (a count, never a
            measurement, so the bar list stays unit-safe). Named after the
            ``available_domains`` column; ``count`` would shadow ``tuple.count``.
    """

    domain: str
    indicator_count: int


class KpiCell(NamedTuple):
    """One KPI band cell.

    A :class:`NamedTuple` rather than a plain tuple so the optional fields are
    named at the call site while ``label_key``/``value`` stay positional.

    Attributes:
        label_key: Catalog key of the cell label
        value: **Already formatted** value (digit conversion is the caller's job)
        help_key: Optional catalog key of the tooltip copy
        tone: One of :data:`KPI_TONES`
        secondary: When true the cell joins the visually separated secondary group
        tag_key: Optional catalog key of a :func:`st.badge` tag rendered beneath the
            metric
    """

    label_key: str
    value: str
    help_key: str | None = None
    tone: str = "default"
    secondary: bool = False
    tag_key: str | None = None


#: The native alert renderer for each callout tone. ``error`` is the Streamlit
#: spelling of the mockup's red callout; the plan's vocabulary is ``error`` too.
_CALLOUT_RENDERERS: Final[dict[str, Callable[[str], object]]] = {
    "warn": st.warning,
    "info": st.info,
    "error": st.error,
}


def _validated(tone: str, allowed: frozenset[str], kind: str) -> str:
    """Return ``tone`` when it is in ``allowed``, else raise.

    Raising keeps the tone out of the class attribute, so a data value can never
    inject a CSS class.
    """
    if tone not in allowed:
        message = f"unknown {kind} tone: {tone!r} (expected one of {sorted(allowed)})"
        raise ValueError(message)
    return tone


def render_callout(
    key: str,
    *,
    tone: str = "warn",
    label_key: str | None = None,
    container_key: str | None = None,
) -> None:
    """Render the mockup's callout as a native Streamlit alert.

    The amber/blue/red tint comes from the ``[theme]`` alert colour options
    (Task 8); the left accent bar and the info glyph are the only CSS, scoped to
    this component's keyed container. The native alert ships **no** icon element
    (probed on Streamlit 1.61.1) and ``st.html`` strips ``<svg>``
    (``wave-0-spike.md`` §6), so the mockup's inline SVG is drawn in CSS instead.

    Args:
        key: Catalog key of the callout body text
        tone: ``"warn"``, ``"info"`` or ``"error"``
        label_key: Optional catalog key rendered as a bold prefix inside the body
        container_key: Optional disambiguator for the CSS hook. Defaults to
            ``key``; pass a distinct value when the same callout renders twice in
            one run (a repeated container key raises in Streamlit)

    Raises:
        ValueError: When ``tone`` is not a known callout tone
    """
    renderer = _CALLOUT_RENDERERS[_validated(tone, CALLOUT_TONES, "callout")]
    body = t(key)
    if label_key is not None:
        # Markdown emphasis, not markup: st.warning/info/error render markdown, so
        # the label is bold without any HTML (and without an escaping concern).
        body = f"**{t(label_key)}** {body}"
    with st.container(key=f"callout-{container_key if container_key is not None else key}"):
        renderer(body)


def render_page_header(
    title_key: str,
    *,
    callout_key: str | None = None,
    tone: str = "warn",
) -> None:
    """Render the dashboard's single page-header pattern (D11, AM-22).

    Every migrated page opens with this call instead of a raw ``st.title``, so the
    D11 layout contract has one header shape and the AST guard has one thing to
    check. The title stays native, so ``AppTest`` keeps seeing ``app.title``.

    No scoped CSS is needed: ``st.title`` already takes the theme's heading font and
    size, and the optional callout brings its own keyed-container hook
    (:func:`render_callout`). The page header therefore emits no ``st-key-*`` class
    of its own.

    Args:
        title_key: Catalog key of the page title (``page.<key>``)
        callout_key: Optional catalog key of a callout rendered beneath the title
        tone: Callout tone when ``callout_key`` is given

    Raises:
        ValueError: When ``tone`` is not a known callout tone and a callout is asked
            for
    """
    st.title(t(title_key))
    if callout_key is not None:
        render_callout(callout_key, tone=tone)


def _render_kpi_cell(cell: KpiCell) -> None:
    """Render one cell inside its already-created keyed container."""
    st.metric(
        t(cell.label_key),
        cell.value,
        help=t(cell.help_key) if cell.help_key is not None else None,
    )
    if cell.tag_key is not None:
        # A real st.badge element beneath the metric, not the `:orange-badge[…]`
        # markdown shorthand: the shorthand would leak its own syntax into the
        # metric label and into the tooltip's accessible name.
        st.badge(t(cell.tag_key), color="orange")


def render_kpi_band(cells: Sequence[KpiCell], *, key: str = "default") -> None:
    """Render the reusable KPI band (D2) as one bordered row of metric cells.

    The band is a single ``st.container(border=True)`` holding one
    ``st.columns`` row, so the cells line up as in the mockup; cells flagged
    ``secondary`` form a visually separated trailing group (a stronger inline
    separator, drawn by the ``:has()`` rule in :mod:`dashboard.components.direction`).
    Cell sizing comes from the theme (``metricValueFontSize`` and friends), so no
    component sets a font-size literal.

    The CSS hook is the per-cell keyed container,
    ``kpi-<band key>-<group>-<index>-tone-<tone>``: the group and index make the
    secondary boundary addressable, the tone makes the value colour addressable,
    and the band key keeps the key unique per cell so no two cells collide (a page
    may render more than one band). The CSS anchors on the ``kpi-`` prefix and the
    fixed ``-<group>-<index>-tone-<tone>`` suffix, so the band key in the middle is
    irrelevant to it.

    Args:
        cells: One :class:`KpiCell` per column, in display order
        key: Suffix that makes the band's keyed container unique when a page
            renders more than one band

    Raises:
        ValueError: When ``cells`` is empty or a cell carries an unknown tone
    """
    if not cells:
        message = "render_kpi_band needs at least one cell"
        raise ValueError(message)
    with st.container(border=True, key=f"kpi-band-{key}"):
        columns = st.columns(len(cells))
        group_indexes: dict[str, int] = {}
        for column, cell in zip(columns, cells, strict=True):
            tone = _validated(cell.tone, KPI_TONES, "kpi")
            group = "secondary" if cell.secondary else "primary"
            index = group_indexes.get(group, 0)
            group_indexes[group] = index + 1
            cell_key = f"kpi-{key}-{group}-{index}-tone-{tone}"
            with column, st.container(key=cell_key):
                _render_kpi_cell(cell)


def render_status_chip(status: str) -> None:
    """Render a standalone collection-run status chip via :func:`st.badge`.

    **Standalone use only.** A chip *inside* an RTL HTML table is the Task 15
    :class:`dashboard.components.html_table.StatusChip` cell, which renders the
    mockup's ``.chip`` markup; ``st.badge`` cannot be used there, because
    ``st.html`` is a separate element rather than an inline container.

    The slug -> tone mapping is **total**: an unrecognised slug renders the unknown
    chip instead of raising, because the slug is a data value
    (``DataCollectionLog.status``) and a new source status must not blank a page.

    Args:
        status: Collection status slug (``success``/``failed``/``partial``)
    """
    label_key, colour = STATUS_CHIPS.get(status, STATUS_CHIP_FALLBACK)
    st.badge(t(label_key), color=colour)


def render_status_dot(label: str, tone: str) -> None:
    """Render a standalone status dot: a coloured dot followed by its label.

    Streamlit has no native bare-dot element, so this is one escaped ``st.html``
    fragment. It reuses the ``.dot``/``.tone-*`` rules the Task 15 table CSS
    already emits — they are global class selectors, so they apply here too and no
    second copy of the CSS is needed.

    The fragment carries its own ``dir="rtl"`` block wrapper, so the dot anchors to
    the right edge wherever it is placed. ``.dot`` is inline-level, so without the
    wrapper its position would be decided by the host block's direction — which is
    LTR for Streamlit's main block, i.e. the dot would drift to the left.

    Args:
        label: **Already resolved** display text (call ``t(...)`` or a label map
            first); it is escaped before interpolation
        tone: One of the shared table tones (``ok``/``warn``/``err``/``accent``/
            ``neutral``)

    Raises:
        ValueError: When ``tone`` is not a known tone
    """
    validated = _validated(tone, TONES, "status dot")
    st.html(f'<div dir="rtl"><span class="dot tone-{validated}">{escape_html(label)}</span></div>')


def _bar_markup(count: int, largest: int) -> str:
    """Build one escaped bar fragment, filled in proportion to ``count``.

    The rail is a full-width track and the fill is anchored to the rail's RTL
    inline start (the right edge, as in the mockup): the ``.bar-rail`` rule in
    :mod:`dashboard.components.direction` declares ``direction: rtl``, because the
    fragment sits in Streamlit's LTR main block and would otherwise grow from the
    left. Only the numeric percentage is interpolated; nothing here is data-derived
    text.
    """
    share = 0.0 if largest <= 0 else max(0.0, min(1.0, count / largest)) * 100.0
    return (
        '<div class="bar-rail">' f'<div class="bar-fill" style="width:{share:.1f}%"></div>' "</div>"
    )


def render_bar_list(
    rows: Sequence[BarRow],
    total_label: str,
    *,
    key: str = "default",
) -> None:
    """Render the indicators-by-domain bar list (AM-17).

    Each row is composed with native ``st.columns`` because the label must stay a
    native ``st.page_link``: only the bar itself is an ``st.html`` fragment
    (``st.page_link`` cannot live inside ``st.html``). The owner of each domain
    comes from the navigation registry (:func:`page_for_domain`), the single
    declaration of domain ownership; a domain with no owner stays visible as plain
    text rather than being dropped.

    Counts only: the bar encodes a row count and the value column a formatted
    count, so no unit is ever mixed on one scale.

    Args:
        rows: One :class:`BarRow` per domain, in display order
        total_label: **Already formatted** footer total (the formatted count plus
            its unit label)
        key: Suffix that makes the panel's keyed container unique when a page
            renders more than one bar list
    """
    with st.container(border=True, key=f"bar-list-{key}"):
        if not rows:
            st.info(t("empty.no_indicators_for_page"))
            return
        largest = max(row.indicator_count for row in rows)
        for row in rows:
            label = domain_label(row.domain)
            owner = page_for_domain(row.domain)
            label_column, bar_column, value_column = st.columns([5, 12, 1])
            with label_column:
                if owner is None:
                    st.markdown(label)
                else:
                    st.page_link(owner.path, label=label)
            with bar_column:
                st.html(_bar_markup(row.indicator_count, largest))
            with value_column:
                st.markdown(format_number(row.indicator_count))
        st.html(
            '<div class="bar-list-foot">'
            f"<span>{escape_html(t('section.indicators_by_domain_total'))}</span>"
            f"<b>{escape_html(total_label)}</b>"
            "</div>"
        )
