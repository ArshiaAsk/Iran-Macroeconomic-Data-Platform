"""
Integration tests for the TGJU pipeline: Bronze -> Silver -> Gold.

These run against a real PostgreSQL + TimescaleDB instance (``make db-up``) and
are skipped when no server is reachable. The Playwright browser is *not* live:
the scraper is injected with a fake browser serving the captured fixtures in
``tests/fixtures/tgju``, so what is under test is the database half of the
pipeline -- the Silver upsert's conflict target, the Gold delete-and-reinsert
against a hypertable, the foreign keys between layers, daily-metrics derivation,
and the audit trail.

Isolation differs from ``test_database.py`` on purpose. ``run_tgju_pipeline``
opens and **commits** its own session per indicator, so a rolled-back test
session cannot undo it; each test truncates the layer tables, runs the pipeline,
and truncates again on the way out.

The ``live`` test at the bottom is the only one that touches the network. It is
skipped unless ``RUN_LIVE_API_TESTS=1`` is set, which keeps it out of ``make
test``, ``make test-integration``, and ``make test-all``:

    RUN_LIVE_API_TESTS=1 poetry run pytest -m live
"""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.connectors.tgju_scraper import (
    FREQUENCY_DAILY,
    SOURCE_NAME,
    SOURCE_TYPE,
    TgjuConfig,
    TgjuScraper,
)
from src.database.connection import DatabaseConnection, init_database
from src.etl.gold import load_gold_series
from src.etl.gold import TRANSFORMATION_TYPE as GOLD_TRANSFORMATION
from src.etl.lineage import LAYER_BRONZE, LAYER_GOLD, LAYER_SILVER, STATUS_SUCCESS
from src.etl.pipeline import PipelineSummary
from src.etl.silver import TRANSFORMATION_TYPE as SILVER_TRANSFORMATION
from src.utils.config import get_config
from src.utils.retry import RateLimiter, RetryPolicy

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")

# Three indicators from TGJU: USD, gold coin, 18K gold
USD_FREE = "TGJU.USD.FREE"
COIN_EMAMI = "TGJU.GOLD.EMAMI"
GOLD_18K = "TGJU.GOLD.18K"
INDICATORS = (USD_FREE, COIN_EMAMI, GOLD_18K)
DOMAINS = {USD_FREE: "fx", COIN_EMAMI: "gold", GOLD_18K: "gold"}

# TGJU only returns current price (1 row per scrape), not historical data.
# Historical series are built by daily scraping over time.
ROWS_PER_INDICATOR = 1
# For integration test: we don't derive RET1D/MA30 from single observations
# (those require time series). Gold layer should only publish the level.
GOLD_ROWS_PER_INDICATOR = ROWS_PER_INDICATOR  # Just the level, no derived metrics

# Truncated between tests
LAYER_TABLES = (
    "gold.gold_analytical",
    "silver.silver_cleaned",
    "bronze.bronze_raw",
    "metadata.chain_linking_log",
    "metadata.transformation_log",
    "metadata.data_collection_log",
    "metadata.indicator_catalog",
)

LIVE_FLAG = "RUN_LIVE_API_TESTS"
MIN_LIVE_OBSERVATIONS = 10
HTTP_OK = 200

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "tgju"
PATH_TO_FIXTURE = {
    "price_dollar_rl": "usd_normal.html",
    "sekee": "coin_emami_normal.html",
    "geram18": "gold_18k_normal.html",
}


class FakePage:
    """Mock Playwright Page that returns fixture HTML."""

    def __init__(self, html: str) -> None:
        self._html = html
        self._closed = False

    def set_default_timeout(self, timeout: float) -> None:
        """Mock set_default_timeout - does nothing in tests."""
        pass

    def goto(self, url: str, **kwargs: Any) -> Mock:
        """Simulate navigation."""
        response = Mock()
        response.ok = True
        response.status = HTTP_OK
        return response

    def content(self) -> str:
        """Return the fixture HTML."""
        return self._html

    def close(self) -> None:
        """Mark page as closed."""
        self._closed = True


