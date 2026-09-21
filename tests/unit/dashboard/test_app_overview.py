"""AppTest smoke test for the Overview page (Task 16).

The Overview is the router's default page and uses ``st.page_link`` for its
per-domain links. ``st.page_link`` requires the target pages to be registered, so
the page is rendered through the entrypoint router rather than as a standalone
page file (``docs/phase-7.1/wave-0-spike.md``).
"""

import re
from datetime import UTC, datetime

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.components.direction import CSS_SELECTORS, direction_css
from dashboard.components.html_table import Dot, StatusChip, Text, TwoLine
from dashboard.components.layout import BarRow
from dashboard.formatting import (
    format_number,
    jalali_date_label,
    relative_time_label,
    tehran_clock_label,
)
from dashboard.i18n import t
from dashboard.labels import domain_label, source_label
from dashboard.navigation import page_for_domain
from dashboard.page_view import (
    build_freshness_rows,
    freshness_display,
    freshness_summary,
    ordered_domain_rows,
    overview_kpi_cells,
    series_inventory_counts,
)
from dashboard.repository import SERIES_KIND_BASE
from tests.unit.dashboard.app_smoke import (
    ORPHAN_INDICATOR,
    REPOSITORY_ROOT,
    FakeDashboardRepository,
    html_texts,
)


def _overview_app() -> AppTest:
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()
    return app


def test_overview_page_renders(fake_streamlit_connection) -> None:
    app = _overview_app()

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.overview")]


