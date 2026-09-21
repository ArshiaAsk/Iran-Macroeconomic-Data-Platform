"""Derived-series discovery and the shared "Include derived" toggle (Task 14).

Derivedness comes only from the ETL-written ``record_metadata["derived_from"]``
as read by the Task 7 repository seam (``list_derived_ids`` and its cached
wrapper). The shared helper below is the only discovery path used by the domain
pages (Inflation, GDP, Trade & Energy, FX & Gold, Welfare & Survey, Labor) and by
the Market page, so these tests pin that it never parses an indicator id, never
requires a catalog row and never appends an already-selected id.
"""

import re

import pandas as pd
import pytest

from dashboard.components.charts import build_time_series_chart
from dashboard.i18n import t
from dashboard.labels import derived_label, domain_label, frequency_label, indicator_label
from dashboard.page_view import derived_series_ids
from dashboard.repository import SERIES_KIND_DERIVED
from tests.unit.dashboard.app_smoke import (
    ENERGY_INDICATOR,
    INFLATION_DERIVED_ID,
    INFLATION_INDICATOR,
    LABOR_INDICATOR,
    MARKET_DERIVED_IDS,
    MARKET_INDICATOR,
    TRADE_DERIVED_ID,
    TRADE_INDICATOR,
    FakeDashboardRepository,
    app_test,
    html_texts,
)

#: One (parent, derived) pair per source shape the ETL namespaces in
#: ``src/etl/gold.py``. Discovery must return each of them unchanged.
SOURCE_SHAPES = (
    ("NY.GDP.MKTP.CD", "WB.NY.GDP.MKTP.CD.YOY"),
    ("LUR", "IMF.LUR.YOY"),
    ("EIA.IRN.CRUDE_PRODUCTION", "EIA.IRN.CRUDE_PRODUCTION.YOY"),
    ("SCI.CPI.URBAN", "SCI.CPI.URBAN.YOY"),
    ("TGJU.USD.FREE", "TGJU.USD.FREE.RET1D"),
    ("TSETMC.TEDPIX", "TSETMC.TEDPIX.ME"),
)

#: Every domain page that renders through ``render_domain_body``, with the widget
#: key of its shared derived toggle.
DOMAIN_PAGE_TOGGLES = (
    ("2_Inflation.py", "inflation_derived"),
    ("3_GDP_Economy.py", "gdp_economy_derived"),
    ("4_Trade_Welfare_Energy.py", "trade_energy_derived"),
    ("5_FX_Gold.py", "fx_gold_derived"),
    ("8_Welfare_Survey.py", "welfare_derived"),
    ("10_Labor.py", "labor_derived"),
)


class MetadataRepository:
    """Repository seam whose discovery is driven by Gold ``derived_from`` rows."""

    def __init__(self, rows: dict[str, str]) -> None:
        self._rows = rows  # derived id -> parent id

    def list_derived_ids(self, parent_ids: list[str]) -> list[str]:
        parents = set(parent_ids)
        return sorted(derived for derived, parent in self._rows.items() if parent in parents)


def _observations_frame(app) -> pd.DataFrame:
    """The loaded Gold observations table rendered by a domain page.

    The grid is localized (Task 20), so its headers are the Persian catalog keys.
    """
    return next(
        frame.value for frame in app.dataframe if t("table.timestamp") in frame.value.columns
    )


def _quality_indicator_ids(app) -> set[str]:
    """Indicator ids in the quality summary's RTL HTML table (Task 35).

    The summary is an HTML table now, so its id column is read off the markup
    (``<bdi class="ltr">…</bdi>``, the isolated LTR token) rather than from an
    ``app.dataframe`` (the Task 16 migration map).
    """
    markup = next(body for body in html_texts(app) if t("table.rows_returned") in body)
    return set(re.findall(r'<bdi class="ltr">([^<]+)</bdi>', markup))


def _loaded_indicator_ids(app) -> set[str]:
    frames = [frame.value for frame in app.dataframe if t("table.timestamp") in frame.value.columns]
    return {indicator for frame in frames for indicator in frame[t("table.indicator_id")]}


