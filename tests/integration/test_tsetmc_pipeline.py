"""
Integration tests for the TSETMC pipeline: Bronze -> Silver -> Gold.

Like the EIA/IMF suites, these run against a real PostgreSQL + TimescaleDB
instance (``make db-up``) and skip when no server is reachable. The cdn is
*not* live: the connector is injected with a fake transport serving the captured
TEDPIX payload (``tests/fixtures/tsetmc/tedpix_cwi_raw.json``), so what is under
test is the database half of the pipeline plus the TSETMC-specific behaviours:

* **TEDPIX only.** Trading value, market P/E, and market cap stay deferred; the
  catalog and both published layers must never gain those indicators.
* **Daily levels plus the approved derivations.** Gold publishes the level,
  ``RET1D``, ``MA30``, and the opt-in month-end ``.ME`` downsample.
* **Holidays stay absent.** The exchange skips Thu/Fri and holidays; no row is
  ever forward-filled for a non-session.

The window is the trailing 70 sessions of the capture, which keeps the fixture
real (a full May-Sep 2026 trading stretch) while staying fast.

Isolation mirrors the other suites: the pipeline commits its own session per
indicator, so each test truncates the layer tables before and after.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.connectors.tsetmc import (
    FREQUENCY_DAILY,
    SOURCE_NAME,
    SOURCE_TYPE,
    TsetmcConfig,
    TsetmcConnector,
    build_spec,
)
from src.database.connection import DatabaseConnection, init_database
from src.etl.gold import (
    derived_ma30_indicator_id,
    derived_month_end_indicator_id,
    derived_ret1d_indicator_id,
)
from src.etl.lineage import STATUS_SUCCESS
from src.etl.pipeline import PipelineSummary, run_pipeline
from src.utils.config import get_config
from src.utils.periods import FREQUENCY_MONTHLY
from tests.conftest import FakeTsetmcClient, load_tsetmc_fixture

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")

TEDPIX = "TSETMC.TEDPIX"
INDICATORS = (TEDPIX,)
DERIVED_PREFIX = "TSETMC"
LEVEL_UNIT = "index points"
PACKAGE_VERSION = "1.2.10"
INS_CODE = "32097828799138957"

RET1D_ID = derived_ret1d_indicator_id(TEDPIX, prefix=DERIVED_PREFIX)
MA30_ID = derived_ma30_indicator_id(TEDPIX, prefix=DERIVED_PREFIX)
MONTH_END_ID = derived_month_end_indicator_id(TEDPIX, prefix=DERIVED_PREFIX)

# Trailing 70 sessions of the capture: 2026-05-30 .. 2026-09-13.
TRAILING_SESSIONS = 70
LEVEL_ROWS = 70
RET1D_ROWS = LEVEL_ROWS - 1
MA30_ROWS = LEVEL_ROWS - 29
MONTH_END_ROWS = 5
FIRST_SESSION = "2026-05-30"
LAST_SESSION = "2026-09-13"
FIRST_RETURN_DATE = "2026-05-31"
FIRST_MA30_DATE = "2026-07-14"
MONTH_END_VALUES = [4236521.1, 5127635.3, 5075098.6, 6547963.8, 7431451.1]
# The month-end series is stamped at the calendar period end, not the session.
MONTH_END_TIMESTAMPS = ["2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30"]

LAYER_TABLES = (
    "gold.gold_analytical",
    "silver.silver_cleaned",
    "bronze.bronze_raw",
    "metadata.chain_linking_log",
    "metadata.transformation_log",
    "metadata.data_collection_log",
    "metadata.indicator_catalog",
)


def window_rows() -> list[dict[str, object]]:
    """The trailing sessions of the captured TEDPIX payload."""
    payload = load_tsetmc_fixture("tedpix_cwi_raw")
    return payload["indexB2"][-TRAILING_SESSIONS:]


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


def run_tsetmc(indicators: tuple[str, ...] = INDICATORS) -> PipelineSummary:
    """Run the real pipeline over the captured payload: no network, real database."""
    connector = TsetmcConnector(
        config=TsetmcConfig(indicators=indicators),
        client=FakeTsetmcClient({"indexB2": window_rows()}),
    )
    return run_pipeline(connector, build_spec(), indicators=indicators)


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
    """A committed pipeline run, cleaned up afterwards."""
    truncate_layers(pipeline_db)
    try:
        yield run_tsetmc()
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
    """TEDPIX lands completely, so the run exits clean."""
    assert [outcome.indicator_id for outcome in published.succeeded] == list(INDICATORS)
    assert published.failed == []
    assert published.exit_code == 0
    assert published.rows_written_silver == LEVEL_ROWS
    assert published.rows_written_gold == LEVEL_ROWS + RET1D_ROWS + MA30_ROWS + MONTH_END_ROWS
    assert published.outcomes[0].records_failed == 0


# ---------------------------------------------------------------- bronze layer


def test_bronze_stores_the_raw_index_payload(published: PipelineSummary, reader: Session) -> None:
    """Bronze keeps the raw ``indexB2`` rows plus the package provenance."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT source_name, source_type, http_status_code, "
            "       jsonb_array_length(raw_data -> 'rows') AS row_count, "
            "       raw_data -> 'meta' ->> 'package' AS package, "
            "       raw_data -> 'meta' ->> 'package_version' AS package_version, "
            "       raw_data -> 'meta' ->> 'ins_code' AS ins_code, "
            "       (raw_data -> 'meta' ->> 'rows_returned')::int AS rows_returned, "
            "       (raw_data -> 'meta' ->> 'rows_usable')::int AS rows_usable, "
            "       metadata ->> 'package' AS meta_package "
            "FROM bronze.bronze_raw"
        )
    ).all()

    assert len(rows) == len(INDICATORS)
    row = rows[0]
    assert row.source_name == SOURCE_NAME
    assert row.source_type == SOURCE_TYPE
    assert row.http_status_code == 200
    assert row.row_count == LEVEL_ROWS
    assert row.package == "finpy-tse"
    assert row.package_version == PACKAGE_VERSION
    assert row.ins_code == INS_CODE
    assert row.rows_returned == LEVEL_ROWS
    assert row.rows_usable == LEVEL_ROWS
    assert row.meta_package == "finpy-tse"


