"""Design-token tests: the token set is pinned to the mockup's ``:root`` block.

The mockup is the design spec, so the test parses its ``:root`` block and asserts
set equality with :data:`dashboard.components.tokens.TOKENS`. A token that exists
in the mockup but not in the module (or vice versa) fails here rather than
showing up as a missing CSS variable at runtime. A second group of assertions
parses ``.streamlit/config.toml`` and checks every colour/radius theme value
equals its declared token, so the theme cannot drift from the tokens (Task 8).
"""

import re
import tomllib
from pathlib import Path
from typing import cast

import pytest

from dashboard.components.tokens import (
    CHART_CATEGORICAL_COLORS,
    TOKENS,
    css_custom_properties,
    custom_properties,
    token,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MOCKUP = REPOSITORY_ROOT / "docs" / "design" / "phase-7.2" / "overview-redesign-mockup.html"
CONFIG = REPOSITORY_ROOT / ".streamlit" / "config.toml"

#: Maps a Streamlit `[theme]` key to the design-token name it must equal. The
#: alert colours map orange=warn, blue=accent/info, red=err, green=ok; yellow has
#: no mockup token and is folded into the warn palette. `baseFontSize` and
#: `chartCategoricalColors` are checked separately (not single :root tokens).
THEME_TOKEN_MAP: dict[str, str] = {
    "primaryColor": "accent",
    "backgroundColor": "bg",
    "secondaryBackgroundColor": "surface",
    "textColor": "text-1",
    "borderColor": "border",
    "baseRadius": "radius",
    "buttonRadius": "radius",
    "dataframeHeaderBackgroundColor": "surface-2",
    "redColor": "err",
    "redBackgroundColor": "err-bg",
    "redTextColor": "err",
    "orangeColor": "warn",
    "orangeBackgroundColor": "warn-bg",
    "orangeTextColor": "warn",
    "yellowColor": "warn",
    "yellowBackgroundColor": "warn-bg",
    "yellowTextColor": "warn",
    "blueColor": "accent",
    "blueBackgroundColor": "accent-soft",
    "blueTextColor": "accent",
    "greenColor": "ok",
    "greenBackgroundColor": "ok-bg",
    "greenTextColor": "ok",
}

_ROOT_BLOCK = re.compile(r":root\s*\{(?P<body>[^}]*)\}", re.DOTALL)


def mockup_tokens() -> dict[str, str]:
    """Parse the mockup's ``:root`` block into a ``{name: value}`` mapping."""
    match = _ROOT_BLOCK.search(MOCKUP.read_text("utf-8"))
    assert match is not None, "mockup has no :root block"
    tokens: dict[str, str] = {}
    for raw_declaration in match.group("body").split(";"):
        declaration = raw_declaration.strip()
        if not declaration:
            continue
        name, _, value = declaration.partition(":")
        tokens[name.strip().removeprefix("--")] = value.strip()
    return tokens


def test_token_set_equals_the_mockup_root_block() -> None:
    assert dict(TOKENS) == mockup_tokens()


def test_mockup_root_block_is_not_empty() -> None:
    # Guards against a parsing regression that would make the equality vacuous.
    assert len(mockup_tokens()) > 15


def test_tokens_are_immutable() -> None:
    with pytest.raises(TypeError):
        cast("dict[str, str]", TOKENS)["accent"] = "#000000"


def test_token_accessor_returns_values_and_rejects_unknown_names() -> None:
    assert token("accent") == "#1D4E89"
    with pytest.raises(KeyError):
        token("not-a-token")


def test_custom_properties_prefix_every_name() -> None:
    properties = custom_properties()

    assert properties["--accent"] == TOKENS["accent"]
    assert set(properties) == {f"--{name}" for name in TOKENS}


def test_css_custom_properties_emits_a_root_block() -> None:
    css = css_custom_properties()

    assert css.startswith(":root {")
    assert css.endswith("}")
    assert "--accent: #1D4E89;" in css
    assert "--radius: 6px;" in css


def _theme_section() -> dict[str, object]:
    data = tomllib.loads(CONFIG.read_text("utf-8"))
    return data["theme"]


def test_theme_colour_and_radius_values_equal_their_tokens() -> None:
    theme = _theme_section()

    for theme_key, token_name in THEME_TOKEN_MAP.items():
        assert theme[theme_key] == TOKENS[token_name], theme_key


def test_theme_base_font_size_is_the_mockup_body_size() -> None:
    # The mockup sets body{font-size:14px}; no :root token carries it, so it is
    # asserted directly against the mockup body rule rather than a token.
    assert _theme_section()["baseFontSize"] == 14


def test_theme_chart_categorical_colours_are_token_colours() -> None:
    theme = _theme_section()
    token_values = set(TOKENS.values())

    colours = theme["chartCategoricalColors"]
    assert isinstance(colours, list)
    for colour in colours:
        assert colour in token_values, colour


def test_theme_chart_categorical_colours_match_the_token_palette_exactly() -> None:
    # One source: the config list must equal the token-derived palette, order
    # included, so Streamlit and the Plotly template assign colours identically.
    assert tuple(_theme_section()["chartCategoricalColors"]) == CHART_CATEGORICAL_COLORS


def test_theme_font_keys_are_owned_by_task_seven() -> None:
    theme = _theme_section()

    assert str(theme["font"]).startswith("Vazirmatn")
    assert str(theme["headingFont"]).startswith("Vazirmatn")


def test_client_toolbar_mode_is_viewer() -> None:
    """Task 28 sets ``[client] toolbarMode = "viewer"`` to hide the native Deploy
    button and developer options. The custom ``[theme]`` already hides the theme
    toggle (D14), so this is the only remaining chrome to suppress."""
    data = tomllib.loads(CONFIG.read_text("utf-8"))
    assert data["client"]["toolbarMode"] == "viewer"
