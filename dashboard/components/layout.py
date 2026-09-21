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

import pandas as pd
import streamlit as st

from dashboard.components.escaping import escape_html
from dashboard.components.html_table import TONES, StatusChip, Tone
from dashboard.formatting import format_number, jalali_date_label, tehran_timestamp_label, to_tehran
from dashboard.i18n import t
from dashboard.labels import domain_label
from dashboard.navigation import page_for_domain
from dashboard.queries import cached_source_freshness
from src.etl.bronze import STATUS_FAILED, STATUS_PARTIAL, STATUS_SUCCESS

__all__ = [
    "CALLOUT_TONES",
    "KPI_TONES",
    "STATUS_CHIPS",
    "STATUS_CHIP_FALLBACK",
    "BarRow",
    "KpiCell",
    "kpi_column_weights",
    "render_bar_list",
    "render_callout",
    "render_filter_bar",
    "render_kpi_band",
    "render_page_header",
    "render_section_header",
    "render_status_chip",
    "render_status_dot",
    "render_top_bar",
    "status_chip_cell",
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

#: ``st.badge`` colour -> RTL-table tone. The two chip renderers share the
#: slug -> (label key, colour) mapping in :data:`STATUS_CHIPS`; only the tone
#: vocabulary differs (``TONES`` for the HTML table, ``BadgeColor`` for
#: ``st.badge``), and this is the total conversion between them.
_STATUS_CHIP_TABLE_TONES: Final[Mapping[BadgeColor, Tone]] = MappingProxyType(
    {
        "red": "err",
        "orange": "warn",
        "yellow": "warn",
        "blue": "accent",
        "green": "ok",
        "violet": "accent",
        "gray": "neutral",
        "grey": "neutral",
        "primary": "accent",
    }
)


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
    detail: str | None = None,
    container_key: str | None = None,
    body: str | None = None,
) -> None:
    """Render the mockup's callout as a native Streamlit alert.

    The amber/blue/red tint comes from the ``[theme]`` alert colour options
    (Task 8); the accent bar and the info glyph are the only CSS, scoped to
    this component's keyed container and placed at the RTL start. The native alert
    ships **no** icon element (probed on Streamlit 1.61.1) and ``st.html`` strips
    ``<svg>`` (``wave-0-spike.md`` §6), so the mockup's inline SVG is drawn in CSS
    instead.

    Args:
        key: Catalog key of the callout body text
        tone: ``"warn"``, ``"info"`` or ``"error"``
        label_key: Optional catalog key rendered as a bold prefix inside the body
        detail: Optional **already resolved** extra paragraph appended to the body
            (``t(...)`` first). Markdown, so keep it to plain text
        container_key: Optional disambiguator for the CSS hook. Defaults to
            ``key``; pass a distinct value when the same callout renders twice in
            one run (a repeated container key raises in Streamlit)
        body: Optional **already resolved** callout text that overrides ``t(key)``.
            ``render_callout`` fills no ``{placeholder}`` fields, so a notice whose
            message carries values (the chart-mode notice, the row-cap hint) passes
            its resolved text here and uses ``key`` for the container hook only

    Raises:
        ValueError: When ``tone`` is not a known callout tone
    """
    renderer = _CALLOUT_RENDERERS[_validated(tone, CALLOUT_TONES, "callout")]
    text = t(key) if body is None else body
    if label_key is not None:
        # Markdown emphasis, not markup: st.warning/info/error render markdown, so
        # the label is bold without any HTML (and without an escaping concern).
        text = f"**{t(label_key)}** {text}"
    if detail is not None:
        text = f"{text}\n\n{detail}"
    with st.container(key=f"callout-{container_key if container_key is not None else key}"):
        renderer(text)


