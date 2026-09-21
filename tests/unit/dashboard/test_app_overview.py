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
from dashboard.components.html_table import DENSITIES, Dot, Ltr, StatusChip, Text, TwoLine, UnitChip
from dashboard.components.layout import BarRow
from dashboard.formatting import (
    RANGE_SEPARATOR,
    format_number,
    jalali_date_label,
    relative_time_label,
    tehran_clock_label,
)
from dashboard.i18n import t
from dashboard.labels import domain_label, frequency_label, indicator_label, source_label
from dashboard.navigation import page_for_domain
from dashboard.page_view import (
    build_coverage_rows,
    build_freshness_rows,
    filter_coverage_frame,
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


def test_freshness_summary_string_colours_only_the_stale_count() -> None:
    """P4: the stale count carries the markdown orange directive (theme warn)."""
    summary = t("section.freshness_summary", fresh=format_number(5), stale=format_number(2))

    assert f":orange[{format_number(2)}]" in summary
    assert f":orange[{format_number(5)}]" not in summary
    assert summary.endswith(t("value.stale"))


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
    """IMF forecast labeling is deferred, so the disclaimer must stay visible.

    The header's callout carries the bold methodology label (Task 33), so the
    disclaimer is a *substring* of the warning body rather than the whole body.
    """
    app = _overview_app()

    bodies = [warning.value for warning in app.warning]
    assert any(t("warn.forecasts_indistinguishable") in body for body in bodies)
    assert any(t("note.methodology_label") in body for body in bodies)


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


# --- Task 32: the Overview coverage table -------------------------------------

#: The ten coverage headers in the mockup's order.
_COVERAGE_HEADERS = (
    t("table.indicator"),
    t("table.domain"),
    t("table.source_name"),
    t("table.frequency"),
    t("table.unit"),
    t("table.coverage_range"),
    t("table.observed_range"),
    t("table.observation_count"),
    t("table.chained_rows"),
    t("table.average_confidence"),
)


def _coverage_frame() -> pd.DataFrame:
    """One World Bank annual row and one TGJU daily row, in that order.

    The pair is the point: the two calendars the range cells have to separate, and
    the two row shapes (a chained/confidence-bearing annual series and a
    three-observation daily snapshot with neither).
    """
    return pd.DataFrame(
        [
            {
                "indicator_id": "NY.GDP.MKTP.CD",
                "name": "GDP (current US$)",
                "unit": "current US$",
                "frequency": "annual",
                "domain": "gdp",
                "source_name": "world_bank",
                "availability_start": pd.Timestamp("1960-12-31", tz="UTC"),
                "availability_end": pd.Timestamp("2025-12-31", tz="UTC"),
                "observed_start": pd.Timestamp("1960-12-31", tz="UTC"),
                "observed_end": pd.Timestamp("2025-12-31", tz="UTC"),
                "observation_count": 66,
                "chain_linked_count": 0,
                "confidence": None,
            },
            {
                "indicator_id": "TGJU.USD.FREE",
                "name": "USD free rate",
                "unit": "IRR",
                "frequency": "daily",
                "domain": "fx",
                "source_name": "tgju",
                "availability_start": pd.Timestamp("2026-09-09", tz="UTC"),
                "availability_end": pd.Timestamp("2026-09-11", tz="UTC"),
                "observed_start": pd.Timestamp("2026-09-09", tz="UTC"),
                "observed_end": pd.Timestamp("2026-09-11", tz="UTC"),
                "observation_count": 3,
                "chain_linked_count": None,
                "confidence": None,
            },
        ]
    )


def test_build_coverage_rows_uses_the_mockup_columns_and_wrapped_headers() -> None:
    table = build_coverage_rows(_coverage_frame())

    assert table.columns == _COVERAGE_HEADERS
    # Only the three right-hand headers are two-line in the mockup.
    assert table.wrap_headers == (
        t("table.observation_count"),
        t("table.chained_rows"),
        t("table.average_confidence"),
    )
    assert len(table.rows) == 2


def test_build_coverage_rows_labels_every_descriptive_cell() -> None:
    table = build_coverage_rows(_coverage_frame())
    cells = table.rows[0]

    assert cells[0] == TwoLine(
        indicator_label("NY.GDP.MKTP.CD", "GDP (current US$)"),
        (Ltr("NY.GDP.MKTP.CD", mono_id=True),),
    )
    assert cells[1] == Text(domain_label("gdp"))
    assert cells[2] == Text(source_label("world_bank"))
    assert cells[3] == Text(frequency_label("annual"))
    assert cells[4] == UnitChip("current US$")
    assert cells[7] == Text(format_number(66), num=True)
    assert cells[8] == Text(format_number(0), num=True)


def test_build_coverage_rows_gives_a_gregorian_source_an_ltr_range_with_exact_dates() -> None:
    """D3 + AM-27(e): the display is a Gregorian year, the tooltip is exact."""
    table = build_coverage_rows(_coverage_frame())

    # The separator comes from the one place that owns it; `test_formatting` pins
    # its exact bytes with literal golden values.
    expected = Ltr(
        f"۱۹۶۰{RANGE_SEPARATOR}۲۰۲۵",
        title=f"1960-12-31{RANGE_SEPARATOR}2025-12-31",
        num=True,
    )
    assert table.rows[0][5] == expected
    assert table.rows[0][6] == expected


def test_build_coverage_rows_keeps_a_jalali_source_in_a_text_cell() -> None:
    """D3: a domestic range is RTL text, and a daily one takes the compact form."""
    table = build_coverage_rows(_coverage_frame())
    compact_daily = f"۱۸{RANGE_SEPARATOR}۲۰ شهریور ۱۴۰۵"

    assert table.rows[1][5] == Text(compact_daily, num=True)
    assert table.rows[1][6] == Text(compact_daily, num=True)


def test_build_coverage_rows_reads_the_calendar_map_it_is_given() -> None:
    """The Task 13 map is injected, so an empty one forces the Jalali form."""
    table = build_coverage_rows(_coverage_frame(), calendar_map={})

    assert table.rows[0][5] == Text(f"۱۳۳۹{RANGE_SEPARATOR}۱۴۰۴", num=True)


def test_build_coverage_rows_renders_the_em_dash_for_every_null() -> None:
    """The mockup's `na` cell: a missing value is never an invented zero."""
    table = build_coverage_rows(_coverage_frame())

    assert table.rows[1][8] == Text(None, num=True)  # chained rows
    assert table.rows[1][9] == Text(None, num=True)  # average confidence
    assert table.rows[0][9] == Text(None, num=True)


def test_build_coverage_rows_renders_a_missing_bound_as_the_em_dash() -> None:
    frame = _coverage_frame()
    frame.loc[0, "observed_start"] = pd.NaT
    frame.loc[0, "observed_end"] = pd.NaT

    table = build_coverage_rows(frame)

    assert table.rows[0][6] == Text(None)
    # The coverage range is unaffected: only the observed pair was cleared.
    assert isinstance(table.rows[0][5], Ltr)


def test_build_coverage_rows_returns_headers_only_for_an_empty_frame() -> None:
    table = build_coverage_rows(_coverage_frame().iloc[0:0])

    assert table.columns == _COVERAGE_HEADERS
    assert table.rows == ()


def test_build_coverage_rows_preserves_the_frame_order() -> None:
    """The repository owns the order; the builder never re-sorts."""
    frame = _coverage_frame().iloc[::-1].reset_index(drop=True)

    table = build_coverage_rows(frame)

    assert table.rows[0][1] == Text(domain_label("fx"))
    assert table.rows[1][1] == Text(domain_label("gdp"))


def test_filter_coverage_frame_applies_each_select_in_memory() -> None:
    frame = _coverage_frame()

    assert len(filter_coverage_frame(frame)) == 2
    assert list(filter_coverage_frame(frame, domain="gdp")["indicator_id"]) == ["NY.GDP.MKTP.CD"]
    assert list(filter_coverage_frame(frame, source="tgju")["indicator_id"]) == ["TGJU.USD.FREE"]
    assert list(filter_coverage_frame(frame, frequency="daily")["indicator_id"]) == [
        "TGJU.USD.FREE"
    ]
    assert filter_coverage_frame(frame, domain="gdp", source="tgju").empty


def test_filter_coverage_frame_skips_a_column_the_frame_does_not_carry() -> None:
    """A partial frame still renders instead of raising on the missing column."""
    frame = _coverage_frame().drop(columns=["frequency"])

    assert len(filter_coverage_frame(frame, frequency="annual")) == 2


def test_overview_coverage_uses_the_markup_strategy_not_a_dataframe(
    fake_streamlit_connection,
) -> None:
    """Task 16's map + Task 32: the coverage grid is an HTML table now."""
    app = _overview_app()

    frames = [frame.value for frame in app.dataframe]
    assert all(t("table.coverage_range") not in frame.columns for frame in frames)
    assert any(t("table.coverage_range") in body for body in html_texts(app))


def test_overview_coverage_table_is_the_coverage_variant_with_two_line_headers(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    body = next(body for body in html_texts(app) if t("table.coverage_range") in body)
    assert '<table class="dt cov comfortable">' in body
    assert "<br>".join(t("table.observation_count").split(" ")) in body
    assert "<br>".join(t("table.chained_rows").split(" ")) in body
    # The indicator id sits in the mockup's block-level `idl` line.
    assert '<bdi class="ltr idl">' in body


def test_overview_coverage_footnote_explains_the_gregorian_calendar(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    assert t("table.coverage_footnote") in [caption.value for caption in app.caption]


def test_overview_coverage_footnote_declares_the_rtl_context() -> None:
    """A native `st.caption` inherits the LTR main block, so it needs the hook."""
    css = direction_css()

    assert f'{CSS_SELECTORS["coverage_footnote"]} {{ direction: rtl; text-align: right; }}' in css


def test_overview_coverage_filter_bar_reduces_the_rows_and_updates_the_label(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()
    repository = FakeDashboardRepository()
    total = len(repository.coverage)
    # The bar starts on "همه" and echoes the whole frame's row count.
    assert t("filter.showing_rows", count=format_number(total)) in [
        element.value for element in app.markdown
    ]

    app.selectbox(key="overview_coverage_domain").select("gdp").run()

    assert not app.exception
    filtered = filter_coverage_frame(repository.coverage, domain="gdp")
    assert 0 < len(filtered) < total
    assert t("filter.showing_rows", count=format_number(len(filtered))) in [
        element.value for element in app.markdown
    ]
    body = next(body for body in html_texts(app) if t("table.coverage_range") in body)
    assert body.count("<tr>") == len(filtered) + 1  # the header row plus the rows


def test_overview_coverage_filter_bar_offers_the_all_option(
    fake_streamlit_connection,
) -> None:
    """The mockup's "همه": the no-filter option is the default and reads as such."""
    app = _overview_app()

    control = app.selectbox(key="overview_coverage_domain")
    assert control.value is None
    assert list(control.options) == [
        t("filter.all"),
        domain_label("gdp"),
        domain_label("inflation"),
    ]


def test_overview_coverage_density_control_offers_the_two_densities(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    control = app.segmented_control(key="overview_coverage_density")
    assert control.value == "comfortable"
    assert list(control.options) == [
        t("filter.density_comfortable"),
        t("filter.density_compact"),
    ]
    # One option per density the HTML table accepts, so the control's value can be
    # passed straight to `render_html_table` (pinned end-to-end below).
    assert len(control.options) == len(DENSITIES)


def test_overview_coverage_table_honours_the_compact_density(
    fake_streamlit_connection,
) -> None:
    app = _overview_app()

    app.segmented_control(key="overview_coverage_density").select("compact").run()

    assert not app.exception
    body = next(body for body in html_texts(app) if t("table.coverage_range") in body)
    assert '<table class="dt cov compact">' in body
