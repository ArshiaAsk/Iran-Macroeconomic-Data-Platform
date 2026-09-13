"""
Statistical Center of Iran (SCI) file scraper connector.

Collects the headline / decile **consumer price index** (monthly) and the
**unemployment rate** (quarterly) that SCI publishes on ``amar.org.ir`` as
Excel workbooks (``.xlsx`` and legacy ``.xls``), PDFs and HTML tables.

Structure
---------
* Publications are direct file links under ``/Portals/0/Statistics/…`` and
  ``/Portals/0/Articles/…`` (see ``tests/fixtures/sci/_capture.json``). The file
  is the unit of collection: one Bronze row per download, with the raw file
  base64-encoded in the envelope metadata and the parsed observations stored
  under ``rows``.
* Parsing is delegated to :mod:`src.connectors.sci_parser`; this module owns
  transport (download, retries, size guard, rate limiting) and provenance only.

robots.txt
----------
``https://www.amar.org.ir/robots.txt`` (captured as
``tests/fixtures/sci/robots.amar.txt``) disallows ``/admin/``, ``/App_*/``,
``/bin/``, ``/images/``, ``/Resources/…``, ``/activity-feed/`` and some query
patterns; the publication paths used here are permitted. ``Crawl-delay: 5``
applies only to ``msnbot``/``Slurp``/``Googlebot``; the platform's 1-2 req/sec
politeness rule is enforced regardless via :class:`RateLimiter`.

Base years
----------
SCI labels CPI workbooks in **Jalali** years (explicit ``100=1400`` /
``1395=100`` markers). Only two bases are published today -- 1395 (2016) and
1400 (2021). Indicator ids carry the **Gregorian** base year (``…B2016`` /
``…B2021``) while the Jalali year stays in the Bronze metadata; the canonical
linked id is created by Gold, not here.

This module never writes to the database directly: Bronze/Silver persistence is
:mod:`src.etl.bronze` and :mod:`src.etl.silver`.
"""

import argparse
import base64
import hashlib
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import unquote, urlparse

import pandas as pd
import requests
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from src.connectors.base import DataConnector, IndicatorMetadata
from src.connectors.sci_parser import (
    FREQUENCY_MONTHLY,
    FREQUENCY_QUARTERLY,
    HEADLINE_LABEL,
    UNIT_INDEX,
    UNIT_PERCENT,
    parse_cpi_decile_excel,
    parse_cpi_excel,
    parse_unemployment_excel,
)
from src.database.schema import utc_now
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.logging import get_logger, log_with_context
from src.utils.retry import RateLimiter, RetryPolicy, is_retryable_status
from src.utils.validation import ValidationResult, validate_data_quality

logger = get_logger(__name__)

SOURCE_NAME = "sci"
SOURCE_TYPE = "file"

DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.0
DEFAULT_PAGE_TIMEOUT_MS = 30000
CHUNK_SIZE = 65536

# CPI publications index page (relative to ``SCI_BASE_URL``).
CPI_INDEX_PATH = "/prices"

# Namespace for SCI's derived Gold series (e.g. SCI.CPI.URBAN.YOY).
DERIVED_PREFIX = "SCI"

# amar.org.ir serves an incomplete TLS chain (leaf issued by "Certum DV TLS G2
# R39 CA", but the server sends older intermediates). The missing intermediate
# is shipped here and pinned, so requests verifies deliberately instead of
# falling back to ``verify=False`` (see tests/fixtures/sci/SOURCES.md).
_BUNDLED_CA_BUNDLE = Path(__file__).parent / "certs" / "certum_dv_tls_g2_r39_ca.pem"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Column contract the Silver layer consumes.
SERIES_COLUMNS = ("timestamp", "value", "indicator_id", "unit", "obs_status")


def _default_page_timeout_ms() -> int:
    """Page timeout in milliseconds, from scraper_page_timeout config."""
    return get_config().collection.scraper_page_timeout * 1000


def _default_download_timeout() -> int:
    """File download timeout in seconds, from scraper_download_timeout config."""
    return get_config().collection.scraper_download_timeout


def _default_max_download_bytes() -> int:
    """Maximum accepted download size, from scraper_max_download_bytes config."""
    return get_config().collection.scraper_max_download_bytes


def _default_min_request_interval() -> float:
    """Minimum request interval, from scraper_min_request_interval config."""
    return get_config().collection.scraper_min_request_interval


def _default_ca_bundle() -> str | None:
    """CA bundle for SCI TLS verification: configured override or pinned intermediate."""
    configured = get_config().api.sci_ca_bundle
    if configured:
        return configured
    return str(_BUNDLED_CA_BUNDLE)


class SciPublication(NamedTuple):
    """
    One SCI publication and how to parse it.

    The first five fields mirror the plan's ``(indicator_id, name, domain,
    frequency, base_year)`` registry tuple; the rest make the entry actionable
    (where the file lives, which parser reads it, which series it contains).

    For a single-series workbook ``indicator_id`` is the series id. For a
    multi-series workbook (the decile publication) it is the **prefix** and
    ``series_ids`` enumerates the ten members.
    """

    indicator_id: str
    name: str
    domain: str
    frequency: str
    base_year: int | None
    path: str
    parser: str
    unit: str | None = UNIT_INDEX
    base_year_gregorian: int | None = None
    has_base_year_changes: bool = False
    base_years: tuple[int, ...] | None = None
    series_ids: tuple[str, ...] = ()
    parser_options: Mapping[str, Any] = {}
    via_browser: bool = False

    @property
    def member_ids(self) -> tuple[str, ...]:
        """Every series id this publication carries (one for single series)."""
        return self.series_ids or (self.indicator_id,)


