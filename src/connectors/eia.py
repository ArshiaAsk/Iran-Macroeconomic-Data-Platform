"""
EIA Open Data API v2 connector for monthly Iranian energy production.

Fetches ``https://api.eia.gov/v2/international/data/`` with facet filters and
paging. The connector is deliberately thin: parsing lives in
:mod:`src.connectors.eia_parser` and persistence lives in
:mod:`src.etl.pipeline`.

Observed API behaviour this module has to absorb (probed 2026-09-12)
--------------------------------------------------------------------
* **Authentication is mandatory.** A missing key returns HTTP 403
  ``{"error": {"code": "API_KEY_MISSING"}}``; an invalid one 403
  ``API_KEY_INVALID``. ``RetryPolicy`` treats every non-429 4xx as permanent, so
  auth failures surface immediately instead of being retried four times. The key
  is read from ``EIA_API_KEY`` and must never appear in Bronze provenance or
  logs.
* **Facets filter server-side.** Iran is ``facets[countryRegionId][]=IRN``;
  crude + NGPL production is ``productId=55`` and total liquids ``productId=53``
  with ``activityId=1`` ("Production").
* **``response.total`` and ``value`` are strings.** ``total`` drives the paging
  loop; ``value`` is coerced by the parser.
* **Paging is ``length`` + ``offset``** (default page 5000). Data arrives
  oldest-first when sorted, which the request does explicitly.
* **An unknown facet is HTTP 200 with ``total: "0"``** -- an empty series, not an
  error. A response object without a ``data`` list is malformed and *is* an
  error.
* **``start``/``end`` are inclusive ``YYYY-MM`` bounds.** Without them the Iran
  crude series reaches back to 1993 (401 months); the platform defaults to a
  recent window (``2024-01``) matching the Phase 4 scope.
"""

import argparse
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests
from requests import HTTPError

from src.connectors.base import DataConnector, IndicatorMetadata
from src.connectors.eia_parser import eia_parser
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.logging import get_logger, log_with_context
from src.utils.periods import FREQUENCY_MONTHLY
from src.utils.retry import RateLimiter, RetryPolicy
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "eia"
SOURCE_TYPE = "api"
DERIVED_PREFIX = "EIA"

DEFAULT_COUNTRY = "IRN"
DEFAULT_START = "2024-01"
DEFAULT_PAGE_LENGTH = 5000
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.5
MIN_TIMEOUT_SECONDS = 30
UNIT_MAX_LENGTH = 50

# Runaway guard: the series under study is ~29 months, but paging is real.
MAX_PAGES = 100

ROUTE = "international/data/"
AUTH_ERROR_STATUS = 403
PLACEHOLDER_API_KEY = "your_eia_api_key_here"

USER_AGENT = "iran-macro-platform/0.1 (research; +https://github.com/ArshiaAsk)"

DEFAULT_UNIT = "thousand barrels per day"


@dataclass(frozen=True)
class EiaIndicator:
    """Registry entry: how one EIA series maps onto the platform catalog."""

    indicator_id: str
    name: str
    domain: str
    product_id: str
    activity_id: str
    unit: str = DEFAULT_UNIT


# EIA's international "Petroleum and other liquids" production facets for Iran.
EIA_INDICATORS: Mapping[str, EiaIndicator] = {
    "EIA.IRN.CRUDE_PRODUCTION": EiaIndicator(
        indicator_id="EIA.IRN.CRUDE_PRODUCTION",
        name="Crude oil, NGPL, and other liquids production",
        domain="energy",
        product_id="55",
        activity_id="1",
    ),
    "EIA.IRN.TOTAL_LIQUIDS": EiaIndicator(
        indicator_id="EIA.IRN.TOTAL_LIQUIDS",
        name="Total petroleum and other liquids production",
        domain="energy",
        product_id="53",
        activity_id="1",
    ),
}

DEFAULT_INDICATORS: tuple[str, ...] = tuple(EIA_INDICATORS)


def is_configured(api_key: str | None) -> bool:
    """
    Report whether an EIA API key is usable.

    The ``.env.example`` placeholder, an empty/whitespace value, and ``None`` all
    mean "not configured" so the run aborts once with an actionable message
    rather than failing every indicator with a 403.

    Args:
        api_key: Configured key

    Returns:
        True when the key looks like a real value
    """
    if api_key is None:
        return False
    stripped = api_key.strip()
    return bool(stripped) and stripped != PLACEHOLDER_API_KEY