class FakeBrowser:
    """Mock Playwright Browser that serves fixture HTML."""

    def __init__(self, fixtures: dict[str, str]) -> None:
        self.fixtures = fixtures
        self._closed = False
        self._page_index = 0

    def new_page(self, **kwargs: Any) -> FakePage:
        """Create a fake page; user_agent is ignored in tests."""
        # Return HTML for each path in order
        html_list = list(self.fixtures.values())
        html = html_list[self._page_index % len(html_list)]
        self._page_index += 1
        return FakePage(html)

    def close(self) -> None:
        """Mark browser as closed."""
        self._closed = True


def load_fixtures() -> dict[str, str]:
    """Load all TGJU HTML fixtures."""
    fixtures = {}
    for path, filename in PATH_TO_FIXTURE.items():
        fixture_path = FIXTURES_DIR / filename
        fixtures[path] = fixture_path.read_text(encoding="utf-8")
    return fixtures


def integration_db_url() -> str:
    """Build the URL of the dedicated test database."""
    db = get_config().database
    return f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}_test"


def _ensure_silver_conflict_target(connection: DatabaseConnection) -> None:
    """
    Guarantee ``uq_silver_indicator_timestamp`` exists on the test database.

    ``create_all_tables()`` is ``checkfirst``: it creates missing *tables* but
    never alters one that already exists, so a test database provisioned before
    migration ``90f0451997ef`` would still be missing the constraint that
    ``write_silver`` names as its ``ON CONFLICT`` target.
    """
    with connection.engine.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    ALTER TABLE silver.silver_cleaned
                        ADD CONSTRAINT uq_silver_indicator_timestamp
                        UNIQUE (indicator_id, timestamp);
                EXCEPTION
                    WHEN duplicate_table THEN NULL;
                END $$;
                """
            )
        )


def truncate_layers(connection: DatabaseConnection) -> None:
    """Empty every table the pipeline writes, chunks included."""
    with connection.engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(LAYER_TABLES)} CASCADE"))


def build_scraper_with_fixtures() -> TgjuScraper:
    """
    Build a TgjuScraper with fake browser serving fixtures.

    Retries and throttling are neutered so a fixture-served run costs nothing in
    wall-clock time.
    """
    fixtures = load_fixtures()
    fake_browser = FakeBrowser(fixtures)

    return TgjuScraper(
        config=TgjuConfig(paths=tuple(PATH_TO_FIXTURE.keys())),
        browser=fake_browser,  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


def run_pipeline() -> PipelineSummary:
    """
    Run the real pipeline over captured HTML: no network, real database.
    """
    from src.connectors.tgju_scraper import run_tgju_pipeline

    connector = build_scraper_with_fixtures()
    return run_tgju_pipeline(connector=connector)


def count(session: Session, table: str, where: str = "TRUE", **params: object) -> int:
    """Row count for one table under an optional predicate."""
    statement = text(f"SELECT count(*) FROM {table} WHERE {where}")
    return int(session.execute(statement, params).scalar_one())


def scalars(session: Session, statement: str, **params: object) -> list[object]:
    """First column of every row returned by ``statement``."""
    return list(session.execute(text(statement), params).scalars().all())


@pytest.fixture(scope="session")
def pipeline_db() -> Generator[DatabaseConnection, None, None]:
    """Provision the test database and point the pipeline's global handle at it."""
    config = get_config().database
    admin_engine = create_engine(config.url, isolation_level="AUTOCOMMIT")
    test_db_name = f"{config.name}_test"

    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL not reachable at {config.host}:{config.port} ({exc})")
    finally:
        admin_engine.dispose()

    # TimescaleDB + layer schemas mirror scripts/init-db.sql.
    setup_engine = create_engine(integration_db_url(), isolation_level="AUTOCOMMIT")
    with setup_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        for schema in SCHEMAS:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    setup_engine.dispose()

    connection = DatabaseConnection(integration_db_url())
    connection.create_all_tables()
    _ensure_silver_conflict_target(connection)
    connection.create_hypertables()

    # The pipeline resolves its session factory through get_db(); without this it
    # would write to the development database.
    init_database(integration_db_url())

    yield connection

    connection.close()