# Publication slug -> metadata + file location. Paths/URLs are the real ones
# captured in Task 1 (tests/fixtures/sci/_capture.json); every base year is
# explicit in the file, never inferred from values.
SCI_INDICATOR_REGISTRY: dict[str, SciPublication] = {
    "cpi_national": SciPublication(
        indicator_id="SCI.CPI.NATIONAL.B2021",
        name="CPI - national (all households), base 1400=2021",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        base_year=1400,
        base_year_gregorian=2021,
        path="/Portals/0/Statistics/ts_national_140505-14050618165053.xlsx",
        parser="cpi_excel",
        unit=UNIT_INDEX,
        has_base_year_changes=True,
        base_years=(2016, 2021),
    ),
    "cpi_urban": SciPublication(
        indicator_id="SCI.CPI.URBAN.B2021",
        name="CPI - urban households, base 1400=2021",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        base_year=1400,
        base_year_gregorian=2021,
        path="/Portals/0/Statistics/ts_urban_140505-14050618165804.xlsx",
        parser="cpi_excel",
        unit=UNIT_INDEX,
        has_base_year_changes=True,
        base_years=(2016, 2021),
    ),
    "cpi_rural": SciPublication(
        indicator_id="SCI.CPI.RURAL.B2021",
        name="CPI - rural households, base 1400=2021",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        base_year=1400,
        base_year_gregorian=2021,
        path="/Portals/0/Statistics/ts_rural-140505-14050618165248.xlsx",
        parser="cpi_excel",
        unit=UNIT_INDEX,
        has_base_year_changes=True,
        base_years=(2016, 2021),
    ),
    "cpi_base1395": SciPublication(
        indicator_id="SCI.CPI.URBAN.B2016",
        name="CPI - urban households, base 1395=2016",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        base_year=1395,
        base_year_gregorian=2016,
        path="/Portals/0/Statistics/ts_cpi_1395=100-14040208113537.xlsx",
        parser="cpi_excel",
        unit=UNIT_INDEX,
        has_base_year_changes=True,
        base_years=(2016, 2021),
        # جدول 3 is the tidy long sheet (1361-01 … 1401-01). The wide جدول 1 only
        # starts at 1381-01 -- the same first period as the 1400-base workbooks --
        # so it offers no older history for the 1395->1400 splice to rescale.
        parser_options={"sheet": "جدول 3"},
    ),
    "cpi_decile": SciPublication(
        indicator_id="SCI.CPI.DECILE.B2021",
        name="CPI by household expenditure decile, base 1400=2021",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        base_year=1400,
        base_year_gregorian=2021,
        path="/Portals/0/Statistics/ts_decile_140505-14050618164745.xlsx",
        parser="cpi_decile_excel",
        unit=UNIT_INDEX,
        series_ids=tuple(f"SCI.CPI.DECILE.B2021.D{n}" for n in range(1, 11)),
    ),
    "unemployment_spring_1405": SciPublication(
        indicator_id="SCI.UNEMPLOYMENT.QUARTERLY",
        name="Unemployment rate (labour force survey, quarterly)",
        domain="labor",
        frequency=FREQUENCY_QUARTERLY,
        base_year=None,
        path="/Portals/0/Statistics/ne_niruye_kar_1405-01-14050525163749.xls",
        parser="unemployment_excel",
        unit=UNIT_PERCENT,
        parser_options={"jalali_year": 1405, "season": "بهار"},
    ),
}

DEFAULT_PUBLICATIONS: tuple[str, ...] = tuple(SCI_INDICATOR_REGISTRY)


@dataclass(frozen=True)
class SciCanonicalIndicator:
    """
    A chain-linked series built from one or more published base-year segments.

    The canonical id is what the catalog marks active and what Gold publishes;
    the ``B<year>`` segment ids stay in Silver and are seeded inactive.
    """

    indicator_id: str
    name: str
    domain: str
    frequency: str
    unit: str | None
    segment_ids: tuple[str, ...]
    base_years: tuple[int, ...]

    @property
    def has_base_year_changes(self) -> bool:
        """True when more than one published base must be linked."""
        return len(self.segment_ids) > 1


# Canonical CPI series and the published base-year segments that feed them.
# Only 1395 (2016) and 1400 (2021) are published (Task 1 finding), so a real
# multi-base link exists only for the urban series; the others carry one segment
# and link as a passthrough.
SCI_CANONICAL_INDICATORS: dict[str, SciCanonicalIndicator] = {
    "SCI.CPI.NATIONAL": SciCanonicalIndicator(
        indicator_id="SCI.CPI.NATIONAL",
        name="CPI - national (all households), chain-linked",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        unit=UNIT_INDEX,
        segment_ids=("SCI.CPI.NATIONAL.B2021",),
        base_years=(2021,),
    ),
    "SCI.CPI.URBAN": SciCanonicalIndicator(
        indicator_id="SCI.CPI.URBAN",
        name="CPI - urban households, chain-linked",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        unit=UNIT_INDEX,
        segment_ids=("SCI.CPI.URBAN.B2016", "SCI.CPI.URBAN.B2021"),
        base_years=(2016, 2021),
    ),
    "SCI.CPI.RURAL": SciCanonicalIndicator(
        indicator_id="SCI.CPI.RURAL",
        name="CPI - rural households, chain-linked",
        domain="inflation",
        frequency=FREQUENCY_MONTHLY,
        unit=UNIT_INDEX,
        segment_ids=("SCI.CPI.RURAL.B2021",),
        base_years=(2021,),
    ),
}


