"""AppTest and composition tests for the Market (TSETMC) page.

The page owns the ``market`` domain. Its level series comes from the catalog and
its platform-computed series (``RET1D``, ``MA30`` and the ``.ME`` month-end
downsample) are discovered from Gold's ``record_metadata["derived_from"]``
through the repository -- never from a hardcoded id list and never from parsing
an indicator id. These tests pin the TSETMC semantics the plan calls out:
absent trading sessions stay absent (never zero), each derived series is charted
in its own labelled panel so a return or a moving average is never presented as
the index level, ``.ME`` is a month-end downsample, and the MA30 warm-up is not
reported as a data-quality defect.
"""

import pandas as pd

from dashboard.components.charts import build_time_series_chart
from dashboard.formatting import format_number
from dashboard.i18n import t
from dashboard.labels import indicator_label
from dashboard.navigation import GROUPS, PAGES
from dashboard.page_view import market_series_groups, market_series_label
from dashboard.repository import SERIES_KIND_BASE, SERIES_KIND_DERIVED
from tests.unit.dashboard.app_smoke import (
    MARKET_ABSENT_DATES,
    MARKET_DERIVED_IDS,
    MARKET_INDICATOR,
    MARKET_MA30_ID,
    MARKET_MA30_START,
    MARKET_ME_ID,
    MARKET_MONTH_ENDS,
    MARKET_NAME,
    MARKET_RET1D_ID,
    MARKET_SESSIONS,
    REPOSITORY_ROOT,
    FakeDashboardRepository,
    app_test,
    market_series,
)

MARKET_PAGE = "9_Market.py"
LEVEL_LABEL = indicator_label(MARKET_INDICATOR, MARKET_NAME)


def derived_label(indicator_id: str) -> str:
    """Panel label the page must render for a derived market series."""
    return indicator_label(indicator_id, MARKET_NAME, MARKET_INDICATOR)


def test_market_page_renders_a_labelled_panel_per_tsetmc_series(
    fake_streamlit_connection,
) -> None:
    app = app_test(MARKET_PAGE)
    app.run()

    assert not app.exception
    assert [title.value for title in app.title] == [t("page.market")]
    subheaders = [subheader.value for subheader in app.subheader]
    assert subheaders[0] == t("section.market_level")
    # RET1D, MA30 and .ME each get their own panel, attributed to their parent.
    assert derived_label(MARKET_RET1D_ID) in subheaders
    assert derived_label(MARKET_MA30_ID) in subheaders
    assert derived_label(MARKET_ME_ID) in subheaders
    assert subheaders.count(derived_label(MARKET_ME_ID)) == 1
    # One panel per series: the level plus every derived series, each its own
    # chart and therefore its own y-axis.
    assert len(app.get("plotly_chart")) == 1 + len(MARKET_DERIVED_IDS)


def test_market_page_states_the_tsetmc_semantics(fake_streamlit_connection) -> None:
    app = app_test(MARKET_PAGE)
    app.run()

    warnings = [warning.value for warning in app.warning]
    infos = [info.value for info in app.info]
    assert t("warn.tsetmc_derived_not_official") in warnings
    assert t("warn.tsetmc_trading_days_absent") in infos
    assert t("warn.tsetmc_ma30_warmup") in infos
    assert t("warn.tsetmc_month_end") in infos
    assert t("warn.tsetmc_deferred_metrics") in infos
    # The session expectation runs on the collected level series only, so the
    # MA30 warm-up (and the .ME downsample) cannot raise a gap warning.
    assert t("warn.missing_periods") not in warnings


def test_market_page_reports_the_observed_session_count(fake_streamlit_connection) -> None:
    app = app_test(MARKET_PAGE)
    app.run()

    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics[t("metric.market_sessions")] == format_number(len(MARKET_SESSIONS))


def test_market_page_is_registered_in_the_navigation_registry() -> None:
    specs = {spec.key: spec for spec in PAGES}
    market = specs["market"]

    assert market.path == "pages/9_Market.py"
    assert market.domains == ("market",)
    assert market.group in GROUPS
    assert market.is_default is False
    assert (REPOSITORY_ROOT / "dashboard" / market.path).is_file()
    # The nav label and the in-page title share one key so they cannot drift.
    assert t("nav.market") == t("page.market")


def test_market_domain_is_owned_by_exactly_one_page() -> None:
    assert [spec.key for spec in PAGES if "market" in spec.domains] == ["market"]


def test_market_page_leaves_every_other_page_ownership_unchanged() -> None:
    specs = {spec.key: spec for spec in PAGES}

    assert specs["inflation"].domains == ("inflation",)
    assert specs["gdp"].domains == ("gdp",)
    assert specs["trade_energy"].domains == ("trade", "energy")
    assert specs["welfare"].domains == ("welfare",)
    assert specs["fx_gold"].domains == ("fx", "gold")
    assert {spec.key for spec in PAGES if not spec.domains} == {
        "overview",
        "correlation",
        "catalog",
    }


