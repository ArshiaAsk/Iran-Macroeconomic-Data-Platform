"""AppTest smoke test for the Overview page (Task 16).

The Overview is the router's default page and uses ``st.page_link`` for its
per-domain links. ``st.page_link`` requires the target pages to be registered, so
the page is rendered through the entrypoint router rather than as a standalone
page file (``docs/phase-7.1/wave-0-spike.md``).
"""

from datetime import UTC, datetime

import pandas as pd
from streamlit.testing.v1 import AppTest

from dashboard.i18n import t
from dashboard.labels import source_label
from dashboard.page_view import freshness_display
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT


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
