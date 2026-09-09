"""
TGJU web scraper connector.

Scrapes daily FX and gold price series from ``https://www.tgju.org/profile/*``
using Playwright for browser automation and the Persian-aware parser from
:mod:`src.connectors.tgju_parser`.

TGJU Structure
--------------
* Each instrument has a profile page: ``/profile/price_dollar_rl`` (USD),
  ``/profile/sekee`` (Emami coin), ``/profile/geram18`` (18K gold)
* Price table: "در یک نگاه" (at a glance) with row "نرخ فعلی" (current rate)
* Price format: Persian digits with thousand separators (e.g. "۲,۲۵۵,۰۰۰")
* Date format: "سه شنبه ۱۷ شهریور ۱۴۰۵" (weekday + day + month + year)
* Time format: "۱۵:۲۶:۲۴" (HH:MM:SS in Persian digits)
* Error case: "شاخص درخواستی در دسترس نیست یا بازار بسته است" (indicator unavailable)

Scraping Constraints
-------------------
* Rate limit: 1-2 requests per second (enforced by :class:`RateLimiter`)
* Politeness: Proper User-Agent, respect robots.txt (checked in Task 2)
* Timeout: 30s page load timeout (configurable via :class:`TgjuConfig`)
* Retries: Handled by :class:`RetryPolicy` (transient network errors only)

This module never touches the database: Bronze persistence is :mod:`src.etl.bronze`.
"""

import argparse
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from src.connectors.base import DataConnector, IndicatorMetadata
from src.connectors.tgju_parser import parse_tgju_html
from src.database.schema import utc_now
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.logging import get_logger, log_with_context
from src.utils.retry import RateLimiter, RetryPolicy
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "tgju"
SOURCE_TYPE = "scraper"
FREQUENCY_DAILY = "daily"

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.0
DEFAULT_PAGE_TIMEOUT_MS = 30000  # 30 seconds in milliseconds

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Maximum retries for transient errors (network, timeout)
MAX_RETRIES = 3

# Indicator registry: TGJU profile path -> (indicator_id, name, domain)
INDICATOR_REGISTRY: dict[str, tuple[str, str, str]] = {
    "price_dollar_rl": ("TGJU.USD.FREE", "USD Free Market Rate", "fx"),
    "sekee": ("TGJU.GOLD.EMAMI", "Emami Gold Coin", "gold"),
    "geram18": ("TGJU.GOLD.18K", "18K Gold per Gram", "gold"),
}

DEFAULT_PATHS: tuple[str, ...] = tuple(INDICATOR_REGISTRY.keys())


def _default_timeout_ms() -> int:
    """Page timeout in milliseconds, from scraper_page_timeout config."""
    return get_config().collection.scraper_page_timeout * 1000


def _default_min_request_interval() -> float:
    """Minimum request interval, from scraper_min_request_interval config."""
    return get_config().collection.scraper_min_request_interval


@dataclass
class TgjuConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    base_url: str = field(default_factory=lambda: get_config().api.tgju_base_url)
    paths: tuple[str, ...] = DEFAULT_PATHS
    page_timeout_ms: int = field(default_factory=_default_timeout_ms)
    min_request_interval: float = field(default_factory=_default_min_request_interval)
    user_agent: str = USER_AGENT
    headless: bool = True

    def profile_url(self, path: str) -> str:
        """Fully-resolved profile URL for one instrument."""
        return f"{self.base_url}/profile/{path}"