def test_overview_reports_domain_counts_and_freshness_sections(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    subheaders = [subheader.value for subheader in app.subheader]
    assert t("section.indicators_by_domain") in subheaders
    assert t("section.source_freshness") in subheaders
    assert t("section.available_coverage") in subheaders
    # The whole-catalog "Key indicators" dump is gone (Task 16).
    assert t("section.key_indicators") not in subheaders


def test_overview_reports_derived_and_orphan_gold_series(fake_streamlit_connection) -> None:
    app = _overview_app()

    labels = {metric.label for metric in app.metric}
    assert t("metric.active_indicators") in labels
    assert t("metric.derived_series") in labels
    assert t("metric.orphan_series") in labels
    assert t("metric.matching_indicators") not in labels


# --- Task 29: the KPI band (six cells) --------------------------------------


def test_overview_kpi_band_renders_six_cells_in_mockup_order(
    fake_streamlit_connection,
) -> None:
    """Right to left, the mockup's six cells: sources, domains, active
    indicators, Gold observations, then the separated derived/orphan pair."""
    app = _overview_app()

    assert not app.exception
    assert [metric.label for metric in app.metric] == [
        t("metric.sources"),
        t("metric.domains"),
        t("metric.active_indicators"),
        t("metric.gold_observations"),
        t("metric.derived_series"),
        t("metric.orphan_series"),
    ]


def test_overview_kpi_band_annotates_three_cells_and_tags_the_orphan(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    assert not app.exception
    assert [metric.help for metric in app.metric] == [
        "",
        "",
        "",
        t("metric.gold_observations_help"),
        t("metric.derived_series_help"),
        t("metric.orphan_series_help"),
    ]
    # Exactly one cell carries the "needs review" tag.
    badges = [element.value for element in app.markdown if "badge" in element.value]
    assert badges == [f":orange-badge[{t('metric.orphan_series_tag')}]"]


def test_overview_kpi_cells_keep_the_derived_and_orphan_counts_separate() -> None:
    """D2: the two secondary counts are never deduplicated or merged."""
    repository = FakeDashboardRepository()
    catalog = repository.list_indicators()
    inventory = repository.series_inventory()

    cells = overview_kpi_cells(catalog, inventory, total_observations=8_195)
    derived, orphan = series_inventory_counts(inventory)
    values = {cell.label_key: cell.value for cell in cells}

    assert values["metric.derived_series"] == format_number(derived)
    assert values["metric.orphan_series"] == format_number(orphan)
    assert values["metric.gold_observations"] == format_number(8_195)
    # The two counts come from separate expressions and stay separate metrics.
    assert "metric.derived_series" in values
    assert "metric.orphan_series" in values
    assert [cell.secondary for cell in cells] == [False, False, False, False, True, True]


def test_overview_kpi_cells_are_empty_safe_for_a_missing_inventory_column() -> None:
    """An inventory frame without the classification columns counts zero."""
    repository = FakeDashboardRepository()
    cells = overview_kpi_cells(
        repository.list_indicators(),
        pd.DataFrame({"indicator_id": ["x"]}),
        total_observations=0,
    )

    values = {cell.label_key: cell.value for cell in cells}
    assert values["metric.derived_series"] == format_number(0)
    assert values["metric.orphan_series"] == format_number(0)


def test_overview_staleness_verdict_is_rendered(fake_streamlit_connection) -> None:
    app = _overview_app()

    # The fake collection log's only run is years old, so the monthly-cadence
    # source is reported stale. The freshness surface is an RTL HTML table now
    # (Task 30), so it is read through the markup helper, not `app.dataframe`.
    markup = next(body for body in html_texts(app) if t("table.run_status") in body)
    for header in (
        t("table.source_name"),
        t("table.staleness"),
        t("table.last_collection"),
        t("table.records_collected"),
        t("table.run_status"),
    ):
        assert f'<th scope="col">{header}</th>' in markup
    assert source_label("world_bank") in markup
    assert f'<span class="dot tone-warn">{t("value.stale")}</span>' in markup
    assert f'<span class="chip tone-ok">{t("value.status_success")}</span>' in markup


def test_overview_freshness_section_header_carries_the_summary(
    fake_streamlit_connection,
) -> None:
    """Task 12's `section.freshness_summary` is the section header's trailing text."""
    app = _overview_app()
    fresh, stale = freshness_summary(
        FakeDashboardRepository().source_freshness(), now=datetime.now(UTC)
    )

    expected = t(
        "section.freshness_summary",
        fresh=format_number(fresh),
        stale=format_number(stale),
    )
    assert expected in [element.value for element in app.markdown]


def test_overview_freshness_uses_the_markup_strategy_not_a_dataframe(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    # No dataframe carries the freshness headers any more (Task 16 map, Task 30).
    frames = [frame.value for frame in app.dataframe]
    assert all(t("table.staleness") not in frame.columns for frame in frames)
    assert any(t("table.run_status") in body for body in html_texts(app))


def test_overview_states_that_forecasts_are_indistinguishable(
    fake_streamlit_connection,
) -> None:
    """IMF forecast labeling is deferred, so the disclaimer must stay visible."""
    app = _overview_app()

    assert t("warn.forecasts_indistinguishable") in [warning.value for warning in app.warning]


def test_fake_orphan_series_has_no_catalog_row_or_parent() -> None:
    """The Gold-only orphan fixture is a genuine orphan, never attributed."""
    inventory = FakeDashboardRepository().series_inventory()
    orphan = inventory[inventory["indicator_id"] == ORPHAN_INDICATOR]

    assert len(orphan) == 1
    assert bool(orphan.iloc[0]["has_catalog_metadata"]) is False
    assert orphan.iloc[0]["series_kind"] == SERIES_KIND_BASE
    assert pd.isna(orphan.iloc[0]["derived_from"])


def test_overview_reports_the_gold_only_orphan_series(fake_streamlit_connection) -> None:
    app = _overview_app()
    repository = FakeDashboardRepository()
    inventory = repository.series_inventory()
    expected_orphans = int((~inventory["has_catalog_metadata"].astype(bool)).sum())

    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics[t("metric.orphan_series")] == format_number(expected_orphans)
    # The orphan has no catalog row, so no catalog-driven page can select it.
    assert ORPHAN_INDICATOR not in set(repository.list_indicators()["indicator_id"])


def _freshness_frame() -> pd.DataFrame:
    collected = datetime(2026, 1, 1, tzinfo=UTC)
    return pd.DataFrame(
        {
            "source_name": ["tgju", "hbsir", "unknown_source"],
            "collection_timestamp": [collected, collected, collected],
            "status": ["success", "success", "success"],
            "records_collected": [1, 2, 3],
            "error_message": [None, None, None],
        }
    )


def test_freshness_display_compares_each_source_against_its_cadence() -> None:
    display = freshness_display(_freshness_frame(), now=datetime(2026, 1, 3, tzinfo=UTC))

    # Two days old: stale for a daily source, fresh for an annual one, and
    # unknown when the source has no expected cadence at all.
    assert display[t("table.staleness")].tolist() == [
        t("value.stale"),
        t("value.fresh"),
        t("value.unknown"),
    ]
    assert display[t("table.source_name")].tolist() == [
        source_label("tgju"),
        source_label("hbsir"),
        "unknown_source",
    ]
    # The stored UTC instant is shown as a Tehran-local Jalali timestamp.
    assert all("،" in value for value in display[t("table.collection_timestamp")])


def test_freshness_display_is_empty_rather_than_invented_without_a_log() -> None:
    display = freshness_display(pd.DataFrame())

    assert display.empty
    assert t("table.staleness") in display.columns


# --- freshness ordering and aggregate (Task 12) ----------------------------


def _ordering_frame() -> pd.DataFrame:
    """Fresh source first in input order, so a stale-first sort is observable."""
    collected = datetime(2026, 1, 1, tzinfo=UTC)
    return pd.DataFrame(
        {
            "source_name": ["hbsir", "tgju", "tsetmc"],
            "collection_timestamp": [collected, collected, collected],
            "status": ["success", "success", "success"],
            "records_collected": [1, 2, 3],
            "error_message": [None, None, None],
        }
    )


def test_freshness_display_orders_stale_rows_first_with_stable_secondary_order() -> None:
    display = freshness_display(_ordering_frame(), now=datetime(2026, 1, 3, tzinfo=UTC))

    # Stale rows (tgju, tsetmc) move ahead of the fresh one (hbsir); the two
    # stale rows keep their input order, so the sort is stable.
    assert display[t("table.source_name")].tolist() == [
        source_label("tgju"),
        source_label("tsetmc"),
        source_label("hbsir"),
    ]
    assert display[t("table.staleness")].tolist() == [
        t("value.stale"),
        t("value.stale"),
        t("value.fresh"),
    ]


def test_freshness_summary_counts_fresh_and_stale_and_ignores_unknown() -> None:
    # tgju is stale, hbsir is fresh, and unknown_source has no cadence.
    assert freshness_summary(_freshness_frame(), now=datetime(2026, 1, 3, tzinfo=UTC)) == (1, 1)
    # A different reference instant changes the verdict, so `now` is honoured.
    assert freshness_summary(_freshness_frame(), now=datetime(2026, 1, 1, tzinfo=UTC)) == (2, 0)
    assert freshness_summary(_ordering_frame(), now=datetime(2026, 1, 3, tzinfo=UTC)) == (1, 2)


def test_freshness_summary_is_zero_for_an_empty_frame() -> None:
    assert freshness_summary(pd.DataFrame(), now=datetime(2026, 1, 3, tzinfo=UTC)) == (0, 0)


# --- Task 30: the freshness table (typed cells) -----------------------------


def test_build_freshness_rows_orders_stale_first_with_typed_cells() -> None:
    now = datetime(2026, 1, 3, tzinfo=UTC)
    collected = datetime(2026, 1, 1, tzinfo=UTC)
    table = build_freshness_rows(_ordering_frame(), now=now)

    assert table.columns == (
        t("table.source_name"),
        t("table.staleness"),
        t("table.last_collection"),
        t("table.records_collected"),
        t("table.run_status"),
    )
    # Stale rows first (tgju, tsetmc), then the fresh one; stable within a verdict.
    assert [row[0] for row in table.rows] == [
        Text(source_label("tgju")),
        Text(source_label("tsetmc")),
        Text(source_label("hbsir")),
    ]
    assert [row[1] for row in table.rows] == [
        Dot(t("value.stale"), "warn"),
        Dot(t("value.stale"), "warn"),
        Dot(t("value.fresh"), "ok"),
    ]
    # The two-line date cell: Jalali date, then time · relative age, amber when stale.
    assert table.rows[0][2] == TwoLine(
        jalali_date_label(collected),
        (Text(tehran_clock_label(collected)), Text(relative_time_label(collected, now=now))),
        primary_tone="warn",
    )
    assert table.rows[2][2].primary_tone == "ok"
    assert [row[3] for row in table.rows] == [
        Text(format_number(2)),
        Text(format_number(3)),
        Text(format_number(1)),
    ]
    assert [row[4] for row in table.rows] == [StatusChip(t("value.status_success"), "ok")] * 3


def test_build_freshness_rows_gives_an_unknown_cadence_a_neutral_dot() -> None:
    table = build_freshness_rows(_freshness_frame(), now=datetime(2026, 1, 3, tzinfo=UTC))

    # tgju stale, hbsir fresh, unknown_source has no cadence: neutral, sorted last.
    assert [row[1] for row in table.rows] == [
        Dot(t("value.stale"), "warn"),
        Dot(t("value.fresh"), "ok"),
        Dot(t("value.unknown"), "neutral"),
    ]
    assert table.rows[-1][0] == Text("unknown_source")


def test_build_freshness_rows_maps_an_unknown_status_to_the_unknown_chip() -> None:
    frame = pd.DataFrame(
        {
            "source_name": ["tgju"],
            "collection_timestamp": [datetime(2026, 1, 1, tzinfo=UTC)],
            "status": ["brand_new_slug"],
            "records_collected": [None],
            "error_message": [None],
        }
    )

    table = build_freshness_rows(frame, now=datetime(2026, 1, 3, tzinfo=UTC))

    assert table.rows[0][4] == StatusChip(t("value.status_unknown"), "neutral")
    # A missing count renders unknown, never an invented zero.
    assert table.rows[0][3] == Text(t("value.unknown"))


def test_build_freshness_rows_returns_headers_only_for_an_empty_frame() -> None:
    table = build_freshness_rows(pd.DataFrame(), now=datetime(2026, 1, 3, tzinfo=UTC))

    assert table.rows == ()
    assert t("table.run_status") in table.columns


def test_freshness_table_uses_its_own_last_collection_header() -> None:
    """P3: the Overview table's header is `آخرین گردآوری`, the generic key stays."""
    assert t("table.last_collection") != t("table.collection_timestamp")
    table = build_freshness_rows(_ordering_frame(), now=datetime(2026, 1, 3, tzinfo=UTC))

    assert t("table.last_collection") in table.columns
    assert t("table.collection_timestamp") not in table.columns
    # The generic header is unchanged for every other surface.
    assert (
        t("table.collection_timestamp")
        in freshness_display(_ordering_frame(), now=datetime(2026, 1, 3, tzinfo=UTC)).columns
    )


# --- Task 31: domain bars + the two-column row ------------------------------


def test_overview_domain_bars_link_each_owned_domain(
    fake_streamlit_connection,
) -> None:
    """The bar list keeps one native ``st.page_link`` per owned domain."""
    app = _overview_app()
    domain_counts = FakeDashboardRepository().available_domains()
    total = int(domain_counts["indicator_count"].sum())

    assert not app.exception
    owned = [
        str(domain)
        for domain in domain_counts["domain"]
        if page_for_domain(str(domain)) is not None
    ]
    assert len(owned) == len(domain_counts)
    # Visible to AppTest as native page links, not raw anchors.
    assert len(app.get("page_link")) == len(owned)

    bars = [body for body in html_texts(app) if "bar-rail" in body]
    assert len(bars) == len(domain_counts)
    # Proportional to the counts, in the count-descending display order (P1): the
    # largest domain fills its rail and every other rail is that domain's share.
    widths = [float(match) for body in bars for match in re.findall(r"width:([\d.]+)%", body)]
    largest = int(domain_counts["indicator_count"].max())
    assert widths.count(100.0) == int((domain_counts["indicator_count"] == largest).sum())
    for width, row in zip(widths, ordered_domain_rows(domain_counts), strict=True):
        assert abs(width - row.indicator_count / largest * 100) < 0.05

    footer = next(body for body in html_texts(app) if "bar-list-foot" in body)
    assert t("section.indicators_by_domain_total") in footer
    assert t("metric.indicator_count", count=format_number(total)) in footer


def test_ordered_domain_rows_sort_count_descending_then_name_ascending() -> None:
    """P1: the mockup's bar order is count-descending, ties by domain name."""
    frame = pd.DataFrame(
        {
            "domain": ["energy", "gdp", "gold", "inflation", "labor", "fx", "market"],
            "indicator_count": [3, 8, 2, 15, 1, 1, 1],
        }
    )

    rows = ordered_domain_rows(frame)

    # 15, 8, 3, 2, then the three 1s in Persian display-name order
    # (ارز < بازار سرمایه < بازار کار).
    assert rows == [
        BarRow("inflation", 15),
        BarRow("gdp", 8),
        BarRow("energy", 3),
        BarRow("gold", 2),
        BarRow("fx", 1),
        BarRow("market", 1),
        BarRow("labor", 1),
    ]


def test_ordered_domain_rows_are_stable_and_keep_an_unknown_count_as_zero() -> None:
    frame = pd.DataFrame({"domain": ["gdp", "inflation"], "indicator_count": [None, 5]})

    # A missing count renders zero (never dropped) and sorts last; the single
    # non-zero row keeps its place.
    assert ordered_domain_rows(frame) == [BarRow("inflation", 5), BarRow("gdp", 0)]


def test_overview_domain_bars_render_in_count_descending_order(
    fake_streamlit_connection,
) -> None:
    """The rendered bars follow the sorted order, not the frame's row order."""
    app = _overview_app()
    domain_counts = FakeDashboardRepository().available_domains()
    expected = [domain_label(row.domain) for row in ordered_domain_rows(domain_counts)]

    assert not app.exception
    labels = [link.proto.label for link in app.get("page_link")]
    assert labels == expected


def test_overview_domain_bars_section_header_carries_the_count_label(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    assert t("table.indicator_count") in [element.value for element in app.markdown]


def test_overview_renders_the_two_column_row_with_freshness_first(
    fake_streamlit_connection,
) -> None:
    """The mockup's row: freshness in the wide column, then the domain bars."""
    app = _overview_app()

    subheaders = [subheader.value for subheader in app.subheader]
    assert subheaders.index(t("section.source_freshness")) < subheaders.index(
        t("section.indicators_by_domain")
    )


def test_overview_row_declares_the_rtl_context() -> None:
    """Task 31: without it the first column would land on the left (LTR main block)."""
    css = direction_css()

    assert CSS_SELECTORS["overview_row"] in css
    assert f'{CSS_SELECTORS["overview_row"]} {{ direction: rtl; }}' in css
