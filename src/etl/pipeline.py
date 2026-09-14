"""
Generic end-to-end collection: discover -> Bronze -> Silver -> Gold.

A source is described by a :class:`SourceSpec` (source name/type, frequency,
derived-series namespace, per-indicator derivation, forecast support, parser)
and a connector that implements :class:`SeriesConnector`. World Bank is the
reference caller via :func:`run_world_bank_pipeline`; TGJU keeps its own
HTML-specific runner. New API sources only add a connector + a spec.

Orchestration contract
----------------------
* **One session per indicator.** Each indicator's Bronze, Silver, and Gold writes
  share a single transaction, so an indicator either lands completely or not at
  all -- and a failure in one indicator cannot roll back another's work.
* **Failures are contained, not swallowed.** A failed indicator is logged,
  counted, and reported; the run continues. The process exit code is non-zero if
  any indicator failed, so a scheduler (Airflow, in Phase 5) can detect it.
* **The catalog is upserted.** ``metadata.indicator_catalog.indicator_id`` is the
  primary key, so seeding blind-inserts would raise on the second run.
  ``availability_start`` / ``availability_end`` are deliberately excluded from the
  upsert's update set: ``discover()`` cannot report per-country coverage, so those
  columns are filled from the observations actually collected.
* **Dry run touches nothing.** ``--dry-run`` performs discovery and fetching (so
  connectivity and parsing are genuinely exercised) but opens no session and
  writes no row.
"""

import argparse
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.connectors.base import IndicatorMetadata
from src.connectors.world_bank import (
    FREQUENCY_ANNUAL,
    SOURCE_NAME,
    SOURCE_TYPE,
    WorldBankConfig,
    WorldBankConnector,
)
from src.database.connection import get_db, init_database
from src.database.schema import IndicatorCatalog, utc_now
from src.etl.bronze import write_bronze
from src.etl.gold import DERIVED_PREFIX, silver_to_gold
from src.etl.lineage import STATUS_FAILED, STATUS_SUCCESS
from src.etl.silver import bronze_to_silver
from src.utils.config import get_config
from src.utils.exceptions import (
    ChainLinkingError,
    DataRetrievalError,
    ParsingError,
    ValidationError,
)
from src.utils.exceptions import (
    ConnectionError as PlatformConnectionError,
)
from src.utils.logging import get_logger, log_with_context, setup_logging

logger = get_logger(__name__)

EXIT_OK = 0
EXIT_FAILED = 1

# Failures that mean "this indicator did not work"; anything else is a bug and is
# allowed to propagate rather than being silently downgraded to a counter.
INDICATOR_ERRORS: tuple[type[Exception], ...] = (
    DataRetrievalError,
    ParsingError,
    ValidationError,
    ChainLinkingError,
)


@runtime_checkable
class FetchResult(Protocol):
    """What a connector hands back for one indicator's fetch."""

    # Read-only properties rather than attributes: a protocol attribute is
    # invariant, so a connector returning ``str`` for a ``str | None`` field
    # would not match. A concrete attribute satisfies a read-only property.
    @property
    def indicator_id(self) -> str:
        ...

    @property
    def frame(self) -> pd.DataFrame:
        ...

    @property
    def raw_envelope(self) -> Any:
        ...

    @property
    def request_url(self) -> str | None:
        ...

    @property
    def http_status_code(self) -> int | None:
        ...

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata``."""
        ...


class SeriesConnector(Protocol):
    """The connector surface :func:`run_pipeline` drives."""

    def connect(self) -> bool:
        ...

    def discover(self) -> list[IndicatorMetadata]:
        ...

    def fetch_series(self, indicator_id: str) -> FetchResult:
        ...

    def disconnect(self) -> None:
        ...


@dataclass(frozen=True)
class IndicatorDerivation:
    """How one indicator's derived Gold series should be produced."""

    derivation_strategy: str | None = None
    include_growth: bool = True
    # Opt-in month-end downsample of a (daily) linked series -> ``.ME`` rows.
    # Defaults to False so existing sources keep their current behavior.
    include_monthly: bool = False