@pytest.fixture()
def published(pipeline_db: DatabaseConnection) -> Generator[PipelineSummary, None, None]:
    """A committed pipeline run over all instruments, cleaned up afterwards."""
    truncate_layers(pipeline_db)
    try:
        yield run_pipeline()
    finally:
        truncate_layers(pipeline_db)


@pytest.fixture()
def reader(pipeline_db: DatabaseConnection) -> Generator[Session, None, None]:
    """A read-only session over the committed run; never commits anything."""
    session = pipeline_db.SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ------------------------------------------------------------------- the run


def test_pipeline_reports_every_indicator_collected(published: PipelineSummary) -> None:
    """All three indicators land completely, so the run exits clean."""
    assert len([outcome.indicator_id for outcome in published.succeeded]) == len(INDICATORS)
    assert published.failed == []
    assert published.exit_code == 0
    # TGJU returns 1 observation per scrape (current price only)
    assert published.rows_written_silver == ROWS_PER_INDICATOR * len(INDICATORS)
    # Each indicator: just the level (no derived metrics from single observations)
    assert published.rows_written_gold == GOLD_ROWS_PER_INDICATOR * len(INDICATORS)
    assert all(outcome.records_failed == 0 for outcome in published.outcomes)



# ---------------------------------------------------------------- bronze layer


