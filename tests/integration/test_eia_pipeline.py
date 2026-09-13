"""
Integration tests for the EIA pipeline: Bronze -> Silver -> Gold.

Like the World Bank and IMF suites, these run against a real PostgreSQL +
TimescaleDB instance (``make db-up``) and skip when no server is reachable. The
HTTP layer is *not* live: the connector is injected with a fake session serving
the captured fixtures in ``tests/fixtures/eia`` (Iran monthly production,
2024-01..2026-05), so what is under test is the database half of the pipeline
plus the EIA-specific behaviours:

* **Monthly frequency end to end.** Silver is tagged ``monthly`` and Gold's
  derived YoY is a genuine prior-year month comparison, not a lag-1 difference.
* **Paging.** With ``page_length=10`` the 29 months arrive in three pages yet
  land as one continuous series.
* **Credentials never reach storage.** The API key is absent from the stored
  Bronze payload and provenance.
* **Missing key aborts once**, before any layer is written.

Isolation mirrors the other suites: the pipeline commits its own session per
indicator, so each test truncates the layer tables before and after.
"""

from collections.abc import Generator, Sequence

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.connectors.eia import (
    SOURCE_NAME,
    SOURCE_TYPE,
    EiaConfig,
    EiaConnector,
    build_spec,
)
from src.database.connection import DatabaseConnection, init_database
from src.etl.gold import DERIVED_YOY_UNIT, derived_growth_indicator_id
from src.etl.lineage import STATUS_SUCCESS
from src.etl.pipeline import PipelineSummary, run_pipeline
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.periods import FREQUENCY_MONTHLY
from src.utils.retry import RateLimiter, RetryPolicy
from tests.conftest import EIA_TEST_KEY, eia_session_for

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")

CRUDE = "EIA.IRN.CRUDE_PRODUCTION"
LIQUIDS = "EIA.IRN.TOTAL_LIQUIDS"
INDICATORS = (CRUDE, LIQUIDS)
DERIVED_PREFIX = "EIA"
UNITS = {CRUDE: "thousand barrels per day", LIQUIDS: "thousand barrels per day"}

# Captured fixtures carry 2024-01 .. 2026-05 with no gaps. YoY needs the same
# month a year earlier, so only 2025-01 onward can produce a derived rate.
MONTHLY_ROWS = 29
YOY_ROWS = 17
FIRST_PERIOD = "2024-01-31"
LAST_PERIOD = "2026-05-31"
PAGE_LENGTH = 10
PAGES_FETCHED = 3

LAYER_TABLES = (
    "gold.gold_analytical",
    "silver.silver_cleaned",
    "bronze.bronze_raw",
    "metadata.chain_linking_log",
    "metadata.transformation_log",
    "metadata.data_collection_log",
    "metadata.indicator_catalog",
)


def integration_db_url() -> str:
    """Build the URL of the dedicated test database."""
    db = get_config().database
    return f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}_test"


def _ensure_silver_conflict_target(connection: DatabaseConnection) -> None:
    """Guarantee the Silver upsert's named conflict target exists."""
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


def run_eia_pipeline(indicators: Sequence[str] = INDICATORS) -> PipelineSummary:
    """Run the real pipeline over captured payloads: no network, real database."""
    connector = EiaConnector(
        config=EiaConfig(
            api_key=EIA_TEST_KEY,
            indicators=tuple(indicators),
            page_length=PAGE_LENGTH,
        ),
        http_session=eia_session_for(indicators),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )
    return run_pipeline(connector, build_spec(), indicators=tuple(indicators))


def count(session: Session, table: str, where: str = "TRUE", **params: object) -> int:
    """Row count for one table under an optional predicate."""
    statement = text(f"SELECT count(*) FROM {table} WHERE {where}")  # table names are constants
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

    init_database(integration_db_url())

    yield connection

    connection.close()


