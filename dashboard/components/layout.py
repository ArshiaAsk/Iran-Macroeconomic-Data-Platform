"""Shared, native-first layout components for the Phase 7.2 dashboard.

Every page composition in the dashboard draws its header, callouts, KPI cells,
section headers, filter bar and states from this module (the D11 layout contract).
The components are **native-first** (D13): they wrap ``st.warning``/``st.info``/
``st.error``, ``st.title``, ``st.subheader``, ``st.metric``,
``st.container(border=True)``, ``st.columns``, ``st.badge`` and ``st.page_link``,
so AppTest keeps seeing typed elements and the HTML-escaping surface stays small.
``st.html`` is used only where no native element exists (the bar itself inside a
bar-list row, and a standalone status dot).

Three rules are load-bearing:

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
"""

from collections.abc import Callable
from typing import Final

import streamlit as st

from dashboard.i18n import t

__all__ = [
    "CALLOUT_TONES",
    "render_callout",
    "render_page_header",
]

CALLOUT_TONES: Final[frozenset[str]] = frozenset({"warn", "info", "error"})
"""Accepted callout tones; each maps to one native Streamlit alert element."""

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
