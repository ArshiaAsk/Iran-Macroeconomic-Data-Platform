"""
Tehran Stock Exchange (TSETMC) connector backed by the ``finpy-tse`` package.

Phase 6 brings the platform's first **package-backed** source: the connector
depends on an optional Poetry extra (``tsetmc`` -> ``finpy-tse``) and imports it
lazily so the default install and unit suite stay package-free. The transport is
an injectable client (the package analogue of ``http_session``); persistence
still flows through the shared ``SourceSpec`` / ``run_pipeline`` / Gold path.

Scope (Phase 6 gate, see ``docs/phase-6/README.md``)
----------------------------------------------------
**OPEN: ``TSETMC.TEDPIX`` only** (the cap-weighted total index, ``insCode``
32097828799138957), plus its derived daily ``RET1D`` / ``MA30`` series and the
month-end ``.ME`` downsample. Trading value, market P/E, and market
capitalization are **deferred**: the package exposes no reliable *historical*
series for them, and the platform does not reconstruct history from a
current-day snapshot.

Why the raw cdn endpoint is fetched directly
--------------------------------------------
``finpy_tse.Get_CWI_History`` selects only ``['dEven', 'xNivInuClMresIbs']`` from
``Index/GetIndexB2History/{insCode}`` and **discards the raw JSON**, which Bronze
must archive (AGENTS.md: always store raw responses). The default client
therefore talks to the same ``cdn.tsetmc.com`` endpoint the package wraps,
reusing the package's request headers and recording its version, and the pure
``tsetmc_parser`` normalizes the raw ``indexB2`` records. ``Get_CWI_History`` is
not called because its Jalali-indexed, single-column frame carries strictly less
information than the raw payload (which already has the Gregorian ``dEven``).

Observed behaviour (probed 2026-09-13)
--------------------------------------
* No authentication; the endpoint answered normally.
* ~4,283 sessions from 2008-12-04 to the capture day.
* Holidays/missing sessions are **absent** from the payload, never filled.
* ``finpy-tse`` has no ``__version__`` attribute; the version comes from
  ``importlib.metadata``.
"""

import argparse
import importlib.metadata
import importlib.util
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import Any, Protocol, runtime_checkable

import pandas as pd
import requests
from requests import HTTPError

from src.connectors.base import DataConnector, IndicatorMetadata
from src.connectors.tsetmc_parser import tsetmc_parser
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.logging import get_logger, log_with_context
from src.utils.retry import RateLimiter, RetryPolicy
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "tsetmc"
SOURCE_TYPE = "package"
DERIVED_PREFIX = "TSETMC"
FREQUENCY_DAILY = "daily"

PACKAGE_DISTRIBUTION = "finpy-tse"
PACKAGE_IMPORT_NAME = "finpy_tse"

MIN_TIMEOUT_SECONDS = 10
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.0
UNIT_MAX_LENGTH = 50

USER_AGENT = "iran-macro-platform/0.1 (research; +https://github.com/ArshiaAsk)"

DEFAULT_UNIT = "index points"

MISSING_EXTRA_MESSAGE = (
    "TSETMC requires the optional 'finpy-tse' package, which is not installed. "
    "Install it with `poetry install -E tsetmc` (or `pip install finpy-tse`)."
)


@dataclass(frozen=True)
class TsetmcIndicator:
    """Registry entry: how one TSETMC index maps onto the platform catalog."""

    indicator_id: str
    name: str
    domain: str
    ins_code: str
    unit: str = DEFAULT_UNIT


#: TSETMC cdn ``Index/GetIndexB2History/{insCode}`` endpoints under contract.
#: Only TEDPIX is opened in Phase 6; see the module docstring for deferrals.
TSETMC_INDICATORS: Mapping[str, TsetmcIndicator] = {
    "TSETMC.TEDPIX": TsetmcIndicator(
        indicator_id="TSETMC.TEDPIX",
        name="Tehran Stock Exchange total index (TEDPIX)",
        domain="market",
        ins_code="32097828799138957",
    ),
}

