"""
World Bank Indicators API v2 connector.

Fetches Iran's annual macroeconomic series from
``https://api.worldbank.org/v2/country/IRN/indicator/{id}``.

Observed API behaviour this module has to absorb
-----------------------------------------------
* The response is a JSON **array** ``[meta, rows]``, not an object.
* Rows arrive **newest-first**; callers get them sorted ascending.
* ``date`` is a **year string** for annual series, converted to
  ``datetime(year, 12, 31, tzinfo=UTC)`` -- the end of the period.
* ``value`` is nullable. Nulls are kept here so :meth:`validate` can measure the
  real null percentage; the Silver transformer drops them.
* An invalid indicator returns **HTTP 200** with a ``message`` payload, so
  ``raise_for_status()`` alone is not enough.
* The observation-level ``unit`` is always ``""``. The indicator endpoint's
  ``unit`` is empty too, so the unit is recovered from the trailing parenthetical
  of the indicator name (``GDP (current US$)`` -> ``current US$``).
* Requests can be slow -- one probe timed out at 25s -- hence a >=30s timeout
  plus retry with backoff.

This module never touches the database: Bronze persistence is :mod:`src.etl.bronze`.
"""

import argparse
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

import pandas as pd
import requests

from src.connectors.base import DataConnector, IndicatorMetadata
from src.database.schema import utc_now
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.logging import get_logger, log_with_context
from src.utils.retry import RateLimiter, RetryPolicy
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "world_bank"
SOURCE_TYPE = "api"
FREQUENCY_ANNUAL = "annual"

DEFAULT_COUNTRY = "IRN"
# One page is enough for a 66-year annual series; pagination is still handled.
DEFAULT_PER_PAGE = 20000
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.5
MIN_TIMEOUT_SECONDS = 30
EARLIEST_YEAR = 1960
# Runaway guard in case `meta.pages` is ever inconsistent with reality.
MAX_PAGES = 100

USER_AGENT = "iran-macro-platform/0.1 (research; +https://github.com/ArshiaAsk)"

# silver.unit / gold.unit / metadata.indicator_catalog.unit are String(50).
UNIT_MAX_LENGTH = 50
DEFAULT_DOMAIN = "unclassified"
ANNUAL_DATE_LENGTH = 4
ENVELOPE_LENGTH = 2

FRAME_COLUMNS = ("timestamp", "value", "indicator_id", "unit", "obs_status")

# Indicator registry: World Bank code -> analytical domain. Domains follow the
# PRD taxonomy (gdp, inflation, trade, monetary, energy, welfare); population
# series are grouped under `welfare` and energy use under `energy`.
INDICATOR_DOMAINS: Mapping[str, str] = MappingProxyType(
    {
        "NY.GDP.MKTP.CD": "gdp",
        "NY.GDP.MKTP.KD": "gdp",
        "NY.GDP.MKTP.KN": "gdp",
        "NY.GDP.MKTP.KD.ZG": "gdp",
        "NY.GDP.PCAP.KD": "gdp",
        "FP.CPI.TOTL.ZG": "inflation",
        "NE.EXP.GNFS.CD": "trade",
        "NE.IMP.GNFS.CD": "trade",
        "NE.RSB.GNFS.CD": "trade",
        "SP.POP.TOTL": "welfare",
        "SP.POP.GROW": "welfare",
        # Discontinued for Iran after 2014 -- kept as a documented sparse series
        # so the pipeline is exercised against real gaps.
        "EG.USE.PCAP.KG.OE": "energy",
    }
)

DEFAULT_INDICATORS: tuple[str, ...] = tuple(INDICATOR_DOMAINS)


def domain_for(indicator_id: str) -> str:
    """
    Look up the analytical domain of a World Bank indicator.

    Args:
        indicator_id: World Bank indicator code

    Returns:
        Registered domain, or ``unclassified`` for unknown codes
    """
    return INDICATOR_DOMAINS.get(indicator_id, DEFAULT_DOMAIN)


def _default_timeout() -> int:
    """Collection timeout, floored at the 30s the API demands in practice."""
    return max(get_config().collection.timeout, MIN_TIMEOUT_SECONDS)


def _default_date_range() -> tuple[int, int]:
    """Full available history: 1960 through the current calendar year."""
    return (EARLIEST_YEAR, utc_now().year)


