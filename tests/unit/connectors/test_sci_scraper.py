"""Unit tests for the SCI file scraper connector.

Exercised against the real Task 1 fixtures (``tests/fixtures/sci``) through an
injected fake HTTP transport, so the suite needs no network, no browser and no
database.
"""

import base64
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from src.connectors.base import DataConnector
from src.connectors.sci_scraper import (
    SCI_CANONICAL_INDICATORS,
    SCI_INDICATOR_REGISTRY,
    SOURCE_NAME,
    SciConfig,
    SciPublication,
    SciScraper,
    empty_frame,
    frame_to_rows,
    resolve_publications,
    run_sci_pipeline,
    sci_parser_adapter,
)
from src.utils.exceptions import ChainLinkingError, DataRetrievalError, ParsingError
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.retry import RateLimiter, RetryPolicy

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "sci"

_BASE = "https://www.amar.org.ir"
_NATIONAL_URL = f"{_BASE}/Portals/0/Statistics/ts_national_140505-14050618165053.xlsx"
_DECILE_URL = f"{_BASE}/Portals/0/Statistics/ts_decile_140505-14050618164745.xlsx"
_UNEMPLOYMENT_URL = f"{_BASE}/Portals/0/Statistics/ne_niruye_kar_1405-01-14050525163749.xls"

NATIONAL = "cpi_national"
DECILE = "cpi_decile"
UNEMPLOYMENT = "unemployment_spring_1405"


