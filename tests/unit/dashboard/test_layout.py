"""Tests for the shared native-first layout components (Tasks 17-22).

The components wrap native Streamlit elements, so the tests assert through
``AppTest``'s typed accessors wherever one exists (``app.warning``,
``app.title``, ``app.metric``, ``app.subheader``, ``app.page_link``) and fall back
to the element protobuf only for ``st.html``. The CSS side is asserted against
:func:`dashboard.components.direction.direction_css`: the keyed-container hook a
component depends on must be registered and emitted, because the DOM behaviour
itself is not visible to ``AppTest``.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.components.direction import CSS_SELECTORS, direction_css
from dashboard.components.layout import BarRow, render_bar_list
from dashboard.formatting import format_number
from dashboard.i18n import t
from dashboard.labels import domain_label
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT, html_texts

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


# --- Task 19: KPI band -----------------------------------------------------

KPI_BAND_SCRIPT = """
from dashboard.components.layout import KpiCell, render_kpi_band

render_kpi_band(
    [
        KpiCell("metric.sources", "۷"),
        KpiCell("metric.domains", "۹"),
        KpiCell("metric.active_indicators", "۵۰"),
        KpiCell("metric.gold_observations", "۸٬۱۹۵", help_key="metric.gold_observations_help"),
        KpiCell(
            "metric.derived_series",
            "۳۲",
            help_key="metric.derived_series_help",
            tone="muted",
            secondary=True,
        ),
        KpiCell(
            "metric.orphan_series",
            "۳۲",
            help_key="metric.orphan_series_help",
            tone="muted",
            secondary=True,
            tag_key="metric.orphan_series_tag",
        ),
    ],
    key="overview",
)
"""


def test_kpi_band_renders_every_cell_in_order() -> None:
    app = _run(KPI_BAND_SCRIPT)

    assert not app.exception
    assert [metric.label for metric in app.metric] == [
        t("metric.sources"),
        t("metric.domains"),
        t("metric.active_indicators"),
        t("metric.gold_observations"),
        t("metric.derived_series"),
        t("metric.orphan_series"),
    ]
    # The caller formats values; the component must not reformat them.
    assert [metric.value for metric in app.metric][-3:] == ["۸٬۱۹۵", "۳۲", "۳۲"]


def test_kpi_band_exposes_each_tooltip_as_a_metric_help() -> None:
    app = _run(KPI_BAND_SCRIPT)

    assert not app.exception
    helps = [metric.help for metric in app.metric]
    assert helps == [
        "",
        "",
        "",
        t("metric.gold_observations_help"),
        t("metric.derived_series_help"),
        t("metric.orphan_series_help"),
    ]


def test_kpi_band_tag_renders_as_a_badge_beneath_the_metric() -> None:
    app = _run(KPI_BAND_SCRIPT)

    assert not app.exception
    # st.badge surfaces to AppTest as markdown, which is the only signal that the
    # tag rendered; exactly one cell carries it.
    badges = [element.value for element in app.markdown if "badge" in element.value]
    assert badges == [f":orange-badge[{t('metric.orphan_series_tag')}]"]


def test_kpi_band_separates_the_secondary_group() -> None:
    app = _run(KPI_BAND_SCRIPT)
    css = direction_css()

    assert not app.exception
    # The boundary is a scoped CSS hook on the first secondary cell's container:
    # AppTest cannot see classes, so the hook's presence is asserted here and its
    # DOM effect was verified in the live probe (see the execution log).
    assert CSS_SELECTORS["kpi_secondary_group"] in css
    assert (
        f'{CSS_SELECTORS["kpi_band"]} {CSS_SELECTORS["kpi_column"]}'
        f':has({CSS_SELECTORS["kpi_secondary_group"]})' in css
    )
    assert "border-inline-start: 1px solid var(--border-strong);" in css


def test_kpi_band_tone_rules_read_design_tokens() -> None:
    css = direction_css()

    for selector_key, token_name in (
        ("kpi_tone_muted", "text-2"),
        ("kpi_tone_ok", "ok"),
        ("kpi_tone_warn", "warn"),
        ("kpi_tone_err", "err"),
        ("kpi_tone_accent", "accent"),
    ):
        assert CSS_SELECTORS[selector_key] in css, selector_key
        assert (
            f'{CSS_SELECTORS[selector_key]} {CSS_SELECTORS["kpi_value"]} '
            f"{{ color: var(--{token_name}); }}" in css
        )


def test_kpi_band_help_copy_is_data_agnostic() -> None:
    """AM-9: no tooltip may state a count or a claim about the current data."""
    digits = "0123456789۰۱۲۳۴۵۶۷۸۹"

    for key in (
        "metric.derived_series_help",
        "metric.orphan_series_help",
        "metric.gold_observations_help",
    ):
        assert not any(character in digits for character in t(key)), key


def test_kpi_band_typography_pins_the_scale_the_theme_cannot_express() -> None:
    """Task 29: the KPI label (13 px/500) and the secondary value (20 px).

    The theme sets one metric-label size and one metric-value size, so the
    mockup's smaller label and the secondary group's smaller value are pinned on
    the band's own keyed hooks rather than through the theme.
    """
    css = direction_css()

    assert CSS_SELECTORS["kpi_label"] in css
    assert f'{CSS_SELECTORS["kpi_label"]} {{ font-size: 13px; font-weight: 500; }}' in css
    assert CSS_SELECTORS["kpi_secondary_cell"] in css
    assert (
        f'{CSS_SELECTORS["kpi_secondary_cell"]} {CSS_SELECTORS["kpi_value"]} '
        "{ font-size: 20px; }" in css
    )
    # The boundary hook and the every-secondary-cell hook are distinct selectors:
    # only the latter may size the value.
    assert CSS_SELECTORS["kpi_secondary_group"] != CSS_SELECTORS["kpi_secondary_cell"]


def test_kpi_band_rejects_an_unknown_tone() -> None:
    app = _run(
        "from dashboard.components.layout import KpiCell, render_kpi_band\n"
        'render_kpi_band([KpiCell("metric.sources", "۷", tone="danger")])\n'
    )

    assert app.exception
    assert "unknown kpi tone" in str(app.exception[0].value)


def test_kpi_band_rejects_an_empty_cell_list() -> None:
    app = _run("from dashboard.components.layout import render_kpi_band\nrender_kpi_band([])\n")

    assert app.exception
    assert "at least one cell" in str(app.exception[0].value)


def test_kpi_band_container_key_lets_a_page_render_two_bands() -> None:
    app = _run(
        "from dashboard.components.layout import KpiCell, render_kpi_band\n"
        'render_kpi_band([KpiCell("metric.sources", "۱")], key="first")\n'
        'render_kpi_band([KpiCell("metric.domains", "۲")], key="second")\n'
    )

    assert not app.exception
    assert len(app.metric) == 2


# --- Task 20: status chip, status dot, bar list ----------------------------

STATUS_CHIP_SCRIPT = """
from dashboard.components.layout import render_status_chip

