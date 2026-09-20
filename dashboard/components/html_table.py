"""RTL HTML table with a typed cell model, rendered through ``st.html``.

The dashboard's tabular surfaces need more than ``st.dataframe`` can express:
status dots, tone chips, mono LTR ids beneath a name, and a date/time/age stack.
``render_html_table`` renders those as semantic HTML (``<table>``/``<th
scope="col">``) inside an RTL wrapper, so the page direction is honoured while
the LTR data tokens (ids, units) stay isolated with ``unicode-bidi: isolate``.

Two rules are load-bearing:

- **Everything data-derived is escaped** through
  :func:`dashboard.components.escaping.escape_html` before interpolation.
- **A tone is a closed set.** :class:`StatusChip`/:class:`Dot` accept only
  ``ok``/``warn``/``err``/``accent``/``neutral``; an unknown tone raises, so a
  data value can never be interpolated into a class name.

The stylesheet lives in the shell CSS owner (:mod:`dashboard.components.direction`)
and is emitted once per run; this module never emits a ``<style>`` block.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypeAlias

import streamlit as st

from dashboard.components.escaping import escape_html
from dashboard.formatting import MISSING_VALUE

__all__ = [
    "DENSITIES",
    "TONES",
    "Cell",
    "Dot",
    "Ltr",
    "StatusChip",
    "Text",
    "TwoLine",
    "UnitChip",
    "build_html_table",
    "render_html_table",
]

Tone: TypeAlias = Literal["ok", "warn", "err", "accent", "neutral"]
"""The closed set of chip/dot tones; each maps to a ``tone-*`` CSS class."""

TONES: Final[frozenset[str]] = frozenset({"ok", "warn", "err", "accent", "neutral"})
"""Accepted tone values. A tone outside this set raises rather than rendering."""

DENSITIES: Final[frozenset[str]] = frozenset({"comfortable", "compact"})
"""Accepted row densities; each maps to a ``dt <density>`` CSS class."""


@dataclass(frozen=True)
class Text:
    """Plain text cell. ``None`` renders the missing-value placeholder."""

    value: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class Ltr:
    """Left-to-right mono cell (an id), isolated so it cannot flip the table."""

    value: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class UnitChip:
    """Left-to-right mono chip for a unit (``current US$``)."""

    value: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class StatusChip:
    """HTML/CSS chip with a tone dot and a label (never ``st.badge``)."""

    label: str | None
    tone: Tone
    title: str | None = None


@dataclass(frozen=True)
class Dot:
    """HTML/CSS status dot with a label."""

    label: str | None
    tone: Tone
    title: str | None = None


InlineCell: TypeAlias = Text | Ltr | UnitChip
"""The text-like variants allowed inside :class:`TwoLine`'s secondary line."""


@dataclass(frozen=True)
class TwoLine:
    """A bold primary line with a secondary line of inline parts.

    Renders a name above its mono id (coverage) or a Jalali date above
    ``time · relative age`` (freshness). The secondary parts are joined by the
    mockup's ``·`` separator through the ``.tm`` CSS rule.
    """

    primary: str | None
    secondary_parts: tuple[InlineCell, ...] = ()
    title: str | None = None


Cell: TypeAlias = Text | Ltr | UnitChip | StatusChip | Dot | TwoLine
"""Every renderable table cell variant."""


def _validated_tone(tone: str) -> str:
    """Return ``tone`` when it is in :data:`TONES`, else raise.

    Raising keeps the tone out of the class attribute, so a data value can never
    inject a CSS class.
    """
    if tone not in TONES:
        message = f"unknown tone: {tone!r} (expected one of {sorted(TONES)})"
        raise ValueError(message)
    return tone


def _validated_density(density: str) -> str:
    """Return ``density`` when it is in :data:`DENSITIES`, else raise."""
    if density not in DENSITIES:
        message = f"unknown density: {density!r} (expected one of {sorted(DENSITIES)})"
        raise ValueError(message)
    return density