@dataclass
class TgjuFetchResult:
    """A parsed series plus everything the Bronze writer needs for provenance."""

    indicator_id: str
    frame: pd.DataFrame
    raw_html: str
    request_url: str
    scraped_at: datetime
    page_load_time_ms: float

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata``."""
        return {
            "indicator_id": self.indicator_id,
            "url": self.request_url,
            "scraped_at": self.scraped_at.isoformat(),
            "page_load_time_ms": self.page_load_time_ms,
            "html_length": len(self.raw_html),
            "rows_usable": int(len(self.frame)),
            "source_type": SOURCE_TYPE,
        }


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


class TgjuScraper(DataConnector):
    """Connector for TGJU web scraper using Playwright."""

    def __init__(
        self,
        config: TgjuConfig | None = None,
        browser: Browser | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """
        Initialize the scraper.

        Args:
            config: Connector configuration; defaults come from ``AppConfig``
            browser: Pre-built Playwright browser (unit tests inject a mock)
            retry_policy: Retry policy; defaults to one built from config
            rate_limiter: Request spacing; defaults to the configured interval
        """
        super().__init__(source_name=SOURCE_NAME)
        self.config = config or TgjuConfig()
        self._browser = browser
        self._owns_browser = browser is None
        self._playwright_context: Playwright | None = None
        self._retry = retry_policy or RetryPolicy.from_config()
        self._rate_limiter = rate_limiter or RateLimiter(self.config.min_request_interval)

    # ---------------------------------------------------------------- transport

    def _ensure_browser(self) -> Browser:
        """Return the Playwright browser, launching one on first use."""
        if self._browser is None:
            self._playwright_context = sync_playwright().start()
            self._browser = self._playwright_context.chromium.launch(headless=self.config.headless)
            self._owns_browser = True
        return self._browser

    def _scrape_page(self, url: str) -> tuple[str, float]:
        """
        Scrape one page with rate limiting and return HTML + load time.

        Args:
            url: Absolute profile URL

        Returns:
            Tuple of (HTML content, page load time in milliseconds)

        Raises:
            DataRetrievalError: If the page cannot be loaded after retries
        """
        browser = self._ensure_browser()
        self._rate_limiter.wait()

        page: Page | None = None
        try:
            start = time.perf_counter()
            page = browser.new_page(user_agent=self.config.user_agent)
            page.set_default_timeout(float(self.config.page_timeout_ms))

            response = page.goto(url, wait_until="domcontentloaded")
            if response is None or not response.ok:
                status = response.status if response else "unknown"
                msg = f"TGJU page load failed: {url} (HTTP {status})"
                raise DataRetrievalError(msg)

            html = page.content()
            elapsed_ms = (time.perf_counter() - start) * 1000
            return html, elapsed_ms

        except Exception as exc:
            if isinstance(exc, DataRetrievalError):
                raise
            msg = f"TGJU scrape error for {url}: {exc}"
            raise DataRetrievalError(msg) from exc

        finally:
            if page:
                page.close()

    # ------------------------------------------------------------- ABC protocol

    def connect(self) -> bool:
        """
        Probe the TGJU homepage to confirm the site is reachable.

        Returns:
            True when the probe succeeds

        Raises:
            ConnectionError: If the site is unreachable after all retries
        """
        url = self.config.base_url
        try:
            browser = self._ensure_browser()
            page = browser.new_page(user_agent=self.config.user_agent)
            page.set_default_timeout(float(self.config.page_timeout_ms))

            try:
                response = page.goto(url, wait_until="domcontentloaded")
                reachable = response is not None and response.ok
            finally:
                page.close()

        except Exception as exc:
            msg = f"TGJU unreachable at {url}: {exc}"
            raise PlatformConnectionError(msg) from exc

        log_with_context(
            logger,
            "INFO" if reachable else "WARNING",
            "tgju connectivity probe",
            url=url,
            reachable=reachable,
        )
        return reachable

    def discover(self) -> list[IndicatorMetadata]:
        """
        Return metadata for all configured TGJU instruments.

        ``availability_start`` / ``availability_end`` are left None since TGJU
        does not expose historical availability metadata. The pipeline fills
        them in from observations actually stored.

        Returns:
            One :class:`IndicatorMetadata` per configured instrument
        """
        discovered: list[IndicatorMetadata] = []

        for path in self.config.paths:
            if path not in INDICATOR_REGISTRY:
                logger.warning("Unknown TGJU path %s, skipping discovery", path)
                continue

            indicator_id, name, domain = INDICATOR_REGISTRY[path]
            meta = IndicatorMetadata(
                indicator_id=indicator_id,
                source_name=SOURCE_NAME,
                name=name,
                description=f"Daily {name} from TGJU",
                unit="IRR",
                frequency=FREQUENCY_DAILY,
                domain=domain,
                source_url=self.config.profile_url(path),
                availability_start=None,  # Filled by pipeline from stored data
                availability_end=None,
                has_base_year_changes=False,  # TGJU prices don't have base year changes
                base_years=None,
            )
            discovered.append(meta)

        log_with_context(
            logger, "INFO", "tgju discovery", discovered_count=len(discovered)
        )
        return discovered

    def fetch(
        self,
        indicator_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch current price for one TGJU instrument.

        TGJU only provides the current price, not historical data, so
        ``start_date`` and ``end_date`` are ignored. Use Airflow daily runs
        to build a historical time series in the database.

        Args:
            indicator_id: TGJU indicator ID (e.g., ``TGJU.USD.FREE``)
            start_date: Ignored (TGJU has no historical API)
            end_date: Ignored (TGJU has no historical API)

        Returns:
            DataFrame with one row (current price) or empty if unavailable

        Raises:
            DataRetrievalError: If scraping fails after retries
            ParsingError: If the HTML cannot be parsed
        """
        # This is the simplified ABC method; real callers use fetch_series()
        result = self.fetch_series(indicator_id)
        return result.frame

    def fetch_series(self, indicator_id: str) -> TgjuFetchResult:
        """
        Fetch and parse one TGJU instrument, returning frame + raw HTML.

        Args:
            indicator_id: TGJU indicator ID (e.g., ``TGJU.USD.FREE``)

        Returns:
            :class:`TgjuFetchResult` with parsed frame and raw HTML

        Raises:
            DataRetrievalError: If the indicator is unknown or scraping fails
            ParsingError: If the HTML cannot be parsed
        """
        # Map indicator_id back to path
        path = None
        for p, (iid, _, _) in INDICATOR_REGISTRY.items():
            if iid == indicator_id:
                path = p
                break

        if path is None:
            msg = f"Unknown TGJU indicator: {indicator_id}"
            raise DataRetrievalError(msg)

        url = self.config.profile_url(path)

        # Scrape with retries
        def operation() -> tuple[str, float]:
            return self._scrape_page(url)

        html, load_time_ms = self._retry.run(operation, "tgju scrape", url=url)
        scraped_at = utc_now()

        # Parse HTML
        try:
            frame = parse_tgju_html(html, indicator_id, now=scraped_at)
        except ParsingError as exc:
            log_with_context(
                logger,
                "ERROR",
                "tgju parsing failed",
                indicator_id=indicator_id,
                url=url,
                error=str(exc),
            )
            raise

        log_with_context(
            logger,
            "INFO",
            "tgju fetch complete",
            indicator_id=indicator_id,
            url=url,
            rows=len(frame),
            load_time_ms=load_time_ms,
        )

        return TgjuFetchResult(
            indicator_id=indicator_id,
            frame=frame,
            raw_html=html,
            request_url=url,
            scraped_at=scraped_at,
            page_load_time_ms=load_time_ms,
        )

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate fetched TGJU data.

        TGJU returns a single current price, so validation checks:
        - Frame is not empty
        - Required columns exist
        - Value is positive
        - No nulls (current price should always be present)

        Args:
            data: DataFrame returned by :meth:`fetch`

        Returns:
            :class:`ValidationResult` with quality metrics
        """
        return validate_data_quality(data, null_threshold=0.0)

    def disconnect(self) -> None:
        """Close the Playwright browser if this connector owns it."""
        if self._owns_browser:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._playwright_context is not None:
                self._playwright_context.stop()
                self._playwright_context = None

    def __enter__(self) -> "TgjuScraper":
        """Context manager entry."""
        return self

    def __exit__(self, *_: Any) -> None:
        """Context manager exit: disconnect."""
        self.disconnect()


# ----------------------------------------------------------- Pipeline runner


def run_tgju_pipeline(
    paths: Sequence[str] | None = None,
    dry_run: bool = False,
    connector: "TgjuScraper | None" = None,
) -> Any:  # Returns PipelineSummary from src.etl.pipeline
    """
    Scrape TGJU instruments into Bronze, Silver, and Gold.

    Args:
        paths: TGJU profile paths to scrape; defaults to all configured paths
        dry_run: Fetch and report without opening a session or writing a row
        connector: Pre-built connector (tests inject one with a mock browser)

    Returns:
        Per-indicator outcomes plus an aggregate exit code

    Raises:
        ConnectionError: If TGJU cannot be reached at all
    """
    from src.database.connection import get_db
    from src.etl.pipeline import (  # local imports avoid circular dependency
        PipelineSummary,
        upsert_indicator_catalog,
    )

    owns_connector = connector is None
    if connector is None:
        config = TgjuConfig()
        if paths:
            config.paths = tuple(paths)
        connector = TgjuScraper(config=config)
    elif paths:
        connector.config.paths = tuple(paths)

    summary = PipelineSummary(dry_run=dry_run)
    targets = connector.config.paths

    # Map paths to indicator_ids
    indicator_ids = []
    for path in targets:
        if path in INDICATOR_REGISTRY:
            indicator_ids.append(INDICATOR_REGISTRY[path][0])
        else:
            logger.warning("Unknown TGJU path %s, skipping", path)

    try:
        connector.connect()
        discovered = connector.discover()

        if not dry_run:
            with get_db().get_session() as session:
                seeded = upsert_indicator_catalog(session, discovered)
            log_with_context(logger, "INFO", "indicator catalog refreshed", rows=seeded)

        for indicator_id in indicator_ids:
            summary.outcomes.append(
                _collect_one_tgju(connector, indicator_id, discovered, dry_run=dry_run)
            )
    finally:
        if owns_connector:
            connector.disconnect()

    log_with_context(
        logger,
        "INFO" if not summary.failed else "WARNING",
        "tgju pipeline complete",
        dry_run=dry_run,
        instruments=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )
    return summary


def _collect_one_tgju(
    connector: "TgjuScraper",
    indicator_id: str,
    discovered: Sequence[IndicatorMetadata],
    dry_run: bool,
) -> Any:  # Returns IndicatorOutcome from src.etl.pipeline
    """
    Scrape one TGJU instrument end to end, containing its failure.

    Each instrument gets its own session so a rollback here cannot undo another
    instrument's committed work.
    """
    from src.database.connection import get_db
    from src.etl.pipeline import IndicatorOutcome
    from src.utils.exceptions import ValidationError

    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    INDICATOR_ERRORS = (DataRetrievalError, ParsingError, ValidationError)

    outcome = IndicatorOutcome(indicator_id=indicator_id, status=STATUS_SUCCESS)
    try:
        fetched = connector.fetch_series(indicator_id)
        outcome.rows_fetched = int(len(fetched.frame))

        # A dry run still counts as success: fetching and parsing are the only
        # work it was asked to do.
        if not dry_run:
            with get_db().get_session() as session:
                _persist_indicator_tgju(
                    session,
                    fetched,
                    outcome,
                    domain=_domain_for_tgju(discovered, indicator_id),
                    unit=_unit_for_tgju(discovered, indicator_id),
                )
    except INDICATOR_ERRORS as exc:
        outcome.status = STATUS_FAILED
        outcome.error = f"{type(exc).__name__}: {exc}"
        log_with_context(
            logger,
            "ERROR",
            "tgju instrument scrape failed",
            indicator_id=indicator_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )

    return outcome


def _tgju_parser(
    rows: Any,  # List of row dicts, each with {"html": ..., "url": ..., "scraped_at": ...}
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Parser adapter for TGJU scraped HTML.

    Args:
        rows: List of row dicts from Bronze extract_rows()
        indicator_id: TGJU indicator ID
        unit: Ignored (unit comes from parser)
        now: Timestamp override for testing

    Returns:
        Parsed DataFrame with columns timestamp, value, indicator_id, unit, obs_status
    """
    # TGJU Bronze stores one observation per scrape as a single row
    if not rows or not isinstance(rows, list) or len(rows) == 0:
        # Return empty DataFrame with correct schema
        return pd.DataFrame(
            {
                "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
                "value": pd.Series(dtype="float64"),
                "indicator_id": pd.Series(dtype="object"),
                "unit": pd.Series(dtype="object"),
                "obs_status": pd.Series(dtype="object"),
            }
        )
    
    # Extract HTML from the first (and only) row
    row = rows[0]
    if isinstance(row, dict) and "html" in row:
        html = row["html"]
        return parse_tgju_html(html, indicator_id, now=now)
    
    # Fallback for unexpected structure
    return pd.DataFrame(
        {
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "value": pd.Series(dtype="float64"),
            "indicator_id": pd.Series(dtype="object"),
            "unit": pd.Series(dtype="object"),
            "obs_status": pd.Series(dtype="object"),
        }
    )


