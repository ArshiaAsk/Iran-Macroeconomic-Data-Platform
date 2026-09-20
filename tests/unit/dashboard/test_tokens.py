"""Design-token tests: the token set is pinned to the mockup's ``:root`` block.

The mockup is the design spec, so the test parses its ``:root`` block and asserts
set equality with :data:`dashboard.components.tokens.TOKENS`. A token that exists
in the mockup but not in the module (or vice versa) fails here rather than
showing up as a missing CSS variable at runtime.
"""

import re
from pathlib import Path
from typing import cast

import pytest

from dashboard.components.tokens import (
    TOKENS,
    css_custom_properties,
    custom_properties,
    token,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MOCKUP = REPOSITORY_ROOT / "docs" / "design" / "phase-7.2" / "overview-redesign-mockup.html"

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
