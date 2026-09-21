"""RTL/typography foundation tests for dashboard/components/direction.py.

The stylesheet touches Streamlit-internal selectors, so the tests assert the
properties that keep it maintainable: everything is scoped and declared in one
mapping, nothing is fetched from the network, and the dataframe/Plotly surfaces
keep their LTR sizing. One AppTest run proves the injection helper is safe to call
from the page/entrypoint path a page actually renders through.
"""

import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest

from dashboard.components.direction import (
    CSS_SELECTORS,
    FONT_STACK,
    _escape_css_string,
    apply_plotly_typography,
    brand_sidebar_css,
    direction_css,
    inject_direction_css,
    plotly_template,
)
from dashboard.components.tokens import CHART_CATEGORICAL_COLORS, token

INJECTION_SCRIPT = (
    "from dashboard.components.direction import inject_direction_css\n" "inject_direction_css()\n"
)


def test_direction_css_stays_scoped_and_offline() -> None:
    css = direction_css()

    assert "@font-face" not in css
    assert "http" not in css
    # Never flip the whole flex tree: it breaks Plotly sizing.
    assert ".stApp" not in css
    assert "body {" not in css
    assert "direction: rtl" in css


def test_every_declared_selector_is_styled() -> None:
    css = direction_css()

    for selector in CSS_SELECTORS.values():
        assert selector in css, selector


def test_direction_css_covers_sidebar_headings_markdown_metrics_and_labels() -> None:
    css = direction_css()

    assert f'{CSS_SELECTORS["sidebar"]} {{ direction: rtl' in css
    assert f'{CSS_SELECTORS["heading"]} {{ direction: rtl' in css
    assert f'{CSS_SELECTORS["markdown"]} {{ direction: rtl' in css
    assert f'{CSS_SELECTORS["metric"]} {{ direction: rtl' in css
    assert f'{CSS_SELECTORS["form_label"]} {{ direction: rtl' in css
    assert FONT_STACK in css


def test_direction_css_pins_the_ltr_grid_and_plotly_canvases() -> None:
    css = direction_css()

    assert f'{CSS_SELECTORS["dataframe"]} {{ direction: ltr; }}' in css
    assert f'{CSS_SELECTORS["plotly_chart"]} {{ direction: ltr; }}' in css


def test_main_block_heading_line_heights_match_the_mockup() -> None:
    """Task 29: the mockup's heading line-heights, which the theme cannot express.

    Streamlit's own heading rule (line-height 1.2) outranks a bare ``h1``/``h3``,
    so the override is scoped to the main block and its specificity is asserted
    here; the computed effect is recorded in the execution log.
    """
    css = direction_css()

    assert CSS_SELECTORS["main_block_heading_1"] == '[data-testid="stMainBlockContainer"] h1'
    assert CSS_SELECTORS["main_block_heading_3"] == '[data-testid="stMainBlockContainer"] h3'
    assert f'{CSS_SELECTORS["main_block_heading_1"]} {{ line-height: 1.4; }}' in css
    assert f'{CSS_SELECTORS["main_block_heading_3"]} {{ line-height: 1.5; }}' in css


def test_markdown_body_line_height_matches_the_mockup() -> None:
    """Task 29: the mockup's body line-height (1.85), measured at 1.9 before."""
    css = direction_css()

    assert "line-height: 1.85;" in css
    assert "line-height: 1.9;" not in css


def test_plotly_template_typography() -> None:
    """The template supplies the Persian typography the builders rely on."""
    template = plotly_template()

    assert template.layout.font.family == FONT_STACK
    assert template.layout.font.size == 13
    assert template.layout.title.font.family == FONT_STACK
    assert template.layout.xaxis.title.font.family == FONT_STACK
    assert template.layout.yaxis.tickfont.family == FONT_STACK
    assert template.layout.hoverlabel.font.family == FONT_STACK