@dataclass
class SciConfig:
    """Per-connector configuration (AGENTS.md: no hardcoded values in logic)."""

    base_url: str = field(default_factory=lambda: get_config().api.sci_base_url)
    publications: tuple[str, ...] = DEFAULT_PUBLICATIONS
    page_timeout_ms: int = field(default_factory=_default_page_timeout_ms)
    download_timeout: int = field(default_factory=_default_download_timeout)
    max_download_bytes: int = field(default_factory=_default_max_download_bytes)
    min_request_interval: float = field(default_factory=_default_min_request_interval)
    ca_bundle: str | None = field(default_factory=_default_ca_bundle)
    user_agent: str = USER_AGENT
    headless: bool = True

    def file_url(self, path: str) -> str:
        """Fully-resolved URL for a publication path."""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"


@dataclass
class SciFetchResult:
    """A parsed publication plus everything the Bronze writer needs."""

    indicator_id: str
    frame: pd.DataFrame
    raw_rows: list[dict[str, Any]]
    raw_envelope: dict[str, Any]
    request_url: str
    http_status_code: int | None
    filename: str
    byte_length: int
    sha256: str
    content_type: str | None
    downloaded_at: datetime

    @property
    def series_ids(self) -> list[str]:
        """Distinct indicator ids present in the parsed frame, in order."""
        if self.frame.empty or "indicator_id" not in self.frame.columns:
            return []
        seen: list[str] = []
        for value in self.frame["indicator_id"].tolist():
            text = str(value)
            if text not in seen:
                seen.append(text)
        return seen

    def collection_metadata(self) -> dict[str, Any]:
        """Provenance dict for ``bronze_raw.metadata`` (never carries the file)."""
        return {
            "indicator_id": self.indicator_id,
            "url": self.request_url,
            "downloaded_at": self.downloaded_at.isoformat(),
            "filename": self.filename,
            "content_type": self.content_type,
            "http_status_code": self.http_status_code,
            "byte_length": self.byte_length,
            "sha256": self.sha256,
            "series_ids": self.series_ids,
            "rows_usable": int(len(self.frame)),
            "source_type": SOURCE_TYPE,
        }


@dataclass(frozen=True)
class _Download:
    """Raw bytes plus the transport-level provenance for one file."""

    data: bytes
    filename: str
    content_type: str | None
    http_status_code: int | None


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


def _filename_from_response(response: requests.Response, url: str) -> str:
    """Best-effort filename: Content-Disposition, then the URL basename."""
    disposition = response.headers.get("Content-Disposition", "")
    marker = "filename="
    if marker in disposition:
        candidate = disposition.split(marker, 1)[1].strip().strip('"').strip("'")
        if candidate:
            return Path(candidate).name
    return Path(unquote(urlparse(url).path)).name or "sci-download"


def _json_safe(value: Any) -> Any:  # noqa: PLR0911 - one small branch per JSON type
    """Coerce a parsed cell into something JSONB can store."""
    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if isinstance(value, str | bool | int):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp | datetime):
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalar
        return _json_safe(value.item())
    return str(value)