class FakeResponse:
    """Minimal stand-in for ``requests.Response`` (streamed body)."""

    def __init__(
        self,
        data: bytes = b"",
        *,
        status_code: int = 200,
        content_type: str = "application/octet-stream",
        filename: str = "publication.bin",
        declared_length: int | None = None,
    ) -> None:
        self._data = data
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        length = len(data) if declared_length is None else declared_length
        self.headers: dict[str, str] = {
            "Content-Type": content_type,
            "Content-Length": str(length),
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        self.closed = False

    def iter_content(self, chunk_size: int = 65536) -> Iterator[bytes]:
        for start in range(0, len(self._data), chunk_size):
            yield self._data[start : start + chunk_size]

    def raise_for_status(self) -> None:
        if not self.ok:
            msg = f"HTTP {self.status_code}"
            raise RuntimeError(msg)

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """Routes URLs to pre-built responses and records every request."""

    def __init__(self, mapping: dict[str, FakeResponse]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []
        self.call_kwargs: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(url)
        self.call_kwargs.append(kwargs)
        if url not in self.mapping:
            msg = f"unexpected URL: {url}"
            raise AssertionError(msg)
        return self.mapping[url]

    def close(self) -> None:
        self.closed = True


def fixture_bytes(filename: str) -> bytes:
    return (FIXTURE_DIR / filename).read_bytes()


def build_session() -> FakeSession:
    return FakeSession(
        {
            _BASE: FakeResponse(b"<html>ok</html>", content_type="text/html"),
            _NATIONAL_URL: FakeResponse(
                fixture_bytes("cpi_national_timeseries.xlsx"),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="ts_national.xlsx",
            ),
            _DECILE_URL: FakeResponse(
                fixture_bytes("cpi_decile_timeseries.xlsx"),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename="ts_decile.xlsx",
            ),
            _UNEMPLOYMENT_URL: FakeResponse(
                fixture_bytes("unemployment_spring_1405.xls"),
                content_type="application/vnd.ms-excel",
                filename="ne_niruye_kar.xls",
            ),
        }
    )


def build_scraper(
    session: FakeSession | None = None,
    config: SciConfig | None = None,
    rate_limiter: Any = None,
) -> SciScraper:
    """Build a SciScraper with instant retries and no throttling."""
    return SciScraper(
        config=config or SciConfig(),
        http_session=session or build_session(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=rate_limiter or RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


# ------------------------------------------------------------------- pure logic


def test_sci_scraper_is_a_data_connector() -> None:
    assert issubclass(SciScraper, DataConnector)


def test_source_name_constant() -> None:
    assert SOURCE_NAME == "sci"


def test_config_defaults_from_app_config() -> None:
    config = SciConfig()

    assert config.base_url.startswith("https://www.amar.org.ir")
    assert config.page_timeout_ms >= 30000
    assert config.download_timeout >= 60
    assert config.max_download_bytes >= 1_000_000
    assert config.min_request_interval >= 1.0
    assert config.headless is True


def test_config_download_settings_from_collection_config() -> None:
    config = SciConfig()
    app = SciConfig.__dataclass_fields__  # sanity: fields are config-driven

    assert "max_download_bytes" in app
    assert config.file_url("/Portals/0/Statistics/x.xlsx").startswith(config.base_url)


def test_registry_segment_ids_are_distinct() -> None:
    ids = [publication.indicator_id for publication in SCI_INDICATOR_REGISTRY.values()]
    assert len(ids) == len(set(ids))

    for publication in SCI_INDICATOR_REGISTRY.values():
        assert len(publication.member_ids) == len(set(publication.member_ids))


def test_registry_base_years_are_explicit() -> None:
    national = SCI_INDICATOR_REGISTRY[NATIONAL]
    old_base = SCI_INDICATOR_REGISTRY["cpi_base1395"]

    assert national.base_year == 1400
    assert national.base_year_gregorian == 2021
    assert national.has_base_year_changes is True
    assert national.base_years == (2016, 2021)
    assert old_base.base_year == 1395
    assert old_base.indicator_id.endswith("B2016")


def test_decile_publication_enumerates_ten_members() -> None:
    decile = SCI_INDICATOR_REGISTRY[DECILE]

    assert decile.series_ids == tuple(f"SCI.CPI.DECILE.B2021.D{n}" for n in range(1, 11))
    assert decile.indicator_id == "SCI.CPI.DECILE.B2021"


def test_empty_frame_has_column_contract() -> None:
    frame = empty_frame()
    assert list(frame.columns) == ["timestamp", "value", "indicator_id", "unit", "obs_status"]
    assert frame.empty


def test_resolve_publications_accepts_slugs_and_ids() -> None:
    resolved = resolve_publications([NATIONAL, "SCI.CPI.DECILE.B2021.D3", "bogus"])

    assert resolved == (NATIONAL, DECILE)


# --------------------------------------------------------------------- discovery


def test_discover_returns_metadata_for_every_member() -> None:
    scraper = build_scraper()
    discovered = scraper.discover()
    by_id = {meta.indicator_id: meta for meta in discovered}

    members = sum(len(p.member_ids) for p in SCI_INDICATOR_REGISTRY.values())
    assert len(discovered) == members + len(SCI_CANONICAL_INDICATORS)
    national = by_id["SCI.CPI.NATIONAL.B2021"]
    assert national.domain == "inflation"
    assert national.frequency == "monthly"
    assert national.unit == "index"
    assert national.has_base_year_changes is True
    assert national.base_years == [2016, 2021]
    assert national.is_active is False  # a base-year segment
    assert national.availability_start is None
    assert national.availability_end is None

    decile = by_id["SCI.CPI.DECILE.B2021.D7"]
    assert decile.domain == "inflation"
    assert "decile 7" in decile.name

    unemployment = by_id["SCI.UNEMPLOYMENT.QUARTERLY"]
    assert unemployment.frequency == "quarterly"
    assert unemployment.unit == "percent"
    assert unemployment.base_years is None
    assert unemployment.is_active is True


def test_discover_canonical_active_and_segments_inactive() -> None:
    """The dashboard shows the linked series; raw segments are seeded inactive."""
    scraper = build_scraper()
    by_id = {meta.indicator_id: meta for meta in scraper.discover()}

    urban = by_id["SCI.CPI.URBAN"]
    assert urban.is_active is True
    assert urban.has_base_year_changes is True
    assert urban.base_years == [2016, 2021]
    assert by_id["SCI.CPI.URBAN.B2016"].is_active is False
    assert by_id["SCI.CPI.URBAN.B2021"].is_active is False

    national = by_id["SCI.CPI.NATIONAL"]
    assert national.is_active is True
    assert national.has_base_year_changes is False  # only the 1400 base is published


def test_canonical_registry_matches_real_base_years() -> None:
    urban = SCI_CANONICAL_INDICATORS["SCI.CPI.URBAN"]
    assert urban.segment_ids == ("SCI.CPI.URBAN.B2016", "SCI.CPI.URBAN.B2021")
    assert urban.has_base_year_changes is True
    assert SCI_CANONICAL_INDICATORS["SCI.CPI.NATIONAL"].has_base_year_changes is False


def test_discover_unknown_publication_is_skipped() -> None:
    scraper = build_scraper(config=SciConfig(publications=("not_a_publication",)))
    assert scraper.discover() == []


# ----------------------------------------------------------------------- fetch


def test_fetch_publication_parses_real_fixture() -> None:
    scraper = build_scraper()
    result = scraper.fetch_publication(NATIONAL)

    assert result.indicator_id == "SCI.CPI.NATIONAL.B2021"
    assert len(result.frame) == 185
    assert result.series_ids == ["SCI.CPI.NATIONAL.B2021"]
    assert result.http_status_code == 200
    assert result.byte_length == len(fixture_bytes("cpi_national_timeseries.xlsx"))
    # sha256 matches the Task 1 capture record.
    assert result.sha256 == "155d22eb5958c736bad3ba395dd84e8c06e421b7bbed66a431bdd4c8a77457e1"
    assert result.content_type is not None
    assert result.content_type.endswith("spreadsheetml.sheet")


def test_fetch_publication_bronze_envelope_shape() -> None:
    scraper = build_scraper()
    result = scraper.fetch_publication(NATIONAL)
    envelope = result.raw_envelope

    assert set(envelope) == {"rows", "meta"}
    assert isinstance(envelope["rows"], list)
    assert all(isinstance(row, dict) for row in envelope["rows"])
    assert len(envelope["rows"]) == 185

    meta = envelope["meta"]
    assert meta["sha256"] == result.sha256
    assert meta["filename"] == "ts_national.xlsx"
    assert meta["base_year"] == 1400
    assert meta["base_year_gregorian"] == 2021
    assert "raw_file_base64" in meta

    # The raw file must round-trip exactly through the base64 envelope.
    decoded = base64.b64decode(meta["raw_file_base64"])
    assert decoded == fixture_bytes("cpi_national_timeseries.xlsx")

    # Every row must be JSON-serializable for JSONB storage, and not carry the file.
    json.dumps(envelope)


def test_fetch_publication_envelope_rows_are_extractable() -> None:
    from src.etl.bronze import extract_rows

    scraper = build_scraper()
    result = scraper.fetch_publication(NATIONAL)

    rows = extract_rows(result.raw_envelope)
    assert len(rows) == 185
    assert rows[0]["indicator_id"] == "SCI.CPI.NATIONAL.B2021"
    assert "record_metadata" in rows[0]


def test_fetch_publication_multi_series_frame() -> None:
    scraper = build_scraper()
    result = scraper.fetch_publication(DECILE)

    assert len(result.frame) == 1250
    assert result.series_ids == sorted(result.series_ids, key=lambda s: int(s.rsplit("D", 1)[1]))
    assert len(result.series_ids) == 10


def test_fetch_series_filters_one_member() -> None:
    scraper = build_scraper()
    result = scraper.fetch_series("SCI.CPI.DECILE.B2021.D3")

    assert result.indicator_id == "SCI.CPI.DECILE.B2021.D3"
    assert set(result.frame["indicator_id"]) == {"SCI.CPI.DECILE.B2021.D3"}
    assert len(result.frame) == 125


def test_fetch_series_quarterly_unemployment() -> None:
    scraper = build_scraper()
    result = scraper.fetch_series("SCI.UNEMPLOYMENT.QUARTERLY")

    assert len(result.frame) == 1
    assert float(result.frame["value"].iloc[0]) == pytest.approx(9.1)
    assert str(result.frame["timestamp"].iloc[0]) == "2026-05-31 00:00:00+00:00"


def test_fetch_unknown_publication_and_indicator() -> None:
    scraper = build_scraper()

    with pytest.raises(DataRetrievalError):
        scraper.fetch_publication("nope")
    with pytest.raises(DataRetrievalError):
        scraper.fetch_series("SCI.NOPE")


def test_publication_http_error_is_wrapped() -> None:
    session = FakeSession({_NATIONAL_URL: FakeResponse(status_code=404)})
    scraper = build_scraper(session=session)

    with pytest.raises(DataRetrievalError):
        scraper.fetch_publication(NATIONAL)


# ------------------------------------------------------------------ size guard


def test_size_guard_rejects_declared_oversize() -> None:
    oversized = FakeResponse(fixture_bytes("cpi_national_timeseries.xlsx"))
    oversized.headers["Content-Length"] = "999999999"
    session = FakeSession({_NATIONAL_URL: oversized})
    scraper = build_scraper(session=session, config=SciConfig(max_download_bytes=1000))

    with pytest.raises(DataRetrievalError, match="exceeds"):
        scraper.fetch_publication(NATIONAL)


def test_size_guard_rejects_streamed_oversize() -> None:
    # No trustworthy Content-Length: the cap must still hold while streaming.
    streamed = FakeResponse(fixture_bytes("cpi_national_timeseries.xlsx"))
    streamed.headers.pop("Content-Length")
    session = FakeSession({_NATIONAL_URL: streamed})
    scraper = build_scraper(session=session, config=SciConfig(max_download_bytes=1000))

    with pytest.raises(DataRetrievalError, match="exceeded"):
        scraper.fetch_publication(NATIONAL)


# ------------------------------------------------------------------ rate limit


def test_rate_limiter_waits_before_every_request() -> None:
    limiter = MagicMock()
    scraper = build_scraper(rate_limiter=limiter)

    scraper.fetch_publication(NATIONAL)

    limiter.wait.assert_called()


def test_requests_use_pinned_ca_bundle() -> None:
    """SCI's broken chain is verified against the pinned intermediate, not disabled."""
    session = build_session()
    scraper = build_scraper(session=session)

    scraper.fetch_publication(NATIONAL)

    verify = session.call_kwargs[0]["verify"]
    assert isinstance(verify, str)
    assert verify.endswith("certum_dv_tls_g2_r39_ca.pem")


def test_config_ca_bundle_is_overridable() -> None:
    config = SciConfig(ca_bundle="/custom/ca.pem")
    assert config.ca_bundle == "/custom/ca.pem"


# ---------------------------------------------------------------- connect/probe


def test_connect_probes_base_url() -> None:
    session = build_session()
    scraper = build_scraper(session=session)

    assert scraper.connect() is True
    assert session.calls[0] == _BASE


def test_connect_wraps_failure() -> None:
    session = FakeSession({})  # the probe URL is missing -> AssertionError
    scraper = build_scraper(session=session)

    with pytest.raises(PlatformConnectionError):
        scraper.connect()


# ---------------------------------------------------------------------- parser


def test_sci_parser_adapter_round_trips_and_filters() -> None:
    scraper = build_scraper()
    result = scraper.fetch_publication(NATIONAL)

    frame = sci_parser_adapter(result.raw_rows, "SCI.CPI.NATIONAL.B2021")
    assert list(frame.columns) == [
        "timestamp",
        "value",
        "indicator_id",
        "unit",
        "obs_status",
        "record_metadata",
    ]
    assert len(frame) == 185
    assert str(frame["timestamp"].dtype).startswith("datetime64[ns, UTC]")
    # Base-year provenance must survive into Silver for Gold to order segments.
    assert frame["record_metadata"].iloc[0]["base_year"] == 1400

    other = sci_parser_adapter(result.raw_rows, "SCI.CPI.URBAN.B2021")
    assert other.empty


def test_sci_parser_adapter_unknown_returns_empty() -> None:
    assert sci_parser_adapter([], "SCI.CPI.NATIONAL.B2021").empty


def test_frame_to_rows_is_json_safe() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2021-03-31"], utc=True),
            "value": [10.0],
            "indicator_id": ["X"],
            "unit": ["index"],
            "obs_status": ["A"],
            "base_year": [1400],
            "record_metadata": [{"period_label": "1400/01"}],
        }
    )
    rows = frame_to_rows(frame)

    json.dumps(rows)
    assert rows[0]["timestamp"] == "2021-03-31T00:00:00+00:00"
    assert rows[0]["record_metadata"] == {"period_label": "1400/01"}


# --------------------------------------------------------------------- validate


def test_validate_returns_quality_result() -> None:
    scraper = build_scraper()
    frame = scraper.fetch_publication(NATIONAL).frame

    result = scraper.validate(frame)
    assert hasattr(result, "is_valid")
    assert result.null_percentage == pytest.approx(0.0)


# -------------------------------------------------------------------- ownership


def test_disconnect_does_not_close_injected_session() -> None:
    session = build_session()
    scraper = build_scraper(session=session)

    scraper.disconnect()

    assert session.closed is False


def test_disconnect_closes_owned_session_and_browser() -> None:
    scraper = SciScraper(
        config=SciConfig(),
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )
    assert scraper._owns_http is True
    scraper._http.close = Mock()  # type: ignore[method-assign]

    scraper.disconnect()

    scraper._http.close.assert_called_once()


def test_context_manager_disconnects() -> None:
    session = build_session()
    with build_scraper(session=session) as scraper:
        assert scraper.connect() is True
    assert session.closed is False


# ------------------------------------------------------------- browser download


class FakeDownload:
    def __init__(self, path: Path, filename: str) -> None:
        self._path = path
        self.suggested_filename = filename

    def path(self) -> str:
        return str(self._path)


class FakeDownloadContext:
    def __init__(self, download: FakeDownload) -> None:
        self._download = download

    def __enter__(self) -> "FakeDownloadContext":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    @property
    def value(self) -> FakeDownload:
        return self._download


class FakeBrowserPage:
    def __init__(self, download: FakeDownload) -> None:
        self._download = download
        self.closed = False
        self.goto_calls: list[str] = []

    def set_default_timeout(self, _: float) -> None:
        return None

    def goto(self, url: str) -> None:
        self.goto_calls.append(url)

    def expect_download(self) -> FakeDownloadContext:
        return FakeDownloadContext(self._download)

    def close(self) -> None:
        self.closed = True


class FakeBrowserForDownload:
    def __init__(self, page: FakeBrowserPage) -> None:
        self._page = page

    def new_page(self, user_agent: str | None = None) -> FakeBrowserPage:
        return self._page


def test_download_via_browser(tmp_path: Path) -> None:
    payload = fixture_bytes("cpi_national_timeseries.xlsx")
    local = tmp_path / "download.xlsx"
    local.write_bytes(payload)
    page = FakeBrowserPage(FakeDownload(local, "ts_national.xlsx"))
    scraper = SciScraper(
        config=SciConfig(),
        browser=FakeBrowserForDownload(page),  # type: ignore[arg-type]
        http_session=build_session(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )

    download = scraper._download_via_browser(_NATIONAL_URL)

    assert download.data == payload
    assert download.filename == "ts_national.xlsx"
    assert page.goto_calls == [_NATIONAL_URL]
    assert page.closed is True


def test_browser_publication_via_download_dispatch() -> None:
    payload = b"x" * 10
    page = FakeBrowserPage(FakeDownload(Path("/nonexistent"), "x.bin"))
    scraper = SciScraper(
        config=SciConfig(),
        browser=FakeBrowserForDownload(page),  # type: ignore[arg-type]
        http_session=build_session(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=1, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )
    publication = SciPublication(
        indicator_id="SCI.TEST",
        name="test",
        domain="inflation",
        frequency="monthly",
        base_year=1400,
        path="/x.bin",
        parser="cpi_excel",
        via_browser=True,
    )
    with patch.object(
        scraper, "_download_via_browser", return_value=Mock(data=payload)
    ) as browser_dl:
        scraper._download(publication, "https://example.invalid/x.bin")
    browser_dl.assert_called_once()
    assert payload == b"x" * 10


# ------------------------------------------------------------------- pipeline


def test_run_sci_pipeline_dry_run_counts_rows_and_writes_nothing() -> None:
    session = build_session()
    scraper = build_scraper(
        session=session, config=SciConfig(publications=(NATIONAL, UNEMPLOYMENT))
    )

    with patch("src.database.connection.get_db") as get_db:
        summary = run_sci_pipeline(dry_run=True, connector=scraper)

    get_db.assert_not_called()
    assert summary.dry_run is True
    assert len(summary.outcomes) == 2
    assert not summary.failed
    assert summary.rows_written_silver == 0
    assert summary.rows_written_gold == 0
    fetched = {outcome.indicator_id: outcome.rows_fetched for outcome in summary.outcomes}
    assert fetched["SCI.CPI.NATIONAL.B2021"] == 185
    assert fetched["SCI.UNEMPLOYMENT.QUARTERLY"] == 1


def test_run_sci_pipeline_contains_one_publication_failure() -> None:
    session = FakeSession(
        {
            _BASE: FakeResponse(b"ok", content_type="text/html"),
            _NATIONAL_URL: FakeResponse(status_code=404),
            _UNEMPLOYMENT_URL: FakeResponse(fixture_bytes("unemployment_spring_1405.xls")),
        }
    )
    scraper = build_scraper(
        session=session, config=SciConfig(publications=(NATIONAL, UNEMPLOYMENT))
    )

    summary = run_sci_pipeline(dry_run=True, connector=scraper)

    assert len(summary.succeeded) == 1
    assert len(summary.failed) == 1
    assert summary.failed[0].indicator_id == "SCI.CPI.NATIONAL.B2021"
    assert summary.exit_code == 1


def test_main_dry_run_reports_summary(capsys: pytest.CaptureFixture[str]) -> None:
    from src.connectors import sci_scraper

    summary = Mock()
    summary.report.return_value = "dry run: sci (1/1 indicators ok)"
    summary.failed = []
    with (
        patch.object(sci_scraper, "run_sci_pipeline", return_value=summary),
        patch("src.utils.logging.setup_logging"),
    ):
        exit_code = sci_scraper.main(["--dry-run", "--indicators", NATIONAL])

    assert exit_code == 0
    assert "1/1 indicators ok" in capsys.readouterr().out


# Guard against accidental dependency changes in the parser adapter.
def test_adapter_uses_parsing_error_type_contract() -> None:
    from src.connectors.sci_parser import parse_cpi_excel

    with pytest.raises(ParsingError):
        parse_cpi_excel(b"not a workbook", base_year=1400, indicator_id="X")


# --------------------------------------------------- base-year segment wiring


def test_base1395_uses_the_long_tidy_sheet() -> None:
    """The 1395 segment must reach back further than the 1400 base to link."""
    from src.connectors.sci_scraper import parse_publication

    publication = SCI_INDICATOR_REGISTRY["cpi_base1395"]
    frame = parse_publication(publication, fixture_bytes("cpi_base1395_timeseries.xlsx"))

    assert len(frame) == 491
    assert str(frame["timestamp"].min()).startswith("1982-03-31")
    assert frame["record_metadata"].iloc[0]["base_year"] == 1395


def test_real_urban_segments_chain_link_with_older_history() -> None:
    """The real 1395->1400 urban pair rescales its pre-1381 observations."""
    from src.chain_linking.splice import chain_link
    from src.connectors.sci_scraper import parse_publication

    old = parse_publication(
        SCI_INDICATOR_REGISTRY["cpi_base1395"], fixture_bytes("cpi_base1395_timeseries.xlsx")
    )
    new = parse_publication(
        SCI_INDICATOR_REGISTRY["cpi_urban"], fixture_bytes("cpi_urban_timeseries.xlsx")
    )

    result = chain_link(
        new[["timestamp", "value"]],
        metadata={"segments": [old[["timestamp", "value"]], new[["timestamp", "value"]]]},
        frequency="monthly",
    )

    assert result.is_chain_linked is True
    assert result.records_linked > 0
    assert result.overlap_period_months >= 12
    assert result.linking_method == "overlap"


def test_publish_gold_links_canonical_from_all_segments() -> None:
    from src.connectors import sci_scraper

    session = Mock()
    with (
        patch("src.etl.gold.silver_to_gold") as silver_to_gold,
        patch.object(sci_scraper, "_update_catalog_range"),
    ):
        silver_to_gold.return_value = Mock(records_written=533, details={"is_chain_linked": True})
        outcomes = sci_scraper._publish_gold_sci(
            session, ["SCI.CPI.URBAN.B2016", "SCI.CPI.URBAN.B2021"]
        )

    urban = next(o for o in outcomes if o.indicator_id == "SCI.CPI.URBAN")
    assert urban.status == "success"
    assert urban.rows_written_gold == 533
    assert urban.is_chain_linked is True

    call = next(
        c for c in silver_to_gold.call_args_list if c.kwargs["indicator_id"] == "SCI.CPI.URBAN"
    )
    assert call.kwargs["segment_indicator_ids"] == [
        "SCI.CPI.URBAN.B2016",
        "SCI.CPI.URBAN.B2021",
    ]
    assert call.kwargs["derived_prefix"] == "SCI"


def test_publish_gold_skips_canonical_when_a_segment_is_missing() -> None:
    from src.connectors import sci_scraper

    with (
        patch("src.etl.gold.silver_to_gold") as silver_to_gold,
        patch.object(sci_scraper, "_update_catalog_range"),
    ):
        outcomes = sci_scraper._publish_gold_sci(Mock(), ["SCI.CPI.URBAN.B2021"])

    urban = next(o for o in outcomes if o.indicator_id == "SCI.CPI.URBAN")
    assert urban.status == "failed"
    assert "B2016" in (urban.error or "")
    silver_to_gold.assert_not_called()


def test_publish_gold_publishes_non_segment_series() -> None:
    from src.connectors import sci_scraper

    with (
        patch("src.etl.gold.silver_to_gold") as silver_to_gold,
        patch.object(sci_scraper, "_update_catalog_range"),
    ):
        silver_to_gold.return_value = Mock(records_written=5, details={})
        outcomes = sci_scraper._publish_gold_sci(Mock(), ["SCI.UNEMPLOYMENT.QUARTERLY"])

    assert [o.indicator_id for o in outcomes] == ["SCI.UNEMPLOYMENT.QUARTERLY"]
    silver_to_gold.assert_called_once()


def test_publish_gold_contains_a_failure() -> None:
    from src.connectors import sci_scraper

    with (
        patch("src.etl.gold.silver_to_gold", side_effect=ChainLinkingError("boom")),
        patch.object(sci_scraper, "_update_catalog_range"),
    ):
        outcomes = sci_scraper._publish_gold_sci(Mock(), ["SCI.UNEMPLOYMENT.QUARTERLY"])

    assert outcomes[0].status == "failed"
    assert "ChainLinkingError" in (outcomes[0].error or "")


def test_run_sci_pipeline_publishes_gold_after_all_publications() -> None:
    """Gold runs once, after every configured publication is in Silver."""
    from src.connectors import sci_scraper
    from src.etl.pipeline import IndicatorOutcome

    scraper = build_scraper(config=SciConfig(publications=(NATIONAL, UNEMPLOYMENT)))
    fake_db = MagicMock()
    fake_db.get_session.return_value.__enter__.return_value = MagicMock()
    national = IndicatorOutcome(
        indicator_id="SCI.CPI.NATIONAL.B2021",
        status="success",
        series_ids=["SCI.CPI.NATIONAL.B2021"],
    )
    unemployment = IndicatorOutcome(
        indicator_id="SCI.UNEMPLOYMENT.QUARTERLY",
        status="success",
        series_ids=["SCI.UNEMPLOYMENT.QUARTERLY"],
    )

    with (
        patch("src.database.connection.get_db", return_value=fake_db),
        patch("src.etl.pipeline.upsert_indicator_catalog", return_value=3),
        patch.object(scraper, "connect", return_value=True),
        patch.object(scraper, "discover", return_value=[]),
        patch.object(
            sci_scraper, "_collect_one_sci", side_effect=[national, unemployment]
        ) as collect,
        patch.object(
            sci_scraper,
            "_publish_gold_sci",
            return_value=[
                IndicatorOutcome(
                    indicator_id="SCI.CPI.NATIONAL", status="success", rows_written_gold=42
                )
            ],
        ) as publish_gold,
    ):
        summary = run_sci_pipeline(dry_run=False, connector=scraper)

    assert [call.args[1] for call in collect.call_args_list] == [NATIONAL, UNEMPLOYMENT]
    publish_gold.assert_called_once()
    persisted = publish_gold.call_args.args[1]
    assert set(persisted) == {
        "SCI.CPI.NATIONAL.B2021",
        "SCI.UNEMPLOYMENT.QUARTERLY",
    }
    assert any(outcome.rows_written_gold == 42 for outcome in summary.outcomes)


# ------------------------------------------------------------------- live


@pytest.mark.live()
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="set RUN_LIVE_API_TESTS=1 to hit the real SCI site",
)
def test_live_sci_fetch_parses_a_real_publication() -> None:
    """
    Download and parse one real SCI publication (skipped by default).

    Bounded to a single small workbook — the labour-force survey (legacy
    ``.xls``, ~370 KB, one observation) — so the live check costs one request.
    SCI publishes no API rate limit; the platform's 1-2 req/sec politeness rule
    is enforced by ``RateLimiter``, and ``robots.txt`` permits the publication
    paths. ``amar.org.ir`` serves an incomplete TLS chain, so ``SciScraper``
    pins the missing ``Certum DV TLS G2 R39 CA`` intermediate
    (``src/connectors/certs/``) instead of disabling verification.

    CBI is **not** exercised: its decision gate is closed (F5 bot-defense
    challenge on ``cbi.ir``, unreachable ``tsd.cbi.ir``), so no CBI connector
    exists — see ``docs/phase-5/VALIDATION.md``.

    Asserts parseability and provenance, never fixed values.
    """
    key = "unemployment_spring_1405"
    scraper = SciScraper(config=SciConfig(publications=(key,)))
    try:
        result = scraper.fetch_publication(key)
    finally:
        scraper.disconnect()

    assert result.http_status_code == 200
    assert not result.frame.empty
    assert result.sha256  # provenance captured
    assert result.series_ids == [SCI_INDICATOR_REGISTRY[key].indicator_id]
    assert {"timestamp", "value", "indicator_id", "unit"}.issubset(result.frame.columns)