def test_derived_series_ids_read_gold_metadata_through_the_repository() -> None:
    repository = FakeDashboardRepository()

    assert derived_series_ids([MARKET_INDICATOR], repository) == sorted(MARKET_DERIVED_IDS)


def test_derived_series_ids_discover_a_catalog_less_series() -> None:
    repository = FakeDashboardRepository()

    # The derived id has no catalog row, yet discovery is metadata-driven.
    assert INFLATION_DERIVED_ID not in set(repository.list_indicators()["indicator_id"])
    assert derived_series_ids([INFLATION_INDICATOR], repository) == [INFLATION_DERIVED_ID]
    assert TRADE_DERIVED_ID not in set(repository.list_indicators()["indicator_id"])
    assert derived_series_ids([TRADE_INDICATOR], repository) == [TRADE_DERIVED_ID]


def test_derived_series_ids_return_nothing_when_no_derived_rows_exist() -> None:
    repository = FakeDashboardRepository()

    # A monthly EIA level has no derived Gold row today.
    assert derived_series_ids([ENERGY_INDICATOR], repository) == []
    # SCI publishes a single quarter, so its domain cannot have a derived row.
    assert derived_series_ids([LABOR_INDICATOR], repository) == []
    # No parents means no query and no result.
    assert derived_series_ids([], repository) == []


def test_derived_series_ids_never_return_an_already_selected_id() -> None:
    repository = FakeDashboardRepository()

    assert (
        derived_series_ids([INFLATION_INDICATOR], repository, exclude=[INFLATION_DERIVED_ID]) == []
    )
    # The parent remains selectable even when its child is excluded.
    assert derived_series_ids([INFLATION_INDICATOR], repository) == [INFLATION_DERIVED_ID]


def test_derived_series_ids_deduplicate_the_parent_selection() -> None:
    repository = FakeDashboardRepository()

    assert derived_series_ids([INFLATION_INDICATOR, INFLATION_INDICATOR], repository) == [
        INFLATION_DERIVED_ID
    ]


@pytest.mark.parametrize(("parent_id", "derived_id"), SOURCE_SHAPES)
def test_derived_series_ids_are_independent_of_the_id_shape(
    parent_id: str,
    derived_id: str,
) -> None:
    repository = MetadataRepository({derived_id: parent_id})

    assert derived_series_ids([parent_id], repository) == [derived_id]


def test_derived_series_ids_return_an_orphan_derived_series() -> None:
    """A derived row whose parent catalog row is missing is still discovered."""
    repository = FakeDashboardRepository()
    orphan_id = "ORPHAN.LEVEL.YOY"
    # A copy keeps the fake frame's dtypes, so the orphan differs only in the
    # metadata-driven fields under test.
    orphan = repository.series.iloc[[0]].copy()
    orphan["indicator_id"] = orphan_id
    orphan["name"] = None
    orphan["source_name"] = None
    orphan["source_url"] = None
    orphan["record_metadata"] = {"derived_from": "MISSING.PARENT"}
    orphan["series_kind"] = SERIES_KIND_DERIVED
    orphan["derived_from"] = "MISSING.PARENT"
    orphan["has_catalog_metadata"] = False
    repository.series = pd.concat([repository.series, orphan], ignore_index=True)

    assert derived_series_ids(["MISSING.PARENT"], repository) == [orphan_id]
    # The orphan keeps null provenance: it is returned, flagged, never guessed.
    frame = repository.load_series([orphan_id])
    assert frame["has_catalog_metadata"].eq(False).all()
    assert frame["name"].isna().all()
    assert frame["source_name"].isna().all()