def test_collection_log_records_the_fetch(published: PipelineSummary, reader: Session) -> None:
    """The Bronze write leaves a successful collection-log row behind."""
    assert published.exit_code == 0

    rows = reader.execute(
        text("SELECT source_name, status, records_collected FROM metadata.data_collection_log")
    ).all()

    assert len(rows) == len(INDICATORS)
    assert rows[0].source_name == SOURCE_NAME
    assert rows[0].status == STATUS_SUCCESS
    assert rows[0].records_collected == LEVEL_ROWS


# ---------------------------------------------------------------- silver layer


def test_silver_is_daily_and_monotonic(published: PipelineSummary, reader: Session) -> None:
    """The daily history is stored in full, one row per trading session."""
    assert published.exit_code == 0

    stored = count(reader, "silver.silver_cleaned", "indicator_id = :id", id=TEDPIX)
    assert stored == published.rows_written_silver == LEVEL_ROWS

    bounds = reader.execute(
        text("SELECT min(timestamp)::date, max(timestamp)::date FROM silver.silver_cleaned")
    ).one()
    assert [str(bound) for bound in bounds] == [FIRST_SESSION, LAST_SESSION]
    assert set(scalars(reader, "SELECT DISTINCT frequency FROM silver.silver_cleaned")) == {
        FREQUENCY_DAILY
    }
    assert set(scalars(reader, "SELECT DISTINCT unit FROM silver.silver_cleaned")) == {LEVEL_UNIT}


def test_silver_never_fills_a_non_session(published: PipelineSummary, reader: Session) -> None:
    """The Iranian weekend (Thu/Fri) produces no row, exactly as the cdn omits it."""
    assert published.exit_code == 0

    assert count(reader, "silver.silver_cleaned", "EXTRACT(DOW FROM timestamp) IN (4, 5)") == 0


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