render_status_chip("success")
render_status_chip("failed")
render_status_chip("partial")
render_status_chip("brand_new_slug")
"""


def test_status_chip_maps_each_known_slug_to_its_badge() -> None:
    app = _run(STATUS_CHIP_SCRIPT)

    assert not app.exception
    badges = [element.value for element in app.markdown if "badge" in element.value]
    assert badges == [
        f":green-badge[{t('value.status_success')}]",
        f":red-badge[{t('value.status_failed')}]",
        f":orange-badge[{t('value.status_partial')}]",
        f":gray-badge[{t('value.status_unknown')}]",
    ]


def test_status_chip_mapping_is_total_for_an_unknown_slug() -> None:
    app = _run(
        "from dashboard.components.layout import render_status_chip\n"
        'render_status_chip("not-a-real-status")\n'
    )

    # A new source status must not blank the page, so the fallback chip renders.
    assert not app.exception
    assert [element.value for element in app.markdown] == [
        f":gray-badge[{t('value.status_unknown')}]"
    ]


def test_status_dot_renders_one_escaped_fragment() -> None:
    app = _run(
        "from dashboard.components.layout import render_status_dot\n"
        'render_status_dot("<b>stale</b> & <script>", "warn")\n'
    )

    assert not app.exception
    # The `dir="rtl"` wrapper is what keeps the inline-level `.dot` at the right
    # edge inside Streamlit's LTR main block.
    assert html_texts(app) == [
        '<div dir="rtl">'
        '<span class="dot tone-warn">&lt;b&gt;stale&lt;/b&gt; &amp; &lt;script&gt;</span>'
        "</div>"
    ]


def test_status_dot_rejects_an_unknown_tone() -> None:
    app = _run(
        "from dashboard.components.layout import render_status_dot\n"
        'render_status_dot("stale", "danger")\n'
    )

    assert app.exception
    assert "unknown status dot tone" in str(app.exception[0].value)


UNOWNED_BAR_LIST_SCRIPT = """
from dashboard.components.layout import BarRow, render_bar_list