def _default_timeout() -> int:
    """Collection timeout, floored at a value these endpoints tolerate."""
    return max(get_config().collection.timeout, MIN_TIMEOUT_SECONDS)


def _missing_key_message() -> str:
    """Actionable error text shown when ``EIA_API_KEY`` is absent."""
    return (
        "EIA API key is not configured. Set EIA_API_KEY in your .env "
        "(register at https://www.eia.gov/opendata/register.php); "
        f"the placeholder {PLACEHOLDER_API_KEY!r} does not count."
    )


@dataclass
class EiaConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    api_key: str | None = field(default_factory=lambda: get_config().api.eia_api_key)
    base_url: str = field(default_factory=lambda: get_config().api.eia_url)
    country: str = DEFAULT_COUNTRY
    indicators: tuple[str, ...] = DEFAULT_INDICATORS
    page_length: int = DEFAULT_PAGE_LENGTH
    start: str | None = DEFAULT_START
    end: str | None = None
    timeout: int = field(default_factory=_default_timeout)
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

    def data_url(self) -> str:
        """Fully-resolved international data endpoint."""
        return f"{self.base_url.rstrip('/')}/{ROUTE}"


@dataclass
class EiaFetchResult:
    """A parsed series plus everything the Bronze writer needs for provenance."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: dict[str, Any]
    request_url: str
    http_status_code: int
    pages_fetched: int
    unit: str | None
    total_reported: int | None = None
    country: str = DEFAULT_COUNTRY

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata`` (never the API key)."""
        return {
            "indicator_id": self.indicator_id,
            "country": self.country,
            "pages_fetched": self.pages_fetched,
            "rows_returned": len(self.raw_envelope.get("rows", [])),
            "rows_usable": int(len(self.frame)),
            "total_reported": self.total_reported,
            "envelope_convention": "raw_data = {rows, meta, raw_response}",
        }