def render_page_header(
    title_key: str,
    *,
    callout_key: str | None = None,
    label_key: str | None = None,
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
        label_key: Optional catalog key rendered as a bold prefix inside the
            callout body (the mockup's methodology label). Only meaningful with
            ``callout_key``
        tone: Callout tone when ``callout_key`` is given

    Raises:
        ValueError: When ``tone`` is not a known callout tone and a callout is asked
            for
    """
    st.title(t(title_key))
    if callout_key is not None:
        render_callout(callout_key, label_key=label_key, tone=tone)


def render_top_bar(
    group_label: str,
    page_label: str,
    *,
    key: str = "top-bar",
) -> None:
    """Render the shell top bar: breadcrumb and last-collection stamp.

    The bar is built from native ``st.columns`` inside a keyed ``st.container``
    (D13/AM-7). The container establishes an RTL context: the first column is the
    rightmost visually, so the breadcrumb lives in column 0 (RTL start) and the
    last-collection stamp in column 1 (RTL end). The component calls
    :func:`dashboard.queries.cached_source_freshness` and formats the latest
    ``collection_timestamp`` through the Tehran/Jalali helpers; if the freshness
    frame is empty or cannot be parsed, it falls back to :data:`value.unknown`.

    Args:
        group_label: Already-resolved sidebar group label (from
            ``t(f"group.{spec.group}")``).
        page_label: Already-resolved page title (from ``t(f"page.{spec.key}")``).
        key: Optional container-key override. The default ``"top-bar"`` is the
            CSS hook in :data:`dashboard.components.direction.CSS_SELECTORS`.
    """
    freshness = cached_source_freshness()
    stamp: str | None = None
    if not freshness.empty and "collection_timestamp" in freshness.columns:
        try:
            latest = freshness["collection_timestamp"].max()
            if pd.notna(latest):
                tehran_ts = to_tehran(pd.Timestamp(latest))
                jalali = jalali_date_label(tehran_ts)
                # The timestamp label includes both date and clock; keep only the
                # clock portion for the stamp (the date is already shown in Jalali).
                time_part = tehran_timestamp_label(tehran_ts).split()[-1]
                stamp = (
                    f"{t('shell.last_collection', date=jalali)} · {time_part} · "
                    f"{t('shell.timezone')}"
                )
        except (ValueError, TypeError):
            stamp = None

    if stamp is None:
        stamp = t("value.unknown")

    breadcrumb = f"{t('shell.breadcrumb_root')} › {group_label} › {page_label}"

    with st.container(key=key):
        breadcrumb_col, stamp_col = st.columns([1, 1])
        with breadcrumb_col:
            st.html(f'<div class="top-bar-breadcrumb">{escape_html(breadcrumb)}</div>')
        with stamp_col:
            st.html(f'<div class="top-bar-stamp">{escape_html(stamp)}</div>')


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


#: Relative width of a secondary KPI cell against a primary one. The mockup sets
#: `.kpi{flex:1}` and `.kpi.sec{flex:1.35}`, so the separated derived/orphan
#: cells are visibly wider than the four primary cells. The values live here (not
#: in CSS) because `st.columns` owns the geometry and expresses it as weights.
_KPI_PRIMARY_WEIGHT: Final[float] = 1.0
_KPI_SECONDARY_WEIGHT: Final[float] = 1.35


def kpi_column_weights(cells: Sequence[KpiCell]) -> list[float]:
    """Column weights for a KPI band: 1 for a primary cell, 1.35 for a secondary.

    Mirrors the mockup's ``.kpi``/``.kpi.sec`` flex ratio. The weights are the
    single source for the secondary group's width, so the ``st.columns`` spec and
    the documented ratio cannot drift.

    Args:
        cells: One :class:`KpiCell` per band column, in display order

    Returns:
        One positive weight per cell, in the same order
    """
    return [_KPI_SECONDARY_WEIGHT if cell.secondary else _KPI_PRIMARY_WEIGHT for cell in cells]


def render_kpi_band(cells: Sequence[KpiCell], *, key: str = "default") -> None:
    """Render the reusable KPI band (D2) as one bordered row of metric cells.

    The band is a single ``st.container(border=True)`` holding one
    ``st.columns`` row, so the cells line up as in the mockup; cells flagged
    ``secondary`` form a visually separated trailing group (a stronger inline
    separator, drawn by the ``:has()`` rule in :mod:`dashboard.components.direction`).
    Secondary cells also take the mockup's wider ``flex: 1.35`` weight through
    :func:`kpi_column_weights`, so the derived/orphan pair is visibly wider than a
    primary cell. Cell sizing comes from the theme (``metricValueFontSize`` and
    friends), so no component sets a font-size literal.

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
        columns = st.columns(kpi_column_weights(cells))
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


def status_chip_cell(status: str) -> StatusChip:
    """Build the RTL-table :class:`StatusChip` for a collection-run status slug.

    The slug -> (label key, colour) mapping is :data:`STATUS_CHIPS` — the same one
    :func:`render_status_chip` uses — so the two chip renderers cannot drift; only
    the tone vocabulary differs and is converted through
    :data:`_STATUS_CHIP_TABLE_TONES`.

    The mapping stays **total**: an unrecognised slug renders the unknown chip
    instead of raising, because the slug is a data value
    (``DataCollectionLog.status``) and a new source status must not blank a page.

    Args:
        status: Collection status slug (``success``/``failed``/``partial``)

    Returns:
        A :class:`StatusChip` cell ready for ``render_html_table``
    """
    label_key, colour = STATUS_CHIPS.get(status, STATUS_CHIP_FALLBACK)
    return StatusChip(t(label_key), _STATUS_CHIP_TABLE_TONES[colour])


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


#: Relative width of the filter bar's spacer column, the mockup's `.grow`: it
#: absorbs the slack so the trailing group pins to the far end of the bar instead
#: of butting up against the filters.
_FILTER_BAR_SPACER_WEIGHT: Final[float] = 2.0


def render_section_header(
    title_key: str,
    *,
    subtitle: str | None = None,
    trailing: str | None = None,
    key: str | None = None,
) -> None:
    """Render a section header: a native subheader with optional secondary text.

    The title stays a native ``st.subheader``, so ``AppTest`` keeps seeing
    ``app.subheader``. The mockup's ``.sec-h`` is one baseline-aligned row with the
    title at the RTL start and the secondary text at the far end; that layout comes
    from the scoped CSS in :mod:`dashboard.components.direction`, which turns the
    keyed container into a ``space-between`` row. The secondary text carries the
    mockup's ``.sec-h .sub`` type (muted, one step down from body text) — the
    subheader itself keeps the theme's heading scale.

    Args:
        title_key: Catalog key of the section title (``section.<name>``)
        subtitle: Optional **already resolved** secondary line rendered beneath the
            title (call ``t(...)`` first). Markdown, so keep it to plain text
        trailing: Optional **already resolved** text pinned to the far end of the
            header row, e.g. a freshness summary. Markdown, so keep it to plain
            text
        key: Optional container-key override. Defaults to ``title_key``, because a
            page renders several section headers and Streamlit raises on a repeated
            container key; distinct titles therefore need no key at all
    """
    suffix = key if key is not None else title_key
    with st.container(key=f"section-header-{suffix}"):
        # The title and its subtitle share one container so the row override places
        # them together at the RTL start; the trailing text is the row's other end.
        with st.container(key=f"section-title-{suffix}"):
            st.subheader(t(title_key))
            if subtitle is not None:
                # Its own container: `st.subheader` renders a `stMarkdownContainer`
                # of its own, so the `.sub` type has to be addressable separately
                # from the heading.
                with st.container(key=f"section-subtitle-{suffix}"):
                    st.markdown(subtitle)
        if trailing is not None:
            with st.container(key=f"section-trailing-{suffix}"):
                st.markdown(trailing)


def render_filter_bar(
    controls: Sequence[Callable[[], None]],
    *,
    trailing: Sequence[Callable[[], None]] = (),
    key: str = "default",
) -> None:
    """Render one filter-bar layout over an arbitrary number of controls.

    Each control is a zero-argument callable that renders itself into the column it
    is given (``st.selectbox``, ``st.segmented_control``, an existing
    ``render_filters`` helper, …), so the bar owns the layout and nothing else.
    Columns are centre-aligned so controls of differing heights — a selectbox next
    to a segmented control — share one baseline row. The container declares
    ``direction: rtl`` (see :mod:`dashboard.components.direction`), so the first
    control is the rightmost, in reading order.

    ``trailing`` holds the controls that belong at the far end of the bar (the
    mockup's row-count echo and density toggle). A spacer column between the two
    groups is the mockup's ``.grow``; it is added only when both groups are present.

    Args:
        controls: Callables rendering the leading filter controls, in display order
        trailing: Callables rendering the controls pinned to the far end
        key: Suffix that makes the container key unique when a page renders more
            than one filter bar

    Raises:
        ValueError: When neither group carries a control
    """
    if not controls and not trailing:
        message = "render_filter_bar needs at least one control"
        raise ValueError(message)
    weights = [1.0] * len(controls)
    if controls and trailing:
        weights.append(_FILTER_BAR_SPACER_WEIGHT)
    weights += [1.0] * len(trailing)
    with st.container(key=f"filter-bar-{key}"):
        columns = st.columns(weights, vertical_alignment="center")
        trailing_start = len(controls) + (1 if controls and trailing else 0)
        for column, control in zip(columns[: len(controls)], controls, strict=True):
            with column:
                control()
        for column, control in zip(columns[trailing_start:], trailing, strict=True):
            with column:
                control()