@dataclass(frozen=True)
class SourceSpec:
    """
    Everything the generic runner needs to know about a source.

    ``parser`` is the pure Bronze-row -> DataFrame function used by Silver; it
    defaults to the World Bank-shaped parser. ``overrides`` lets a source opt
    individual indicators out of (or into) derived series -- IMF rate
    indicators, for example, are already percentages.
    """

    source_name: str
    source_type: str
    frequency: str
    derived_prefix: str
    indicators: tuple[str, ...] = ()
    default_derivation: IndicatorDerivation = field(default_factory=IndicatorDerivation)
    overrides: Mapping[str, IndicatorDerivation] = field(default_factory=dict)
    supports_forecasts: bool = False
    parser: Callable[..., pd.DataFrame] | None = None


WORLD_BANK_SPEC = SourceSpec(
    source_name=SOURCE_NAME,
    source_type=SOURCE_TYPE,
    frequency=FREQUENCY_ANNUAL,
    derived_prefix=DERIVED_PREFIX,
)


@dataclass
class IndicatorOutcome:
    """What happened to one indicator during a run."""

    indicator_id: str
    status: str
    rows_fetched: int = 0
    rows_written_silver: int = 0
    rows_written_gold: int = 0
    records_failed: int = 0
    is_chain_linked: bool = False
    bronze_id: UUID | None = None
    # Series actually persisted to Silver for this outcome (SCI uses this to
    # decide which canonical indicators can be chain-linked).
    series_ids: list[str] = field(default_factory=list)
    error: str | None = None

    def summary(self) -> dict[str, Any]:
        """Log-friendly view of this indicator's result."""
        return {
            "indicator_id": self.indicator_id,
            "status": self.status,
            "rows_fetched": self.rows_fetched,
            "rows_written_silver": self.rows_written_silver,
            "rows_written_gold": self.rows_written_gold,
            "records_failed": self.records_failed,
            "is_chain_linked": self.is_chain_linked,
            "bronze_id": str(self.bronze_id) if self.bronze_id else None,
            "error": self.error,
        }


@dataclass
class PipelineSummary:
    """Aggregate result of a pipeline run."""

    source_name: str = SOURCE_NAME
    dry_run: bool = False
    outcomes: list[IndicatorOutcome] = field(default_factory=list)

    @property
    def succeeded(self) -> list[IndicatorOutcome]:
        """Indicators that completed without error."""
        return [item for item in self.outcomes if item.status == STATUS_SUCCESS]

    @property
    def failed(self) -> list[IndicatorOutcome]:
        """Indicators that failed."""
        return [item for item in self.outcomes if item.status == STATUS_FAILED]

    @property
    def rows_written_gold(self) -> int:
        """Total Gold rows published across all indicators."""
        return sum(item.rows_written_gold for item in self.outcomes)

    @property
    def rows_written_silver(self) -> int:
        """Total Silver rows written across all indicators."""
        return sum(item.rows_written_silver for item in self.outcomes)

    @property
    def exit_code(self) -> int:
        """0 when every indicator succeeded, 1 otherwise."""
        return EXIT_FAILED if self.failed else EXIT_OK

    def report(self) -> str:
        """Human-readable one-line-per-indicator report for the CLI."""
        lines = [
            f"{'dry run' if self.dry_run else 'run'}: {self.source_name} "
            f"({len(self.succeeded)}/{len(self.outcomes)} indicators ok)"
        ]
        for item in self.outcomes:
            if item.status == STATUS_FAILED:
                lines.append(f"  FAIL {item.indicator_id}: {item.error}")
            elif self.dry_run:
                lines.append(f"  ok   {item.indicator_id}: {item.rows_fetched} rows fetched")
            else:
                lines.append(
                    f"  ok   {item.indicator_id}: {item.rows_fetched} fetched, "
                    f"{item.rows_written_silver} silver, {item.rows_written_gold} gold"
                    f"{' (chain-linked)' if item.is_chain_linked else ''}"
                )
        if not self.dry_run:
            lines.append(
                f"totals: {self.rows_written_silver} silver rows, "
                f"{self.rows_written_gold} gold rows"
            )
        return "\n".join(lines)