def test_plotly_template_is_typography_palette_and_layout_only() -> None:
    template = plotly_template()

    # Palette comes from the token-derived categorical colours.
    assert list(template.layout.colorway) == list(CHART_CATEGORICAL_COLORS)
    # Grid/border colours are tokens, not literals.
    assert template.layout.xaxis.gridcolor == token("border")
    assert template.layout.yaxis.gridcolor == token("border")
    assert template.layout.xaxis.linecolor == token("border-strong")
    # RTL-friendly legend/title placement is present, but the time axis is not
    # reversed (no autorange reversal) — time stays left to right.
    assert template.layout.legend.orientation == "h"
    assert template.layout.legend.xanchor == "right"
    assert template.layout.title.xanchor == "right"
    assert template.layout.xaxis.autorange is None
    # Sizing and margins stay with the chart builders.
    assert template.layout.height is None
    assert template.layout.width is None
    assert template.layout.autosize is None
    assert template.layout.margin.l is None
    assert template.layout.margin.r is None
    assert template.layout.margin.t is None
    assert template.layout.margin.b is None


def test_apply_plotly_typography_preserves_existing_layout() -> None:
    figure = go.Figure()
    figure.update_layout(height=512, xaxis_title="x")

    returned = apply_plotly_typography(figure)

    assert returned is figure
    assert figure.layout.height == 512
    assert figure.layout.xaxis.title.text == "x"
    assert figure.layout.template.layout.font.family == FONT_STACK


def test_injection_helper_runs_inside_a_streamlit_app() -> None:
    app = AppTest.from_string(INJECTION_SCRIPT)
    app.run()

    assert not app.exception
    assert len(app.markdown) == 1
    assert "direction: rtl" in app.markdown[0].value


def test_injection_helper_wraps_the_stylesheet_in_a_style_element() -> None:
    """Regression: bare CSS passed to st.markdown renders as visible text."""
    app = AppTest.from_string(INJECTION_SCRIPT)
    app.run()

    injected = app.markdown[0].value
    assert injected.startswith("<style>")
    assert injected.endswith("</style>")
    # The whole stylesheet must sit inside the element, not beside it.
    assert injected == f"<style>{direction_css()}</style>"


def test_injection_helper_is_importable_without_a_streamlit_run() -> None:
    assert callable(inject_direction_css)


def test_direction_css_emits_token_custom_properties_on_root() -> None:
    css = direction_css()

    assert ":root {" in css
    assert "--accent: #1D4E89;" in css
    assert "--radius: 6px;" in css
    assert "--font-ui:" in css


def test_chrome_selectors_are_registered() -> None:
    for key in (
        "sidebar_content",
        "sidebar_header",
        "sidebar_nav_link_active",
        "sidebar_user_content",
        "main_block_container",
    ):
        assert key in CSS_SELECTORS, key


def test_chrome_block_is_comment_marked_and_names_the_tested_version() -> None:
    css = direction_css()

    # The chrome block is isolated behind a comment that names the tested
    # Streamlit version, so a future bump is a visible manual checkpoint.
    assert "Streamlit-chrome selectors" in css
    assert "Streamlit 1.61.1" in css
    assert "wave-0-spike.md" in css
    # The fragile active-link class is not used.
    assert "st-emotion-cache-" not in css


def test_chrome_block_styles_sidebar_width_active_item_and_max_width() -> None:
    css = direction_css()

    assert "width: 256px" in css
    assert "max-width: 1360px" in css
    assert f'{CSS_SELECTORS["sidebar_nav_link_active"]} {{' in css
    assert "border-inline-start: 3px solid var(--accent);" in css
    assert f'{CSS_SELECTORS["sidebar_user_content"]} {{ order: 2; margin-top: auto;' in css


def test_chrome_block_seats_the_top_bar_under_the_native_header() -> None:
    """Step 0b: the main container's top padding clears the 52.5 px native
    header and seats the top bar 12 px below it (64 px total), replacing the
    old 120 px that left a 67.5 px empty gap."""
    css = direction_css()

    assert "padding-top: 64px" in css
    assert "padding-top: 120px" not in css