def _persist_indicator_tgju(
    session: Any,  # SQLAlchemy Session
    fetched: TgjuFetchResult,
    outcome: Any,  # IndicatorOutcome
    domain: str,
    unit: str | None,
) -> None:
    """Write one TGJU instrument to Bronze → Silver → Gold."""
    from src.etl import bronze, gold, silver
    from src.etl.pipeline import update_catalog_availability

    # Bronze: Store raw HTML as the envelope
    # Wrap HTML in a single "row" since TGJU returns one observation per scrape
    bronze_id = bronze.write_bronze(
        session,
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        raw_envelope={
            "rows": [{"html": fetched.raw_html, "url": fetched.request_url, "scraped_at": fetched.scraped_at.isoformat()}]
        },
        request_url=fetched.request_url,
        http_status_code=None,  # Playwright doesn't expose status code easily in our usage
        record_metadata=fetched.collection_metadata(),
    )
    outcome.bronze_id = bronze_id

    # Silver: Clean and validate with TGJU parser
    silver_result = silver.bronze_to_silver(
        session,
        bronze_id=bronze_id,
        indicator_id=fetched.indicator_id,
        source_name=SOURCE_NAME,
        frequency=FREQUENCY_DAILY,
        unit=unit,
        parser=_tgju_parser,
    )
    outcome.rows_written_silver = silver_result.records_written
    outcome.records_failed = silver_result.records_failed

    # Update catalog with observed date range
    def _observed_range(frame: pd.DataFrame) -> tuple[datetime | None, datetime | None]:
        if frame.empty or "timestamp" not in frame.columns:
            return (None, None)
        return (frame["timestamp"].min(), frame["timestamp"].max())

    start, end = _observed_range(fetched.frame)
    update_catalog_availability(session, fetched.indicator_id, start, end)

    # Gold: Chain-link and publish daily metrics (RET1D + MA30)
    gold_result = gold.silver_to_gold(
        session,
        indicator_id=fetched.indicator_id,
        domain=domain,
        derived_prefix="TGJU",
        derivation_strategy="daily",
    )
    outcome.rows_written_gold = gold_result.records_written
    outcome.is_chain_linked = bool(gold_result.details.get("is_chain_linked"))