@pytest.fixture()
def published(pipeline_db: DatabaseConnection) -> Generator[PipelineSummary, None, None]:
    """A committed pipeline run over both indicators, cleaned up afterwards."""
    truncate_layers(pipeline_db)
    try:
        yield run_eia_pipeline()
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
    """Both indicators land completely, so the run exits clean."""
    assert [outcome.indicator_id for outcome in published.succeeded] == list(INDICATORS)
    assert published.failed == []
    assert published.exit_code == 0
    assert published.rows_written_silver == MONTHLY_ROWS * len(INDICATORS)
    assert published.rows_written_gold == (MONTHLY_ROWS + YOY_ROWS) * len(INDICATORS)
    assert all(outcome.records_failed == 0 for outcome in published.outcomes)


# ---------------------------------------------------------------- bronze layer


def test_bronze_stores_one_envelope_per_indicator_and_pages(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Bronze keeps the flattened rows, the paging metadata, and every page."""
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS)

    rows = reader.execute(
        text(
            "SELECT source_name, source_type, http_status_code, "
            "       jsonb_array_length(raw_data -> 'rows') AS row_count, "
            "       jsonb_typeof(raw_data -> 'raw_response') AS raw_type, "
            "       jsonb_array_length(raw_data -> 'raw_response') AS page_count, "
            "       (raw_data -> 'meta' ->> 'pages_fetched')::int AS pages_fetched, "
            "       (raw_data -> 'meta' ->> 'total_reported')::int AS total_reported, "
            "       raw_data -> 'meta' ->> 'country' AS country, "
            "       raw_data -> 'meta' ->> 'product_id' AS product_id, "
            "       metadata ->> 'indicator_id' AS indicator_id "
            "FROM bronze.bronze_raw ORDER BY metadata ->> 'indicator_id'"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.source_type == SOURCE_TYPE
        assert row.http_status_code == 200
        assert row.row_count == MONTHLY_ROWS
        assert row.raw_type == "array"
        assert row.page_count == PAGES_FETCHED
        assert row.pages_fetched == PAGES_FETCHED
        assert row.total_reported == MONTHLY_ROWS
        assert row.country == "IRN"
    assert {row.product_id for row in rows} == {"55", "53"}


def test_bronze_never_stores_the_api_key(published: PipelineSummary, reader: Session) -> None:
    """An append-only audit log must not become a credential leak."""
    assert published.exit_code == 0

    leaked = count(
        reader,
        "bronze.bronze_raw",
        "raw_data::text LIKE :pattern OR metadata::text LIKE :pattern",
        pattern=f"%{EIA_TEST_KEY}%",
    )

    assert leaked == 0


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
        assert row.records_collected == MONTHLY_ROWS


# ---------------------------------------------------------------- silver layer


def test_silver_is_monthly_and_monotonic(published: PipelineSummary, reader: Session) -> None:
    """Each indicator's monthly history is stored in full, one row per month."""
    for outcome in published.outcomes:
        stored = count(
            reader,
            "silver.silver_cleaned",
            "indicator_id = :indicator_id",
            indicator_id=outcome.indicator_id,
        )
        assert stored == outcome.rows_written_silver == MONTHLY_ROWS

    bounds = reader.execute(
        text("SELECT min(timestamp)::date, max(timestamp)::date FROM silver.silver_cleaned")
    ).one()
    assert [str(bound) for bound in bounds] == [FIRST_PERIOD, LAST_PERIOD]
    assert set(scalars(reader, "SELECT DISTINCT frequency FROM silver.silver_cleaned")) == {
        FREQUENCY_MONTHLY
    }
    assert set(scalars(reader, "SELECT DISTINCT unit FROM silver.silver_cleaned")) == set(
        UNITS.values()
    )


def test_silver_rows_resolve_to_their_bronze_envelope(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Every cleaned observation can be traced back to the payload it came from."""
    assert published.exit_code == 0

    orphans = count(
        reader,
        "silver.silver_cleaned s LEFT JOIN bronze.bronze_raw b ON b.id = s.bronze_id",
        "b.id IS NULL",
    )

    assert orphans == 0


# ------------------------------------------------------------------ gold layer


def test_gold_publishes_monthly_levels_and_prior_year_yoy(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Derived YoY is one year earlier per month, not the previous month."""
    assert published.exit_code == 0

    counts = dict(
        reader.execute(
            text("SELECT indicator_id, count(*) FROM gold.gold_analytical GROUP BY 1")
        ).all()
    )

    expected: dict[str, int] = {}
    for indicator_id in INDICATORS:
        expected[indicator_id] = MONTHLY_ROWS
        expected[derived_growth_indicator_id(indicator_id, prefix=DERIVED_PREFIX)] = YOY_ROWS
    assert counts == expected

    growth_units = set(
        scalars(
            reader,
            "SELECT DISTINCT unit FROM gold.gold_analytical WHERE indicator_id LIKE 'EIA.%.YOY'",
        )
    )
    assert growth_units == {DERIVED_YOY_UNIT}


def test_gold_yoy_compares_the_same_month_a_year_earlier(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """2025-05's derived rate uses 2024-05's level, not 2025-04's."""
    assert published.exit_code == 0

    level_id = CRUDE
    growth_id = derived_growth_indicator_id(level_id, prefix=DERIVED_PREFIX)

    current = reader.execute(
        text(
            "SELECT value FROM gold.gold_analytical "
            "WHERE indicator_id = :id AND timestamp = '2025-05-31'"
        ),
        {"id": level_id},
    ).scalar_one()
    prior = reader.execute(
        text(
            "SELECT value FROM gold.gold_analytical "
            "WHERE indicator_id = :id AND timestamp = '2024-05-31'"
        ),
        {"id": level_id},
    ).scalar_one()
    rate = reader.execute(
        text(
            "SELECT value FROM gold.gold_analytical "
            "WHERE indicator_id = :id AND timestamp = '2025-05-31'"
        ),
        {"id": growth_id},
    ).scalar_one()

    assert float(rate) == pytest.approx((current / prior - 1) * 100, rel=1e-9)
    # The previous month's level is a *different* number, proving the alignment.
    previous = reader.execute(
        text(
            "SELECT value FROM gold.gold_analytical "
            "WHERE indicator_id = :id AND timestamp = '2025-04-30'"
        ),
        {"id": level_id},
    ).scalar_one()
    assert float(rate) != pytest.approx((current / previous - 1) * 100)


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
    assert count(reader, "gold.gold_analytical") == published.rows_written_gold


def test_catalog_records_the_observed_monthly_coverage(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Availability is filled from the collected months; domain is energy."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, availability_start::date, availability_end::date, "
            "       domain, frequency "
            "FROM metadata.indicator_catalog ORDER BY indicator_id"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert str(row.availability_start) == FIRST_PERIOD
        assert str(row.availability_end) == LAST_PERIOD
        assert row.domain == "energy"
        assert row.frequency == FREQUENCY_MONTHLY


# -------------------------------------------------------------- idempotency


def test_rerun_upserts_silver_and_republishes_gold(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """A second collection of the same window adds no duplicates."""
    silver_before = set(scalars(reader, "SELECT id FROM silver.silver_cleaned"))
    gold_before = set(scalars(reader, "SELECT id FROM gold.gold_analytical"))
    reader.rollback()

    second = run_eia_pipeline()

    assert second.exit_code == 0
    assert count(reader, "silver.silver_cleaned") == len(silver_before)
    assert set(scalars(reader, "SELECT id FROM silver.silver_cleaned")) == silver_before
    assert count(reader, "gold.gold_analytical") == len(gold_before)
    assert set(scalars(reader, "SELECT id FROM gold.gold_analytical")).isdisjoint(gold_before)
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS) * 2
    assert published.rows_written_silver == second.rows_written_silver


# --------------------------------------------------------- API-key failure


def test_missing_api_key_aborts_without_writing(
    pipeline_db: DatabaseConnection,
) -> None:
    """The run aborts once, actionably, and leaves every layer empty."""
    truncate_layers(pipeline_db)
    session = pipeline_db.SessionLocal()
    try:
        connector = EiaConnector(
            config=EiaConfig(api_key=None, indicators=(CRUDE,)),
            http_session=eia_session_for([CRUDE]),  # type: ignore[arg-type]
        )
        with pytest.raises(PlatformConnectionError, match="EIA_API_KEY"):
            run_pipeline(connector, build_spec(), indicators=(CRUDE,))

        assert count(session, "bronze.bronze_raw") == 0
        assert count(session, "silver.silver_cleaned") == 0
        assert count(session, "gold.gold_analytical") == 0
    finally:
        session.rollback()
        session.close()
        truncate_layers(pipeline_db)
