"""
Integration tests for the IMF pipeline: Bronze -> Silver -> Gold.

Like the World Bank suite, these run against a real PostgreSQL + TimescaleDB
instance (``make db-up``) and skip when no server is reachable. The HTTP layer
is *not* live: the connector is injected with a fake session serving the captured
fixtures in ``tests/fixtures/imf`` (WEO April 2026 vintage, Iran 2010-2031), so
what is under test is the database half of the pipeline plus the two IMF-specific
behaviours:

* **Forecast rows survive every layer.** 2027-2031 are projections; Silver keeps
  them, labels each ``observation_type``, and the catalog records the horizon.
* **Derived YoY is opt-in per indicator.** Level series (``NGDPD``) get a derived
  year-over-year, while rate series (``PCPIPCH``) are already percentages and get
  none -- the ``SourceSpec.overrides`` mechanism.

Isolation mirrors ``test_world_bank_pipeline.py``: the pipeline commits its own
session per indicator, so each test truncates the layer tables before and after.

The ``live`` test at the bottom is the only one that touches the network:

    RUN_LIVE_API_TESTS=1 poetry run pytest -m live
"""

import os
from collections.abc import Generator, Sequence

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.connectors.imf import (
    DERIVED_PREFIX,
    SOURCE_NAME,
    SOURCE_TYPE,
    ImfConfig,
    ImfConnector,
    build_spec,
)
from src.database.connection import DatabaseConnection, init_database
from src.etl.gold import DERIVED_YOY_UNIT, derived_growth_indicator_id
from src.etl.gold import TRANSFORMATION_TYPE as GOLD_TRANSFORMATION
from src.etl.lineage import LAYER_BRONZE, LAYER_GOLD, LAYER_SILVER, STATUS_SUCCESS
from src.etl.pipeline import PipelineSummary, run_pipeline
from src.etl.silver import TRANSFORMATION_TYPE as SILVER_TRANSFORMATION
from src.utils.config import get_config
from src.utils.periods import FREQUENCY_ANNUAL
from src.utils.retry import RateLimiter, RetryPolicy
from tests.conftest import imf_session_for

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")

# A level series (derived YoY) plus a rate series (no derived YoY): enough to
# prove per-indicator derivation overrides and per-indicator domain mapping.
GDP = "NGDPD"
CPI = "PCPIPCH"
INDICATORS = (GDP, CPI)
DOMAINS = {GDP: "gdp", CPI: "inflation"}
UNITS = {GDP: "Billions of U.S. dollars", CPI: "Annual percent change"}

# Captured fixtures carry IRN 2010-2031 (WEO April 2026). The vintage year is an
# estimate, years before it are actual, and the five after it are forecasts.
ANNUAL_ROWS = 22
ACTUAL_ROWS = 16
ESTIMATE_ROWS = 1
FORECAST_ROWS = 5
VINTAGE = 2026
FORECAST_THROUGH = 2031
YOY_ROWS = ANNUAL_ROWS - 1
FIRST_PERIOD = "2010-12-31"
LAST_PERIOD = "2031-12-31"

# Truncated between tests; CASCADE handles ordering, but every table the
# pipeline writes has to be listed or rows leak into the next test.
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
MIN_LIVE_OBSERVATIONS = 20
HTTP_OK = 200


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