DEFAULT_INDICATORS: tuple[str, ...] = tuple(TSETMC_INDICATORS)


def is_available() -> bool:
    """Report whether the optional ``finpy-tse`` package can be imported."""
    try:
        return importlib.util.find_spec(PACKAGE_IMPORT_NAME) is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def package_version() -> str | None:
    """Installed ``finpy-tse`` distribution version, or None when absent."""
    try:
        return importlib.metadata.version(PACKAGE_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return None


def _default_timeout() -> int:
    """Configured collection timeout, floored at a value the cdn tolerates."""
    return max(get_config().api.tsetmc_timeout, MIN_TIMEOUT_SECONDS)


@dataclass(frozen=True)
class TsetmcConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    base_url: str = field(default_factory=lambda: get_config().api.tsetmc_base_url)
    timeout: int = field(default_factory=_default_timeout)
    indicators: tuple[str, ...] = DEFAULT_INDICATORS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

    def index_history_url(self, ins_code: str) -> str:
        """Fully-resolved raw cdn endpoint for one index."""
        return f"{self.base_url.rstrip('/')}/Index/GetIndexB2History/{ins_code}"


@dataclass(frozen=True)
class TsetmcIndexPayload:
    """One raw cdn index response plus the request that produced it."""

    raw: Mapping[str, Any]
    request_url: str
    http_status_code: int | None = None

    def rows(self) -> list[dict[str, Any]]:
        """The ``indexB2`` records as plain dicts (empty when malformed)."""
        data = self.raw.get("indexB2")
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]


@runtime_checkable
class TsetmcClient(Protocol):
    """
    The injectable transport seam (the package analogue of ``http_session``).

    Unit tests inject a fake so the suite never imports ``finpy_tse`` or touches
    the network; production builds the default :class:`FinpyTseClient`.
    """

    @property
    def package_version(self) -> str | None:
        """Version of the underlying package, for Bronze provenance."""
        ...

    def is_available(self) -> bool:
        """Whether the underlying package can be imported."""
        ...

    def fetch_index_history(self, ins_code: str) -> TsetmcIndexPayload:
        """Fetch the raw ``indexB2`` payload for one index."""
        ...


@dataclass
class TsetmcFetchResult:
    """A parsed series plus everything the Bronze writer needs for provenance."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: dict[str, Any]
    request_url: str
    http_status_code: int | None
    package_version: str | None
    ins_code: str

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata``."""
        return {
            "indicator_id": self.indicator_id,
            "package": PACKAGE_DISTRIBUTION,
            "package_version": self.package_version,
            "ins_code": self.ins_code,
            "rows_returned": len(self.raw_envelope.get("rows", [])),
            "rows_usable": int(len(self.frame)),
            "envelope_convention": "raw_data = {rows, meta}",
        }


