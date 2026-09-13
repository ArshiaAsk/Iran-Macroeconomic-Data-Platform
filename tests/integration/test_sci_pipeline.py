"""
Integration tests for the SCI pipeline: Bronze -> Silver -> Gold.

These run against a real PostgreSQL + TimescaleDB instance (``make db-up``) and
are skipped when no server is reachable. The transport is *not* live: the
connector is injected with a fake HTTP session serving the captured fixtures in
``tests/fixtures/sci``, so what is under test is the database half of the
pipeline -- the Silver upsert's conflict target, the Gold delete-and-reinsert
against a hypertable, the multi-segment chain-link of the ``B2016``/``B2021``
CPI publications into the canonical ``SCI.CPI.URBAN`` series, the catalog
seeding (canonicals active, base-year segments inactive), and the audit trail.

Isolation differs from ``test_database.py`` on purpose. ``run_sci_pipeline``
opens and **commits** its own session per publication, so a rolled-back test
session cannot undo it; each test truncates the layer tables, runs the pipeline,
and truncates again on the way out.

The ``live`` test at the bottom is the only one that touches the network. It is
skipped unless ``RUN_LIVE_API_TESTS=1`` is set, which keeps it out of ``make
test``, ``make test-integration``, and ``make test-all``:

    RUN_LIVE_API_TESTS=1 poetry run pytest -m live

Task 1 finding that shapes the expectations here: SCI publishes only two CPI
bases (1395=2016 and 1400=2021), so only the urban series has a real
multi-segment link. The national/rural canonicals carry a single segment and
publish as passthrough (no ``ChainLinkingLog`` row).
"""

import os
from collections.abc import Generator, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.connectors.sci_scraper import (
    SCI_CANONICAL_INDICATORS,
    SCI_INDICATOR_REGISTRY,
    SOURCE_NAME,
    SOURCE_TYPE,
    SciConfig,
    SciScraper,
)
from src.database.connection import DatabaseConnection, init_database
from src.etl.gold import derived_growth_indicator_id, load_gold_series
from src.etl.lineage import LAYER_BRONZE, LAYER_GOLD, LAYER_SILVER, STATUS_SUCCESS
from src.etl.pipeline import PipelineSummary
from src.utils.config import get_config
from src.utils.retry import RateLimiter, RetryPolicy

pytestmark = pytest.mark.integration

SCHEMAS = ("bronze", "silver", "gold", "metadata")

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sci"

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS_CONTENT_TYPE = "application/vnd.ms-excel"

# One publication slug -> the Task 1 fixture that stands in for its download.
PUBLICATION_FIXTURES: dict[str, str] = {
    "cpi_national": "cpi_national_timeseries.xlsx",
    "cpi_urban": "cpi_urban_timeseries.xlsx",
    "cpi_rural": "cpi_rural_timeseries.xlsx",
    "cpi_base1395": "cpi_base1395_timeseries.xlsx",
    "cpi_decile": "cpi_decile_timeseries.xlsx",
    "unemployment_spring_1405": "unemployment_spring_1405.xls",
}
PUBLICATIONS = tuple(PUBLICATION_FIXTURES)

# The urban series is the only canonical with two real published bases.
URBAN = "SCI.CPI.URBAN"
URBAN_SEGMENTS = ("SCI.CPI.URBAN.B2016", "SCI.CPI.URBAN.B2021")
SINGLE_SEGMENT_CANONICALS = ("SCI.CPI.NATIONAL", "SCI.CPI.RURAL")

# Observed row counts (Task 4/5 fixture runs).
ROWS_BY_SEGMENT = {
    "SCI.CPI.URBAN.B2016": 491,
    "SCI.CPI.URBAN.B2021": 293,
}

# The tidy base-1395 sheet reaches back to 1361-01 (1982-03-31), well before the
# 1400-base workbooks, so the splice has real history to rescale.
URBAN_EARLIEST = "1982-03-31"

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
MIN_LIVE_PUBLICATIONS = 1
HTTP_OK = 200