def test_derived_rows_are_labelled_with_the_parent_and_derivation() -> None:
    frame = pd.DataFrame(
        [
            {
                "indicator_id": INFLATION_INDICATOR,
                "name": "Inflation",
                "timestamp": pd.Timestamp("2021-01-01", tz="UTC"),
                "value": 2.0,
                "unit": "%",
                "derived_from": None,
            },
            {
                "indicator_id": INFLATION_DERIVED_ID,
                "name": "Inflation",
                "timestamp": pd.Timestamp("2021-01-01", tz="UTC"),
                "value": 100.0,
                "unit": "annual %",
                "derived_from": INFLATION_INDICATOR,
            },
        ]
    )

    names = {trace.name for trace in build_time_series_chart(frame).data}

    suffix = derived_label("YOY")
    assert len(names) == 2
    # The derived trace is named after its parent *and* the derivation fragment,
    # never after the raw derived id.
    assert any(name.endswith(f"{suffix} (annual %)") for name in names)
    assert any(name.endswith("(%)") and suffix not in name for name in names)
    assert not any(INFLATION_DERIVED_ID in name for name in names)


def test_unknown_derived_suffix_is_ignored_not_invented() -> None:
    """A derived row with an unrecognised suffix falls back to its parent name."""
    frame = pd.DataFrame(
        [
            {
                "indicator_id": "WB.NEW.IND.NEWSUF",
                "name": "A new indicator",
                "timestamp": pd.Timestamp("2021-01-01", tz="UTC"),
                "value": 1.0,
                "unit": "index",
                "derived_from": "NEW.IND",
            }
        ]
    )

    names = {trace.name for trace in build_time_series_chart(frame).data}

    assert names == {"A new indicator (index)"}


def test_inflation_page_toggle_off_by_default_preserves_behavior(
    fake_streamlit_connection,
) -> None:
    app = app_test("2_Inflation.py")
    app.run()

    assert not app.exception
    assert [checkbox.value for checkbox in app.checkbox] == [False]
    assert _loaded_indicator_ids(app) == {INFLATION_INDICATOR}
    assert len(_quality_indicator_ids(app)) == 1


def test_inflation_page_toggle_on_includes_the_derived_series(
    fake_streamlit_connection,
) -> None:
    app = app_test("2_Inflation.py")
    app.run()
    app.checkbox(key="inflation_derived").check()
    app.run()

    assert not app.exception
    assert _loaded_indicator_ids(app) == {INFLATION_INDICATOR, INFLATION_DERIVED_ID}
    assert _quality_indicator_ids(app) == {
        INFLATION_INDICATOR,
        INFLATION_DERIVED_ID,
    }
    # The derived rows keep their parent provenance and their derived flag. The
    # grid is localized, so the classification is rendered through the label layer.
    derived = _observations_frame(app)
    derived = derived[derived[t("table.indicator_id")] == INFLATION_DERIVED_ID]
    assert not derived.empty
    assert set(derived[t("table.derived_from")]) == {indicator_label(INFLATION_INDICATOR)}
    assert set(derived[t("table.series_kind")]) == {t("value.derived")}
    assert set(derived[t("table.name")]) == {
        indicator_label(INFLATION_DERIVED_ID, "Inflation", INFLATION_INDICATOR)
    }
    # Unit, frequency and domain travel with the Gold row, as stored; the labels
    # are the Persian display names.
    assert set(derived[t("table.unit")]) == {"annual %"}
    assert set(derived[t("table.frequency")]) == {frequency_label("annual")}
    assert set(derived[t("table.domain")]) == {domain_label("inflation")}


@pytest.mark.parametrize(("page", "derived_key"), DOMAIN_PAGE_TOGGLES)
def test_every_domain_page_uses_the_shared_derived_control(
    page: str,
    derived_key: str,
    fake_streamlit_connection,
) -> None:
    app = app_test(page)
    app.run()

    assert not app.exception
    assert derived_key in {checkbox.key for checkbox in app.checkbox}


def test_market_page_includes_derived_through_the_same_helper(
    fake_streamlit_connection,
) -> None:
    app = app_test("9_Market.py")
    app.run()

    assert not app.exception
    # The Market page always exposes its derived series, so it has no toggle.
    assert not app.checkbox
    assert set(MARKET_DERIVED_IDS).issubset(_loaded_indicator_ids(app))