def _catalog_values(item: IndicatorMetadata) -> dict[str, Any]:
    """Map discovered metadata onto ``metadata.indicator_catalog`` columns."""
    stamped = utc_now()
    return {
        "indicator_id": item.indicator_id,
        "name": item.name,
        "description": item.description,
        "unit": item.unit,
        "frequency": item.frequency,
        "domain": item.domain,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "availability_start": item.availability_start,
        "availability_end": item.availability_end,
        "has_base_year_changes": item.has_base_year_changes,
        "base_years": item.base_years,
        "is_active": item.is_active,
        "created_at": stamped,
        "updated_at": stamped,
    }


def upsert_indicator_catalog(session: Session, discovered: Sequence[IndicatorMetadata]) -> int:
    """
    Seed or refresh the indicator catalog.

    ``availability_start`` / ``availability_end`` are set on insert but never
    overwritten on conflict: they are derived from collected observations by
    :func:`update_catalog_availability`, and the discovery endpoint has nothing
    better to offer.

    Args:
        session: Active session; the caller owns the transaction
        discovered: Metadata rows returned by the connector's ``discover()``

    Returns:
        Number of catalog rows submitted
    """
    if not discovered:
        return 0

    values = [_catalog_values(item) for item in discovered]
    statement = pg_insert(IndicatorCatalog).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[IndicatorCatalog.indicator_id],
        set_={
            "name": statement.excluded.name,
            "description": statement.excluded.description,
            "unit": statement.excluded.unit,
            "frequency": statement.excluded.frequency,
            "domain": statement.excluded.domain,
            "source_name": statement.excluded.source_name,
            "source_url": statement.excluded.source_url,
            "has_base_year_changes": statement.excluded.has_base_year_changes,
            "base_years": statement.excluded.base_years,
            "is_active": statement.excluded.is_active,
            "updated_at": statement.excluded.updated_at,
        },
    )
    session.execute(statement)
    session.flush()
    return len(values)


def _observed_range(frame: pd.DataFrame) -> tuple[datetime | None, datetime | None]:
    """First and last period that actually carry a value."""
    if frame.empty or "value" not in frame.columns:
        return (None, None)
    observed = frame.dropna(subset=["value"])
    if observed.empty:
        return (None, None)
    return (
        pd.Timestamp(observed["timestamp"].min()).to_pydatetime(),
        pd.Timestamp(observed["timestamp"].max()).to_pydatetime(),
    )


def update_catalog_availability(
    session: Session,
    indicator_id: str,
    availability_start: datetime | None,
    availability_end: datetime | None,
) -> bool:
    """
    Record the coverage a collection actually observed.

    Args:
        session: Active session; the caller owns the transaction
        indicator_id: Catalog row to update
        availability_start: Earliest period with a value
        availability_end: Latest period with a value

    Returns:
        True when a catalog row was updated
    """
    entry = session.get(IndicatorCatalog, indicator_id)
    if entry is None:
        return False
    entry.availability_start = availability_start
    entry.availability_end = availability_end
    session.flush()
    return True


def _unit_for(discovered: Sequence[IndicatorMetadata], indicator_id: str) -> str | None:
    """Unit discovered for an indicator, if discovery reached it."""
    for item in discovered:
        if item.indicator_id == indicator_id:
            return item.unit
    return None


def _domain_for(discovered: Sequence[IndicatorMetadata], indicator_id: str) -> str | None:
    """Domain discovered for an indicator, if discovery reached it."""
    for item in discovered:
        if item.indicator_id == indicator_id:
            return item.domain
    return None


def _derivation_for(spec: SourceSpec, indicator_id: str) -> IndicatorDerivation:
    """Resolve an indicator's derivation, falling back to the source default."""
    return spec.overrides.get(indicator_id, spec.default_derivation)


