"""
IMF DataMapper connector: annual WEO history plus five-year projections.

Fetches ``https://www.imf.org/external/datamapper/api/v1``-style endpoints. The
connector is deliberately thin: parsing lives in :mod:`src.connectors.imf_parser`
and persistence lives in :mod:`src.etl.pipeline`.

Observed API behaviour this module has to absorb (probed 2026-09-12)
--------------------------------------------------------------------
* ``/indicators`` returns ``{"indicators": {CODE: {label, description, source,
  unit, dataset, last-modified}}}`` (132 codes, WEO April 2026 vintage).
* ``/indicators`` is used for discovery **and** for the WEO vintage: the data
  payload itself carries no ``source``, so the vintage comes from here.
* The country path is **ignored**: ``/NGDP_RPCH/IRN`` returns the same
  229-country payload as ``/NGDP_RPCH``, so Iran is selected client-side.
* The ``periods`` query parameter is **ignored**: the full series is returned
  regardless. There is no server-side filtering, so :meth:`fetch` ignores its
  date range and the whole series is stored.
* An invalid indicator returns **HTTP 200** with only an ``api`` key (no
  ``values``), so a missing ``values[code]`` is treated as a retrieval error.
* ``values`` contains an empty-string key mapped to ``null``; the parser skips
  it.

Forecast semantics
------------------
The API does not label projections. This connector classifies years against the
WEO vintage parsed from ``source`` (actual / estimate / forecast) -- a project
convention documented in :mod:`src.connectors.imf_parser`. Forecast rows are
future-dated by design and are retained through Silver and Gold via the generic
runner's ``supports_forecasts`` flag.
"""

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from src.connectors.base import DataConnector, IndicatorMetadata
from src.connectors.imf_parser import (
    OBSERVATION_FORECAST,
    flatten_values,
    imf_parser,
    parse_indicator_metadata,
    vintage_year,
)
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.logging import get_logger, log_with_context
from src.utils.periods import FREQUENCY_ANNUAL
from src.utils.retry import RateLimiter, RetryPolicy
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "imf"
SOURCE_TYPE = "api"

DEFAULT_COUNTRY = "IRN"
DERIVED_PREFIX = "IMF"
MIN_TIMEOUT_SECONDS = 30
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.5
UNIT_MAX_LENGTH = 50

USER_AGENT = "iran-macro-platform/0.1 (research; +https://github.com/ArshiaAsk)"


@dataclass(frozen=True)
class ImfIndicator:
    """Registry entry: how one IMF indicator maps onto the platform catalog."""

    indicator_id: str
    name: str
    domain: str
    unit: str
    include_growth: bool = True


# Level series (billions of USD, USD per capita) get a derived YoY. Rate series
# are already percentages and are not re-derived from (it would be meaningless).
IMF_INDICATORS: Mapping[str, ImfIndicator] = {
    "NGDP_RPCH": ImfIndicator(
        "NGDP_RPCH", "Real GDP growth", "gdp", "Annual percent change", include_growth=False
    ),
    "PCPIPCH": ImfIndicator(
        "PCPIPCH",
        "Inflation rate, average consumer prices",
        "inflation",
        "Annual percent change",
        include_growth=False,
    ),
    "NGDPD": ImfIndicator("NGDPD", "GDP, current prices", "gdp", "Billions of U.S. dollars"),
    "NGDPDPC": ImfIndicator(
        "NGDPDPC", "GDP per capita, current prices", "gdp", "U.S. dollars per capita"
    ),
    "LUR": ImfIndicator("LUR", "Unemployment rate", "welfare", "Percent", include_growth=False),
    "BCA_NGDPD": ImfIndicator(
        "BCA_NGDPD",
        "Current account balance (% of GDP)",
        "trade",
        "Percent of GDP",
        include_growth=False,
    ),
}

DEFAULT_INDICATORS: tuple[str, ...] = tuple(IMF_INDICATORS)


def _default_timeout() -> int:
    """Collection timeout, floored at the 30s these endpoints demand in practice."""
    return max(get_config().collection.timeout, MIN_TIMEOUT_SECONDS)


@dataclass
class ImfConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    base_url: str = field(default_factory=lambda: get_config().api.imf_url)
    country: str = DEFAULT_COUNTRY
    timeout: int = field(default_factory=_default_timeout)
    indicators: tuple[str, ...] = DEFAULT_INDICATORS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

    def data_url(self, indicator_id: str) -> str:
        """Fully-resolved data endpoint for one indicator."""
        return f"{self.base_url}/{indicator_id}"

    def indicators_url(self) -> str:
        """Metadata endpoint describing every available indicator."""
        return f"{self.base_url}/indicators"

    def countries_url(self) -> str:
        """Cheap endpoint used for the connectivity probe."""
        return f"{self.base_url}/countries"