class FinpyTseClient:
    """
    Default transport: the raw cdn endpoint the ``finpy-tse`` package wraps.

    The package is imported lazily on first use so constructing the connector
    never requires the optional extra; a missing package surfaces as one
    actionable :class:`ConnectionError`.
    """

    def __init__(
        self,
        config: TsetmcConfig,
        http_session: requests.Session | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Store the transport collaborators injected by the connector."""
        self.config = config
        self._http_session = http_session
        self._owns_session = http_session is None
        self._retry = retry_policy or RetryPolicy.from_config()
        self._rate_limiter = rate_limiter or RateLimiter(config.min_request_interval)
        self._module: ModuleType | None = None

    @property
    def package_version(self) -> str | None:
        """Installed ``finpy-tse`` version, or None when absent."""
        return package_version()

    def is_available(self) -> bool:
        """Whether ``finpy-tse`` can be imported."""
        return is_available()

    def close(self) -> None:
        """Close the HTTP session if this client created it."""
        if self._http_session is not None and self._owns_session:
            self._http_session.close()
            self._http_session = None

    def fetch_index_history(self, ins_code: str) -> TsetmcIndexPayload:
        """
        Fetch and return the raw ``indexB2`` payload for one index.

        Args:
            ins_code: TSETMC instrument code of the index

        Returns:
            Raw cdn JSON plus the request URL and HTTP status

        Raises:
            ConnectionError: If the optional package is missing or the request fails
            DataRetrievalError: If the payload has no ``indexB2`` array
        """
        self._load_module()
        url = self.config.index_history_url(ins_code)
        response = self._get(url)
        try:
            payload = response.json()
        except ValueError as exc:
            msg = f"TSETMC response from {url} was not valid JSON"
            raise DataRetrievalError(msg) from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("indexB2"), list):
            msg = f"TSETMC index payload for {ins_code} had no indexB2 array"
            raise DataRetrievalError(msg)
        return TsetmcIndexPayload(
            raw=payload,
            request_url=url,
            http_status_code=response.status_code,
        )

    # --------------------------------------------------------------- internals

    def _load_module(self) -> ModuleType:
        """Import ``finpy_tse`` once, or raise one actionable error."""
        if self._module is None:
            try:
                import finpy_tse
            except ImportError as exc:
                raise PlatformConnectionError(MISSING_EXTRA_MESSAGE) from exc
            self._module = finpy_tse
        return self._module

    def _ensure_session(self) -> requests.Session:
        """Return the HTTP session, creating one with the package's headers."""
        if self._http_session is None:
            session = requests.Session()
            package_headers = getattr(self._load_module(), "headers", None)
            if isinstance(package_headers, Mapping):
                session.headers.update({str(k): str(v) for k, v in package_headers.items()})
            session.headers.setdefault("User-Agent", USER_AGENT)
            session.headers.setdefault("Accept", "application/json")
            self._http_session = session
            self._owns_session = True
        return self._http_session

    def _get(self, url: str) -> requests.Response:
        """Perform one rate-limited, retried GET."""
        session = self._ensure_session()

        def operation() -> requests.Response:
            self._rate_limiter.wait()
            response = session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            return response

        try:
            return self._retry.run(operation, "TSETMC index history request", url=url)
        except HTTPError as exc:
            msg = f"TSETMC rejected the request to {url}: {exc}"
            raise PlatformConnectionError(msg) from exc


class TsetmcConnector(DataConnector):
    """Connector for the TSETMC cdn index endpoints (TEDPIX)."""

    def __init__(
        self,
        config: TsetmcConfig | None = None,
        client: TsetmcClient | None = None,
        http_session: requests.Session | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """
        Initialize the connector.

        Args:
            config: Connector configuration; defaults come from ``AppConfig``
            client: Injected transport (unit tests pass a fake); defaults to
                :class:`FinpyTseClient`
            http_session: Session for the default client (tests inject a fake)
            retry_policy: Retry policy for the default client
            rate_limiter: Request spacing for the default client
        """
        super().__init__(source_name=SOURCE_NAME)
        self.config = config or TsetmcConfig()
        self._retry = retry_policy or RetryPolicy.from_config()
        self._rate_limiter = rate_limiter or RateLimiter(self.config.min_request_interval)
        self._owns_client = client is None
        self._client: TsetmcClient = client or FinpyTseClient(
            config=self.config,
            http_session=http_session,
            retry_policy=self._retry,
            rate_limiter=self._rate_limiter,
        )

    @property
    def client(self) -> TsetmcClient:
        """The active transport, exposed for tests and diagnostics."""
        return self._client

    def connect(self) -> bool:
        """
        Verify the optional package is importable and probe the cdn endpoint.

        Returns:
            True when the probe returns a usable ``indexB2`` payload

        Raises:
            ConnectionError: If the extra is missing or the endpoint is unreachable
        """
        if not self._client.is_available():
            raise PlatformConnectionError(MISSING_EXTRA_MESSAGE)

        probe = self._probe_indicator()
        try:
            payload = self._client.fetch_index_history(probe.ins_code)
        except PlatformConnectionError:
            raise
        except (DataRetrievalError, ParsingError) as exc:
            msg = f"TSETMC cdn unreachable for {probe.indicator_id}: {exc}"
            raise PlatformConnectionError(msg) from exc

        reachable = bool(payload.rows())
        log_with_context(
            logger,
            "INFO" if reachable else "WARNING",
            "tsetmc connectivity probe",
            indicator_id=probe.indicator_id,
            url=payload.request_url,
            http_status_code=payload.http_status_code,
            rows=len(payload.rows()),
            reachable=reachable,
        )
        return reachable

    def discover(self) -> list[IndicatorMetadata]:
        """
        Describe every configured indicator from the committed registry.

        ``availability_start`` / ``availability_end`` stay None: coverage is
        filled in by the pipeline from the observations it actually stores.

        Returns:
            One :class:`IndicatorMetadata` per configured indicator
        """
        discovered: list[IndicatorMetadata] = []
        for indicator_id in self.config.indicators:
            registry = TSETMC_INDICATORS.get(indicator_id)
            if registry is None:
                logger.warning("Unknown TSETMC indicator %s, skipping", indicator_id)
                continue
            discovered.append(
                IndicatorMetadata(
                    indicator_id=indicator_id,
                    name=registry.name,
                    description=None,
                    unit=registry.unit[:UNIT_MAX_LENGTH],
                    frequency=FREQUENCY_DAILY,
                    domain=registry.domain,
                    source_name=self.source_name,
                    source_url=self.config.index_history_url(registry.ins_code),
                    availability_start=None,
                    availability_end=None,
                    has_base_year_changes=False,
                    base_years=None,
                )
            )
        return discovered

    def fetch(self, indicator_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch one indicator's series as a DataFrame.

        The cdn endpoint returns the full history; the ABC's date arguments
        exist for protocol conformance only and are ignored (Gold handles any
        windowing).

        Args:
            indicator_id: Platform indicator id
            start_date: Ignored
            end_date: Ignored

        Returns:
            DataFrame with columns timestamp, value, indicator_id, unit, obs_status
        """
        del start_date, end_date
        return self.fetch_series(indicator_id).frame

    def fetch_series(self, indicator_id: str) -> TsetmcFetchResult:
        """
        Fetch one index's full history as raw cdn rows plus a normalized frame.

        Args:
            indicator_id: Platform indicator id

        Returns:
            Parsed frame plus the raw ``indexB2`` envelope and provenance

        Raises:
            DataRetrievalError: If the indicator is not registered
        """
        registry = TSETMC_INDICATORS.get(indicator_id)
        if registry is None:
            msg = f"TSETMC indicator {indicator_id} is not registered"
            raise DataRetrievalError(msg)

        payload = self._client.fetch_index_history(registry.ins_code)
        rows = payload.rows()
        frame = tsetmc_parser(rows, indicator_id, registry.unit)

        meta = {
            "indicator_id": indicator_id,
            "ins_code": registry.ins_code,
            "frequency": FREQUENCY_DAILY,
            "package": PACKAGE_DISTRIBUTION,
            "package_version": self._client.package_version,
            "rows_returned": len(rows),
            "rows_usable": int(len(frame)),
        }
        raw_envelope = {"rows": rows, "meta": meta}

        log_with_context(
            logger,
            "INFO",
            "tsetmc series fetched",
            indicator_id=indicator_id,
            ins_code=registry.ins_code,
            rows_returned=len(rows),
            rows_usable=int(len(frame)),
        )

        return TsetmcFetchResult(
            indicator_id=indicator_id,
            frame=frame,
            raw_envelope=raw_envelope,
            request_url=payload.request_url,
            http_status_code=payload.http_status_code,
            package_version=self._client.package_version,
            ins_code=registry.ins_code,
        )

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate a fetched index series.

        Runs the shared quality checks, then rejects non-positive index levels
        (TEDPIX is a positive chained level).

        Args:
            data: DataFrame produced by :meth:`fetch`

        Returns:
            Quality report with a positivity error when any level is ``<= 0``
        """
        result = validate_data_quality(data)
        if "value" in data.columns:
            non_positive = int((data["value"].dropna() <= 0).sum())
            if non_positive:
                result.errors.append(f"{non_positive} TSETMC index observation(s) are not positive")
                result.is_valid = False
        return result

    def disconnect(self) -> None:
        """Close the default client (an injected client is the caller's to close)."""
        if not self._owns_client:
            return
        closer = getattr(self._client, "close", None)
        if callable(closer):
            closer()

    # --------------------------------------------------------------- internals

    def _probe_indicator(self) -> TsetmcIndicator:
        """First configured registered indicator, for the connectivity probe."""
        for indicator_id in self.config.indicators:
            registry = TSETMC_INDICATORS.get(indicator_id)
            if registry is not None:
                return registry
        return next(iter(TSETMC_INDICATORS.values()))


def build_spec() -> Any:
    """Build the pipeline ``SourceSpec`` for TSETMC (local import avoids a cycle)."""
    from src.etl.pipeline import IndicatorDerivation, SourceSpec

    return SourceSpec(
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        frequency=FREQUENCY_DAILY,
        derived_prefix=DERIVED_PREFIX,
        indicators=DEFAULT_INDICATORS,
        default_derivation=IndicatorDerivation(
            derivation_strategy="daily",
            include_growth=True,
            include_monthly=True,
        ),
        parser=tsetmc_parser,
    )


def run_tsetmc_pipeline(
    indicators: Sequence[str] | None = None,
    dry_run: bool = False,
    connector: TsetmcConnector | None = None,
) -> Any:  # Returns PipelineSummary from src.etl.pipeline
    """
    Collect TSETMC daily index history into Bronze, Silver, and Gold.

    Programmatic entry point for orchestrators (the Airflow DAG) and scripts:
    it builds the connector + ``SourceSpec`` and hands the run to the shared
    :func:`src.etl.pipeline.run_pipeline`. No ingestion logic lives here.

    Args:
        indicators: Indicator ids to collect; defaults to the connector registry
        dry_run: Fetch and report without opening a session or writing a row
        connector: Pre-built connector (tests inject one with a fake client)

    Returns:
        Per-indicator outcomes plus an aggregate exit code

    Raises:
        ConnectionError: If the TSETMC cdn cannot be reached at all
    """
    from dataclasses import replace

    from src.database.connection import get_db, init_database
    from src.etl.pipeline import run_pipeline

    owns_connector = connector is None
    if connector is None:
        config = TsetmcConfig()
        if indicators:
            config = replace(config, indicators=tuple(indicators))
        connector = TsetmcConnector(config=config)
    elif indicators:
        connector.config = replace(connector.config, indicators=tuple(indicators))

    # run_cli normally initializes the shared database singleton; callers that
    # bypass it (the DAG) still need one engine before the first get_db().
    if not dry_run:
        try:
            get_db()
        except RuntimeError:
            app_config = get_config()
            init_database(app_config.database.url, echo=app_config.debug)

    try:
        return run_pipeline(
            connector,
            build_spec(),
            indicators=connector.config.indicators,
            dry_run=dry_run,
        )
    finally:
        if owns_connector:
            connector.disconnect()


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the TSETMC pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any indicator failed)
    """
    from dataclasses import replace

    from src.etl.pipeline import run_cli

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.tsetmc",
        description="Collect TSETMC daily index history into Bronze/Silver/Gold.",
    )
    parser.add_argument(
        "--indicators",
        help=f"Comma-separated indicator codes (default: all {len(DEFAULT_INDICATORS)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report without writing to the database",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Ignored: the cdn returns full history (accepted for parity)",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Ignored: the cdn returns full history (accepted for parity)",
    )
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    args = parser.parse_args(argv)

    selected = (
        tuple(code.strip() for code in args.indicators.split(",") if code.strip())
        if args.indicators
        else None
    )
    config = TsetmcConfig()
    if selected:
        config = replace(config, indicators=selected)
    connector = TsetmcConnector(config=config)
    return run_cli(
        indicators=selected,
        dry_run=args.dry_run,
        log_level=args.log_level,
        connector=connector,
        spec=build_spec(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