def test_gold_publishes_levels_and_the_approved_derivations(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Levels, ``RET1D``, ``MA30`` and the month-end ``.ME`` are all published."""
    assert published.exit_code == 0

    counts = dict(
        reader.execute(
            text("SELECT indicator_id, count(*) FROM gold.gold_analytical GROUP BY 1")
        ).all()
    )

    assert counts == {
        TEDPIX: LEVEL_ROWS,
        RET1D_ID: RET1D_ROWS,
        MA30_ID: MA30_ROWS,
        MONTH_END_ID: MONTH_END_ROWS,
    }
    assert set(scalars(reader, "SELECT DISTINCT unit FROM gold.gold_analytical")) == {
        LEVEL_UNIT,
        "%",
    }


def test_gold_ret1d_matches_the_session_change(published: PipelineSummary, reader: Session) -> None:
    """RET1D is the simple percentage change against the prior session."""
    assert published.exit_code == 0

    values = [
        float(value)
        for value in scalars(
            reader,
            "SELECT value FROM silver.silver_cleaned ORDER BY timestamp LIMIT 2",
        )
    ]
    rate = reader.execute(
        text(
            "SELECT value FROM gold.gold_analytical "
            "WHERE indicator_id = :id AND timestamp::date = :day"
        ),
        {"id": RET1D_ID, "day": FIRST_RETURN_DATE},
    ).scalar_one()

    assert float(rate) == pytest.approx((values[1] / values[0] - 1) * 100, rel=1e-9)


def test_gold_ma30_matches_the_trailing_thirty_session_mean(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The first MA30 is the mean of the first thirty sessions (no partial window)."""
    assert published.exit_code == 0

    expected = reader.execute(
        text(
            "SELECT avg(value) FROM (SELECT value FROM silver.silver_cleaned ORDER BY timestamp LIMIT 30) w"
        )
    ).scalar_one()
    value = reader.execute(
        text(
            "SELECT value FROM gold.gold_analytical "
            "WHERE indicator_id = :id AND timestamp::date = :day"
        ),
        {"id": MA30_ID, "day": FIRST_MA30_DATE},
    ).scalar_one()

    assert float(value) == pytest.approx(float(expected), rel=1e-9)
    # MA30 needs a full window, so the 29 sessions before it carry no MA row.
    assert (
        count(
            reader,
            "gold.gold_analytical",
            "indicator_id = :id AND timestamp::date < :day",
            id=MA30_ID,
            day=FIRST_MA30_DATE,
        )
        == 0
    )


def test_gold_month_end_republishes_the_last_session_of_each_month(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """``.ME`` keeps the month's last observation, stamped at the period end."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT timestamp::date, value, frequency "
            "FROM gold.gold_analytical WHERE indicator_id = :id ORDER BY timestamp"
        ),
        {"id": MONTH_END_ID},
    ).all()

    assert [str(row.timestamp) for row in rows] == MONTH_END_TIMESTAMPS
    assert [float(row.value) for row in rows] == MONTH_END_VALUES
    assert {row.frequency for row in rows} == {FREQUENCY_MONTHLY}
    assert set(
        scalars(
            reader,
            "SELECT DISTINCT unit FROM gold.gold_analytical WHERE indicator_id = :id",
            id=MONTH_END_ID,
        )
    ) == {LEVEL_UNIT}


def test_gold_month_end_creates_no_month_without_a_session(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """One ``.ME`` row per observed month: missing months are absent, not filled."""
    assert published.exit_code == 0

    session_months = reader.execute(
        text(
            "SELECT count(DISTINCT date_trunc('month', timestamp)) "
            "FROM silver.silver_cleaned WHERE indicator_id = :id"
        ),
        {"id": TEDPIX},
    ).scalar_one()

    assert (
        count(reader, "gold.gold_analytical", "indicator_id = :id", id=MONTH_END_ID)
        == int(session_months)
        == MONTH_END_ROWS
    )


def test_gold_rows_resolve_to_their_silver_observation(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Derived rows keep the lineage of the observation they were built from."""
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


# ------------------------------------------------------------------- catalog


def test_catalog_records_the_observed_daily_coverage(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Availability is filled from the collected sessions; domain is market."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, availability_start::date, availability_end::date, "
            "       domain, frequency, unit, is_active, has_base_year_changes "
            "FROM metadata.indicator_catalog ORDER BY indicator_id"
        )
    ).all()

    assert [row.indicator_id for row in rows] == [TEDPIX]
    row = rows[0]
    assert str(row.availability_start) == FIRST_SESSION
    assert str(row.availability_end) == LAST_SESSION
    assert row.domain == "market"
    assert row.frequency == FREQUENCY_DAILY
    assert row.unit == LEVEL_UNIT
    assert row.is_active is True
    assert row.has_base_year_changes is False


def test_deferred_indicators_are_absent_everywhere(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Trading value, market P/E and market cap are not silently introduced."""
    assert published.exit_code == 0

    published_ids = set(scalars(reader, "SELECT DISTINCT indicator_id FROM gold.gold_analytical"))
    catalog_ids = set(scalars(reader, "SELECT indicator_id FROM metadata.indicator_catalog"))
    silver_ids = set(scalars(reader, "SELECT DISTINCT indicator_id FROM silver.silver_cleaned"))

    assert published_ids == {TEDPIX, RET1D_ID, MA30_ID, MONTH_END_ID}
    assert catalog_ids == silver_ids == {TEDPIX}
    for deferred in ("TRADING", "VALUE", "PE", "MARKET_CAP", "CAP"):
        assert not any(deferred in indicator_id for indicator_id in published_ids)


# -------------------------------------------------------------- idempotency


def test_rerun_upserts_silver_and_republishes_gold(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """A second collection of the same sessions adds no duplicates."""
    silver_before = set(scalars(reader, "SELECT id FROM silver.silver_cleaned"))
    gold_before = set(scalars(reader, "SELECT id FROM gold.gold_analytical"))
    reader.rollback()

    second = run_tsetmc()

    assert second.exit_code == 0
    assert count(reader, "silver.silver_cleaned") == len(silver_before)
    assert set(scalars(reader, "SELECT id FROM silver.silver_cleaned")) == silver_before
    assert count(reader, "gold.gold_analytical") == len(gold_before)
    assert set(scalars(reader, "SELECT id FROM gold.gold_analytical")).isdisjoint(gold_before)
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS) * 2
    assert count(reader, "metadata.indicator_catalog") == len(INDICATORS)
    assert published.rows_written_silver == second.rows_written_silver
    assert published.rows_written_gold == second.rows_written_gold