@dataclass
class WorldBankConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    base_url: str = field(default_factory=lambda: get_config().api.world_bank_url)
    country: str = DEFAULT_COUNTRY
    per_page: int = DEFAULT_PER_PAGE
    timeout: int = field(default_factory=_default_timeout)
    date_range: tuple[int, int] = field(default_factory=_default_date_range)
    indicators: tuple[str, ...] = DEFAULT_INDICATORS
    min_request_interval: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

    def data_url(self, indicator_id: str) -> str:
        """Fully-resolved data endpoint for one indicator."""
        return f"{self.base_url}/country/{self.country}/indicator/{indicator_id}"

    def indicator_url(self, indicator_id: str) -> str:
        """Metadata endpoint for one indicator."""
        return f"{self.base_url}/indicator/{indicator_id}"


@dataclass
class WorldBankFetchResult:
    """A parsed series plus everything the Bronze writer needs for provenance."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: list[Any]
    request_url: str
    http_status_code: int
    pages_fetched: int
    unit: str | None
    source_last_updated: str | None = None
    total_reported: int | None = None

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata``."""
        return {
            "indicator_id": self.indicator_id,
            "country": DEFAULT_COUNTRY,
            "pages_fetched": self.pages_fetched,
            "rows_returned": len(self.raw_envelope[1]) if len(self.raw_envelope) > 1 else 0,
            "rows_usable": int(len(self.frame)),
            "source_last_updated": self.source_last_updated,
            "total_reported": self.total_reported,
            "envelope_convention": "raw_data = {meta, rows}",
        }


def extract_unit(api_unit: str | None, indicator_name: str) -> str | None:
    """
    Recover a usable unit string for an indicator.

    The API supplies an empty ``unit`` at both the observation and indicator
    level, so the trailing parenthetical of the indicator name is used instead.

    Args:
        api_unit: ``unit`` field as returned by the API (usually ``""``)
        indicator_name: Human-readable indicator name

    Returns:
        Unit truncated to the column width, or None when none can be derived
    """
    if api_unit and api_unit.strip():
        return api_unit.strip()[:UNIT_MAX_LENGTH]

    match = re.search(r"\(([^()]+)\)\s*$", indicator_name or "")
    if match:
        return match.group(1).strip()[:UNIT_MAX_LENGTH] or None
    return None


def _error_message(payload: Any) -> str | None:
    """Return the API's error text when ``payload`` is an error envelope."""
    head: Any = None
    if isinstance(payload, list) and payload:
        head = payload[0]
    elif isinstance(payload, dict):
        head = payload

    if not isinstance(head, dict) or "message" not in head:
        return None
    messages = head.get("message")
    if not messages:
        return None
    if isinstance(messages, list) and messages and isinstance(messages[0], dict):
        first = messages[0]
        return f"{first.get('key', 'error')}: {first.get('value', '')}".strip()
    return str(messages)


def _parse_annual_timestamp(date_value: Any) -> datetime:
    """
    Convert a World Bank annual ``date`` field to a period-end timestamp.

    Args:
        date_value: Year as returned by the API, e.g. ``"2022"``

    Returns:
        December 31 of that year, timezone-aware in UTC

    Raises:
        ParsingError: If the value is not a bare four-digit year
    """
    text = str(date_value).strip()
    if len(text) != ANNUAL_DATE_LENGTH or not text.isdigit():
        msg = f"expected a four-digit annual date, got {date_value!r}"
        raise ParsingError(msg)
    return datetime(int(text), 12, 31, tzinfo=UTC)


def _coerce_value(raw_value: Any) -> float | None:
    """Convert an observation value to float, preserving nulls as None."""
    if raw_value is None or raw_value == "":
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"non-numeric observation value {raw_value!r}"
        raise ParsingError(msg) from exc


def empty_frame() -> pd.DataFrame:
    """An empty series frame with the connector's column contract."""
    return pd.DataFrame(
        {
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "value": pd.Series(dtype="float64"),
            "indicator_id": pd.Series(dtype="object"),
            "unit": pd.Series(dtype="object"),
            "obs_status": pd.Series(dtype="object"),
        }
    )


