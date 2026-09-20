"""Design tokens for the Phase 7.2 dashboard redesign.

This module is the single source for the palette, corner radii and font families
that the Streamlit theme (``.streamlit/config.toml``), the shell stylesheet
(``dashboard/components/direction.py``) and the Plotly template read. The set
mirrors the ``:root`` block of
``docs/design/phase-7.2/overview-redesign-mockup.html`` exactly, and
``tests/unit/dashboard/test_tokens.py`` parses that file and fails when the two
drift, so a token added to the mockup cannot be silently forgotten here.

Token names carry no CSS ``--`` prefix; :func:`custom_properties` adds it. The
mapping is immutable and every value is a plain string, so it is safe to share.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

__all__ = ["TOKENS", "css_custom_properties", "custom_properties", "token"]

TOKENS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "bg": "#F6F7F9",
        "surface": "#fff",
        "surface-2": "#F1F3F6",
        "hover": "#F3F6FA",
        "border": "#E1E5EB",
        "border-strong": "#C9D0DA",
        "text-1": "#1B2430",
        "text-2": "#4A5566",
        "text-3": "#667385",
        "accent": "#1D4E89",
        "accent-soft": "#E8EFF8",
        "ok": "#1F7A4D",
        "ok-bg": "#E6F3EC",
        "warn": "#9A5B00",
        "warn-bg": "#FBF1DC",
        "err": "#B42318",
        "err-bg": "#FDECEA",
        "neutral-bg": "#EEF1F5",
        "radius": "6px",
        "radius-lg": "8px",
        "font-ui": '"Vazirmatn",Tahoma,system-ui,sans-serif',
        "font-mono": '"DejaVu Sans Mono",monospace',
    }
)
"""Every token in the mockup's ``:root`` block, keyed by name without ``--``."""


def token(name: str) -> str:
    """Return the value of one token.

    Args:
        name: Token name without the CSS ``--`` prefix (e.g. ``"accent"``)

    Returns:
        The token value exactly as written in the mockup

    Raises:
        KeyError: When ``name`` is not a declared token
    """
    try:
        return TOKENS[name]
    except KeyError:
        message = f"unknown design token: {name!r}"
        raise KeyError(message) from None


def custom_properties() -> Mapping[str, str]:
    """Return the tokens keyed by their CSS custom-property name (``--name``)."""
    return MappingProxyType({f"--{name}": value for name, value in TOKENS.items()})


def css_custom_properties() -> str:
    """Emit the tokens as one ``:root { … }`` CSS block for the shell stylesheet."""
    declarations = " ".join(f"--{name}: {value};" for name, value in TOKENS.items())
    return f":root {{ {declarations} }}"
