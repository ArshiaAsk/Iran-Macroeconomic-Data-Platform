"""
Integration tests for the HBSIR pipeline: Bronze -> Silver -> Gold.

Like the EIA/IMF suites, these run against a real PostgreSQL + TimescaleDB
instance (``make db-up``) and skip when no server is reachable. The HBSIR package
is *not* imported: the connector is injected with a fake loader serving the
committed 1400 extract (``tests/fixtures/hbsir/income_expenditure_weight_1400_sample.csv``),
so what is under test is the database half of the pipeline plus the HBSIR-specific
behaviours:

* **No microdata is persisted.** Bronze holds one derived aggregate row per
  indicator plus a manifest (checksum, tables, survey years) -- never households.
* **The relative-poverty contract is explicit.** The poverty row carries the
  ``50% x weighted median income`` rule, its multiplier, and
  ``is_official_poverty_line = false`` in the stored metadata.
* **Rates and shares get no growth.** Gini, the poverty rate, and the decile
  shares are levels; Gold must not derive a YoY or month-end series for them.
* **Jalali survey years map to the Gregorian year end.** 1400 lands on
  2022-03-20 (Esfand 29), recorded alongside the original Jalali year.

Isolation mirrors the other suites: the pipeline commits its own session per
indicator, so each test truncates the layer tables before and after.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.connectors.hbsir import (
    INCOME_TABLE,
    SOURCE_NAME,
    SOURCE_TYPE,
    WEIGHT_TABLE,
    HbsirConfig,
    HbsirConnector,
    build_spec,
)
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
)
from src.database.connection import DatabaseConnection, init_database
from src.etl.lineage import STATUS_SUCCESS
from src.etl.pipeline import PipelineSummary, run_pipeline
from src.utils.config import get_config
from src.utils.periods import FREQUENCY_ANNUAL
from tests.conftest import FakeHbsirLoader, load_hbsir_csv

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")

INDICATORS = DEFAULT_INDICATORS
SURVEY_YEAR = 1400
YEAR_END = "2022-03-20"
PACKAGE_VERSION = "0.6.6"
EXTRACT_CHECKSUM = "8930e99a524a76b59e74c2495a57b76c58c7898db6611ce1b5eea1306947a27d"

# Reference metrics for the committed 200-household extract (Task 5 regression).
GINI_VALUE = 0.47445754165296994
POVERTY_RATE = 8.662455899542106
POVERTY_LINE = 23187194.0
WEIGHTED_HOUSEHOLDS = 93253.0
DECILE_SUM = 100.0
UNIT_GINI = "index (0-1)"
UNIT_PERCENT = "percent"

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


def sample_loader() -> FakeHbsirLoader:
    """A fake loader over the committed two-column 1400 extract."""
    frame = load_hbsir_csv("income_expenditure_weight_1400_sample")
    return FakeHbsirLoader(
        tables={
            INCOME_TABLE: frame[["Year", "ID", "Income"]],
            WEIGHT_TABLE: frame[["Year", "ID", "Weight"]],
        }
    )


def run_hbsir(indicators: tuple[str, ...] = INDICATORS) -> PipelineSummary:
    """Run the real pipeline over the captured extract: no package, real database."""
    connector = HbsirConnector(
        config=HbsirConfig(indicators=indicators, years=(SURVEY_YEAR,)),
        loader=sample_loader(),
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
    """A committed pipeline run over all twelve indicators, cleaned up afterwards."""
    truncate_layers(pipeline_db)
    try:
        yield run_hbsir()
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
    """All twelve survey indicators land completely; the run exits clean."""
    assert [outcome.indicator_id for outcome in published.succeeded] == list(INDICATORS)
    assert published.failed == []
    assert published.exit_code == 0
    assert published.rows_written_silver == len(INDICATORS)
    # Gini/poverty/deciles are rates and shares: no derived growth or monthly rows.
    assert published.rows_written_gold == len(INDICATORS)
    assert all(outcome.records_failed == 0 for outcome in published.outcomes)


# ---------------------------------------------------------------- bronze layer


def test_bronze_stores_one_derived_envelope_per_indicator(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Bronze keeps the aggregate row plus the manifest, never the microdata."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT source_name, source_type, "
            "       jsonb_array_length(raw_data -> 'rows') AS row_count, "
            "       jsonb_typeof(raw_data -> 'rows' -> 0 -> 'record_metadata') AS meta_type, "
            "       raw_data -> 'meta' ->> 'package' AS package, "
            "       raw_data -> 'meta' ->> 'package_version' AS package_version, "
            "       raw_data -> 'meta' ->> 'microdata_persisted' AS microdata_persisted, "
            "       raw_data -> 'meta' ->> 'extract_checksum_sha256' AS checksum, "
            "       metadata ->> 'indicator_id' AS indicator_id, "
            "       metadata ->> 'microdata_persisted' AS log_microdata "
            "FROM bronze.bronze_raw ORDER BY metadata ->> 'indicator_id'"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.source_type == SOURCE_TYPE
        assert row.row_count == 1  # one aggregate per indicator, not 200 households
        assert row.meta_type == "object"
        assert row.package == "hbsir"
        assert row.package_version == PACKAGE_VERSION
        assert row.microdata_persisted == "false"
        assert row.log_microdata == "false"
        assert row.checksum == EXTRACT_CHECKSUM


def test_bronze_never_stores_household_rows(published: PipelineSummary, reader: Session) -> None:
    """The redistributable payload is aggregates only: no ID/Income records."""
    assert published.exit_code == 0

    leaked = count(
        reader,
        "bronze.bronze_raw",
        "raw_data -> 'rows' -> 0 ? 'ID' OR raw_data -> 'rows' -> 0 ? 'Income'",
    )

    assert leaked == 0
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS)


def test_bronze_poverty_row_carries_the_relative_methodology(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The poverty contract is explicit and not presented as the official line."""
    assert published.exit_code == 0

    row = reader.execute(
        text(
            "SELECT raw_data -> 'rows' -> 0 -> 'record_metadata' AS meta "
            "FROM bronze.bronze_raw WHERE metadata ->> 'indicator_id' = :id"
        ),
        {"id": POVERTY_INDICATOR},
    ).one()
    meta = row.meta

    assert meta["poverty_line_rule"] == "50% of weighted median household income"
    assert float(meta["poverty_line_k"]) == 0.5
    assert meta["is_official_poverty_line"] is False
    assert float(meta["poverty_line_rial"]) == pytest.approx(POVERTY_LINE)
    assert int(meta["jalali_year"]) == SURVEY_YEAR


