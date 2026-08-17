"""
Integration tests for the database layer.

These run against a real PostgreSQL + TimescaleDB instance (``make db-up``) and
are skipped when no server is reachable. They use a dedicated ``*_test``
database so development data is never touched.
"""

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.database.connection import DatabaseConnection, get_db, init_database
from src.database.schema import (
    BronzeRaw,
    GoldAnalytical,
    IndicatorCatalog,
    SilverCleaned,
)
from src.utils.config import get_config

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")


def integration_db_url() -> str:
    """Build the URL of the dedicated test database."""
    db = get_config().database
    return f"postgresql://{db.user}:{db.password}@{db.host}:{db.port}/{db.name}_test"


@pytest.fixture(scope="session")
def test_db() -> Generator[DatabaseConnection, None, None]:
    """Provision a dedicated test database with schemas, tables and hypertables."""
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
    connection.create_hypertables()

    yield connection

    connection.close()


@pytest.fixture()
def session(test_db: DatabaseConnection) -> Generator[Session, None, None]:
    """Yield a session that is always rolled back, leaving no rows behind."""
    db_session = test_db.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()


def make_bronze() -> BronzeRaw:
    """Build a minimal Bronze row."""
    return BronzeRaw(
        source_name="integration_source",
        source_type="api",
        raw_data={"value": 1},
    )


def test_connection_succeeds(test_db: DatabaseConnection) -> None:
    """A live connection is reported as healthy."""
    assert test_db.test_connection() is True


def test_search_path_includes_all_layers(session: Session) -> None:
    """The pool listener puts every layer schema on the search path."""
    search_path = session.execute(text("SHOW search_path")).scalar_one()

    for schema in SCHEMAS:
        assert schema in search_path


def test_all_tables_created(test_db: DatabaseConnection) -> None:
    """Every model has a physical table in its declared schema."""
    expected = {
        ("bronze", "bronze_raw"),
        ("silver", "silver_cleaned"),
        ("gold", "gold_analytical"),
        ("metadata", "indicator_catalog"),
        ("metadata", "data_collection_log"),
        ("metadata", "transformation_log"),
        ("metadata", "chain_linking_log"),
    }

    with test_db.get_session() as db_session:
        rows = db_session.execute(
            text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema IN ('bronze','silver','gold','metadata')"
            )
        ).all()

    assert expected <= {tuple(row) for row in rows}


def test_gold_analytical_is_hypertable(test_db: DatabaseConnection) -> None:
    """The Gold layer table is registered as a TimescaleDB hypertable."""
    with test_db.get_session() as db_session:
        rows = db_session.execute(
            text(
                "SELECT hypertable_schema, hypertable_name "
                "FROM timescaledb_information.hypertables"
            )
        ).all()

    assert ("gold", "gold_analytical") in {tuple(row) for row in rows}


def test_compression_policy_registered(test_db: DatabaseConnection) -> None:
    """A compression policy job exists for the hypertable."""
    with test_db.get_session() as db_session:
        count = db_session.execute(
            text(
                "SELECT count(*) FROM timescaledb_information.jobs "
                "WHERE proc_name = 'policy_compression'"
            )
        ).scalar_one()

    assert count >= 1


def test_create_hypertables_is_idempotent(test_db: DatabaseConnection) -> None:
    """Re-running hypertable setup on an existing hypertable does not raise."""
    test_db.create_hypertables()


def test_insert_defaults_are_applied(session: Session) -> None:
    """Insert-time column defaults land on the row when it is flushed."""
    bronze = make_bronze()
    session.add(bronze)
    session.flush()

    silver = SilverCleaned(
        indicator_id="INTEGRATION_TEST",
        timestamp=datetime(2020, 6, 30, tzinfo=UTC),
        value=42.0,
        frequency="monthly",
        source_name="integration_source",
        bronze_id=bronze.id,
    )
    session.add(silver)
    session.flush()

    assert silver.validation_status == "valid"
    assert silver.is_outlier is False
    assert bronze.collection_timestamp is not None


def test_timestamps_are_timezone_aware(session: Session) -> None:
    """created_at defaults are stored as timezone-aware UTC, not naive local time."""
    bronze = make_bronze()
    session.add(bronze)
    session.flush()
    session.refresh(bronze)

    assert bronze.created_at.tzinfo is not None
    assert bronze.created_at.utcoffset() is not None
    # Should be within a few minutes of now, proving UTC was not double-shifted.
    drift = abs((datetime.now(UTC) - bronze.created_at).total_seconds())
    assert drift < 300


def test_record_metadata_maps_to_metadata_column(session: Session) -> None:
    """The renamed attribute still reads/writes the physical `metadata` column."""
    bronze = make_bronze()
    bronze.record_metadata = {"origin": "integration"}
    session.add(bronze)
    session.flush()

    stored = session.execute(
        text("SELECT metadata FROM bronze.bronze_raw WHERE id = :id"),
        {"id": bronze.id},
    ).scalar_one()

    assert stored == {"origin": "integration"}


def test_indicator_catalog_defaults(session: Session) -> None:
    """Catalog boolean defaults are applied on insert."""
    indicator = IndicatorCatalog(
        indicator_id=f"INTEGRATION_{uuid4().hex[:8]}",
        name="Integration Indicator",
        frequency="annual",
        domain="gdp",
        source_name="integration_source",
    )
    session.add(indicator)
    session.flush()

    assert indicator.is_active is True
    assert indicator.has_base_year_changes is False


def test_gold_roundtrip_through_layers(session: Session) -> None:
    """A row can flow Bronze -> Silver -> Gold with foreign keys intact."""
    bronze = make_bronze()
    session.add(bronze)
    session.flush()

    silver = SilverCleaned(
        indicator_id="INTEGRATION_TEST",
        timestamp=datetime(2021, 3, 31, tzinfo=UTC),
        value=99.5,
        frequency="monthly",
        source_name="integration_source",
        bronze_id=bronze.id,
    )
    session.add(silver)
    session.flush()

    gold = GoldAnalytical(
        indicator_id="INTEGRATION_TEST",
        timestamp=datetime(2021, 3, 31, tzinfo=UTC),
        value=99.5,
        frequency="monthly",
        domain="gdp",
        silver_id=silver.id,
    )
    session.add(gold)
    session.flush()

    assert gold.is_chain_linked is False
    assert gold.silver_record.bronze_id == bronze.id


def test_get_session_rolls_back_on_error(test_db: DatabaseConnection) -> None:
    """An exception inside get_session rolls the transaction back."""
    marker = f"ROLLBACK_{uuid4().hex[:8]}"

    def insert_then_fail() -> None:
        """Write a row, then blow up before the context manager commits."""
        with test_db.get_session() as db_session:
            db_session.add(BronzeRaw(source_name=marker, source_type="api", raw_data={"v": 1}))
            db_session.flush()
            msg = "forced failure"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        insert_then_fail()

    with test_db.get_session() as db_session:
        count = db_session.execute(
            text("SELECT count(*) FROM bronze.bronze_raw WHERE source_name = :name"),
            {"name": marker},
        ).scalar_one()

    assert count == 0


def test_init_database_sets_global_connection() -> None:
    """init_database registers the singleton returned by get_db."""
    connection = init_database(integration_db_url())
    try:
        assert get_db() is connection
    finally:
        connection.close()
