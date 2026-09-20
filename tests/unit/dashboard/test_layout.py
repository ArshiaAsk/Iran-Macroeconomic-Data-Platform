"""Tests for the shared native-first layout components (Tasks 17-22).

The components wrap native Streamlit elements, so the tests assert through
``AppTest``'s typed accessors wherever one exists (``app.warning``,
``app.title``, ``app.metric``, ``app.subheader``, ``app.page_link``) and fall back
to the element protobuf only for ``st.html``. The CSS side is asserted against
:func:`dashboard.components.direction.direction_css`: the keyed-container hook a
component depends on must be registered and emitted, because the DOM behaviour
itself is not visible to ``AppTest``.
"""

from streamlit.testing.v1 import AppTest

from dashboard.components.direction import CSS_SELECTORS, direction_css
from dashboard.i18n import t

# --- Task 17: callout ------------------------------------------------------


def _run(script: str) -> AppTest:
    app = AppTest.from_string(script)
    app.run()
    return app


def test_callout_renders_the_native_alert_for_its_tone() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("warn.catalog_empty", tone="warn")\n'
        'render_callout("empty.no_observations", tone="info")\n'
        'render_callout("empty.catalog_empty", tone="error")\n'
    )

    assert not app.exception
    assert [warning.value for warning in app.warning] == [t("warn.catalog_empty")]
    assert [info.value for info in app.info] == [t("empty.no_observations")]
    assert [error.value for error in app.error] == [t("empty.catalog_empty")]


def test_callout_defaults_to_the_warn_alert() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("warn.catalog_empty")\n'
    )

    assert not app.exception
    assert [warning.value for warning in app.warning] == [t("warn.catalog_empty")]


def test_callout_label_is_a_bold_prefix_inside_the_body() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("warn.forecasts_indistinguishable", label_key="note.methodology_label")\n'
    )

    assert not app.exception
    assert app.warning[0].value == (
        f"**{t('note.methodology_label')}** {t('warn.forecasts_indistinguishable')}"
    )


def test_callout_label_is_optional() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("empty.no_observations", tone="info")\n'
    )

    assert not app.exception
    assert app.info[0].value == t("empty.no_observations")


def test_callout_rejects_an_unknown_tone() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("empty.no_observations", tone="danger")\n'
    )

    assert app.exception
    assert "unknown callout tone" in str(app.exception[0].value)


def test_callout_container_key_defaults_to_the_catalog_key() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("empty.no_observations", tone="info")\n'
        'render_callout("empty.no_observations", tone="info")\n'
    )

    # The keyed container is the CSS hook, so the same body key twice collides and
    # Streamlit raises. This is the documented reason `container_key` exists.
    assert app.exception
    assert "multiple elements with the same" in str(app.exception[0].value).lower()


def test_callout_container_key_disambiguates_a_repeated_body() -> None:
    app = _run(
        "from dashboard.components.layout import render_callout\n"
        'render_callout("empty.no_observations", tone="info", container_key="first")\n'
        'render_callout("empty.no_observations", tone="info", container_key="second")\n'
    )

    assert not app.exception
    assert len(app.info) == 2


def test_callout_css_hook_is_registered_and_emitted() -> None:
    css = direction_css()

    assert "callout" in CSS_SELECTORS
    assert CSS_SELECTORS["callout"] in css
    # The left accent bar and the CSS-drawn glyph both hang off the keyed hook.
    assert f'{CSS_SELECTORS["callout"]} [data-testid="stAlertContainer"] {{' in css
    assert "border-inline-start: 3px solid currentColor;" in css
    assert f'{CSS_SELECTORS["callout"]} [data-testid="stAlertContainer"]::before' in css


# --- Task 18: page header --------------------------------------------------


def test_page_header_renders_the_title_natively() -> None:
    app = _run(
        "from dashboard.components.layout import render_page_header\n"
        'render_page_header("page.overview")\n'
    )

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.overview")]
    # No callout asked for, so no alert is rendered.
    assert not app.warning
    assert not app.info
    assert not app.error


def test_page_header_renders_the_callout_beneath_the_title() -> None:
    app = _run(
        "from dashboard.components.layout import render_page_header\n"
        'render_page_header("page.overview", callout_key="warn.forecasts_indistinguishable")\n'
    )

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.overview")]
    assert [warning.value for warning in app.warning] == [t("warn.forecasts_indistinguishable")]


def test_page_header_honours_the_callout_tone() -> None:
    app = _run(
        "from dashboard.components.layout import render_page_header\n"
        'render_page_header("page.labor", callout_key="warn.labor_publication", tone="info")\n'
    )

    assert not app.exception
    assert [info.value for info in app.info] == [t("warn.labor_publication")]
    assert not app.warning


def test_page_header_rejects_an_unknown_callout_tone() -> None:
    app = _run(
        "from dashboard.components.layout import render_page_header\n"
        'render_page_header("page.labor", callout_key="warn.labor_publication", tone="danger")\n'
    )

    assert app.exception
    assert "unknown callout tone" in str(app.exception[0].value)