def run_imf_pipeline(indicators: Sequence[str] = INDICATORS) -> PipelineSummary:
    """
    Run the real pipeline over captured payloads: no network, real database.

    The runner does not own the connector's lifecycle, but a fake session needs
    no closing; retries and throttling are neutered so the run is instant.
    """
    connector = ImfConnector(
        config=ImfConfig(indicators=tuple(indicators)),
        http_session=imf_session_for(indicators),  # type: ignore[arg-type]
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
        yield run_imf_pipeline()
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
    assert published.rows_written_silver == ANNUAL_ROWS * len(INDICATORS)
    assert published.rows_written_gold == ANNUAL_ROWS * len(INDICATORS) + YOY_ROWS
    assert all(outcome.records_failed == 0 for outcome in published.outcomes)


# ---------------------------------------------------------------- bronze layer


def test_bronze_stores_one_immutable_envelope_per_indicator(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Bronze keeps the whole DataMapper payload, rows and raw response included."""
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS)

    rows = reader.execute(
        text(
            "SELECT source_name, source_type, http_status_code, "
            "       raw_data ? 'meta' AS has_meta, "
            "       raw_data ? 'raw_response' AS has_raw, "
            "       jsonb_array_length(raw_data -> 'rows') AS row_count, "
            "       (raw_data -> 'meta' ->> 'vintage')::int AS vintage, "
            "       (raw_data -> 'meta' ->> 'forecast_through')::int AS forecast_through, "
            "       raw_data -> 'meta' ->> 'country' AS country, "
            "       metadata ->> 'indicator_id' AS indicator_id "
            "FROM bronze.bronze_raw ORDER BY metadata ->> 'indicator_id'"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.source_type == SOURCE_TYPE
        assert row.http_status_code == HTTP_OK
        assert row.has_meta is True
        assert row.has_raw is True
        assert row.row_count == ANNUAL_ROWS
        assert row.vintage == VINTAGE
        assert row.forecast_through == FORECAST_THROUGH
        assert row.country == "IRN"


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
        assert row.records_collected == ANNUAL_ROWS


# ---------------------------------------------------------------- silver layer


def test_silver_counts_match_the_reported_writes(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Each indicator's full history plus forecasts is stored, one row per year."""
    for outcome in published.outcomes:
        stored = count(
            reader,
            "silver.silver_cleaned",
            "indicator_id = :indicator_id",
            indicator_id=outcome.indicator_id,
        )
        assert stored == outcome.rows_written_silver == ANNUAL_ROWS

    bounds = reader.execute(
        text("SELECT min(timestamp)::date, max(timestamp)::date FROM silver.silver_cleaned")
    ).one()
    assert [str(bound) for bound in bounds] == [FIRST_PERIOD, LAST_PERIOD]
    assert set(scalars(reader, "SELECT DISTINCT frequency FROM silver.silver_cleaned")) == {
        FREQUENCY_ANNUAL
    }


def test_silver_retains_and_labels_forecasts(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Future-dated projections survive Silver, tagged actual/estimate/forecast."""
    assert published.exit_code == 0

    for indicator_id in INDICATORS:
        stored = dict(
            reader.execute(
                text(
                    "SELECT metadata ->> 'observation_type' AS kind, count(*) "
                    "FROM silver.silver_cleaned WHERE indicator_id = :indicator_id "
                    "GROUP BY 1"
                ),
                {"indicator_id": indicator_id},
            ).all()
        )
        assert stored == {
            "actual": ACTUAL_ROWS,
            "estimate": ESTIMATE_ROWS,
            "forecast": FORECAST_ROWS,
        }

    # The projected years themselves are present, not silently dropped.
    future_rows = count(
        reader,
        "silver.silver_cleaned",
        "metadata ->> 'observation_type' = 'forecast'",
    )
    assert future_rows == FORECAST_ROWS * len(INDICATORS)


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
    for indicator_id, unit in UNITS.items():
        assert set(
            scalars(
                reader,
                "SELECT DISTINCT unit FROM silver.silver_cleaned WHERE indicator_id = :id",
                id=indicator_id,
            )
        ) == {unit}


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


def test_gold_publishes_levels_and_only_opt_in_growth(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Level series get a derived YoY; rate series do not."""
    assert published.exit_code == 0

    counts = dict(
        reader.execute(
            text("SELECT indicator_id, count(*) FROM gold.gold_analytical GROUP BY 1")
        ).all()
    )

    expected = {
        GDP: ANNUAL_ROWS,
        derived_growth_indicator_id(GDP, prefix=DERIVED_PREFIX): YOY_ROWS,
        CPI: ANNUAL_ROWS,
    }
    assert counts == expected
    # The rate series must not have grown a derived series.
    assert derived_growth_indicator_id(CPI, prefix=DERIVED_PREFIX) not in counts

    growth_rows = reader.execute(
        text(
            "SELECT unit, domain, frequency FROM gold.gold_analytical "
            "WHERE indicator_id = :id LIMIT 1"
        ),
        {"id": derived_growth_indicator_id(GDP, prefix=DERIVED_PREFIX)},
    ).one()
    assert growth_rows.unit == DERIVED_YOY_UNIT
    assert growth_rows.domain == DOMAINS[GDP]
    assert growth_rows.frequency == FREQUENCY_ANNUAL


def test_gold_keeps_forecast_levels(published: PipelineSummary, reader: Session) -> None:
    """Gold publishes the projected years rather than truncating at the vintage."""
    assert published.exit_code == 0

    for indicator_id in INDICATORS:
        assert (
            count(
                reader,
                "gold.gold_analytical",
                "indicator_id = :id AND timestamp >= '2027-12-31'",
                id=indicator_id,
            )
            == FORECAST_ROWS
        )


def test_gold_rows_carry_the_discovered_domain(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Discovery's domain reaches the analytical layer, derived series included."""
    assert published.exit_code == 0

    for indicator_id, domain in DOMAINS.items():
        stored = set(
            scalars(
                reader,
                "SELECT DISTINCT domain FROM gold.gold_analytical "
                "WHERE indicator_id IN (:level, :growth)",
                level=indicator_id,
                growth=derived_growth_indicator_id(indicator_id, prefix=DERIVED_PREFIX),
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
    assert count(reader, "gold.gold_analytical") == published.rows_written_gold


# ----------------------------------------------------------- catalog/lineage


def test_audit_trail_records_both_transform_layers(
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


def test_catalog_records_the_observed_coverage(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Availability is filled from the collected observations, forecasts included."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, availability_start::date, availability_end::date, "
            "       domain, is_active, has_base_year_changes "
            "FROM metadata.indicator_catalog ORDER BY indicator_id"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert str(row.availability_start) == FIRST_PERIOD
        assert str(row.availability_end) == LAST_PERIOD
        assert row.domain == DOMAINS[row.indicator_id]
        assert row.is_active is True
        assert row.has_base_year_changes is False


# -------------------------------------------------------------- idempotency


def test_rerun_upserts_silver_and_republishes_gold(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """A second collection of the same vintage adds no duplicates."""
    silver_before = set(scalars(reader, "SELECT id FROM silver.silver_cleaned"))
    gold_before = set(scalars(reader, "SELECT id FROM gold.gold_analytical"))
    reader.rollback()

    second = run_imf_pipeline()

    assert second.exit_code == 0
    assert count(reader, "silver.silver_cleaned") == len(silver_before)
    assert set(scalars(reader, "SELECT id FROM silver.silver_cleaned")) == silver_before
    assert count(reader, "gold.gold_analytical") == len(gold_before)
    assert set(scalars(reader, "SELECT id FROM gold.gold_analytical")).isdisjoint(gold_before)
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS) * 2
    assert count(reader, "metadata.indicator_catalog") == len(INDICATORS)
    assert published.rows_written_silver == second.rows_written_silver


# --------------------------------------------------------------- live API


@pytest.mark.live()
@pytest.mark.skipif(
    os.environ.get(LIVE_FLAG) != "1",
    reason=f"live API test: set {LIVE_FLAG}=1 to run it",
)
def test_live_imf_fetch_returns_history_and_forecasts() -> None:
    """The real API still answers with the contract the connector expects."""
    with ImfConnector(config=ImfConfig(indicators=(GDP,))) as connector:
        assert connector.connect() is True
        result = connector.fetch_series(GDP)

    assert result.http_status_code == HTTP_OK
    assert len(result.frame) >= MIN_LIVE_OBSERVATIONS
    assert result.frame["timestamp"].is_monotonic_increasing
    assert result.vintage is not None
    # WEO publishes five projection years beyond the vintage.
    assert result.forecast_through is not None
    assert result.forecast_through >= result.vintage + 1