render_bar_list(
    [BarRow("economy", 4), BarRow("a_dead_domain", 2)],
    "6 domain-less",
)
"""


def test_bar_list_scales_each_bar_to_the_largest_count() -> None:
    app = _run(UNOWNED_BAR_LIST_SCRIPT)

    assert not app.exception
    bars = [body for body in html_texts(app) if "bar-rail" in body]
    assert bars == [
        '<div class="bar-rail"><div class="bar-fill" style="width:100.0%"></div></div>',
        '<div class="bar-rail"><div class="bar-fill" style="width:50.0%"></div></div>',
    ]


def test_bar_list_renders_counts_through_the_formatter() -> None:
    app = _run(UNOWNED_BAR_LIST_SCRIPT)

    assert not app.exception
    values = [element.value for element in app.markdown]
    # Persian digits, so the row value is display-formatted, not raw.
    assert "۴" in values
    assert "۲" in values


def test_bar_list_footer_carries_the_caption_and_the_total() -> None:
    app = _run(UNOWNED_BAR_LIST_SCRIPT)

    assert not app.exception
    footers = [body for body in html_texts(app) if "bar-list-foot" in body]
    assert footers == [
        '<div class="bar-list-foot">'
        f"<span>{t('section.indicators_by_domain_total')}</span>"
        "<b>6 domain-less</b></div>"
    ]


def test_bar_list_escapes_the_total_label() -> None:
    app = _run(
        "from dashboard.components.layout import BarRow, render_bar_list\n"
        'render_bar_list([BarRow("economy", 1)], "<img src=x onerror=alert(1)>")\n'
    )

    assert not app.exception
    footer = next(body for body in html_texts(app) if "bar-list-foot" in body)
    assert "&lt;img src=x onerror=alert(1)&gt;" in footer
    assert "<img" not in footer


def test_bar_list_renders_the_shared_empty_state_without_rows() -> None:
    app = _run(
        "from dashboard.components.layout import render_bar_list\n" 'render_bar_list([], "0")\n'
    )

    assert not app.exception
    assert [info.value for info in app.info] == [t("empty.no_indicators_for_page")]


def test_bar_list_keeps_the_owner_link_a_native_page_link(
    fake_streamlit_connection: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The label of an owned domain must stay a native ``st.page_link`` (AM-17).

    ``st.page_link`` only resolves inside a run whose ``st.navigation`` registered
    the target pages, so the component is exercised through the real entrypoint
    (``dashboard/app.py``), with the Overview's domain-counts block replaced by a
    ``render_bar_list`` call. ``economy`` is a dead domain with no owner, so it must
    render as plain text and produce no link.
    """
    rendered: list[bool] = []

    def fake_domain_counts(domain_counts: pd.DataFrame) -> None:
        rendered.append(True)
        render_bar_list(
            [BarRow("inflation", 15), BarRow("economy", 2)],
            f"{format_number(17)} {t('table.indicator_count')}",
        )

    monkeypatch.setattr("dashboard.page_view._render_domain_counts", fake_domain_counts)
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()

    assert not app.exception
    assert rendered == [True]
    # One link: the owned domain only.
    assert len(app.get("page_link")) == 1
    # The unowned domain stays visible as text.
    labels = [element.value for element in app.markdown]
    assert domain_label("economy") in labels
    bars = [body for body in html_texts(app) if "bar-rail" in body]
    assert len(bars) == 2


# --- Tasks 17-20: the component RTL context --------------------------------


def test_component_containers_declare_their_own_rtl_context() -> None:
    """Each shared component establishes the RTL context its mockup geometry needs.

    Streamlit's main block is ``dir: ltr``, so an inherited ``inline-start`` is the
    *left* edge. Without these declarations the callout's accent bar and glyph, the
    KPI band's cell order and the bar-list's row order/footer/fill all mirror to the
    left of the mockup. The declarations' DOM effect was verified with a Playwright
    probe against Streamlit 1.61.1 and recorded in the execution log (Task 20);
    AppTest cannot see computed styles, so the stylesheet is asserted here.
    """
    css = direction_css()

    assert f'{CSS_SELECTORS["callout"]} [data-testid="stAlertContainer"] {{ direction: rtl;' in css
    assert f'{CSS_SELECTORS["kpi_band"]} {{ direction: rtl;' in css
    assert f'{CSS_SELECTORS["bar_list"]} {{ direction: rtl; }}' in css
    assert f'{CSS_SELECTORS["bar_list"]} {CSS_SELECTORS["bar_rail"]} {{ direction: rtl;' in css