class EiaConnector(DataConnector):
    """Connector for the EIA Open Data API v2 international dataset."""

    def __init__(
        self,
        config: EiaConfig | None = None,
        http_session: requests.Session | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """
        Initialize the connector.

        Args:
            config: Connector configuration; defaults come from ``AppConfig``
            http_session: Pre-built session (unit tests inject a fake)
            retry_policy: Retry policy; defaults to one built from config
            rate_limiter: Request spacing; defaults to the configured interval
        """
        super().__init__(source_name=SOURCE_NAME)
        self.config = config or EiaConfig()
        self._http_session = http_session
        self._owns_session = http_session is None
        self._retry = retry_policy or RetryPolicy.from_config()
        self._rate_limiter = rate_limiter or RateLimiter(self.config.min_request_interval)

    # ---------------------------------------------------------------- transport

    def _ensure_session(self) -> requests.Session:
        """Return the HTTP session, creating a configured one on first use."""
        if self._http_session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
            self._http_session = session
            self._owns_session = True
        return self._http_session

    def _request(self, url: str, params: Mapping[str, Any]) -> tuple[Any, requests.Response]:
        """
        Perform one rate-limited, retried GET and return parsed JSON.

        Args:
            url: Absolute endpoint URL
            params: Query parameters (including the API key)

        Returns:
            Tuple of parsed JSON payload and the response object

        Raises:
            PlatformConnectionError: On an authentication rejection (403)
            DataRetrievalError: If every attempt failed with a transient error
            ParsingError: If the response body is not valid JSON
        """
        session = self._ensure_session()

        def operation() -> tuple[Any, requests.Response]:
            self._rate_limiter.wait()
            response = session.get(url, params=dict(params), timeout=self.config.timeout)
            try:
                response.raise_for_status()
            except HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status == AUTH_ERROR_STATUS:
                    msg = f"EIA rejected the API key (HTTP 403): {_error_detail(response)}"
                    raise PlatformConnectionError(msg) from exc
                # requests embeds the prepared URL -- api_key included -- in its
                # HTTPError text, which would otherwise reach retry logs and the
                # run report. Re-raise with the credential scrubbed.
                msg = _scrub_api_key(str(exc), self.config.api_key)
                raise HTTPError(msg, response=exc.response, request=exc.request) from exc
            try:
                payload = response.json()
            except ValueError as exc:
                msg = f"EIA response from {url} was not valid JSON"
                raise ParsingError(msg) from exc
            return payload, response

        return self._retry.run(operation, "eia GET", url=url)

    # ------------------------------------------------------------- ABC protocol

    def connect(self) -> bool:
        """
        Validate the API key and probe the data endpoint.

        Returns:
            True when the probe returns a usable payload

        Raises:
            ConnectionError: If the key is absent/placeholder or rejected
        """
        if not is_configured(self.config.api_key):
            raise PlatformConnectionError(_missing_key_message())

        url = self.config.data_url()
        params = self._params(self._probe_indicator(), offset=0, length=1)
        try:
            payload, response = self._request(url, params)
        except PlatformConnectionError:
            raise
        except (DataRetrievalError, ParsingError) as exc:
            msg = f"EIA API unreachable at {url}: {exc}"
            raise PlatformConnectionError(msg) from exc

        reachable = isinstance(payload, Mapping) and isinstance(payload.get("response"), Mapping)
        log_with_context(
            logger,
            "INFO" if reachable else "WARNING",
            "eia connectivity probe",
            url=url,
            http_status_code=response.status_code,
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
            registry = EIA_INDICATORS.get(indicator_id)
            if registry is None:
                logger.warning("Unknown EIA indicator %s, skipping", indicator_id)
                continue
            discovered.append(
                IndicatorMetadata(
                    indicator_id=indicator_id,
                    name=registry.name,
                    description=None,
                    unit=registry.unit[:UNIT_MAX_LENGTH],
                    frequency=FREQUENCY_MONTHLY,
                    domain=registry.domain,
                    source_name=self.source_name,
                    source_url=self.config.data_url(),
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

        The configured ``start``/``end`` bounds win; the ABC's date arguments
        exist for protocol conformance only.

        Args:
            indicator_id: Platform indicator id
            start_date: Ignored in favour of ``EiaConfig.start``
            end_date: Ignored in favour of ``EiaConfig.end``

        Returns:
            DataFrame with columns timestamp, value, indicator_id, unit, obs_status
        """
        del start_date, end_date
        return self.fetch_series(indicator_id).frame

    def fetch_series(self, indicator_id: str) -> EiaFetchResult:
        """
        Fetch one indicator, paging until ``response.total`` is reached.

        Args:
            indicator_id: Platform indicator id

        Returns:
            Parsed frame plus raw envelope and request provenance

        Raises:
            PlatformConnectionError: If the API key is absent/placeholder
            DataRetrievalError: If the indicator is unknown or the payload is malformed
        """
        registry = EIA_INDICATORS.get(indicator_id)
        if registry is None:
            msg = f"EIA indicator {indicator_id} is not registered"
            raise DataRetrievalError(msg)
        if not is_configured(self.config.api_key):
            raise PlatformConnectionError(_missing_key_message())

        url = self.config.data_url()
        rows: list[Mapping[str, Any]] = []
        raw_pages: list[Any] = []
        status_code = 0
        total_reported: int | None = None
        page = 0

        while page < MAX_PAGES:
            params = self._params(registry, offset=len(rows), length=self.config.page_length)
            payload, response = self._request(url, params)
            status_code = response.status_code
            raw_pages.append(payload)
            page += 1

            response_block = payload.get("response") if isinstance(payload, Mapping) else None
            if not isinstance(response_block, Mapping):
                msg = f"EIA response from {url} had no response object"
                raise ParsingError(msg)
            data = response_block.get("data")
            if not isinstance(data, list):
                msg = f"EIA response for {indicator_id} had no data array"
                raise DataRetrievalError(msg)

            if total_reported is None:
                total_reported = _as_int(response_block.get("total"))

            rows.extend(row for row in data if isinstance(row, Mapping))
            if not data or len(data) < self.config.page_length:
                break
            if total_reported is not None and len(rows) >= total_reported:
                break

        unit = registry.unit
        frame = eia_parser(rows, indicator_id, unit)

        meta = {
            "indicator_id": indicator_id,
            "country": self.config.country,
            "product_id": registry.product_id,
            "activity_id": registry.activity_id,
            "frequency": FREQUENCY_MONTHLY,
            "start": self.config.start,
            "end": self.config.end,
            "pages_fetched": page,
            "rows_returned": len(rows),
            "rows_usable": int(len(frame)),
            "total_reported": total_reported,
        }
        raw_envelope = {"rows": list(rows), "meta": meta, "raw_response": raw_pages}

        log_with_context(
            logger,
            "INFO",
            "eia series fetched",
            indicator_id=indicator_id,
            rows_returned=len(rows),
            rows_usable=int(len(frame)),
            pages_fetched=page,
            total_reported=total_reported,
        )

        return EiaFetchResult(
            indicator_id=indicator_id,
            frame=frame,
            raw_envelope=raw_envelope,
            request_url=self._public_url(registry),
            http_status_code=status_code,
            pages_fetched=page,
            unit=unit,
            total_reported=total_reported,
            country=self.config.country,
        )

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate a fetched series with the shared quality checks.

        Args:
            data: DataFrame produced by :meth:`fetch`

        Returns:
            Quality report; nulls are reported as warnings, not errors
        """
        return validate_data_quality(data)

    def disconnect(self) -> None:
        """Close the HTTP session if this connector created it."""
        if self._http_session is not None and self._owns_session:
            self._http_session.close()
            self._http_session = None

    # --------------------------------------------------------------- internals

    def _probe_indicator(self) -> EiaIndicator:
        """First registered indicator among the configured ones, for the probe."""
        for indicator_id in self.config.indicators:
            registry = EIA_INDICATORS.get(indicator_id)
            if registry is not None:
                return registry
        return next(iter(EIA_INDICATORS.values()))

    def _params(self, indicator: EiaIndicator, offset: int, length: int) -> dict[str, Any]:
        """Build one page's query parameters (API key included)."""
        params: dict[str, Any] = {
            "frequency": FREQUENCY_MONTHLY,
            "data[0]": "value",
            "facets[countryRegionId][]": self.config.country,
            "facets[productId][]": indicator.product_id,
            "facets[activityId][]": indicator.activity_id,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": length,
            "offset": offset,
            "api_key": self.config.api_key,
        }
        if self.config.start:
            params["start"] = self.config.start
        if self.config.end:
            params["end"] = self.config.end
        return params

    def _public_url(self, indicator: EiaIndicator) -> str:
        """Request URL with the API key stripped, for safe Bronze provenance."""
        params = self._params(indicator, offset=0, length=self.config.page_length)
        params.pop("api_key", None)
        return f"{self.config.data_url()}?{urllib.parse.urlencode(params)}"


def _scrub_api_key(message: str, api_key: str | None) -> str:
    """Replace a credential with a placeholder before it is logged or raised."""
    if not api_key:
        return message
    return message.replace(api_key, "***")


def _as_int(value: Any) -> int | None:
    """Best-effort conversion of the string ``response.total`` to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _error_detail(response: requests.Response) -> str:
    """Extract the EIA error code/message from a failed response, if present."""
    try:
        payload = response.json()
    except ValueError:
        return "unparseable error body"
    if not isinstance(payload, Mapping):
        return "unparseable error body"
    error = payload.get("error")
    if isinstance(error, Mapping):
        code = error.get("code", "UNKNOWN")
        message = error.get("message", "")
        return f"{code}: {message}".strip()
    return "unknown error"


def build_spec() -> Any:
    """Build the pipeline ``SourceSpec`` for EIA (local import avoids a cycle)."""
    from src.etl.pipeline import IndicatorDerivation, SourceSpec

    return SourceSpec(
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        frequency=FREQUENCY_MONTHLY,
        derived_prefix=DERIVED_PREFIX,
        indicators=DEFAULT_INDICATORS,
        default_derivation=IndicatorDerivation(include_growth=True),
        parser=eia_parser,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the EIA pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any indicator failed)
    """
    from src.etl.pipeline import run_cli

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.eia",
        description="Collect EIA monthly Iranian energy production into Bronze/Silver/Gold.",
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
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    args = parser.parse_args(argv)

    selected = (
        tuple(code.strip() for code in args.indicators.split(",") if code.strip())
        if args.indicators
        else None
    )
    config = EiaConfig()
    if selected:
        config.indicators = selected
    connector = EiaConnector(config=config)
    return run_cli(
        indicators=selected,
        dry_run=args.dry_run,
        log_level=args.log_level,
        connector=connector,
        spec=build_spec(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