@dataclass
class ImfFetchResult:
    """A parsed series plus everything the Bronze writer needs for provenance."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: dict[str, Any]
    request_url: str
    http_status_code: int
    unit: str | None
    vintage: int | None
    source: str | None
    forecast_through: int | None = None

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata``."""
        return {
            "indicator_id": self.indicator_id,
            "country": DEFAULT_COUNTRY,
            "vintage": self.vintage,
            "source": self.source,
            "unit": self.unit,
            "rows_returned": len(self.raw_envelope.get("rows", [])),
            "rows_usable": int(len(self.frame)),
            "forecast_through": self.forecast_through,
            "envelope_convention": "raw_data = {rows, meta, raw_response}",
        }


class ImfConnector(DataConnector):
    """Connector for the IMF DataMapper API."""

    def __init__(
        self,
        config: ImfConfig | None = None,
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
        self.config = config or ImfConfig()
        self._http_session = http_session
        self._owns_session = http_session is None
        self._retry = retry_policy or RetryPolicy.from_config()
        self._rate_limiter = rate_limiter or RateLimiter(self.config.min_request_interval)
        self._metadata_cache: dict[str, Mapping[str, Any]] | None = None

    # ---------------------------------------------------------------- transport

    def _ensure_session(self) -> requests.Session:
        """Return the HTTP session, creating a configured one on first use."""
        if self._http_session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
            self._http_session = session
            self._owns_session = True
        return self._http_session

    def _request(
        self, url: str, params: Mapping[str, Any] | None = None
    ) -> tuple[Any, requests.Response]:
        """
        Perform one rate-limited, retried GET and return parsed JSON.

        Args:
            url: Absolute endpoint URL
            params: Query parameters

        Returns:
            Tuple of parsed JSON payload and the response object

        Raises:
            DataRetrievalError: If every attempt failed with a transient error
            ParsingError: If the response body is not valid JSON
        """
        session = self._ensure_session()

        def operation() -> tuple[Any, requests.Response]:
            self._rate_limiter.wait()
            response = session.get(url, params=dict(params or {}), timeout=self.config.timeout)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                msg = f"IMF response from {url} was not valid JSON"
                raise ParsingError(msg) from exc
            return payload, response

        return self._retry.run(operation, "imf GET", url=url)

    def _indicator_metadata(self) -> dict[str, Mapping[str, Any]]:
        """Load and cache the ``/indicators`` map (source of units and vintage)."""
        if self._metadata_cache is None:
            payload, _ = self._request(self.config.indicators_url())
            if not isinstance(payload, Mapping):
                msg = "IMF /indicators returned an unexpected payload"
                raise ParsingError(msg)
            parsed = parse_indicator_metadata(payload)
            if not parsed:
                msg = "IMF /indicators returned no metadata"
                raise DataRetrievalError(msg)
            self._metadata_cache = parsed
        return self._metadata_cache

    # ------------------------------------------------------------- ABC protocol

    def connect(self) -> bool:
        """
        Probe the ``/countries`` endpoint to confirm the API is reachable.

        Returns:
            True when the probe returns a usable payload

        Raises:
            ConnectionError: If the API is unreachable after all retries
        """
        url = self.config.countries_url()
        try:
            payload, response = self._request(url)
        except (DataRetrievalError, ParsingError) as exc:
            msg = f"IMF API unreachable at {url}: {exc}"
            raise PlatformConnectionError(msg) from exc

        reachable = isinstance(payload, Mapping) and bool(payload.get("countries"))
        log_with_context(
            logger,
            "INFO" if reachable else "WARNING",
            "imf connectivity probe",
            url=url,
            http_status_code=response.status_code,
            reachable=reachable,
        )
        return reachable

    def discover(self) -> list[IndicatorMetadata]:
        """
        Describe every configured indicator using ``/indicators`` metadata.

        ``availability_start`` / ``availability_end`` stay None: the API does not
        report per-country coverage, so the pipeline fills them from what it
        actually stores.

        Returns:
            One :class:`IndicatorMetadata` per configured indicator

        Raises:
            DataRetrievalError: If ``/indicators`` cannot be retrieved
        """
        metadata = self._indicator_metadata()
        discovered: list[IndicatorMetadata] = []

        for indicator_id in self.config.indicators:
            registry = IMF_INDICATORS.get(indicator_id)
            if registry is None:
                logger.warning("Unknown IMF indicator %s, skipping", indicator_id)
                continue

            meta = metadata.get(indicator_id, {})
            unit = str(meta.get("unit") or registry.unit)[:UNIT_MAX_LENGTH]
            description = meta.get("description")

            discovered.append(
                IndicatorMetadata(
                    indicator_id=indicator_id,
                    name=str(meta.get("label") or registry.name),
                    description=str(description) if description else None,
                    unit=unit,
                    frequency=FREQUENCY_ANNUAL,
                    domain=registry.domain,
                    source_name=self.source_name,
                    source_url=self.config.data_url(indicator_id),
                    availability_start=None,
                    availability_end=None,
                    # WEO series are a single consistent vintage, no rebasing.
                    has_base_year_changes=False,
                    base_years=None,
                )
            )

        log_with_context(
            logger,
            "INFO",
            "imf indicators discovered",
            indicator_count=len(discovered),
            source=metadata.get(next(iter(metadata), ""), {}).get("source"),
        )
        return discovered

    def fetch(self, indicator_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch one indicator's full series as a DataFrame.

        The DataMapper ignores date filtering, so the requested range may be
        anything; the full available series is returned.

        Args:
            indicator_id: IMF indicator code
            start_date: Ignored (no server-side filtering)
            end_date: Ignored (no server-side filtering)

        Returns:
            DataFrame with columns timestamp, value, indicator_id, unit,
            obs_status, observation_type
        """
        # The DataMapper ignores date filtering; the range is part of the ABC
        # contract only. Delete the names so linters see they are intentional.
        del start_date, end_date
        return self.fetch_series(indicator_id).frame

    def fetch_series(self, indicator_id: str) -> ImfFetchResult:
        """
        Fetch one indicator and keep the raw payload for Bronze.

        Args:
            indicator_id: IMF indicator code

        Returns:
            Parsed frame plus raw envelope and request provenance

        Raises:
            DataRetrievalError: If the indicator is unknown or has no IRN series
        """
        registry = IMF_INDICATORS.get(indicator_id)
        if registry is None:
            msg = f"IMF indicator {indicator_id} is not registered"
            raise DataRetrievalError(msg)

        meta = self._indicator_metadata().get(indicator_id)
        if meta is None:
            msg = f"IMF does not publish indicator {indicator_id}"
            raise DataRetrievalError(msg)

        source = meta.get("source")
        vintage = vintage_year(source)
        unit = str(meta.get("unit") or registry.unit)[:UNIT_MAX_LENGTH]

        url = self.config.data_url(indicator_id)
        payload, response = self._request(url)
        if not isinstance(payload, Mapping):
            msg = f"unexpected IMF payload from {url}: {type(payload).__name__}"
            raise ParsingError(msg)

        values = payload.get("values")
        if not isinstance(values, Mapping) or indicator_id not in values:
            msg = f"IMF returned no values for {indicator_id}"
            raise DataRetrievalError(msg)

        rows = flatten_values(values, indicator_id, self.config.country, vintage)
        frame = imf_parser(rows, indicator_id, unit)
        forecast_years = [
            int(row["period"]) for row in rows if row["observation_type"] == OBSERVATION_FORECAST
        ]
        forecast_through = max(forecast_years) if forecast_years else None

        raw_envelope = {
            "rows": rows,
            "meta": {
                "indicator_id": indicator_id,
                "country": self.config.country,
                "vintage": vintage,
                "source": source,
                "unit": unit,
                "rows_returned": len(rows),
                "forecast_through": forecast_through,
            },
            "raw_response": payload,
        }

        log_with_context(
            logger,
            "INFO",
            "imf series fetched",
            indicator_id=indicator_id,
            rows_returned=len(rows),
            rows_usable=int(len(frame)),
            vintage=vintage,
            forecast_through=forecast_through,
        )

        return ImfFetchResult(
            indicator_id=indicator_id,
            frame=frame,
            raw_envelope=raw_envelope,
            request_url=url,
            http_status_code=response.status_code,
            unit=unit,
            vintage=vintage,
            source=str(source) if source else None,
            forecast_through=forecast_through,
        )

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate a fetched series, permitting future-dated forecast periods.

        Args:
            data: DataFrame produced by :meth:`fetch`

        Returns:
            Quality report; nulls are reported as warnings, not errors
        """
        return validate_data_quality(data, allow_future=True)

    def disconnect(self) -> None:
        """Close the HTTP session if this connector created it."""
        if self._http_session is not None and self._owns_session:
            self._http_session.close()
            self._http_session = None


def build_spec() -> Any:
    """Build the pipeline ``SourceSpec`` for IMF (local import avoids a cycle)."""
    from src.etl.pipeline import IndicatorDerivation, SourceSpec

    return SourceSpec(
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        frequency=FREQUENCY_ANNUAL,
        derived_prefix=DERIVED_PREFIX,
        indicators=DEFAULT_INDICATORS,
        supports_forecasts=True,
        parser=imf_parser,
        overrides={
            code: IndicatorDerivation(include_growth=False)
            for code, indicator in IMF_INDICATORS.items()
            if not indicator.include_growth
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the IMF pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any indicator failed)
    """
    from src.etl.pipeline import run_cli

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.imf",
        description="Collect IMF WEO indicators for Iran into Bronze/Silver/Gold.",
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
    config = ImfConfig()
    if selected:
        config.indicators = selected
    connector = ImfConnector(config=config)
    return run_cli(
        indicators=selected,
        dry_run=args.dry_run,
        log_level=args.log_level,
        connector=connector,
        spec=build_spec(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
