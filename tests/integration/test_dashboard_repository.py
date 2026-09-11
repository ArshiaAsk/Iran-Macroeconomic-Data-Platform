"""Integration tests for dashboard queries against PostgreSQL."""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from dashboard.components.exports import serialize_csv
from dashboard.repository import DashboardRepository
from src.database.schema import (
    BronzeRaw,
    DataCollectionLog,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
)

pytestmark = pytest.mark.integration
pytest_plugins = ["tests.integration.test_database"]


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


def seed_dashboard_rows(session: Session) -> list[str]:
    suffix = uuid4().hex[:8]
    indicator_ids = [f"TEST_GDP_{suffix}", f"TEST_CPI_{suffix}"]
    bronze = BronzeRaw(source_name="test_source", source_type="api", raw_data={"rows": []})
    session.add(bronze)
    session.flush()
    for position, indicator_id in enumerate(indicator_ids):
        catalog = IndicatorCatalog(
            indicator_id=indicator_id,
            name=f"Test indicator {position}",
            unit="index",
            frequency="annual",
            domain="gdp" if position == 0 else "inflation",
            source_name="test_source",
            availability_start=datetime(2020, 1, 1, tzinfo=UTC),
            availability_end=datetime(2022, 1, 1, tzinfo=UTC),
        )
        session.add(catalog)
        for year in range(2020, 2023):
            silver = SilverCleaned(
                indicator_id=indicator_id,
                timestamp=datetime(year, 12, 31, tzinfo=UTC),
                value=float(year),
                unit="index",
                frequency="annual",
                source_name="test_source",
                bronze_id=bronze.id,
            )
            session.add(silver)
            session.flush()
            session.add(
                GoldAnalytical(
                    indicator_id=indicator_id,
                    timestamp=silver.timestamp,
                    value=float(year),
                    original_value=float(year) - 1 if year == 2021 else None,
                    is_chain_linked=year == 2021,
                    chain_linking_confidence=0.9 if year == 2021 else None,
                    unit="index",
                    frequency="annual",
                    domain="gdp" if position == 0 else "inflation",
                    silver_id=silver.id,
                )
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
    assert "chain_linking_confidence" in content
