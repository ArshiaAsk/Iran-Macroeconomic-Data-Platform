"""AppTest smoke test for the Overview page (Task 16).

The Overview is the router's default page and uses ``st.page_link`` for its
per-domain links. ``st.page_link`` requires the target pages to be registered, so
the page is rendered through the entrypoint router rather than as a standalone
page file (``docs/phase-7.1/wave-0-spike.md``).
"""

from datetime import UTC, datetime

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.formatting import format_number
from dashboard.i18n import t
from dashboard.labels import source_label
from dashboard.page_view import freshness_display
from dashboard.repository import SERIES_KIND_BASE
from tests.unit.dashboard.app_smoke import (
    ORPHAN_INDICATOR,
    REPOSITORY_ROOT,
    FakeDashboardRepository,
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


def test_overview_staleness_verdict_is_rendered(fake_streamlit_connection) -> None:
    app = _overview_app()

    # The fake collection log's only run is years old, so the monthly-cadence
    # source is reported stale.
    freshness = next(
        frame.value for frame in app.dataframe if t("table.staleness") in frame.value.columns
    )
    assert freshness[t("table.staleness")].tolist() == [t("value.stale")]


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