def _domain_for_tgju(discovered: Sequence[IndicatorMetadata], indicator_id: str) -> str:
    """Look up the domain of a TGJU indicator from discovery metadata."""
    for meta in discovered:
        if meta.indicator_id == indicator_id:
            return meta.domain
    return "unclassified"


def _unit_for_tgju(discovered: Sequence[IndicatorMetadata], indicator_id: str) -> str | None:
    """Look up the unit of a TGJU indicator from discovery metadata."""
    for meta in discovered:
        if meta.indicator_id == indicator_id:
            return meta.unit
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the TGJU scraper pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any instrument failed)
    """
    from src.utils.config import get_config
    from src.utils.logging import setup_logging

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.tgju_scraper",
        description="Scrape TGJU daily FX/gold prices into Bronze/Silver/Gold.",
    )
    parser.add_argument(
        "--paths",
        help=f"Comma-separated TGJU paths (default: all {len(DEFAULT_PATHS)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report without writing to the database",
    )
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    args = parser.parse_args(argv)

    config = get_config()
    setup_logging(
        level=args.log_level or config.logging.level,
        log_format=config.logging.format,
    )

    paths = (
        tuple(p.strip() for p in args.paths.split(",") if p.strip())
        if args.paths
        else None
    )

    try:
        summary = run_tgju_pipeline(paths=paths, dry_run=args.dry_run)
    except (PlatformConnectionError, DataRetrievalError) as exc:
        log_with_context(
            logger,
            "ERROR",
            "tgju pipeline aborted",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        print(f"pipeline aborted: {type(exc).__name__}: {exc}")
        return 1

    print(summary.report())
    return 0 if not summary.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