# --- Task 21: section header, filter bar -----------------------------------

SECTION_HEADER_SCRIPT = """
from dashboard.components.layout import render_section_header

render_section_header("section.available_coverage")
render_section_header("section.source_freshness", trailing="۵ به‌روز · ۲ کهنه")
render_section_header(
    "section.indicators_by_domain",
    subtitle="شاخص‌های فعال هر حوزه",
    trailing="تعداد شاخص",
    key="bars",
)
"""


def test_section_header_renders_the_title_natively() -> None:
    app = _run(SECTION_HEADER_SCRIPT)

    assert not app.exception
    # A native st.subheader, so AppTest keeps seeing app.subheader.
    assert [subheader.value for subheader in app.subheader] == [
        t("section.available_coverage"),
        t("section.source_freshness"),
        t("section.indicators_by_domain"),
    ]


def test_section_header_secondary_text_is_optional() -> None:
    app = _run(
        "from dashboard.components.layout import render_section_header\n"
        'render_section_header("section.available_coverage")\n'
    )

    assert not app.exception
    # No subtitle and no trailing text, so nothing but the subheader is emitted.
    assert not app.markdown
    assert len(app.subheader) == 1


def test_section_header_renders_the_trailing_text() -> None:
    app = _run(SECTION_HEADER_SCRIPT)

    assert not app.exception
    # The trailing slot carries already-resolved text, so it passes through.
    assert "۵ به‌روز · ۲ کهنه" in [element.value for element in app.markdown]


def test_section_header_renders_the_subtitle_under_the_title() -> None:
    app = _run(SECTION_HEADER_SCRIPT)

    assert not app.exception
    assert "شاخص‌های فعال هر حوزه" in [element.value for element in app.markdown]


def test_section_header_container_key_derives_from_the_title() -> None:
    # A page renders several headers, so the default key is the title itself and
    # distinct titles never collide.
    app = _run(
        "from dashboard.components.layout import render_section_header\n"
        'render_section_header("section.available_coverage")\n'
        'render_section_header("section.source_freshness")\n'
    )

    assert not app.exception
    assert len(app.subheader) == 2


def test_section_header_container_key_can_be_overridden() -> None:
    # The same title twice needs an explicit key, exactly as the callout does.
    app = _run(
        "from dashboard.components.layout import render_section_header\n"
        'render_section_header("section.available_coverage")\n'
        'render_section_header("section.available_coverage", key="second")\n'
    )

    assert not app.exception
    assert len(app.subheader) == 2


def test_section_header_css_turns_the_container_into_one_row() -> None:
    css = direction_css()

    assert CSS_SELECTORS["section_header"] in css
    assert (
        f'{CSS_SELECTORS["section_header"]} {{ direction: rtl; flex-direction: row !important; '
        "justify-content: space-between; align-items: baseline; }" in css
    )
    # The mockup's `.sec-h .sub` type reaches only the optional secondary text.
    assert (
        f'{CSS_SELECTORS["section_subtitle"]} [data-testid="stMarkdownContainer"], '
        f'{CSS_SELECTORS["section_trailing"]} [data-testid="stMarkdownContainer"] '
        "{ font-size: 12.5px; color: var(--text-3); }" in css
    )


def test_section_header_selectors_cannot_match_the_nested_containers() -> None:
    """The row override must not apply to the containers it positions.

    The hooks are attribute-substring selectors, so a nested container whose key
    started with the header's stem would also receive the row override and lose its
    column layout. The title/subtitle grouping container is unstyled, so only the
    two styled nested hooks can be checked here.
    """
    stem = "st-key-section-header-"

    assert stem in CSS_SELECTORS["section_header"]
    for key in ("section_subtitle", "section_trailing"):
        assert stem not in CSS_SELECTORS[key], key


def _filter_bar_script(control_count: int) -> str:
    return (
        "import streamlit as st\n"
        "from dashboard.components.layout import render_filter_bar\n"
        "from dashboard.i18n import t\n"
        'KEYS = ["filter.domain", "filter.source", "filter.frequency", '
        '"filter.indicators", "filter.start_date", "filter.end_date"]\n'
        "\n"
        "\n"
        "def make(key):\n"
        "    def control():\n"
        "        st.selectbox(t(key), [t('filter.all')])\n"
        "    return control\n"
        "\n"
        "\n"
        f"render_filter_bar([make(key) for key in KEYS[:{control_count}]])\n"
    )