def _with_title(markup: str, title: str | None) -> str:
    """Wrap ``markup`` in a titled span when a tooltip is supplied."""
    if title is None:
        return markup
    return f'<span title="{escape_html(title)}">{markup}</span>'


def _or_missing(value: str | None, null_placeholder: str) -> str:
    """Escape ``value``, or render the escaped missing-value placeholder."""
    if value is None:
        return f'<span class="na">{escape_html(null_placeholder)}</span>'
    return escape_html(value)


def _render_inline(cell: InlineCell, null_placeholder: str) -> str:
    """Render a text-like cell (used directly and inside :class:`TwoLine`)."""
    if isinstance(cell, Ltr):
        value = _or_missing(cell.value, null_placeholder)
        return _with_title(f'<bdi class="ltr">{value}</bdi>', cell.title)
    if isinstance(cell, UnitChip):
        value = _or_missing(cell.value, null_placeholder)
        return _with_title(f'<span class="unit">{value}</span>', cell.title)
    value = _or_missing(cell.value, null_placeholder)
    return _with_title(value, cell.title)


def _render_cell(cell: Cell, null_placeholder: str) -> str:
    """Render one cell to escaped HTML markup."""
    if isinstance(cell, StatusChip):
        tone = _validated_tone(cell.tone)
        label = "" if cell.label is None else escape_html(cell.label)
        return _with_title(f'<span class="chip tone-{tone}">{label}</span>', cell.title)
    if isinstance(cell, Dot):
        tone = _validated_tone(cell.tone)
        label = "" if cell.label is None else escape_html(cell.label)
        return _with_title(f'<span class="dot tone-{tone}">{label}</span>', cell.title)
    if isinstance(cell, TwoLine):
        parts = "".join(
            f"<span>{_render_inline(part, null_placeholder)}</span>"
            for part in cell.secondary_parts
        )
        inner = f'<span class="name">{_or_missing(cell.primary, null_placeholder)}</span>'
        if parts:
            inner += f'<span class="sm tm">{parts}</span>'
        return _with_title(inner, cell.title)
    return _render_inline(cell, null_placeholder)


def build_html_table(
    columns: Sequence[str],
    rows: Sequence[Sequence[Cell]],
    *,
    density: str = "comfortable",
    null_placeholder: str = MISSING_VALUE,
) -> str:
    """Build the RTL table markup as a string (pure; no Streamlit call).

    Args:
        columns: Localized column headers, rendered as ``<th scope="col">``
        rows: One sequence of cells per row
        density: ``"comfortable"`` or ``"compact"`` (a ``dt <density>`` class)
        null_placeholder: Text for a ``None`` text-like value (never for chips/dots)

    Returns:
        The table wrapped in ``<div class="dt-wrap" dir="rtl">``, which scrolls
        sideways within its own box (``overflow-x: auto``) so the page never does

    Raises:
        ValueError: When ``density`` is not a known density
    """
    density_class = _validated_density(density)
    headers = "".join(f'<th scope="col">{escape_html(column)}</th>' for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_render_cell(cell, null_placeholder)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return (
        '<div class="dt-wrap" dir="rtl">'
        f'<table class="dt {density_class}">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
        "</div>"
    )


def render_html_table(
    columns: Sequence[str],
    rows: Sequence[Sequence[Cell]],
    *,
    density: str = "comfortable",
    null_placeholder: str = MISSING_VALUE,
) -> None:
    """Render the RTL table into the running app via ``st.html``.

    Args:
        columns: Localized column headers
        rows: One sequence of cells per row
        density: ``"comfortable"`` or ``"compact"``
        null_placeholder: Text for a ``None`` text-like value

    Raises:
        ValueError: When ``density`` is not a known density
    """
    st.html(
        build_html_table(
            columns,
            rows,
            density=density,
            null_placeholder=null_placeholder,
        )
    )