def _persist_indicator(
    session: Session,
    spec: SourceSpec,
    fetched: FetchResult,
    outcome: IndicatorOutcome,
    domain: str | None,
    unit: str | None,
) -> None:
    """Write one fetched series through Bronze, Silver, and Gold."""
    bronze_id = write_bronze(
        session,
        source_name=spec.source_name,
        source_type=spec.source_type,
        raw_envelope=fetched.raw_envelope,
        request_url=fetched.request_url,
        http_status_code=fetched.http_status_code,
        record_metadata=fetched.collection_metadata(),
    )
    outcome.bronze_id = bronze_id

    derivation = _derivation_for(spec, fetched.indicator_id)
    strategy = derivation.derivation_strategy or spec.default_derivation.derivation_strategy
    silver = bronze_to_silver(
        session,
        bronze_id=bronze_id,
        indicator_id=fetched.indicator_id,
        source_name=spec.source_name,
        frequency=spec.frequency,
        unit=unit,
        parser=spec.parser,
        allow_future=spec.supports_forecasts,
    )
    outcome.rows_written_silver = silver.records_written
    outcome.records_failed = silver.records_failed

    start, end = _observed_range(fetched.frame)
    update_catalog_availability(session, fetched.indicator_id, start, end)

    gold = silver_to_gold(
        session,
        indicator_id=fetched.indicator_id,
        domain=domain,
        include_growth=derivation.include_growth,
        derived_prefix=spec.derived_prefix,
        derivation_strategy=strategy or "yoy",
        include_monthly=derivation.include_monthly,
    )
    outcome.rows_written_gold = gold.records_written
    outcome.is_chain_linked = bool(gold.details.get("is_chain_linked"))


def run_world_bank_pipeline(
    indicators: Sequence[str] | None = None,
    dry_run: bool = False,
    connector: WorldBankConnector | None = None,
) -> PipelineSummary:
    """
    Collect World Bank indicators for Iran into Bronze, Silver, and Gold.

    Args:
        indicators: Indicator codes to collect; defaults to the connector's registry
        dry_run: Fetch and report without opening a session or writing a row
        connector: Pre-built connector (tests inject one with a fake HTTP session)

    Returns:
        Per-indicator outcomes plus an aggregate exit code

    Raises:
        ConnectionError: If the API cannot be reached at all
    """
    owns_connector = connector is None
    if connector is None:
        config = WorldBankConfig()
        if indicators:
            config.indicators = tuple(indicators)
        connector = WorldBankConnector(config=config)
    elif indicators:
        connector.config.indicators = tuple(indicators)

    try:
        return run_pipeline(
            connector,
            WORLD_BANK_SPEC,
            indicators=connector.config.indicators,
            dry_run=dry_run,
        )
    finally:
        if owns_connector:
            connector.disconnect()


def run_pipeline(
    connector: SeriesConnector,
    spec: SourceSpec,
    indicators: Sequence[str] | None = None,
    dry_run: bool = False,
) -> PipelineSummary:
    """
    Run one source end to end, containing per-indicator failures.

    The runner connects the connector but does not close it: the caller owns the
    connector's lifecycle (the World Bank wrapper above closes one it built).

    Args:
        connector: Connector implementing :class:`SeriesConnector`
        spec: Source description driving frequency, derivation, and parsing
        indicators: Indicator codes to collect; defaults to ``spec.indicators``
        dry_run: Fetch and report without opening a session or writing a row

    Returns:
        Per-indicator outcomes plus an aggregate exit code

    Raises:
        ConnectionError: If the source cannot be reached at all
    """
    targets = tuple(indicators) if indicators is not None else spec.indicators
    summary = PipelineSummary(source_name=spec.source_name, dry_run=dry_run)

    connector.connect()
    discovered = connector.discover()

    if not dry_run:
        with get_db().get_session() as session:
            seeded = upsert_indicator_catalog(session, discovered)
        log_with_context(
            logger,
            "INFO",
            "indicator catalog refreshed",
            source=spec.source_name,
            rows=seeded,
        )

    for indicator_id in targets:
        summary.outcomes.append(
            _collect_one(connector, spec, indicator_id, discovered, dry_run=dry_run)
        )

    log_with_context(
        logger,
        "INFO" if not summary.failed else "WARNING",
        "pipeline complete",
        source=spec.source_name,
        dry_run=dry_run,
        indicators=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )
    return summary