def test_collection_log_records_each_fetch(published: PipelineSummary, reader: Session) -> None:
    """Every Bronze write leaves a successful collection-log row behind."""
    assert published.exit_code == 0

    rows = reader.execute(
        text("SELECT source_name, status, records_collected FROM metadata.data_collection_log")
    ).all()

    assert len(rows) == len(INDICATORS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.status == STATUS_SUCCESS
        assert row.records_collected == 1


# ---------------------------------------------------------------- silver layer


def test_silver_is_annual_and_aligned_to_the_gregorian_year_end(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Every indicator lands once, on 2022-03-20, tagged annual."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, timestamp::date AS day, frequency, unit, "
            "       metadata ->> 'jalali_year' AS jalali_year "
            "FROM silver.silver_cleaned ORDER BY indicator_id"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert str(row.day) == YEAR_END
        assert row.frequency == FREQUENCY_ANNUAL
        assert int(row.jalali_year) == SURVEY_YEAR
    units = {row.indicator_id: row.unit for row in rows}
    assert units[GINI_INDICATOR] == UNIT_GINI
    assert set(units.values()) - {UNIT_GINI} == {UNIT_PERCENT}


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


def test_gold_publishes_annual_levels_only(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Gini/poverty/deciles publish as levels with no derived series."""
    assert published.exit_code == 0

    assert count(reader, "gold.gold_analytical") == len(INDICATORS)
    assert set(scalars(reader, "SELECT DISTINCT indicator_id FROM gold.gold_analytical")) == set(
        INDICATORS
    )
    assert count(reader, "gold.gold_analytical", "indicator_id LIKE '%.YOY'") == 0
    assert count(reader, "gold.gold_analytical", "indicator_id LIKE '%.ME'") == 0
    assert set(scalars(reader, "SELECT DISTINCT frequency FROM gold.gold_analytical")) == {
        FREQUENCY_ANNUAL
    }


def test_gold_reproduces_the_reference_weighted_metrics(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The stored Gini, poverty rate, and decile shares match the Task 5 reference."""
    assert published.exit_code == 0

    values = dict(
        reader.execute(text("SELECT indicator_id, value FROM gold.gold_analytical")).all()
    )

    assert float(values[GINI_INDICATOR]) == pytest.approx(GINI_VALUE, abs=1e-9)
    assert float(values[POVERTY_INDICATOR]) == pytest.approx(POVERTY_RATE, abs=1e-6)
    decile_sum = sum(float(values[indicator_id]) for indicator_id in DECILE_INDICATORS)
    assert decile_sum == pytest.approx(DECILE_SUM, abs=1e-6)
    # The weighted household count rides along in the Silver row metadata
    # (Gold level rows only carry chain-linking metadata, which HBSIR never uses).
    households = reader.execute(
        text(
            "SELECT metadata -> 'weighted_households' FROM silver.silver_cleaned "
            "WHERE indicator_id = :id"
        ),
        {"id": GINI_INDICATOR},
    ).scalar_one()
    assert float(households) == pytest.approx(WEIGHTED_HOUSEHOLDS)


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


def test_catalog_records_the_annual_welfare_coverage(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Availability is the survey year end; domain is welfare and cadence annual."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, availability_start::date, availability_end::date, "
            "       domain, frequency, unit, is_active "
            "FROM metadata.indicator_catalog ORDER BY indicator_id"
        )
    ).all()

    assert [row.indicator_id for row in rows] == sorted(INDICATORS)
    for row in rows:
        assert str(row.availability_start) == YEAR_END
        assert str(row.availability_end) == YEAR_END
        assert row.domain == "welfare"
        assert row.frequency == FREQUENCY_ANNUAL
        assert row.is_active is True
    units = {row.indicator_id: row.unit for row in rows}
    assert units[GINI_INDICATOR] == UNIT_GINI
    assert all(
        unit == UNIT_PERCENT
        for indicator_id, unit in units.items()
        if indicator_id != GINI_INDICATOR
    )


# -------------------------------------------------------------- idempotency


def test_rerun_upserts_silver_and_republishes_gold(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """A second collection of the same survey year adds no duplicates."""
    silver_before = set(scalars(reader, "SELECT id FROM silver.silver_cleaned"))
    gold_before = set(scalars(reader, "SELECT id FROM gold.gold_analytical"))
    reader.rollback()

    second = run_hbsir()

    assert second.exit_code == 0
    assert count(reader, "silver.silver_cleaned") == len(silver_before)
    assert set(scalars(reader, "SELECT id FROM silver.silver_cleaned")) == silver_before
    assert count(reader, "gold.gold_analytical") == len(gold_before)
    assert set(scalars(reader, "SELECT id FROM gold.gold_analytical")).isdisjoint(gold_before)
    assert count(reader, "bronze.bronze_raw") == len(INDICATORS) * 2
    assert count(reader, "metadata.indicator_catalog") == len(INDICATORS)
    assert published.rows_written_silver == second.rows_written_silver