def test_bronze_stores_one_html_envelope_per_indicator(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Bronze keeps exactly what the scraper returned, once per fetch."""
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS)

    rows = reader.execute(
        text(
            "SELECT source_name, source_type, request_url, "
            "       length(raw_data::text) > 1000 AS has_html, "
            "       metadata ->> 'indicator_id' AS indicator_id "
            "FROM bronze.bronze_raw ORDER BY metadata ->> 'indicator_id'"
        )
    ).all()

    assert len(rows) == len(INDICATORS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.source_type == SOURCE_TYPE
        assert row.request_url.startswith("https://")
        assert row.has_html is True

    # Bronze ids reported by the run are the rows that actually exist.
    stored = set(scalars(reader, "SELECT id FROM bronze.bronze_raw"))
    assert {outcome.bronze_id for outcome in published.outcomes} == stored


def test_collection_log_records_each_fetch(published: PipelineSummary, reader: Session) -> None:
    """Every Bronze write leaves a collection-log row behind."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT source_name, status, records_collected "
            "FROM metadata.data_collection_log ORDER BY records_collected"
        )
    ).all()

    assert len(rows) == len(INDICATORS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.status == STATUS_SUCCESS
        assert row.records_collected == ROWS_PER_INDICATOR



# ---------------------------------------------------------------- silver layer


def test_silver_counts_match_the_reported_writes(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Each indicator's parsed observation is stored, one row per scrape."""
    for outcome in published.outcomes:
        stored = count(
            reader,
            "silver.silver_cleaned",
            "indicator_id = :indicator_id",
            indicator_id=outcome.indicator_id,
        )
        assert stored == outcome.rows_written_silver == ROWS_PER_INDICATOR

    assert set(scalars(reader, "SELECT DISTINCT frequency FROM silver.silver_cleaned")) == {
        FREQUENCY_DAILY
    }


def test_silver_units_come_from_discovery(published: PipelineSummary, reader: Session) -> None:
    """The unit stamped on every observation is the one the catalog holds."""
    assert published.exit_code == 0

    mismatched = count(
        reader,
        "silver.silver_cleaned s JOIN metadata.indicator_catalog c "
        "ON c.indicator_id = s.indicator_id",
        "s.unit IS DISTINCT FROM c.unit",
    )

    assert mismatched == 0
    assert None not in scalars(reader, "SELECT DISTINCT unit FROM silver.silver_cleaned")


def test_silver_rows_resolve_to_their_bronze_envelope(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Every cleaned observation can be traced back to the HTML it came from."""
    assert published.exit_code == 0

    orphans = count(
        reader,
        "silver.silver_cleaned s LEFT JOIN bronze.bronze_raw b ON b.id = s.bronze_id",
        "b.id IS NULL",
    )

    assert orphans == 0



# ------------------------------------------------------------------ gold layer


def test_gold_publishes_levels_only(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Each indicator yields its level; no derived metrics from single observations."""
    assert published.exit_code == 0

    counts = dict(
        reader.execute(
            text("SELECT indicator_id, count(*) FROM gold.gold_analytical GROUP BY 1")
        ).all()
    )

    expected = {}
    for indicator_id in INDICATORS:
        expected[indicator_id] = ROWS_PER_INDICATOR

    assert counts == expected

    # No derived metrics (RET1D, MA30) from single observations
    assert count(reader, "gold.gold_analytical", "indicator_id LIKE '%.RET1D'") == 0
    assert count(reader, "gold.gold_analytical", "indicator_id LIKE '%.MA30'") == 0


def test_gold_rows_carry_the_discovered_domain(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Discovery's domain reaches the analytical layer."""
    assert published.exit_code == 0

    for indicator_id, domain in DOMAINS.items():
        stored = set(
            scalars(
                reader,
                "SELECT DISTINCT domain FROM gold.gold_analytical "
                "WHERE indicator_id = :level",
                level=indicator_id,
            )
        )
        assert stored == {domain}


def test_gold_rows_resolve_to_their_silver_observation(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Lineage is unbroken: every published row points at a Silver observation."""
    assert published.exit_code == 0

    orphans = count(
        reader,
        "gold.gold_analytical g LEFT JOIN silver.silver_cleaned s ON s.id = g.silver_id",
        "s.id IS NULL",
    )

    assert orphans == 0


def test_gold_rows_live_in_the_timescale_hypertable(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Published rows are stored as hypertable chunks, not in a plain table."""
    assert published.exit_code == 0

    chunks = count(
        reader,
        "timescaledb_information.chunks",
        "hypertable_schema = 'gold' AND hypertable_name = 'gold_analytical'",
    )

    assert chunks >= 1
    # Reading through the hypertable returns everything the run reported.
    assert count(reader, "gold.gold_analytical") == published.rows_written_gold


def test_load_gold_series_reads_the_published_levels(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The Gold reader used by downstream analysis sees the committed rows."""
    assert published.exit_code == 0

    frame = load_gold_series(reader, USD_FREE)

    assert len(frame) == ROWS_PER_INDICATOR
    assert frame["value"].notna().all()
    assert set(frame["domain"]) == {DOMAINS[USD_FREE]}



# -------------------------------------------------------------- audit trail


def test_transformation_log_records_both_hops(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Each indicator leaves one Bronze->Silver and one Silver->Gold audit row."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT source_layer, target_layer, transformation_type, status, count(*) AS rows "
            "FROM metadata.transformation_log GROUP BY 1, 2, 3, 4 ORDER BY 1"
        )
    ).all()

    assert [tuple(row) for row in rows] == [
        (LAYER_BRONZE, LAYER_SILVER, SILVER_TRANSFORMATION, STATUS_SUCCESS, len(INDICATORS)),
        (LAYER_SILVER, LAYER_GOLD, GOLD_TRANSFORMATION, STATUS_SUCCESS, len(INDICATORS)),
    ]
    assert all(
        seconds is not None
        for seconds in scalars(
            reader, "SELECT execution_time_seconds FROM metadata.transformation_log"
        )
    )


def test_no_chain_linking_log_for_daily_prices(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Daily prices have no base year, so nothing claims to be chain-linked."""
    assert published.exit_code == 0

    assert count(reader, "metadata.chain_linking_log") == 0
    assert count(reader, "gold.gold_analytical", "is_chain_linked") == 0
    assert count(reader, "gold.gold_analytical", "chain_linking_confidence IS NOT NULL") == 0
    assert not any(outcome.is_chain_linked for outcome in published.outcomes)


def test_catalog_records_the_observed_coverage(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Availability is filled from the data collected, not from discovery."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, domain, is_active, has_base_year_changes, frequency "
            "FROM metadata.indicator_catalog "
            "WHERE indicator_id IN :indicators "
            "ORDER BY indicator_id"
        ),
        {"indicators": tuple(INDICATORS)},
    ).all()

    assert len(rows) == len(INDICATORS)
    for row in rows:
        assert row.domain == DOMAINS[row.indicator_id]
        assert row.is_active is True
        assert row.has_base_year_changes is False
        assert row.frequency == FREQUENCY_DAILY



# -------------------------------------------------------------- idempotency


def test_rerun_upserts_silver_and_republishes_gold(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """
    A second collection of the same data adds no duplicates.

    Silver is upserted on ``(indicator_id, timestamp)`` so its rows keep their
    ids; Gold is deleted and reinserted (a hypertable's composite primary key
    rules out an upsert) so its ids change while the count does not. Bronze is
    append-only by design: a second fetch is a second immutable envelope.
    """
    silver_before = set(scalars(reader, "SELECT id FROM silver.silver_cleaned"))
    gold_before = set(scalars(reader, "SELECT id FROM gold.gold_analytical"))
    # Close the read transaction before the pipeline writes: it has served its
    # purpose, and holding it open across another session's commits proves nothing.
    reader.rollback()

    second = run_pipeline()

    assert second.exit_code == 0
    assert count(reader, "silver.silver_cleaned") == len(silver_before)
    assert set(scalars(reader, "SELECT id FROM silver.silver_cleaned")) == silver_before
    assert count(reader, "gold.gold_analytical") == len(gold_before)
    assert set(scalars(reader, "SELECT id FROM gold.gold_analytical")).isdisjoint(gold_before)
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS) * 2
    assert count(reader, "metadata.indicator_catalog") == len(INDICATORS)

    # Each observation now cites the envelope it was last refreshed from.
    assert (
        count(
            reader,
            "silver.silver_cleaned s LEFT JOIN bronze.bronze_raw b ON b.id = s.bronze_id",
            "b.id IS NULL",
        )
        == 0
    )
    assert len(set(scalars(reader, "SELECT DISTINCT bronze_id FROM silver.silver_cleaned"))) == len(
        INDICATORS
    )
    assert published.rows_written_silver == second.rows_written_silver



# --------------------------------------------------------------- live scraper


@pytest.mark.live()
@pytest.mark.skipif(
    os.environ.get(LIVE_FLAG) != "1",
    reason=f"live scraper test: set {LIVE_FLAG}=1 to run it",
)
def test_live_tgju_scrape_returns_daily_prices() -> None:
    """The real TGJU website still answers with the contract the scraper expects."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        scraper = TgjuScraper(
            config=TgjuConfig(paths=("price_dollar_rl",)),
            browser=browser,
        )
        try:
            assert scraper.connect() is True
            result = scraper.fetch_series(USD_FREE)
        finally:
            scraper.disconnect()

    assert len(result.frame) >= MIN_LIVE_OBSERVATIONS
    assert result.frame["timestamp"].is_monotonic_increasing
    assert result.frame["value"].notna().sum() >= MIN_LIVE_OBSERVATIONS
    assert result.scraped_at is not None
    assert result.raw_html is not None and len(result.raw_html) > 1000
