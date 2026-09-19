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
    apply_plotly_typography,
    direction_css,
    inject_direction_css,
    plotly_template,
)

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


def test_plotly_template_is_typography_only() -> None:
    template = plotly_template()

    assert template.layout.font.family == FONT_STACK
    assert template.layout.xaxis.title.font.family == FONT_STACK
    assert template.layout.yaxis.tickfont.family == FONT_STACK
    # Sizing stays with the chart builders.
    assert template.layout.height is None
    assert template.layout.width is None
    assert template.layout.autosize is None


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


def test_injection_helper_is_importable_without_a_streamlit_run() -> None:
    assert callable(inject_direction_css)