def _collect_one(
    connector: SeriesConnector,
    spec: SourceSpec,
    indicator_id: str,
    discovered: Sequence[IndicatorMetadata],
    dry_run: bool,
) -> IndicatorOutcome:
    """
    Run one indicator end to end, containing its failure.

    Each indicator gets its own session so a rollback here cannot undo another
    indicator's committed work.
    """
    outcome = IndicatorOutcome(indicator_id=indicator_id, status=STATUS_SUCCESS)
    try:
        fetched = connector.fetch_series(indicator_id)
        outcome.rows_fetched = int(len(fetched.frame))

        # A dry run still counts as success: fetching and parsing are the only
        # work it was asked to do.
        if not dry_run:
            with get_db().get_session() as session:
                _persist_indicator(
                    session,
                    spec,
                    fetched,
                    outcome,
                    domain=_domain_for(discovered, indicator_id),
                    unit=_unit_for(discovered, indicator_id),
                )
    except INDICATOR_ERRORS as exc:
        outcome.status = STATUS_FAILED
        outcome.error = f"{type(exc).__name__}: {exc}"
        log_with_context(
            logger,
            "ERROR",
            "indicator collection failed",
            indicator_id=indicator_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
    else:
        log_with_context(logger, "INFO", "indicator collected", **outcome.summary())

    return outcome


def _ensure_database() -> None:
    """Initialize the global connection if the process has not done so yet."""
    try:
        get_db()
    except RuntimeError:
        config = get_config()
        init_database(config.database.url, echo=config.debug)


def run_cli(
    indicators: Iterable[str] | None = None,
    dry_run: bool = False,
    log_level: str | None = None,
    connector: SeriesConnector | None = None,
    spec: SourceSpec = WORLD_BANK_SPEC,
) -> int:
    """
    CLI entry point shared by the source-specific ``main()`` functions.

    With no ``connector`` this runs the World Bank pipeline exactly as before,
    preserving ``python -m src.etl.pipeline``. A source that passes its own
    connector + :class:`SourceSpec` owns that connector's lifecycle here.

    Args:
        indicators: Indicator codes to collect; defaults to the source registry
        dry_run: Fetch and report without writing to the database
        log_level: Override the configured log level
        connector: Pre-built connector; omit to run World Bank from configuration
        spec: Source description driving the run when ``connector`` is given

    Returns:
        Process exit code: 0 when every indicator succeeded, 1 otherwise
    """
    config = get_config()
    setup_logging(
        level=log_level or config.logging.level,
        log_format=config.logging.format,
    )

    if not dry_run:
        _ensure_database()

    selected = tuple(indicators) if indicators else None
    try:
        if connector is None:
            summary = run_world_bank_pipeline(indicators=selected, dry_run=dry_run)
        else:
            summary = run_pipeline(connector, spec, indicators=selected, dry_run=dry_run)
    except (PlatformConnectionError, DataRetrievalError) as exc:
        log_with_context(
            logger,
            "ERROR",
            "pipeline aborted",
            source=spec.source_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        print(f"pipeline aborted: {type(exc).__name__}: {exc}")  # - CLI output
        return EXIT_FAILED
    finally:
        if connector is not None:
            connector.disconnect()

    print(summary.report())  # - CLI output
    return summary.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """
    Standalone entry point: ``python -m src.etl.pipeline``.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code
    """
    parser = argparse.ArgumentParser(
        prog="python -m src.etl.pipeline",
        description="Run the World Bank Bronze/Silver/Gold pipeline for Iran.",
    )
    parser.add_argument("--indicators", help="Comma-separated indicator codes")
    parser.add_argument("--dry-run", action="store_true", help="Fetch without writing")
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    args = parser.parse_args(argv)

    selected = (
        tuple(code.strip() for code in args.indicators.split(",") if code.strip())
        if args.indicators
        else None
    )
    return run_cli(indicators=selected, dry_run=args.dry_run, log_level=args.log_level)


if __name__ == "__main__":
    raise SystemExit(main())