@pytest.mark.parametrize("control_count", [1, 3, 6])
def test_filter_bar_renders_an_arbitrary_number_of_controls(control_count: int) -> None:
    app = _run(_filter_bar_script(control_count))

    assert not app.exception
    assert len(app.selectbox) == control_count


def test_filter_bar_pins_the_trailing_group_to_the_far_end() -> None:
    app = _run(
        "import streamlit as st\n"
        "from dashboard.components.layout import render_filter_bar\n"
        "from dashboard.i18n import t\n"
        "\n"
        "\n"
        "def row_count():\n"
        "    st.markdown(t('filter.showing_rows', count='۸'))\n"
        "\n"
        "\n"
        "def density():\n"
        "    st.segmented_control(\n"
        "        t('filter.density'),\n"
        "        [t('filter.density_comfortable'), t('filter.density_compact')],\n"
        "    )\n"
        "\n"
        "\n"
        "def domain():\n"
        "    st.selectbox(t('filter.domain'), [t('filter.all')])\n"
        "\n"
        "\n"
        "render_filter_bar([domain], trailing=[row_count, density])\n"
    )

    assert not app.exception
    assert [selectbox.label for selectbox in app.selectbox] == [t("filter.domain")]
    assert [control.label for control in app.segmented_control] == [t("filter.density")]
    assert t("filter.showing_rows", count="۸") in [element.value for element in app.markdown]


def test_filter_bar_rejects_an_empty_control_list() -> None:
    app = _run("from dashboard.components.layout import render_filter_bar\nrender_filter_bar([])\n")

    assert app.exception
    assert "at least one control" in str(app.exception[0].value)


def test_filter_bar_container_declares_the_rtl_context() -> None:
    css = direction_css()

    assert CSS_SELECTORS["filter_bar"] in css
    assert f'{CSS_SELECTORS["filter_bar"]} {{ direction: rtl; }}' in css


# --- Task 28: top bar / breadcrumb + last-collection stamp ------------------


def test_top_bar_selector_is_registered_and_styled() -> None:
    """The top bar's keyed-container hook is declared in ``CSS_SELECTORS`` and
    emitted by ``direction_css()``, with the columns row held to the mockup's
    48 px via ``min-height`` (a plain ``height`` is inert on this flex item —
    see the Step 0b note in ``direction.py``)."""
    assert "top_bar" in CSS_SELECTORS
    css = direction_css()
    assert CSS_SELECTORS["top_bar"] in css
    assert f'{CSS_SELECTORS["top_bar"]} {{ direction: rtl; }}' in css
    assert "min-height: 48px" in css
    assert "top-bar-breadcrumb" in css
    assert "top-bar-stamp" in css


def test_top_bar_renders_breadcrumb_and_stamp(
    fake_streamlit_connection: None,
) -> None:
    """The breadcrumb carries the root › group › page, and the stamp carries the
    last-collection date through the Tehran/Jalali helpers."""
    app = _run(
        "from dashboard.components.layout import render_top_bar\n"
        'render_top_bar("مرور و تحلیل", "مرور کلی")\n'
    )

    assert not app.exception
    fragments = html_texts(app)
    breadcrumb = next(f for f in fragments if "top-bar-breadcrumb" in f)
    stamp = next(f for f in fragments if "top-bar-stamp" in f)
    # The breadcrumb root, group and page labels all appear.
    assert t("shell.breadcrumb_root") in breadcrumb
    assert "مرور و تحلیل" in breadcrumb
    assert "مرور کلی" in breadcrumb
    # The stamp carries the timezone label (always present) and the
    # last-collection prefix (present when freshness has data).
    assert t("shell.timezone") in stamp
    assert t("shell.last_collection", date="")[:10] in stamp


def test_top_bar_renders_unknown_placeholder_when_freshness_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty freshness frame renders the unknown placeholder, not a crash."""
    import pandas as pd

    from dashboard.queries import cached_source_freshness

    cached_source_freshness.clear()
    monkeypatch.setattr(
        "dashboard.components.layout.cached_source_freshness",
        lambda: pd.DataFrame(),
    )

    app = _run(
        "from dashboard.components.layout import render_top_bar\n"
        'render_top_bar("مرور و تحلیل", "مرور کلی")\n'
    )

    assert not app.exception
    stamp = next(f for f in html_texts(app) if "top-bar-stamp" in f)
    assert t("value.unknown") in stamp


def test_top_bar_container_declares_the_rtl_context() -> None:
    css = direction_css()

    assert f'{CSS_SELECTORS["top_bar"]} {{ direction: rtl; }}' in css