def test_market_series_groups_split_level_derived_and_month_end_rows() -> None:
    level, derived, month_end = market_series_groups(market_series())

    assert set(level["indicator_id"]) == {MARKET_INDICATOR}
    assert set(derived["indicator_id"]) == {MARKET_RET1D_ID, MARKET_MA30_ID}
    assert set(month_end["indicator_id"]) == {MARKET_ME_ID}
    # The split is a partition: no row is dropped, duplicated or invented.
    assert len(level) + len(derived) + len(month_end) == len(market_series())


def test_market_series_groups_is_empty_safe() -> None:
    level, derived, month_end = market_series_groups(pd.DataFrame())

    assert level.empty
    assert derived.empty
    assert month_end.empty


def test_derived_market_rows_follow_the_task_7_contract() -> None:
    """The page's data contract, through the shared fake repository seam.

    The repository's own join/provenance behaviour is covered against a real
    session by ``tests/unit/dashboard/test_repository.py`` and
    ``tests/integration/test_dashboard_repository.py``; this test pins the shape
    the page relies on: derived rows are reachable only through metadata
    discovery and carry their parent's name and source.
    """
    repository = FakeDashboardRepository()
    derived_ids = repository.list_derived_ids([MARKET_INDICATOR])

    # Discovery is metadata-driven from Gold, never a hardcoded id list...
    assert set(derived_ids) == set(MARKET_DERIVED_IDS)
    assert repository.list_derived_ids([]) == []
    # ...and the derived series have no catalog row to be discovered from.
    assert not set(derived_ids) & set(repository.list_indicators()["indicator_id"])

    frame = repository.load_series([MARKET_INDICATOR, *derived_ids])
    ret1d = frame[frame["indicator_id"] == MARKET_RET1D_ID]
    assert set(ret1d["series_kind"]) == {SERIES_KIND_DERIVED}
    assert set(ret1d["derived_from"]) == {MARKET_INDICATOR}
    # Parent provenance reaches the derived row (name, source and source url).
    assert set(ret1d["name"]) == {MARKET_NAME}
    assert set(ret1d["source_name"]) == {"tsetmc"}
    assert not ret1d["has_catalog_metadata"].any()
    level = frame[frame["indicator_id"] == MARKET_INDICATOR]
    assert set(level["series_kind"]) == {SERIES_KIND_BASE}
    assert level["has_catalog_metadata"].all()


def test_level_and_derived_series_are_charted_in_separate_panels() -> None:
    level, derived, month_end = market_series_groups(market_series())

    # The level chart cannot contain a derived series: RET1D/MA30 are never on
    # the index level's axis.
    assert set(level["indicator_id"]) == {MARKET_INDICATOR}
    assert not set(MARKET_DERIVED_IDS) & set(level["indicator_id"])
    assert len(build_time_series_chart(level).data) == 1

    for frame in (derived, month_end):
        assert not set(frame["indicator_id"]) & {MARKET_INDICATOR}

    # Each derived series is labelled with its parent *and* its derivation, so
    # no panel presents a rate or a moving average as the index level.
    labels = [
        market_series_label(frame)
        for frame in (
            derived[derived["indicator_id"] == MARKET_RET1D_ID],
            derived[derived["indicator_id"] == MARKET_MA30_ID],
            month_end,
        )
    ]
    assert labels == [
        derived_label(MARKET_RET1D_ID),
        derived_label(MARKET_MA30_ID),
        derived_label(MARKET_ME_ID),
    ]
    for label in labels:
        assert label != LEVEL_LABEL
        assert label.startswith(LEVEL_LABEL)
    assert len(set(labels)) == len(labels)


def test_month_end_downsample_is_presented_as_month_end_data() -> None:
    _, derived, month_end = market_series_groups(market_series())

    assert set(month_end["indicator_id"]) == {MARKET_ME_ID}
    assert set(month_end["frequency"]) == {"monthly"}
    assert month_end["timestamp"].isin(MARKET_MONTH_ENDS).all()
    assert month_end["timestamp"].dt.is_month_end.all()
    # A downsample, not a continuous monthly series: far fewer rows than the
    # daily series it samples.
    assert len(month_end) < len(derived)
    assert len(month_end) < len(MARKET_SESSIONS)


def test_absent_trading_sessions_are_not_filled_with_zeros() -> None:
    level, _, _ = market_series_groups(market_series())

    # Exactly one row per session the source reported: no synthetic calendar row.
    assert len(level) == len(MARKET_SESSIONS)
    assert level["timestamp"].tolist() == list(MARKET_SESSIONS)
    assert not level["timestamp"].isin(MARKET_ABSENT_DATES).any()
    # An absent session is absent -- never carried as a zero value.
    assert (level["value"] == 0).sum() == 0
    assert level["value"].notna().all()


def test_ma30_warmup_prefix_is_not_a_missing_data_defect() -> None:
    level, derived, _ = market_series_groups(market_series())
    ma30 = derived[derived["indicator_id"] == MARKET_MA30_ID]

    # MA30 starts after the level (the fixture's shortened warm-up) and holds
    # only real sessions: its prefix is a property of the derivation.
    assert ma30["timestamp"].min() == MARKET_MA30_START
    assert ma30["timestamp"].min() > level["timestamp"].min()
    assert set(ma30["timestamp"]).issubset(set(level["timestamp"]))
    assert len(ma30) == len(MARKET_SESSIONS) - 3
