"""Shared empty / error / loading states for the Phase 7.2 dashboard (Task 22).

Every page shows the same three states through these helpers, so the tone, the
spacing and the copy of each state are declared once instead of re-derived per
page. Each helper is a thin wrapper over
:func:`dashboard.components.layout.render_callout`, which renders a **native**
``st.info``/``st.error``: the states therefore stay visible to ``AppTest`` as
``app.info`` and ``app.error``, and they inherit the callout's keyed-container CSS
hook (the accent bar, the glyph and the alert tint) with no CSS of their own.

Two rules are load-bearing:

- **The tone belongs to the state, not the caller.** An empty or loading state is
  informational and an error state is an error, so a caller cannot render a failed
  load in the informational tone.
- **One state key per run.** The callout's container key derives from the body key,
  and Streamlit raises on a repeated container key. A page that legitimately shows
  the same state twice must call
  :func:`dashboard.components.layout.render_callout` directly with an explicit
  ``container_key``.
"""

from dashboard.components.layout import render_callout
from dashboard.i18n import t

__all__ = ["render_empty", "render_error", "render_loading"]


def render_empty(key: str) -> None:
    """Render the shared empty state for a catalog ``empty.*`` message.

    Args:
        key: Catalog key of the message, e.g. ``"empty.no_observations"``
    """
    render_callout(key, tone="info")


def render_error(key: str, *, detail: str | None = None) -> None:
    """Render the shared error state: the message, the retry hint, then any detail.

    Args:
        key: Catalog key of the error message, e.g. ``"state.error"``
        detail: Optional **already resolved** extra paragraph (an exception
            message, the failing source, …). Markdown, so keep it to plain text
    """
    body = t("state.retry_hint")
    if detail is not None:
        body = f"{body}\n\n{detail}"
    render_callout(key, tone="error", detail=body)


def render_loading() -> None:
    """Render the shared loading state."""
    render_callout("state.loading", tone="info")