def frame_to_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a parsed frame into JSON-safe row dicts for the Bronze envelope."""
    return [
        {str(key): _json_safe(value) for key, value in record.items()}
        for record in frame.to_dict("records")
    ]


def _require_base_year(publication: SciPublication) -> int:
    """Base year for a CPI publication, or a hard parsing error."""
    if publication.base_year is None:
        msg = f"Publication {publication.indicator_id} has no base year to parse against"
        raise ParsingError(msg)
    return publication.base_year


def parse_publication(publication: SciPublication, data: bytes) -> pd.DataFrame:
    """
    Parse one downloaded publication into a tidy frame.

    Args:
        publication: Registry entry describing the file and its layout
        data: Raw file bytes

    Returns:
        Tidy observation frame (may carry several ``indicator_id`` values)

    Raises:
        ParsingError: If the layout is unknown or the file cannot be parsed
    """
    parser = publication.parser
    options = dict(publication.parser_options)

    if parser == "cpi_excel":
        return parse_cpi_excel(
            data,
            base_year=_require_base_year(publication),
            indicator_id=publication.indicator_id,
            sheet=options.get("sheet"),
            row_label=options.get("row_label", HEADLINE_LABEL),
            unit=publication.unit,
        )
    if parser == "cpi_decile_excel":
        return parse_cpi_decile_excel(
            data,
            base_year=_require_base_year(publication),
            indicator_id_prefix=publication.indicator_id,
            sheet=options.get("sheet"),
            unit=publication.unit,
        )
    if parser == "unemployment_excel":
        return parse_unemployment_excel(
            data,
            indicator_id=publication.indicator_id,
            jalali_year=int(options["jalali_year"]),
            season=str(options["season"]),
            unit=publication.unit or UNIT_PERCENT,
        )

    msg = f"Unknown SCI parser {parser!r} for publication {publication.indicator_id}"
    raise ParsingError(msg)


class SciScraper(DataConnector):
    """Connector for SCI file publications on ``amar.org.ir``."""

    def __init__(
        self,
        config: SciConfig | None = None,
        browser: Browser | None = None,
        http_session: requests.Session | None = None,
        retry_policy: RetryPolicy | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """
        Initialize the scraper.

        Args:
            config: Connector configuration; defaults come from ``AppConfig``
            browser: Pre-built Playwright browser (only needed for
                ``via_browser`` publications; unit tests inject a mock)
            http_session: HTTP transport for direct file links; injected in tests
            retry_policy: Retry policy; defaults to one built from config
            rate_limiter: Request spacing; defaults to the configured interval
        """
        super().__init__(source_name=SOURCE_NAME)
        self.config = config or SciConfig()
        self._browser = browser
        self._owns_browser = browser is None
        self._playwright_context: Playwright | None = None
        self._http = http_session or requests.Session()
        self._owns_http = http_session is None
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

    def _request(self, url: str) -> requests.Response:
        """Issue a streaming GET, converting retryable statuses to HTTPError."""
        response = self._http.get(
            url,
            timeout=self.config.download_timeout,
            stream=True,
            headers={"User-Agent": self.config.user_agent, "Accept": "*/*"},
            verify=self.config.ca_bundle,
        )
        if response.ok:
            return response
        status = response.status_code
        if is_retryable_status(status):
            try:
                response.raise_for_status()
            finally:
                response.close()
        response.close()
        msg = f"SCI download failed: {url} (HTTP {status})"
        raise DataRetrievalError(msg)

    def _read_capped(self, response: requests.Response, url: str) -> bytes:
        """Read a response body, refusing payloads over ``max_download_bytes``."""
        max_bytes = self.config.max_download_bytes
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                declared_bytes = int(declared)
            except ValueError:
                declared_bytes = None
            if declared_bytes is not None and declared_bytes > max_bytes:
                msg = f"SCI file exceeds {max_bytes} bytes: {url}"
                raise DataRetrievalError(msg)

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                msg = f"SCI file exceeded {max_bytes} bytes while streaming: {url}"
                raise DataRetrievalError(msg)
            chunks.append(chunk)
        if total == 0:
            msg = f"SCI download produced no bytes: {url}"
            raise DataRetrievalError(msg)
        return b"".join(chunks)

    def _download_http(self, url: str) -> _Download:
        """Download a direct file link with retries, rate limiting, and a size cap."""
        self._rate_limiter.wait()
        response = self._retry.run(lambda: self._request(url), "sci download", url=url)
        try:
            data = self._read_capped(response, url)
            filename = _filename_from_response(response, url)
            content_type = response.headers.get("Content-Type")
            status = int(response.status_code)
        finally:
            response.close()
        return _Download(data, filename, content_type, status)

    def _download_via_browser(self, url: str) -> _Download:
        """Download a publication that is only reachable through a browser click."""
        browser = self._ensure_browser()
        self._rate_limiter.wait()

        page: Page | None = None
        try:
            page = browser.new_page(user_agent=self.config.user_agent)
            page.set_default_timeout(float(self.config.page_timeout_ms))
            with page.expect_download() as download_info:
                page.goto(url)
            download = download_info.value
            local_path = download.path()
            data = Path(str(local_path)).read_bytes()
            if len(data) > self.config.max_download_bytes:
                msg = f"SCI file exceeds {self.config.max_download_bytes} bytes: {url}"
                raise DataRetrievalError(msg)
            return _Download(data, download.suggested_filename, None, None)
        except Exception as exc:
            if isinstance(exc, DataRetrievalError):
                raise
            msg = f"SCI browser download error for {url}: {exc}"
            raise DataRetrievalError(msg) from exc
        finally:
            if page is not None:
                page.close()

    def _download(self, publication: SciPublication, url: str) -> _Download:
        """Download one publication via the transport it declares."""
        if publication.via_browser:
            return self._download_via_browser(url)
        return self._download_http(url)

    # ------------------------------------------------------------- ABC protocol

    def connect(self) -> bool:
        """
        Probe the SCI site to confirm it is reachable.

        Returns:
            True when the probe succeeds

        Raises:
            ConnectionError: If the site is unreachable after all retries
        """
        url = self.config.base_url
        self._rate_limiter.wait()
        try:
            response = self._retry.run(
                lambda: self._http.get(
                    url, timeout=self.config.download_timeout, verify=self.config.ca_bundle
                ),
                "sci probe",
                url=url,
            )
            try:
                reachable = bool(response.ok)
            finally:
                response.close()
        except Exception as exc:
            msg = f"SCI unreachable at {url}: {exc}"
            raise PlatformConnectionError(msg) from exc

        log_with_context(
            logger,
            "INFO" if reachable else "WARNING",
            "sci connectivity probe",
            url=url,
            reachable=reachable,
        )
        return reachable

    def discover(self) -> list[IndicatorMetadata]:
        """
        Return metadata for every series in the configured publications.

        ``availability_start`` / ``availability_end`` stay ``None``: SCI offers
        no per-series coverage metadata, so the pipeline fills them from the
        observations actually stored.

        Returns:
            One :class:`IndicatorMetadata` per series, including ``B<year>``
            segments (the canonical linked id is created by Gold)
        """
        discovered: list[IndicatorMetadata] = []
        configured: dict[str, SciPublication] = {}

        for key in self.config.publications:
            publication = SCI_INDICATOR_REGISTRY.get(key)
            if publication is None:
                logger.warning("Unknown SCI publication %s, skipping discovery", key)
                continue
            for member_id in publication.member_ids:
                configured[member_id] = publication

        # Canonical (linked) series first, active: these are what the dashboard
        # should show. A canonical appears when at least one of its segments is
        # configured.
        for canonical in SCI_CANONICAL_INDICATORS.values():
            if any(segment_id in configured for segment_id in canonical.segment_ids):
                discovered.append(_canonical_metadata(canonical, self.config))

        segment_ids = {
            segment_id
            for canonical in SCI_CANONICAL_INDICATORS.values()
            for segment_id in canonical.segment_ids
        }
        for member_id, publication in configured.items():
            discovered.append(
                _publication_member_metadata(
                    publication,
                    member_id,
                    self.config,
                    is_active=member_id not in segment_ids,
                )
            )

        log_with_context(logger, "INFO", "sci discovery", discovered_count=len(discovered))
        return discovered

    def fetch(
        self,
        indicator_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """
        Fetch one series (ABC compatibility).

        SCI publishes whole files, not per-period queries, so ``start_date`` and
        ``end_date`` are ignored; use :meth:`fetch_series` to keep provenance.

        Args:
            indicator_id: Series id (single-series or decile member)
            start_date: Ignored (SCI files are full-history publications)
            end_date: Ignored (SCI files are full-history publications)

        Returns:
            Tidy frame for the requested series

        Raises:
            DataRetrievalError: If the indicator is unknown or the file fails
            ParsingError: If the file cannot be parsed
        """
        return self.fetch_series(indicator_id).frame

    def _publication_for(self, indicator_id: str) -> str | None:
        """Publication slug carrying ``indicator_id``, if any."""
        for key, publication in SCI_INDICATOR_REGISTRY.items():
            if indicator_id in publication.member_ids:
                return key
        return None

    def fetch_publication(self, publication_key: str) -> SciFetchResult:
        """
        Download and parse one publication (may carry several series).

        Args:
            publication_key: One of :data:`SCI_INDICATOR_REGISTRY`

        Returns:
            :class:`SciFetchResult` with the parsed frame and Bronze envelope

        Raises:
            DataRetrievalError: If the publication is unknown or the download fails
            ParsingError: If the file cannot be parsed
        """
        publication = SCI_INDICATOR_REGISTRY.get(publication_key)
        if publication is None:
            msg = f"Unknown SCI publication: {publication_key}"
            raise DataRetrievalError(msg)

        url = self.config.file_url(publication.path)
        started = time.perf_counter()
        download = self._download(publication, url)
        downloaded_at = utc_now()
        checksum = hashlib.sha256(download.data).hexdigest()

        try:
            frame = parse_publication(publication, download.data)
        except ParsingError as exc:
            log_with_context(
                logger,
                "ERROR",
                "sci parsing failed",
                indicator_id=publication.indicator_id,
                url=url,
                error=str(exc),
            )
            raise

        raw_rows = frame_to_rows(frame)
        envelope = _build_envelope(
            publication,
            download,
            raw_rows,
            url=url,
            downloaded_at=downloaded_at,
            sha256=checksum,
        )

        log_with_context(
            logger,
            "INFO",
            "sci fetch complete",
            indicator_id=publication.indicator_id,
            publication=publication_key,
            url=url,
            rows=len(frame),
            series=len({str(v) for v in frame["indicator_id"].tolist()}),
            byte_length=len(download.data),
            download_ms=round((time.perf_counter() - started) * 1000, 1),
        )

        return SciFetchResult(
            indicator_id=publication.indicator_id,
            frame=frame,
            raw_rows=raw_rows,
            raw_envelope=envelope,
            request_url=url,
            http_status_code=download.http_status_code,
            filename=download.filename,
            byte_length=len(download.data),
            sha256=checksum,
            content_type=download.content_type,
            downloaded_at=downloaded_at,
        )

    def fetch_series(self, indicator_id: str) -> SciFetchResult:
        """
        Download and parse the publication carrying a single series.

        Args:
            indicator_id: Series id (single-series or decile member)

        Returns:
            :class:`SciFetchResult` filtered to ``indicator_id`` (the envelope
            still carries the whole file, which is Bronze's unit)

        Raises:
            DataRetrievalError: If the id is unknown or not present in the file
            ParsingError: If the file cannot be parsed
        """
        key = self._publication_for(indicator_id)
        if key is None:
            msg = f"Unknown SCI indicator: {indicator_id}"
            raise DataRetrievalError(msg)

        result = self.fetch_publication(key)
        if indicator_id not in result.series_ids:
            msg = f"SCI file for {key} does not contain series {indicator_id}"
            raise DataRetrievalError(msg)

        result.indicator_id = indicator_id
        result.frame = result.frame[result.frame["indicator_id"] == indicator_id].reset_index(
            drop=True
        )
        return result

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """
        Validate a parsed SCI frame.

        Args:
            data: Frame returned by :meth:`fetch`

        Returns:
            :class:`ValidationResult` with quality metrics
        """
        return validate_data_quality(data, null_threshold=5.0)

    def disconnect(self) -> None:
        """Close the HTTP session and browser only if this connector created them."""
        if self._owns_http:
            self._http.close()
        if self._owns_browser:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._playwright_context is not None:
                self._playwright_context.stop()
                self._playwright_context = None

    def __enter__(self) -> "SciScraper":
        """Context manager entry."""
        return self

    def __exit__(self, *_: Any) -> None:
        """Context manager exit: disconnect."""
        self.disconnect()


# ----------------------------------------------------------- helpers / runner


def _member_name(publication: SciPublication, member_id: str) -> str:
    """Human name for one series, decorating decile members."""
    if member_id != publication.indicator_id and member_id.startswith(publication.indicator_id):
        suffix = member_id[len(publication.indicator_id) :].lstrip(".")
        if suffix.startswith("D") and suffix[1:].isdigit():
            return f"{publication.name} - decile {suffix[1:]}"
    return publication.name


def _canonical_metadata(
    canonical: SciCanonicalIndicator,
    config: SciConfig,
) -> IndicatorMetadata:
    """Discovery metadata for a canonical (chain-linked) series."""
    return IndicatorMetadata(
        indicator_id=canonical.indicator_id,
        name=canonical.name,
        description=(
            f"SCI {canonical.name}; chain-linked from " f"{', '.join(canonical.segment_ids)}"
        ),
        unit=canonical.unit,
        frequency=canonical.frequency,
        domain=canonical.domain,
        source_name=SOURCE_NAME,
        source_url=f"{config.base_url.rstrip('/')}{CPI_INDEX_PATH}",
        availability_start=None,  # Filled from observed data
        availability_end=None,
        has_base_year_changes=canonical.has_base_year_changes,
        base_years=list(canonical.base_years),
        is_active=True,
    )


def _publication_member_metadata(
    publication: SciPublication,
    member_id: str,
    config: SciConfig,
    *,
    is_active: bool,
) -> IndicatorMetadata:
    """Discovery metadata for one series carried by a publication."""
    return IndicatorMetadata(
        indicator_id=member_id,
        name=_member_name(publication, member_id),
        description=(
            f"SCI {publication.name} (base year {publication.base_year})"
            if publication.base_year is not None
            else f"SCI {publication.name}"
        ),
        unit=publication.unit,
        frequency=publication.frequency,
        domain=publication.domain,
        source_name=SOURCE_NAME,
        source_url=config.file_url(publication.path),
        availability_start=None,
        availability_end=None,
        has_base_year_changes=publication.has_base_year_changes,
        base_years=list(publication.base_years) if publication.base_years else None,
        # Base-year segments stay inactive; the canonical series is what users see.
        is_active=is_active,
    )


def _build_envelope(
    publication: SciPublication,
    download: _Download,
    raw_rows: list[dict[str, Any]],
    *,
    url: str,
    downloaded_at: datetime,
    sha256: str,
) -> dict[str, Any]:
    """
    Build the ``{"rows", "meta"}`` Bronze envelope for a file publication.

    The unit of Bronze is the **file**: ``rows`` holds the parsed observations
    (JSON-safe) and ``meta`` carries the file's provenance plus the raw bytes as
    base64 (kept under the configured size guard). ``extract_rows`` reads the
    parsed rows, so the raw file must never be placed there.
    """
    meta: dict[str, Any] = {
        "filename": download.filename,
        "content_type": download.content_type,
        "byte_length": len(download.data),
        "sha256": sha256,
        "url": url,
        "downloaded_at": downloaded_at.isoformat(),
        "indicator_id": publication.indicator_id,
        "base_year": publication.base_year,  # Jalali, as published
        "base_year_gregorian": publication.base_year_gregorian,
        "parser": publication.parser,
        "raw_file_base64": base64.b64encode(download.data).decode("ascii"),
    }
    return {"rows": raw_rows, "meta": meta}


def sci_parser_adapter(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,  # noqa: ARG001 - Silver parser protocol
) -> pd.DataFrame:
    """
    Silver parser adapter for SCI Bronze envelopes.

    The publication was already parsed at collection time, so this only rehydrates
    the stored rows for one series into the Silver column contract.

    Args:
        rows: Parsed observation dicts stored under the envelope's ``rows``
        indicator_id: Series to extract
        unit: Resolved unit; the stored ``unit`` column wins when present
        now: Ignored (Silver owns the future-period cutoff)

    Returns:
        Tidy frame with columns timestamp, value, indicator_id, unit, obs_status
    """
    relevant = [row for row in rows if str(row.get("indicator_id")) == indicator_id]
    if not relevant:
        return empty_frame()

    frame = pd.DataFrame(relevant)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if "unit" not in frame.columns:
        frame["unit"] = unit
    elif unit is not None:
        frame["unit"] = frame["unit"].fillna(unit)
    if "obs_status" not in frame.columns:
        frame["obs_status"] = None
    columns: list[str] = list(SERIES_COLUMNS)
    # Keep the parser's per-row provenance (base_year, period_label) so Silver
    # can persist it for Gold's base-year segment ordering.
    if "record_metadata" in frame.columns:
        columns.append("record_metadata")
    return frame[columns].reset_index(drop=True)


def _series_frequency(series_frame: pd.DataFrame, default: str) -> str:
    """Frequency of a single series, falling back when it is mixed or absent."""
    if "frequency" not in series_frame.columns:
        return default
    values = {str(value) for value in series_frame["frequency"].dropna().tolist()}
    if len(values) == 1:
        return values.pop()
    return default


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


def run_sci_pipeline(
    publications: Sequence[str] | None = None,
    dry_run: bool = False,
    connector: "SciScraper | None" = None,
) -> Any:  # Returns PipelineSummary from src.etl.pipeline
    """
    Download SCI publications into Bronze and Silver (Gold chain-linking is a
    separate step, since the canonical linked id is built from every segment).

    Args:
        publications: Publication slugs to collect; defaults to all configured
        dry_run: Fetch and report without opening a session or writing a row
        connector: Pre-built connector (tests inject one with a fake transport)

    Returns:
        Per-publication outcomes plus an aggregate exit code

    Raises:
        ConnectionError: If SCI cannot be reached at all
    """
    from src.database.connection import get_db, init_database
    from src.etl.pipeline import (  # local imports avoid circular dependency
        PipelineSummary,
        upsert_indicator_catalog,
    )

    owns_connector = connector is None
    if connector is None:
        config = SciConfig()
        if publications:
            config.publications = tuple(publications)
        connector = SciScraper(config=config)
    elif publications:
        connector.config.publications = tuple(publications)

    summary = PipelineSummary(source_name=SOURCE_NAME, dry_run=dry_run)
    targets = connector.config.publications

    if not dry_run:
        try:
            get_db()
        except RuntimeError:
            app_config = get_config()
            init_database(app_config.database.url, echo=app_config.debug)

    try:
        connector.connect()
        discovered = connector.discover()

        if not dry_run:
            with get_db().get_session() as session:
                seeded = upsert_indicator_catalog(session, discovered)
            log_with_context(logger, "INFO", "indicator catalog refreshed", rows=seeded)

        persisted: list[str] = []
        for key in targets:
            outcome = _collect_one_sci(connector, key, discovered, dry_run=dry_run)
            summary.outcomes.append(outcome)
            persisted.extend(outcome.series_ids)

        # Chain-link canonicals only after every configured publication has been
        # persisted, so a canonical sees all of its base-year segments.
        if not dry_run and persisted:
            with get_db().get_session() as session:
                summary.outcomes.extend(_publish_gold_sci(session, persisted))
    finally:
        if owns_connector:
            connector.disconnect()

    log_with_context(
        logger,
        "INFO" if not summary.failed else "WARNING",
        "sci pipeline complete",
        dry_run=dry_run,
        publications=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )
    return summary


def _collect_one_sci(
    connector: "SciScraper",
    publication_key: str,
    discovered: Sequence[IndicatorMetadata],
    dry_run: bool,
) -> Any:  # Returns IndicatorOutcome from src.etl.pipeline
    """
    Collect one SCI publication end to end, containing its failure.

    Each publication gets its own session so a rollback here cannot undo another
    publication's committed work.
    """
    from src.database.connection import get_db
    from src.etl.pipeline import IndicatorOutcome
    from src.utils.exceptions import ValidationError

    status_success = "success"
    status_failed = "failed"
    indicator_errors = (DataRetrievalError, ParsingError, ValidationError)

    publication = SCI_INDICATOR_REGISTRY.get(publication_key)
    indicator_id = publication.indicator_id if publication else publication_key
    outcome = IndicatorOutcome(indicator_id=indicator_id, status=status_success)

    try:
        fetched = connector.fetch_publication(publication_key)
        outcome.indicator_id = fetched.indicator_id
        outcome.rows_fetched = int(len(fetched.frame))

        # A dry run still counts as success: fetch + parse are the whole job.
        if not dry_run:
            with get_db().get_session() as session:
                _persist_publication_sci(
                    session,
                    fetched,
                    outcome,
                    unit=_unit_for_sci(discovered, fetched.series_ids),
                )
    except indicator_errors as exc:
        outcome.status = status_failed
        outcome.error = f"{type(exc).__name__}: {exc}"
        log_with_context(
            logger,
            "ERROR",
            "sci publication failed",
            publication=publication_key,
            error=str(exc),
            error_type=type(exc).__name__,
        )

    return outcome


def _persist_publication_sci(
    session: Any,  # SQLAlchemy Session
    fetched: SciFetchResult,
    outcome: Any,  # IndicatorOutcome
    unit: str | None,
) -> None:
    """
    Write one SCI file to Bronze, then each of its series to Silver.

    The file is Bronze's unit (one row), so every series in a multi-series
    workbook shares the same Bronze id. Gold chain-linking is intentionally not
    run here: the canonical linked id is published once all base-year segments
    exist (see the Phase 5 runner-wiring task).
    """
    from src.etl import bronze, silver
    from src.etl.pipeline import update_catalog_availability

    bronze_id = bronze.write_bronze(
        session,
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        raw_envelope=fetched.raw_envelope,
        request_url=fetched.request_url,
        http_status_code=fetched.http_status_code,
        record_metadata=fetched.collection_metadata(),
    )
    outcome.bronze_id = bronze_id

    silver_written = 0
    records_failed = 0
    envelope_rows = fetched.raw_envelope.get("rows", [])
    for series_id in fetched.series_ids:
        series_frame = fetched.frame[fetched.frame["indicator_id"] == series_id].reset_index(
            drop=True
        )
        # The file is one Bronze row, but it may carry several series (the
        # deciles). Scope the parse to this series' rows so the sibling series
        # are not counted as future/skipped in this series' transformation log.
        series_rows = [row for row in envelope_rows if str(row.get("indicator_id")) == series_id]
        silver_result = silver.bronze_to_silver(
            session,
            bronze_id=bronze_id,
            indicator_id=series_id,
            source_name=SOURCE_NAME,
            frequency=_series_frequency(series_frame, _frequency_for(series_id)),
            unit=unit,
            parser=sci_parser_adapter,
            rows=series_rows,
        )
        silver_written += silver_result.records_written
        records_failed += silver_result.records_failed

        start, end = _observed_range(series_frame)
        update_catalog_availability(session, series_id, start, end)

    outcome.rows_written_silver = silver_written
    outcome.records_failed = records_failed
    outcome.series_ids = list(fetched.series_ids)


def _update_catalog_range(session: Any, indicator_id: str) -> None:
    """Refresh a catalog row's observed coverage from its published Gold rows."""
    from src.etl.gold import load_gold_series
    from src.etl.pipeline import update_catalog_availability

    start, end = _observed_range(load_gold_series(session, indicator_id))
    update_catalog_availability(session, indicator_id, start, end)


def _publish_gold_sci(session: Any, persisted_series: Sequence[str]) -> list[Any]:
    """
    Publish Gold for every series persisted in a run.

    Canonical CPI indicators are chain-linked from all their base-year segments
    (one ``silver_to_gold(..., segment_indicator_ids=[...])`` call each, only
    once every expected segment exists). Series that are not base-year segments
    of a canonical indicator (unemployment, decile members) publish Gold through
    the ordinary single-series path.

    Args:
        session: Active session; the caller owns the transaction
        persisted_series: Series ids written to Silver during the run

    Returns:
        One :class:`IndicatorOutcome` per canonical/plain Gold publication
    """
    from src.etl.gold import silver_to_gold
    from src.etl.pipeline import IndicatorOutcome
    from src.utils.exceptions import ChainLinkingError, ValidationError

    status_success = "success"
    status_failed = "failed"
    gold_errors = (ChainLinkingError, DataRetrievalError, ParsingError, ValidationError)

    persisted = set(persisted_series)
    outcomes: list[Any] = []
    claimed: set[str] = set()

    for canonical in SCI_CANONICAL_INDICATORS.values():
        present = [segment for segment in canonical.segment_ids if segment in persisted]
        if not present:
            continue
        claimed.update(present)

        missing = [segment for segment in canonical.segment_ids if segment not in persisted]
        if missing:
            log_with_context(
                logger,
                "WARNING",
                "skipping chain-linking: not all segments persisted",
                indicator_id=canonical.indicator_id,
                missing=missing,
            )
            outcomes.append(
                IndicatorOutcome(
                    indicator_id=canonical.indicator_id,
                    status=status_failed,
                    error=f"missing Silver segment(s): {', '.join(missing)}",
                )
            )
            continue

        try:
            result = silver_to_gold(
                session,
                indicator_id=canonical.indicator_id,
                domain=canonical.domain,
                base_years=list(canonical.base_years),
                derived_prefix=DERIVED_PREFIX,
                derivation_strategy="yoy",
                segment_indicator_ids=present,
            )
        except gold_errors as exc:
            outcomes.append(
                IndicatorOutcome(
                    indicator_id=canonical.indicator_id,
                    status=status_failed,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            log_with_context(
                logger,
                "ERROR",
                "canonical chain-linking failed",
                indicator_id=canonical.indicator_id,
                error=str(exc),
            )
            continue

        _update_catalog_range(session, canonical.indicator_id)
        outcomes.append(
            IndicatorOutcome(
                indicator_id=canonical.indicator_id,
                status=status_success,
                rows_written_gold=result.records_written,
                is_chain_linked=bool(result.details.get("is_chain_linked")),
            )
        )

    for series_id in sorted(persisted - claimed):
        try:
            result = silver_to_gold(
                session,
                indicator_id=series_id,
                derived_prefix=DERIVED_PREFIX,
                derivation_strategy="yoy",
            )
        except gold_errors as exc:
            outcomes.append(
                IndicatorOutcome(
                    indicator_id=series_id,
                    status=status_failed,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        _update_catalog_range(session, series_id)
        outcomes.append(
            IndicatorOutcome(
                indicator_id=series_id,
                status=status_success,
                rows_written_gold=result.records_written,
                is_chain_linked=bool(result.details.get("is_chain_linked")),
            )
        )

    return outcomes


def _frequency_for(indicator_id: str) -> str:
    """Publication frequency for a series id, falling back to monthly."""
    for publication in SCI_INDICATOR_REGISTRY.values():
        if indicator_id in publication.member_ids:
            return publication.frequency
    return FREQUENCY_MONTHLY


def _unit_for_sci(discovered: Sequence[IndicatorMetadata], series_ids: Sequence[str]) -> str | None:
    """Unit of the first discovered series that matches the fetched ones."""
    wanted = set(series_ids)
    for meta in discovered:
        if meta.indicator_id in wanted:
            return meta.unit
    return None


def resolve_publications(items: Sequence[str]) -> tuple[str, ...]:
    """
    Resolve CLI ``--indicators`` values to publication slugs.

    Accepts either publication slugs (``cpi_national``) or series ids
    (``SCI.CPI.NATIONAL.B2021``); unknown values are logged and skipped.

    Args:
        items: Raw CLI values

    Returns:
        Publication slugs in input order, de-duplicated
    """
    resolved: list[str] = []
    for item in items:
        key = item if item in SCI_INDICATOR_REGISTRY else None
        if key is None:
            for candidate, publication in SCI_INDICATOR_REGISTRY.items():
                if item in publication.member_ids:
                    key = candidate
                    break
        if key is None:
            logger.warning("Unknown SCI publication/indicator %s, skipping", item)
            continue
        if key not in resolved:
            resolved.append(key)
    return tuple(resolved)


def main(argv: Sequence[str] | None = None) -> int:
    """
    CLI entry point: run the SCI scraper pipeline.

    Args:
        argv: Argument vector; defaults to ``sys.argv[1:]``

    Returns:
        Process exit code (0 on success, 1 if any publication failed)
    """
    from src.utils.logging import setup_logging

    parser = argparse.ArgumentParser(
        prog="python -m src.connectors.sci_scraper",
        description="Download SCI CPI/unemployment publications into Bronze/Silver.",
    )
    parser.add_argument(
        "--indicators",
        help=(
            "Comma-separated publication slugs or series ids "
            f"(default: all {len(DEFAULT_PUBLICATIONS)})"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and parse without writing to the database",
    )
    parser.add_argument("--log-level", default=None, help="Override the configured log level")
    args = parser.parse_args(argv)

    config = get_config()
    setup_logging(
        level=args.log_level or config.logging.level,
        log_format=config.logging.format,
    )

    publications = None
    if args.indicators:
        publications = resolve_publications(
            [item.strip() for item in args.indicators.split(",") if item.strip()]
        )

    try:
        summary = run_sci_pipeline(publications=publications, dry_run=args.dry_run)
    except (PlatformConnectionError, DataRetrievalError) as exc:
        log_with_context(
            logger,
            "ERROR",
            "sci pipeline aborted",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        print(f"pipeline aborted: {type(exc).__name__}: {exc}")
        return 1

    print(summary.report())
    return 0 if not summary.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