def test_top_bar_full_bleed_reads_the_main_container_padding_property() -> None:
    """P5: the main container owns ``--main-pad-x``; the top bar reads the same
    property for its negative inline margin and its matching inline padding, so
    the two values cannot drift."""
    css = direction_css()
    main = CSS_SELECTORS["main_block_container"]
    top = CSS_SELECTORS["top_bar"]

    # Declared once, on the main container.
    assert f"{main} {{" in css
    assert "--main-pad-x: 70px;" in css
    assert css.count("--main-pad-x:") == 1
    # Both sides of the full-bleed trick use the property, never a literal.
    assert "padding-left: var(--main-pad-x) !important;" in css
    assert "padding-right: var(--main-pad-x) !important;" in css
    assert f"{top} {{ direction: rtl; background: var(--surface);" in css
    assert "width: calc(100% + 2 * var(--main-pad-x));" in css
    assert "max-width: calc(100% + 2 * var(--main-pad-x));" in css
    assert "margin-inline: calc(-1 * var(--main-pad-x));" in css
    assert "padding-inline: var(--main-pad-x);" in css


# --- Task 27: sidebar brand (fallback 2) — CSS-pinned mark + text ---

BRAND = "سامانهٔ داده‌ها"


def test_escape_css_string_doubles_backslashes() -> None:
    assert _escape_css_string("a\\b") == "a\\\\b"


def test_escape_css_string_escapes_double_quotes() -> None:
    assert _escape_css_string('a"b') == 'a\\"b'


def test_escape_css_string_hex_escapes_control_characters() -> None:
    # A NUL (U+0000) is illegal in a CSS string; it must become a hex escape.
    assert _escape_css_string("a\x00b") == "a\\000000 b"


def test_escape_css_string_leaves_persian_unchanged() -> None:
    assert _escape_css_string(BRAND) == BRAND


def test_brand_css_emits_before_mark_and_after_text() -> None:
    css = brand_sidebar_css(BRAND)

    header = CSS_SELECTORS["sidebar_header"]
    assert f"{header}::before" in css
    assert f"{header}::after" in css
    # The mark is a CSS-drawn square (no SVG, no text glyph).
    assert 'content: ""' in css
    # The brand text is interpolated into the ::after content property.
    assert f'content: "{BRAND}"' in css
    assert "var(--accent)" in css  # mark fill
    assert "font-weight: 700" in css  # brand text


def test_brand_text_is_pinned_to_a_single_line() -> None:
    """Step 0a: the brand ellipsizes instead of wrapping into the navigation."""
    css = brand_sidebar_css(BRAND)

    assert "white-space: nowrap;" in css
    assert "overflow: hidden;" in css
    assert "text-overflow: ellipsis;" in css
    # The ::after text is the flexible child that may shrink (min-width: 0).
    assert "flex: 1 1 auto; min-width: 0;" in css


def test_sidebar_header_does_not_wrap() -> None:
    css = direction_css()

    assert "flex-wrap: nowrap;" in css


def test_brand_css_escapes_the_brand_text() -> None:
    """A brand containing a backslash or quote cannot break the CSS content string."""
    css = brand_sidebar_css('test"brand\\path')

    assert 'content: "test\\"brand\\\\path"' in css


def test_brand_css_is_not_part_of_direction_css() -> None:
    """The brand rules are dynamic (they carry i18n text) and live in their own
    builder, so direction_css() stays brand-free and the no-arg injection test
    stays green."""
    assert "stSidebarHeader" not in direction_css().replace(CSS_SELECTORS["sidebar_header"], "")


_BRAND_INJECTION_SCRIPT = (
    "from dashboard.components.direction import inject_direction_css\n"
    f'inject_direction_css(brand_text="{BRAND}")\n'
)


def test_inject_with_brand_text_appends_brand_rules() -> None:
    app = AppTest.from_string(_BRAND_INJECTION_SCRIPT)
    app.run()

    assert not app.exception
    injected = app.markdown[0].value
    assert injected.startswith("<style>")
    assert injected.endswith("</style>")
    assert BRAND in injected
    assert "::after" in injected


def test_inject_without_brand_text_omits_brand_rules() -> None:
    """The no-arg call path (used by tests and standalone runs) stays brand-free."""
    app = AppTest.from_string(INJECTION_SCRIPT)
    app.run()

    assert not app.exception
    injected = app.markdown[0].value
    assert injected == f"<style>{direction_css()}</style>"
    assert "::after" not in injected