def rows_to_frame(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Convert raw observation rows into the connector's DataFrame contract.

    Nulls are preserved, rows are sorted ascending by period end, and periods
    that have not finished yet are dropped (a future timestamp would make
    ``validate_date_range`` fail).

    Args:
        rows: Observation objects from the API envelope
        indicator_id: Indicator these rows belong to
        unit: Resolved unit for the series
        now: Clock override for the future-period cutoff

    Returns:
        DataFrame with columns timestamp, value, indicator_id, unit, obs_status
    """
    if not rows:
        return empty_frame()

    cutoff = now or utc_now()
    records = [
        {
            "timestamp": _parse_annual_timestamp(row.get("date")),
            "value": _coerce_value(row.get("value")),
            "indicator_id": indicator_id,
            "unit": unit,
            "obs_status": row.get("obs_status") or None,
        }
        for row in rows
    ]

    frame = pd.DataFrame.from_records(records, columns=list(FRAME_COLUMNS))
    frame["value"] = frame["value"].astype("float64")
    frame = frame[frame["timestamp"] <= cutoff]
    return frame.sort_values("timestamp").reset_index(drop=True)


class WorldBankConnector(DataConnector):
    """Connector for the World Bank Indicators API v2."""

    def __init__(
        self,
        config: WorldBankConfig | None = None,
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
        self.config = config or WorldBankConfig()
        self._http_session = http_session
        self._owns_session = http_session is None
        self._retry = retry_policy or RetryPolicy.from_config()
        self._rate_limiter = rate_limiter or RateLimiter(self.config.min_request_interval)
        self._unit_cache: dict[str, str | None] = {}

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
        Perform one rate-limited, retried GET and return the parsed payload.

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
            response = session.get(url, params=dict(params), timeout=self.config.timeout)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                msg = f"World Bank response from {url} was not valid JSON"
                raise ParsingError(msg) from exc
            return payload, response

        return self._retry.run(operation, "world_bank GET", url=url)

    def _request_envelope(
        self, url: str, params: Mapping[str, Any]
    ) -> tuple[
        dict[str, Any],
        list[Any],
        requests.Response,
    ]:
        """
        Fetch one page and split it into ``(meta, rows, response)``.

        Raises:
            DataRetrievalError: On an API error payload returned with HTTP 200
            ParsingError: If the envelope is not the documented ``[meta, rows]``
        """
        payload, response = self._request(url, params)

        error = _error_message(payload)
        if error:
            msg = f"World Bank API rejected {url}: {error}"
            raise DataRetrievalError(msg)

        if not isinstance(payload, list) or len(payload) < ENVELOPE_LENGTH:
            msg = f"unexpected World Bank envelope from {url}: {type(payload).__name__}"
            raise ParsingError(msg)

        meta = payload[0] if isinstance(payload[0], dict) else {}
        rows = payload[1] if isinstance(payload[1], list) else []
        return meta, rows, response

    # ------------------------------------------------------------- ABC protocol

    def connect(self) -> bool:
        """
        Probe a cheap endpoint to confirm the API is reachable.

        Returns:
            True when the probe returns a usable envelope

        Raises:
            ConnectionError: If the API is unreachable after all retries
        """
        url = f"{self.config.base_url}/country/{self.config.country}"
        try:
            _, rows, response = self._request_envelope(url, {"format": "json", "per_page": 1})
        except (DataRetrievalError, ParsingError) as exc:
            msg = f"World Bank API unreachable at {url}: {exc}"
            raise PlatformConnectionError(msg) from exc

        reachable = bool(rows)
        log_with_context(
            logger,
            "INFO" if reachable else "WARNING",
            "world bank connectivity probe",
            url=url,
            http_status_code=response.status_code,
            reachable=reachable,
        )
        return reachable

    def discover(self) -> list[IndicatorMetadata]:
        """
        Read metadata for every configured indicator.

        ``availability_start`` / ``availability_end`` are deliberately left None:
        the API does not report per-country coverage, so the pipeline fills them
        in from the observations it actually stores.

        Returns:
            One :class:`IndicatorMetadata` per configured indicator

        Raises:
            DataRetrievalError: If an indicator's metadata cannot be retrieved
        """
        discovered: list[IndicatorMetadata] = []
        source_label: str | None = None

        for indicator_id in self.config.indicators:
            url = self.config.indicator_url(indicator_id)
            _, rows, _ = self._request_envelope(url, {"format": "json"})
            if not rows or not isinstance(rows[0], dict):
                msg = f"World Bank returned no metadata for {indicator_id}"
                raise DataRetrievalError(msg)

            row = rows[0]
            name = str(row.get("name") or indicator_id)
            unit = extract_unit(row.get("unit"), name)
            self._unit_cache[indicator_id] = unit
            source = row.get("source")
            if isinstance(source, dict) and source.get("value"):
                source_label = str(source["value"])

            discovered.append(
                IndicatorMetadata(
                    indicator_id=str(row.get("id") or indicator_id),
                    name=name,
                    description=(row.get("sourceNote") or None),
                    unit=unit,
                    frequency=FREQUENCY_ANNUAL,
                    domain=domain_for(indicator_id),
                    source_name=self.source_name,
                    source_url=self.config.data_url(indicator_id),
                    availability_start=None,
                    availability_end=None,
                    # WDI constant-price series are pre-rebased by the Bank, so
                    # a single series carries no internal base-year break.
                    has_base_year_changes=False,
                    base_years=None,
                )
            )

        log_with_context(
            logger,
            "INFO",
            "world bank indicators discovered",
            indicator_count=len(discovered),
            source=source_label,
        )
        return discovered

    def fetch(self, indicator_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch one indicator's series as a DataFrame.

        Args:
            indicator_id: World Bank indicator code
            start_date: Earliest period to request
            end_date: Latest period to request

        Returns:
            DataFrame with columns timestamp, value, indicator_id, unit, obs_status
        """
        return self.fetch_series(indicator_id, start_date, end_date).frame

    def fetch_series(
        self,
        indicator_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> WorldBankFetchResult:
        """
        Fetch one indicator and keep the raw envelope for Bronze.

        Args:
            indicator_id: World Bank indicator code
            start_date: Earliest period to request; defaults to the config range
            end_date: Latest period to request; defaults to the config range

        Returns:
            Parsed frame plus raw envelope and request provenance

        Raises:
            DataRetrievalError: On an API error payload or exhausted retries
        """
        start_year = start_date.year if start_date else self.config.date_range[0]
        end_year = end_date.year if end_date else self.config.date_range[1]

        url = self.config.data_url(indicator_id)
        base_params: dict[str, Any] = {
            "format": "json",
            "per_page": self.config.per_page,
            "date": f"{start_year}:{end_year}",
        }

        first_meta: dict[str, Any] = {}
        all_rows: list[Any] = []
        status_code = 0
        page = 1

        while page <= MAX_PAGES:
            meta, rows, response = self._request_envelope(url, {**base_params, "page": page})
            status_code = response.status_code
            if page == 1:
                first_meta = meta
            all_rows.extend(rows)

            total_pages = int(meta.get("pages") or 1)
            if page >= total_pages:
                break
            page += 1

        unit = self._unit_cache.get(indicator_id)
        frame = rows_to_frame(all_rows, indicator_id, unit)

        log_with_context(
            logger,
            "INFO",
            "world bank series fetched",
            indicator_id=indicator_id,
            rows_returned=len(all_rows),
            rows_usable=int(len(frame)),
            pages_fetched=page,
            date_range=base_params["date"],
        )

        return WorldBankFetchResult(
            indicator_id=indicator_id,
            frame=frame,
            raw_envelope=[first_meta, all_rows],
            request_url=f"{url}?format=json&date={start_year}:{end_year}"
            f"&per_page={self.config.per_page}",
            http_status_code=status_code,
            pages_fetched=page,
            unit=unit,
            source_last_updated=first_meta.get("lastupdated"),
            total_reported=int(first_meta["total"])
            if first_meta.get("total") is not None
            else None,
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


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the World Bank pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any indicator failed)
    """
    from src.etl.pipeline import run_cli  # local import avoids a circular import

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.world_bank",
        description="Collect World Bank indicators for Iran into Bronze/Silver/Gold.",
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

    indicators = (
        tuple(code.strip() for code in args.indicators.split(",") if code.strip())
        if args.indicators
        else None
    )
    return run_cli(indicators=indicators, dry_run=args.dry_run, log_level=args.log_level)


if __name__ == "__main__":
    raise SystemExit(main())
