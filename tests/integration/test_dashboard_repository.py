"""Integration tests for dashboard queries against PostgreSQL."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from dashboard.components.exports import serialize_csv
from dashboard.components.quality import summarize_quality
from dashboard.i18n import t
from dashboard.labels import source_label
from dashboard.page_view import freshness_display
from dashboard.repository import SERIES_KIND_BASE, SERIES_KIND_DERIVED, DashboardRepository
from src.database.schema import (
    BronzeRaw,
    DataCollectionLog,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
)

pytestmark = pytest.mark.integration
pytest_plugins = ["tests.integration.test_database"]

DEFAULT_SOURCE_URL = "https://example.test/source"


@pytest.fixture()
def session(request: pytest.FixtureRequest) -> Generator[Session, None, None]:
    """Yield a rolled-back session using the existing integration database fixture."""
    connection = request.getfixturevalue("test_db")
    database_session = connection.SessionLocal()
    try:
        yield database_session
    finally:
        database_session.rollback()
        database_session.close()


def make_bronze(session: Session) -> BronzeRaw:
    """Insert the Bronze row the seeded Silver/Gold observations descend from."""
    bronze = BronzeRaw(source_name="test_source", source_type="api", raw_data={"rows": []})
    session.add(bronze)
    session.flush()
    return bronze


def seed_catalog(
    session: Session,
    indicator_id: str,
    *,
    name: str | None = None,
    domain: str = "gdp",
    frequency: str = "annual",
    unit: str = "index",
    source_name: str = "test_source",
    source_url: str | None = DEFAULT_SOURCE_URL,
    availability_start: datetime | None = None,
    availability_end: datetime | None = None,
) -> None:
    """Insert one ``indicator_catalog`` row."""
    session.add(
        IndicatorCatalog(
            indicator_id=indicator_id,
            name=name or f"Catalog name for {indicator_id}",
            unit=unit,
            frequency=frequency,
            domain=domain,
            source_name=source_name,
            source_url=source_url,
            availability_start=availability_start,
            availability_end=availability_end,
        )
    )
    session.flush()


def seed_gold_series(
    session: Session,
    indicator_id: str,
    bronze: BronzeRaw,
    *,
    years: tuple[int, ...] = (2020, 2021, 2022),
    domain: str = "gdp",
    frequency: str = "annual",
    unit: str = "index",
    source_name: str = "test_source",
    metadata: dict[str, Any] | None = None,
    chain_linked_year: int | None = None,
    chain_linking_confidence: float = 0.9,
) -> None:
    """Insert one Silver + Gold observation per year, without any catalog row."""
    for year in years:
        silver = SilverCleaned(
            indicator_id=indicator_id,
            timestamp=datetime(year, 12, 31, tzinfo=UTC),
            value=float(year),
            unit=unit,
            frequency=frequency,
            source_name=source_name,
            bronze_id=bronze.id,
        )
        session.add(silver)
        session.flush()
        is_linked = year == chain_linked_year
        session.add(
            GoldAnalytical(
                indicator_id=indicator_id,
                timestamp=silver.timestamp,
                value=float(year),
                original_value=float(year) - 1 if is_linked else None,
                is_chain_linked=is_linked,
                chain_linking_confidence=chain_linking_confidence if is_linked else None,
                unit=unit,
                frequency=frequency,
                domain=domain,
                silver_id=silver.id,
                record_metadata=metadata,
            )
        )
    session.flush()


def unique_id(prefix: str) -> str:
    """Return an indicator id that cannot collide across tests."""
    return f"{prefix}_{uuid4().hex[:8]}"


def seed_dashboard_rows(session: Session) -> list[str]:
    suffix = uuid4().hex[:8]
    indicator_ids = [f"TEST_GDP_{suffix}", f"TEST_CPI_{suffix}"]
    bronze = make_bronze(session)
    for position, indicator_id in enumerate(indicator_ids):
        domain = "gdp" if position == 0 else "inflation"
        seed_catalog(
            session,
            indicator_id,
            name=f"Test indicator {position}",
            domain=domain,
            availability_start=datetime(2020, 1, 1, tzinfo=UTC),
            availability_end=datetime(2022, 1, 1, tzinfo=UTC),
        )
        seed_gold_series(
            session,
            indicator_id,
            bronze,
            domain=domain,
            chain_linked_year=2021,
        )
    session.add(
        DataCollectionLog(
            source_name="test_source",
            collection_timestamp=datetime(2023, 1, 1, tzinfo=UTC),
            status="success",
            records_collected=6,
        )
    )
    session.flush()
    return indicator_ids


def test_repository_filters_catalog_series_coverage_and_freshness(session: Session) -> None:
    indicator_ids = seed_dashboard_rows(session)
    repository = DashboardRepository(session)

    catalog = repository.list_indicators(
        search="Test indicator",
        domains=["gdp", "inflation"],
        frequencies=["annual"],
        sources=["test_source"],
    )
    series = repository.load_series(
        indicator_ids,
        datetime(2021, 1, 1, tzinfo=UTC),
        datetime(2021, 12, 31, tzinfo=UTC),
    )
    coverage = repository.coverage_summary(indicator_ids)
    freshness = repository.source_freshness()

    assert set(catalog["indicator_id"]) == set(indicator_ids)
    assert len(series) == 2
    assert series["timestamp"].dt.tz is not None
    assert set(coverage["observation_count"]) == {3}
    assert "test_source" in set(freshness["source_name"])


def test_selected_export_contains_exact_database_rows(session: Session) -> None:
    indicator_ids = seed_dashboard_rows(session)
    repository = DashboardRepository(session)
    series = repository.load_series(indicator_ids)
    content = serialize_csv(series).decode("utf-8")

    assert content.count("\n") == len(series) + 1
    # The chain-linking confidence column survives the export; its header is the
    # localized one (Task 21), so the raw English column name is not expected.
    assert t("table.chain_linking_confidence") in content


def test_load_series_returns_catalog_backed_row_unchanged(session: Session) -> None:
    indicator_id = unique_id("TEST_LEVEL")
    bronze = make_bronze(session)
    seed_catalog(
        session,
        indicator_id,
        name="Catalog level name",
        domain="inflation",
        source_name="world_bank",
        source_url="https://api.worldbank.test/level",
    )
    seed_gold_series(session, indicator_id, bronze, domain="inflation")

    frame = DashboardRepository(session).load_series([indicator_id])

    assert len(frame) == 3
    assert frame["name"].unique().tolist() == ["Catalog level name"]
    assert frame["source_name"].unique().tolist() == ["world_bank"]
    assert frame["source_url"].unique().tolist() == ["https://api.worldbank.test/level"]
    assert frame["domain"].unique().tolist() == ["inflation"]
    assert frame["series_kind"].unique().tolist() == [SERIES_KIND_BASE]
    assert frame["derived_from"].isna().all()
    assert frame["has_catalog_metadata"].all()


def test_load_series_resolves_parent_provenance_for_derived_series(session: Session) -> None:
    parent_id = unique_id("TEST_PARENT")
    derived_id = f"{parent_id}.YOY"
    bronze = make_bronze(session)
    seed_catalog(
        session,
        parent_id,
        name="Parent level name",
        source_name="world_bank",
        source_url="https://api.worldbank.test/parent",
    )
    seed_gold_series(session, parent_id, bronze)
    seed_gold_series(
        session,
        derived_id,
        bronze,
        metadata={"derived_from": parent_id, "method": "yoy_growth"},
    )

    frame = DashboardRepository(session).load_series([derived_id])

    assert frame["indicator_id"].unique().tolist() == [derived_id]
    assert frame["series_kind"].unique().tolist() == [SERIES_KIND_DERIVED]
    assert frame["derived_from"].unique().tolist() == [parent_id]
    assert frame["name"].unique().tolist() == ["Parent level name"]
    assert frame["source_name"].unique().tolist() == ["world_bank"]
    assert frame["source_url"].unique().tolist() == ["https://api.worldbank.test/parent"]
    assert not frame["has_catalog_metadata"].any()


def test_load_series_keeps_direct_catalog_provenance_for_derived_series(session: Session) -> None:
    parent_id = unique_id("TEST_PARENT")
    derived_id = f"{parent_id}.MA30"
    bronze = make_bronze(session)
    seed_catalog(session, parent_id, name="Parent level name", source_name="world_bank")
    seed_catalog(session, derived_id, name="Derived own name", source_name="dashboard_derived")
    seed_gold_series(session, derived_id, bronze, metadata={"derived_from": parent_id})

    frame = DashboardRepository(session).load_series([derived_id])

    assert frame["series_kind"].unique().tolist() == [SERIES_KIND_DERIVED]
    assert frame["name"].unique().tolist() == ["Derived own name"]
    assert frame["source_name"].unique().tolist() == ["dashboard_derived"]
    assert frame["has_catalog_metadata"].all()


def test_load_series_inherits_tsetmc_provenance_for_a_derived_series(session: Session) -> None:
    """The TSETMC parent source reaches its derived row, driving the session rule."""
    parent_id = unique_id("TSETMC.TEDPIX")
    derived_id = f"{parent_id}.RET1D"
    bronze = make_bronze(session)
    seed_catalog(
        session,
        parent_id,
        name="Tehran Stock Exchange total index (TEDPIX)",
        domain="market",
        frequency="daily",
        source_name="tsetmc",
        source_url="http://cdn.tsetmc.com/api",
    )
    seed_gold_series(session, parent_id, bronze, domain="market", frequency="daily")
    seed_gold_series(
        session,
        derived_id,
        bronze,
        domain="market",
        frequency="daily",
        metadata={"derived_from": parent_id, "method": "daily_return"},
    )

    frame = DashboardRepository(session).load_series([derived_id])
    row = frame.iloc[0]
    assert row["series_kind"] == SERIES_KIND_DERIVED
    assert row["derived_from"] == parent_id
    assert row["source_name"] == "tsetmc"
    assert bool(row["has_catalog_metadata"]) is False

    quality = summarize_quality(
        frame,
        frame["timestamp"].min().to_pydatetime(),
        frame["timestamp"].max().to_pydatetime(),
    )
    assert bool(quality.loc[0, "expected_is_estimated"]) is True


def test_load_series_flags_derived_series_with_unresolvable_parent(session: Session) -> None:
    derived_id = unique_id("TEST_ORPHAN_DERIVED")
    bronze = make_bronze(session)
    seed_gold_series(
        session,
        derived_id,
        bronze,
        metadata={"derived_from": f"MISSING_PARENT_{uuid4().hex[:8]}"},
    )

    frame = DashboardRepository(session).load_series([derived_id])

    assert frame["indicator_id"].unique().tolist() == [derived_id]
    assert frame["series_kind"].unique().tolist() == [SERIES_KIND_DERIVED]
    assert frame["name"].isna().all()
    assert frame["source_name"].isna().all()
    assert frame["source_url"].isna().all()
    assert not frame["has_catalog_metadata"].any()


@pytest.mark.parametrize(
    "metadata",
    [None, {}, {"method": "yoy_growth"}, {"derived_from": ""}, {"derived_from": 1405}],
    ids=["none", "empty", "absent", "blank-string", "number"],
)
def test_load_series_treats_unusable_metadata_as_base(
    session: Session, metadata: dict[str, Any] | None
) -> None:
    indicator_id = unique_id("TEST_ODD_METADATA")
    bronze = make_bronze(session)
    seed_gold_series(session, indicator_id, bronze, metadata=metadata)

    frame = DashboardRepository(session).load_series([indicator_id])

    assert len(frame) == 3
    assert frame["series_kind"].unique().tolist() == [SERIES_KIND_BASE]
    assert frame["derived_from"].isna().all()
    assert not frame["has_catalog_metadata"].any()


def test_load_series_discovers_a_new_derived_series(session: Session) -> None:
    parent_id = unique_id("TEST_FUTURE_PARENT")
    derived_id = f"{parent_id}.ROLLINGCORR"
    bronze = make_bronze(session)
    seed_catalog(session, parent_id, name="Future parent", source_name="hbsir")
    seed_gold_series(session, parent_id, bronze)
    seed_gold_series(
        session,
        derived_id,
        bronze,
        metadata={"derived_from": parent_id, "method": "rolling_correlation"},
    )
    repository = DashboardRepository(session)

    frame = repository.load_series([derived_id])

    assert frame["indicator_id"].unique().tolist() == [derived_id]
    assert frame["name"].unique().tolist() == ["Future parent"]
    assert repository.list_derived_ids([parent_id]) == [derived_id]


def test_list_derived_ids_returns_only_children_of_requested_parents(session: Session) -> None:
    first_parent = unique_id("TEST_PARENT")
    second_parent = unique_id("TEST_PARENT")
    first_child = f"{first_parent}.RET1D"
    second_child = f"{second_parent}.MA30"
    bronze = make_bronze(session)
    for parent in (first_parent, second_parent):
        seed_catalog(session, parent)
        seed_gold_series(session, parent, bronze, years=(2020,))
    for child, parent in ((first_child, first_parent), (second_child, second_parent)):
        seed_gold_series(
            session,
            child,
            bronze,
            years=(2020,),
            metadata={"derived_from": parent, "method": "derived"},
        )
    repository = DashboardRepository(session)

    assert repository.list_derived_ids([first_parent]) == [first_child]
    assert repository.list_derived_ids([first_parent, second_parent]) == sorted(
        [first_child, second_child]
    )
    assert repository.list_derived_ids([unique_id("TEST_NO_CHILDREN")]) == []


def test_load_series_keeps_indicator_and_date_filtering_for_derived_rows(session: Session) -> None:
    parent_id = unique_id("TEST_FILTER_PARENT")
    other_id = unique_id("TEST_FILTER_OTHER")
    derived_id = f"{parent_id}.YOY"
    bronze = make_bronze(session)
    seed_catalog(session, parent_id, name="Filter parent")
    seed_catalog(session, other_id, name="Filter other")
    seed_gold_series(session, parent_id, bronze, chain_linked_year=2021)
    seed_gold_series(session, other_id, bronze, domain="inflation")
    seed_gold_series(session, derived_id, bronze, metadata={"derived_from": parent_id})
    repository = DashboardRepository(session)

    selected = repository.load_series(
        [derived_id, parent_id],
        datetime(2021, 1, 1, tzinfo=UTC),
        datetime(2021, 12, 31, tzinfo=UTC),
    )
    only_parent = repository.load_series([parent_id])
    unmatched = repository.load_series([other_id, derived_id])
    unfiltered_catalog = repository.list_indicators(sources=["test_source"])

    assert selected["indicator_id"].tolist() == [derived_id, parent_id]
    assert selected["timestamp"].dt.year.unique().tolist() == [2021]
    assert selected.loc[selected["indicator_id"] == parent_id, "is_chain_linked"].all()
    assert not selected.loc[selected["indicator_id"] == derived_id, "is_chain_linked"].any()
    assert only_parent["indicator_id"].unique().tolist() == [parent_id]
    assert unmatched["indicator_id"].unique().tolist() == [other_id, derived_id]
    assert {parent_id, other_id} <= set(unfiltered_catalog["indicator_id"])
    assert derived_id not in set(unfiltered_catalog["indicator_id"])


def test_load_series_ordering_and_coverage_summary_are_unchanged(session: Session) -> None:
    parent_id = unique_id("TEST_ORDER_PARENT")
    derived_id = f"{parent_id}.MA30"
    bronze = make_bronze(session)
    seed_catalog(session, parent_id, name="Order parent")
    seed_gold_series(session, parent_id, bronze, chain_linked_year=2021)
    seed_gold_series(session, derived_id, bronze, metadata={"derived_from": parent_id})
    repository = DashboardRepository(session)

    frame = repository.load_series([derived_id, parent_id])
    coverage = repository.coverage_summary([parent_id, derived_id])

    assert frame["indicator_id"].tolist() == [derived_id] * 3 + [parent_id] * 3
    assert frame["timestamp"].dt.year.tolist() == [2020, 2021, 2022] * 2
    indexed = coverage.set_index("indicator_id")
    assert indexed.loc[parent_id, "observation_count"] == 3
    assert indexed.loc[parent_id, "chain_linked_count"] == 1
    # Coverage stays catalog-driven: it describes the catalogued indicator, so a
    # derived id without a catalog row is not part of this contract.
    assert derived_id not in indexed.index


def test_series_inventory_reports_the_orphan_and_classifies_every_gold_series(
    session: Session,
) -> None:
    """The inventory flags a catalog-less Gold series instead of dropping it."""
    orphan_id = unique_id("TEST_ORPHAN_INVENTORY")
    cataloged_id = unique_id("TEST_CATALOGED_INVENTORY")
    derived_id = f"{cataloged_id}.YOY"
    bronze = make_bronze(session)
    seed_catalog(session, cataloged_id, name="Cataloged parent")
    seed_gold_series(session, cataloged_id, bronze, years=(2020,))
    seed_gold_series(
        session,
        derived_id,
        bronze,
        years=(2020,),
        metadata={"derived_from": cataloged_id},
    )
    # A genuine orphan: Gold rows, no catalog row, no parent.
    seed_gold_series(session, orphan_id, bronze, years=(2020,))

    inventory = DashboardRepository(session).series_inventory().set_index("indicator_id")

    assert {cataloged_id, derived_id, orphan_id} <= set(inventory.index)
    assert bool(inventory.loc[cataloged_id, "has_catalog_metadata"]) is True
    assert inventory.loc[cataloged_id, "series_kind"] == SERIES_KIND_BASE
    assert bool(inventory.loc[derived_id, "has_catalog_metadata"]) is False
    assert inventory.loc[derived_id, "series_kind"] == SERIES_KIND_DERIVED
    assert inventory.loc[derived_id, "derived_from"] == cataloged_id
    # The orphan is reported with null provenance, never given a guessed source.
    assert bool(inventory.loc[orphan_id, "has_catalog_metadata"]) is False
    assert inventory.loc[orphan_id, "series_kind"] == SERIES_KIND_BASE
    assert pd.isna(inventory.loc[orphan_id, "derived_from"])


def test_source_freshness_returns_the_latest_run_and_staleness_compares_cadence(
    session: Session,
) -> None:
    """Freshness picks the newest run per source; staleness compares its cadence."""
    # Far-future timestamps so the seeded run is unambiguously the latest for the
    # source regardless of any real collection log already in the database.
    older = datetime(2098, 1, 1, tzinfo=UTC)
    newest = datetime(2099, 1, 1, tzinfo=UTC)
    session.add_all(
        [
            DataCollectionLog(
                source_name="tgju",
                collection_timestamp=older,
                status="success",
                records_collected=1,
            ),
            DataCollectionLog(
                source_name="tgju",
                collection_timestamp=newest,
                status="success",
                records_collected=2,
            ),
        ]
    )
    unknown_source = unique_id("TEST_UNKNOWN_SOURCE")
    session.add(
        DataCollectionLog(
            source_name=unknown_source,
            collection_timestamp=newest,
            status="success",
            records_collected=3,
        )
    )
    session.flush()

    freshness = DashboardRepository(session).source_freshness()
    latest = freshness[freshness["source_name"] == "tgju"]

    # Exactly one row per source, and it is the newest run.
    assert latest["collection_timestamp"].tolist() == [newest]
    assert int(latest["records_collected"].iloc[0]) == 2

    seeded = freshness[freshness["source_name"].isin(["tgju", unknown_source])]
    stale = freshness_display(seeded, now=datetime(2099, 1, 5, tzinfo=UTC))
    verdicts = dict(zip(stale[t("table.source_name")], stale[t("table.staleness")], strict=True))
    # `tgju` is a daily source: four days old is stale.
    assert verdicts[source_label("tgju")] == t("value.stale")
    # An unknown source has no expected cadence, so no staleness claim is made.
    assert verdicts[unknown_source] == t("value.unknown")

    fresh = freshness_display(seeded, now=datetime(2099, 1, 1, tzinfo=UTC))
    fresh_verdicts = dict(
        zip(fresh[t("table.source_name")], fresh[t("table.staleness")], strict=True)
    )
    assert fresh_verdicts[source_label("tgju")] == t("value.fresh")