class FakeResponse:
    """Minimal stand-in for ``requests.Response`` (streamed body)."""

    def __init__(
        self,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        filename: str = "publication.bin",
    ) -> None:
        self._data = data
        self.status_code = HTTP_OK
        self.ok = True
        self.headers: dict[str, str] = {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        self.closed = False

    def iter_content(self, chunk_size: int = 65536) -> Iterator[bytes]:
        for start in range(0, len(self._data), chunk_size):
            yield self._data[start : start + chunk_size]

    def raise_for_status(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """Routes SciScraper downloads to fixture bytes and records every request."""

    def __init__(self, mapping: Mapping[str, FakeResponse]) -> None:
        self.mapping = dict(mapping)
        self.calls: list[str] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(url)
        if url not in self.mapping:
            msg = f"unexpected URL: {url}"
            raise AssertionError(msg)
        return self.mapping[url]

    def close(self) -> None:
        self.closed = True


def fixture_bytes(filename: str) -> bytes:
    return (FIXTURES_DIR / filename).read_bytes()


def build_session() -> FakeSession:
    config = SciConfig()
    mapping: dict[str, FakeResponse] = {
        config.base_url: FakeResponse(b"<html>ok</html>", content_type="text/html"),
    }
    for slug, filename in PUBLICATION_FIXTURES.items():
        publication = SCI_INDICATOR_REGISTRY[slug]
        content_type = XLS_CONTENT_TYPE if filename.endswith(".xls") else XLSX_CONTENT_TYPE
        mapping[config.file_url(publication.path)] = FakeResponse(
            fixture_bytes(filename),
            content_type=content_type,
            filename=filename,
        )
    return FakeSession(mapping)


def build_scraper_with_fixtures() -> SciScraper:
    """
    Build a SciScraper with a fake session serving fixtures.

    Retries and throttling are neutered so a fixture-served run costs nothing in
    wall-clock time.
    """
    return SciScraper(
        config=SciConfig(publications=PUBLICATIONS),
        http_session=build_session(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


def run_pipeline() -> PipelineSummary:
    """Run the real pipeline over captured files: no network, real database."""
    from src.connectors.sci_scraper import run_sci_pipeline

    return run_sci_pipeline(connector=build_scraper_with_fixtures())


def count(session: Session, table: str, where: str = "TRUE", **params: object) -> int:
    """Row count for one table under an optional predicate."""
    statement = text(f"SELECT count(*) FROM {table} WHERE {where}")
    return int(session.execute(statement, params).scalar_one())


def scalars(session: Session, statement: str, **params: object) -> list[object]:
    """First column of every row returned by ``statement``."""
    return list(session.execute(text(statement), params).scalars().all())


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
    """A committed pipeline run over all publications, cleaned up afterwards."""
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


def test_pipeline_reports_every_publication_collected(published: PipelineSummary) -> None:
    """All six publications land completely, so the run exits clean."""
    assert published.failed == []
    assert published.exit_code == 0
    assert all(outcome.records_failed == 0 for outcome in published.outcomes)

    # Every publication contributed its series; Gold adds one outcome per
    # canonical (3) plus one per non-segment series (10 deciles + unemployment).
    collected = [outcome for outcome in published.outcomes if outcome.rows_fetched]
    assert len(collected) == len(PUBLICATIONS)
    assert published.rows_written_silver == sum(
        outcome.rows_written_silver for outcome in collected
    )


# ---------------------------------------------------------------- bronze layer


def test_bronze_stores_one_file_envelope_per_publication(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Bronze keeps exactly what the scraper returned, once per publication."""
    assert count(reader, "bronze.bronze_raw") == len(PUBLICATIONS)

    rows = reader.execute(
        text(
            "SELECT source_name, source_type, request_url, "
            "       length(raw_data::text) > 1000 AS has_payload, "
            "       metadata ->> 'indicator_id' AS indicator_id, "
            "       metadata ->> 'sha256' AS sha256 "
            "FROM bronze.bronze_raw"
        )
    ).all()

    assert len(rows) == len(PUBLICATIONS)
    for row in rows:
        assert row.source_name == SOURCE_NAME
        assert row.source_type == SOURCE_TYPE
        assert row.request_url.startswith("https://")
        assert row.has_payload is True
        assert row.sha256 is not None

    # Bronze ids reported by the run are the rows that actually exist.
    stored = set(scalars(reader, "SELECT id FROM bronze.bronze_raw"))
    reported = {outcome.bronze_id for outcome in published.outcomes if outcome.bronze_id}
    assert reported == stored


# ---------------------------------------------------------------- silver layer


def test_silver_segments_carry_disjoint_ranges_that_overlap(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The two urban bases share no (indicator_id, timestamp) and do overlap."""
    assert published.exit_code == 0

    for segment_id, expected in ROWS_BY_SEGMENT.items():
        stored = count(
            reader,
            "silver.silver_cleaned",
            "indicator_id = :indicator_id",
            indicator_id=segment_id,
        )
        assert stored == expected

    old_end = reader.execute(
        text(
            "SELECT max(timestamp) FROM silver.silver_cleaned " "WHERE indicator_id = :indicator_id"
        ),
        {"indicator_id": URBAN_SEGMENTS[0]},
    ).scalar_one()
    new_start = reader.execute(
        text(
            "SELECT min(timestamp) FROM silver.silver_cleaned " "WHERE indicator_id = :indicator_id"
        ),
        {"indicator_id": URBAN_SEGMENTS[1]},
    ).scalar_one()

    # A link needs the old base to reach at least as far as the new one begins.
    assert new_start <= old_end


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


# ------------------------------------------------------------------ gold layer


def test_gold_publishes_the_canonical_linked_urban_series(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The canonical urban CPI is continuous from the 1395 base back to 1361."""
    assert published.exit_code == 0

    frame = load_gold_series(reader, URBAN)

    assert not frame.empty
    assert str(frame["timestamp"].min()).startswith(URBAN_EARLIEST)
    # Both source bases reach Gold under the canonical id, never under raw ids.
    for segment_id in URBAN_SEGMENTS:
        assert count(reader, "gold.gold_analytical", "indicator_id = :i", i=segment_id) == 0


def test_gold_marks_only_rescaled_rows_as_chain_linked(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """``is_chain_linked`` is true exactly for the rows the splice rescaled."""
    assert published.exit_code == 0

    linked = count(reader, "gold.gold_analytical", "indicator_id = :i AND is_chain_linked", i=URBAN)
    total = count(reader, "gold.gold_analytical", "indicator_id = :i", i=URBAN)
    assert 0 < linked < total


def test_gold_every_level_row_keeps_its_original_value(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """``original_value`` is populated on every published level, linked or not."""
    assert published.exit_code == 0

    missing = count(
        reader,
        "gold.gold_analytical",
        "original_value IS NULL AND indicator_id NOT LIKE '%.YOY'",
    )

    assert missing == 0


def test_gold_derives_exact_yoy_growth_for_the_canonical(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The annual-over-annual derived series exists for the linked canonical."""
    assert published.exit_code == 0

    yoy_id = derived_growth_indicator_id(URBAN, prefix="SCI")
    assert count(reader, "gold.gold_analytical", "indicator_id = :i", i=yoy_id) > 0


# -------------------------------------------------------------- audit trail


def test_chain_linking_log_records_the_urban_splice(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The 1395 -> 1400 urban splice leaves one success row with its confidence."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT indicator_id, base_year_from, base_year_to, linking_method, "
            "       records_linked, overlap_period_months, avg_confidence_score, status "
            "FROM metadata.chain_linking_log"
        )
    ).all()

    assert len(rows) == 1
    row = rows[0]
    assert row.indicator_id == URBAN
    assert row.linking_method == "overlap"
    assert row.records_linked > 0
    assert row.overlap_period_months >= 12
    assert row.avg_confidence_score is not None
    assert row.status == STATUS_SUCCESS

    # Single-base canonicals are passthroughs: no link is claimed for them.
    assert (
        count(
            reader,
            "metadata.chain_linking_log",
            "indicator_id IN :ids",
            ids=SINGLE_SEGMENT_CANONICALS,
        )
        == 0
    )


# -------------------------------------------------------------------- catalog


def test_catalog_activates_canonicals_and_hides_segments(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """The dashboard gets the linked series; raw base-year segments stay inactive."""
    assert published.exit_code == 0

    for canonical in SCI_CANONICAL_INDICATORS.values():
        stored = reader.execute(
            text(
                "SELECT is_active, has_base_year_changes, base_years "
                "FROM metadata.indicator_catalog WHERE indicator_id = :i"
            ),
            {"i": canonical.indicator_id},
        ).one()
        assert stored.is_active is True
        assert stored.has_base_year_changes is (len(canonical.segment_ids) > 1)
        assert stored.base_years == list(canonical.base_years)

    inactive = count(
        reader,
        "metadata.indicator_catalog",
        "is_active = FALSE AND indicator_id IN :ids",
        ids=URBAN_SEGMENTS,
    )
    assert inactive == len(URBAN_SEGMENTS)


def test_catalog_coverage_comes_from_observed_gold(
    published: PipelineSummary, reader: Session
) -> None:
    """Availability is filled from the linked series, not from discovery."""
    assert published.exit_code == 0

    row = reader.execute(
        text(
            "SELECT availability_start, availability_end FROM metadata.indicator_catalog "
            "WHERE indicator_id = :i"
        ),
        {"i": URBAN},
    ).one()

    assert row.availability_start is not None
    assert str(row.availability_start).startswith(URBAN_EARLIEST)
    assert row.availability_end is not None


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
    assert published.exit_code == 0

    silver_before = set(scalars(reader, "SELECT id FROM silver.silver_cleaned"))
    gold_before = set(scalars(reader, "SELECT id FROM gold.gold_analytical"))
    reader.rollback()

    second = run_pipeline()

    assert second.exit_code == 0
    assert count(reader, "silver.silver_cleaned") == len(silver_before)
    assert set(scalars(reader, "SELECT id FROM silver.silver_cleaned")) == silver_before
    assert count(reader, "gold.gold_analytical") == len(gold_before)
    assert set(scalars(reader, "SELECT id FROM gold.gold_analytical")).isdisjoint(gold_before)
    assert count(reader, "bronze.bronze_raw") == len(PUBLICATIONS) * 2
    # Catalog seeding is an upsert: no duplicate indicator ids after a re-run.
    catalog_ids = scalars(reader, "SELECT indicator_id FROM metadata.indicator_catalog")
    assert len(catalog_ids) == len(set(catalog_ids))


# -------------------------------------------------------------------- audit


def test_transformation_log_records_both_hops(
    published: PipelineSummary,
    reader: Session,
) -> None:
    """Silver writes leave one Bronze->Silver audit row per series; Gold one per target."""
    assert published.exit_code == 0

    rows = reader.execute(
        text(
            "SELECT source_layer, target_layer, transformation_type, count(*) AS rows "
            "FROM metadata.transformation_log WHERE status = :ok "
            "GROUP BY 1, 2, 3"
        ),
        {"ok": STATUS_SUCCESS},
    ).all()

    by_hop = {(row.source_layer, row.target_layer): row.rows for row in rows}
    # Bronze->Silver: one row per series (only distinct combinations survive the
    # GROUP BY, so assert presence rather than a fragile exact count).
    assert by_hop[(LAYER_BRONZE, LAYER_SILVER)] > 0
    # Silver->Gold: the canonical and plain targets.
    assert by_hop[(LAYER_SILVER, LAYER_GOLD)] > 0
    assert all(row.transformation_type for row in rows)


# ------------------------------------------------------------- live (gated)


@pytest.mark.live()
@pytest.mark.skipif(
    os.environ.get(LIVE_FLAG) != "1",
    reason=f"set {LIVE_FLAG}=1 to run live SCI network tests",
)
def test_live_sci_publications_are_parseable() -> None:
    """
    A bounded live run over real SCI downloads (skipped by default).

    ``amar.org.ir`` serves an incomplete TLS chain; the connector pins the
    missing intermediate (``src/connectors/certs/``) instead of disabling
    verification. SCI has no published rate limit beyond the platform's 1-2
    req/sec politeness rule, enforced by ``RateLimiter``.
    """
    from src.connectors.sci_scraper import run_sci_pipeline

    summary = run_sci_pipeline(publications=PUBLICATIONS[:MIN_LIVE_PUBLICATIONS], dry_run=True)

    assert summary.exit_code == 0
    assert len(summary.succeeded) == MIN_LIVE_PUBLICATIONS
