"""
Unit tests for the TSETMC connector.

Every test injects a fake transport (``FakeTsetmcClient``) or a fake HTTP
session, so the suite never imports ``finpy_tse`` and never touches the network.
The captured fixture (``tests/fixtures/tsetmc/tedpix_cwi_raw.json``) is the real
cdn payload recorded during the Phase 6 Task 1 gate.
"""

import importlib.metadata
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from src.connectors.base import DataConnector
from src.connectors.tsetmc import (
    DEFAULT_INDICATORS,
    DERIVED_PREFIX,
    FREQUENCY_DAILY,
    PACKAGE_DISTRIBUTION,
    SOURCE_NAME,
    SOURCE_TYPE,
    TSETMC_INDICATORS,
    FinpyTseClient,
    TsetmcConfig,
    TsetmcConnector,
    TsetmcIndexPayload,
    build_spec,
    is_available,
    main,
    package_version,
    run_tsetmc_pipeline,
)
from src.connectors.tsetmc_parser import tsetmc_parser
from src.utils.config import get_config
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError
from src.utils.retry import RateLimiter, RetryPolicy
from tests.conftest import (
    FakeHTTPSession,
    FakeResponse,
    FakeTsetmcClient,
    load_tsetmc_fixture,
)

TEDPIX = "TSETMC.TEDPIX"
INS_CODE = "32097828799138957"


def full_payload() -> dict[str, Any]:
    """The captured full TEDPIX payload (4,283 real sessions)."""
    return load_tsetmc_fixture("tedpix_cwi_raw")


def window_payload() -> dict[str, Any]:
    """The captured payload sliced to the two-week Jalali 1404-06 window."""
    rows = full_payload()["indexB2"]
    return {"indexB2": [row for row in rows if 20250823 <= row["dEven"] <= 20250906]}


def small_payload() -> dict[str, Any]:
    """Three minimal sessions, enough for connector plumbing assertions."""
    return {
        "indexB2": [
            {"insCode": 32097828799138957, "dEven": 20250101, "xNivInuClMresIbs": 100.0},
            {"insCode": 32097828799138957, "dEven": 20250102, "xNivInuClMresIbs": 101.0},
            {"insCode": 32097828799138957, "dEven": 20250104, "xNivInuClMresIbs": 103.0},
        ]
    }


def build_connector(
    client: FakeTsetmcClient | None = None, **config_kwargs: Any
) -> TsetmcConnector:
    """Connector wired to a fake transport and a single-indicator config."""
    config = TsetmcConfig(indicators=(TEDPIX,), **config_kwargs)
    return TsetmcConnector(config=config, client=client or FakeTsetmcClient(small_payload()))


def make_http_client(session: FakeHTTPSession) -> FinpyTseClient:
    """A default client over a fake HTTP session with instant retries."""
    return FinpyTseClient(
        config=TsetmcConfig(),
        http_session=session,  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=2, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


def allow_package(monkeypatch: pytest.MonkeyPatch, client: FinpyTseClient) -> None:
    """Pretend ``finpy_tse`` is importable without importing it."""
    monkeypatch.setattr(
        client,
        "_load_module",
        lambda: SimpleNamespace(headers={"User-Agent": "finpy-tse-test"}),
    )


# ------------------------------------------------------------------- pure registry


def test_connector_is_a_data_connector() -> None:
    """The connector implements the shared ABC, not an ad-hoc interface."""
    assert issubclass(TsetmcConnector, DataConnector)


def test_only_tedpix_is_opened_in_phase_six() -> None:
    """Trading value, market P/E, and market cap stay deferred."""
    assert tuple(TSETMC_INDICATORS) == (TEDPIX,)
    assert DEFAULT_INDICATORS == (TEDPIX,)
    for deferred in ("TSETMC.TRADING_VALUE", "TSETMC.MARKET_PE", "TSETMC.MARKET_CAP"):
        assert deferred not in TSETMC_INDICATORS


def test_registry_maps_tedpix_to_its_index_code() -> None:
    """The registry carries the verified cdn ``insCode`` and market domain."""
    tedpix = TSETMC_INDICATORS[TEDPIX]

    assert tedpix.ins_code == INS_CODE
    assert tedpix.domain == "market"
    assert tedpix.unit == "index points"


def test_config_builds_the_index_history_url_without_a_double_slash() -> None:
    """The base URL and route compose cleanly even with a trailing slash."""
    config = TsetmcConfig(base_url="http://cdn.example/api/")

    assert config.index_history_url("123") == ("http://cdn.example/api/Index/GetIndexB2History/123")


def test_default_timeout_never_drops_below_ten_seconds() -> None:
    """The cdn can be slow; too short a timeout guarantees failures."""
    assert TsetmcConfig().timeout >= 10


def test_build_spec_describes_a_daily_source_with_month_end() -> None:
    """The spec drives the daily derivation plus the month-end downsample."""
    spec = build_spec()

    assert spec.source_name == SOURCE_NAME
    assert spec.source_type == SOURCE_TYPE
    assert spec.frequency == FREQUENCY_DAILY
    assert spec.derived_prefix == DERIVED_PREFIX
    assert spec.indicators == (TEDPIX,)
    assert spec.supports_forecasts is False
    assert spec.default_derivation.derivation_strategy == "daily"
    assert spec.default_derivation.include_growth is True
    assert spec.default_derivation.include_monthly is True
    assert spec.parser is tsetmc_parser


def test_package_version_reads_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """The package has no ``__version__``; the dist metadata is the source."""
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "1.2.10")

    assert package_version() == "1.2.10"


def test_package_version_is_none_when_the_extra_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing optional extra reports no version rather than raising."""

    def missing(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr("importlib.metadata.version", missing)

    assert package_version() is None


def test_is_available_reflects_find_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Availability mirrors whether the import spec can be located."""
    monkeypatch.setattr("importlib.util.find_spec", lambda _name: object())
    assert is_available() is True

    monkeypatch.setattr("importlib.util.find_spec", lambda _name: None)
    assert is_available() is False


# ------------------------------------------------------------------- connectivity


def test_default_connector_uses_the_finpy_client() -> None:
    """With no injected client the connector builds the package transport."""
    assert isinstance(TsetmcConnector().client, FinpyTseClient)


def test_connect_probes_the_cdn_endpoint() -> None:
    """A successful probe returns True and hits the index endpoint."""
    client = FakeTsetmcClient(small_payload())
    connector = build_connector(client)

    assert connector.connect() is True
    assert client.calls == [INS_CODE]


def test_connect_returns_false_for_an_empty_payload() -> None:
    """An empty ``indexB2`` array is reachable but not usable."""
    connector = build_connector(FakeTsetmcClient({"indexB2": []}))

    assert connector.connect() is False


def test_connect_raises_when_the_extra_is_missing() -> None:
    """A missing optional package gives one actionable, package-free error."""
    connector = build_connector(FakeTsetmcClient(small_payload(), available=False))

    with pytest.raises(PlatformConnectionError, match="finpy-tse"):
        connector.connect()


def test_connect_wraps_retrieval_failures() -> None:
    """A malformed payload surfaces as a connection error at connect time."""
    client = FakeTsetmcClient(DataRetrievalError("cdn returned nonsense"))
    connector = build_connector(client)

    with pytest.raises(PlatformConnectionError, match="unreachable"):
        connector.connect()


def test_disconnect_leaves_an_injected_client_open() -> None:
    """An injected client belongs to the caller and is not closed."""
    client = FakeTsetmcClient(small_payload())
    connector = build_connector(client)

    connector.disconnect()

    assert client.closed is False


def test_disconnect_closes_a_client_it_created(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default client owns its HTTP session and closes it."""
    connector = TsetmcConnector(config=TsetmcConfig(indicators=(TEDPIX,)))
    client = connector.client
    assert isinstance(client, FinpyTseClient)
    allow_package(monkeypatch, client)

    client._ensure_session()  # ownership probe
    connector.disconnect()

    assert client._http_session is None  # session released


# ------------------------------------------------------------------- discovery


def test_discover_describes_daily_market_indicators() -> None:
    """Discovery reports the registry with availability left to the pipeline."""
    discovered = build_connector().discover()

    assert len(discovered) == 1
    meta = discovered[0]
    assert meta.indicator_id == TEDPIX
    assert meta.frequency == FREQUENCY_DAILY
    assert meta.domain == "market"
    assert meta.unit == "index points"
    assert meta.source_name == SOURCE_NAME
    assert meta.availability_start is None
    assert meta.availability_end is None
    assert meta.has_base_year_changes is False
    assert meta.source_url is not None and meta.source_url.endswith(
        f"/Index/GetIndexB2History/{INS_CODE}"
    )


def test_discover_skips_unregistered_indicators() -> None:
    """An unknown code is skipped rather than fabricated."""
    connector = TsetmcConnector(
        config=TsetmcConfig(indicators=("TSETMC.NOT_REAL",)),
        client=FakeTsetmcClient(small_payload()),
    )

    assert connector.discover() == []
    with pytest.raises(DataRetrievalError, match="not registered"):
        connector.fetch_series("TSETMC.NOT_REAL")


# ------------------------------------------------------------------- fetching


def test_fetch_series_returns_frame_and_raw_envelope() -> None:
    """The result carries the normalized frame and the raw ``indexB2`` rows."""
    payload = window_payload()
    client = FakeTsetmcClient(payload)
    result = build_connector(client).fetch_series(TEDPIX)

    assert len(result.frame) == 9
    assert result.raw_envelope["rows"] == payload["indexB2"]
    assert result.raw_envelope["meta"]["ins_code"] == INS_CODE
    assert result.raw_envelope["meta"]["package"] == PACKAGE_DISTRIBUTION
    assert result.raw_envelope["meta"]["rows_returned"] == 9
    assert result.raw_envelope["meta"]["rows_usable"] == 9
    assert result.request_url.startswith("http")
    assert result.package_version == "1.2.10"
    assert client.calls == [INS_CODE]


def test_collection_metadata_records_package_provenance() -> None:
    """Bronze metadata names the package, its version, and the index code."""
    result = build_connector(FakeTsetmcClient(small_payload())).fetch_series(TEDPIX)

    metadata = result.collection_metadata()
    assert metadata["package"] == "finpy-tse"
    assert metadata["package_version"] == "1.2.10"
    assert metadata["ins_code"] == INS_CODE
    assert metadata["rows_returned"] == 3
    assert metadata["rows_usable"] == 3
    assert metadata["envelope_convention"] == "raw_data = {rows, meta}"


def test_fetch_ignores_the_protocol_date_range() -> None:
    """The ABC date arguments do not window the full-history fetch."""
    connector = build_connector(FakeTsetmcClient(small_payload()))

    frame = connector.fetch(TEDPIX, datetime(2020, 1, 1, tzinfo=UTC), datetime.now(UTC))

    assert len(frame) == 3


def test_fetch_series_requires_a_registered_indicator() -> None:
    """An unknown indicator code fails before any transport call."""
    client = FakeTsetmcClient(small_payload())

    with pytest.raises(DataRetrievalError, match="not registered"):
        build_connector(client).fetch_series("TSETMC.NOT_REAL")
    assert client.calls == []


# ------------------------------------------------------------------- validation


def test_validate_accepts_a_positive_index_series() -> None:
    """A normal TEDPIX window validates cleanly."""
    connector = build_connector()
    frame = tsetmc_parser(small_payload()["indexB2"], TEDPIX, "index points")

    assert connector.validate(frame).is_valid is True


def test_validate_rejects_non_positive_index_levels() -> None:
    """A zero/negative level is invalid for a positive chained index."""
    connector = build_connector()
    rows = [
        {"dEven": 20250101, "xNivInuClMresIbs": 100.0},
        {"dEven": 20250102, "xNivInuClMresIbs": 0.0},
    ]
    result = connector.validate(tsetmc_parser(rows, TEDPIX, "index points"))

    assert result.is_valid is False
    assert any("not positive" in error for error in result.errors)


# ------------------------------------------------------------------- transport


def test_finpy_client_fetches_the_raw_index_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default transport GETs the cdn endpoint and returns raw JSON."""
    session = FakeHTTPSession(router=lambda url, params: full_payload())
    client = make_http_client(session)
    allow_package(monkeypatch, client)

    payload = client.fetch_index_history(INS_CODE)

    assert payload.http_status_code == 200
    assert payload.request_url.endswith(f"/Index/GetIndexB2History/{INS_CODE}")
    assert len(payload.rows()) == 4283
    assert session.calls and session.calls[0][0] == payload.request_url


def test_finpy_client_rejects_a_payload_without_indexb2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JSON body without ``indexB2`` is a retrieval error."""
    session = FakeHTTPSession(router=lambda url, params: {"unexpected": []})
    client = make_http_client(session)
    allow_package(monkeypatch, client)

    with pytest.raises(DataRetrievalError, match="indexB2"):
        client.fetch_index_history(INS_CODE)


def test_finpy_client_rejects_a_non_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-JSON body is a retrieval error, not a crash."""
    session = FakeHTTPSession(router=lambda url, params: _BadJsonResponse())
    client = make_http_client(session)
    allow_package(monkeypatch, client)

    with pytest.raises(DataRetrievalError, match="valid JSON"):
        client.fetch_index_history(INS_CODE)


def test_finpy_client_surfaces_a_permanent_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 404 is not retried and becomes an actionable connection error."""
    session = FakeHTTPSession(router=lambda url, params: FakeResponse({}, status_code=404))
    client = make_http_client(session)
    allow_package(monkeypatch, client)

    with pytest.raises(PlatformConnectionError, match="rejected"):
        client.fetch_index_history(INS_CODE)


def test_finpy_client_retries_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 5xx is retried and reported as a retrieval failure after attempts."""
    session = FakeHTTPSession(router=lambda url, params: FakeResponse({}, status_code=500))
    client = make_http_client(session)
    allow_package(monkeypatch, client)

    with pytest.raises(DataRetrievalError):
        client.fetch_index_history(INS_CODE)
    assert len(session.calls) == 2


class _BadJsonResponse(FakeResponse):
    """A 200 response whose body is not valid JSON."""

    def __init__(self) -> None:
        super().__init__(payload=None)

    def json(self) -> Any:
        """Mimic ``requests`` when the body cannot be decoded."""
        msg = "not json"
        raise ValueError(msg)


# ------------------------------------------------------------------- cli


def test_main_parses_indicators_and_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI selects indicators and hands the run to the shared runner."""
    captured: dict[str, Any] = {}

    def fake_run_cli(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("src.etl.pipeline.run_cli", fake_run_cli)

    exit_code = main(["--indicators", TEDPIX, "--dry-run"])

    assert exit_code == 0
    assert captured["indicators"] == (TEDPIX,)
    assert captured["dry_run"] is True
    assert captured["spec"].source_name == SOURCE_NAME
    assert captured["connector"].config.indicators == (TEDPIX,)


# --------------------------------------------------- programmatic entry point


def test_run_tsetmc_pipeline_hands_control_to_the_shared_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DAG entry point builds the spec and calls run_pipeline unchanged."""
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_run_pipeline(connector: Any, spec: Any, **kwargs: Any) -> Any:
        captured.update(connector=connector, spec=spec, **kwargs)
        return sentinel

    monkeypatch.setattr("src.etl.pipeline.run_pipeline", fake_run_pipeline)
    connector = build_connector()

    result = run_tsetmc_pipeline(connector=connector, dry_run=True)

    assert result is sentinel
    assert captured["connector"] is connector
    assert captured["spec"].source_name == SOURCE_NAME
    assert captured["spec"].indicators == (TEDPIX,)
    assert captured["dry_run"] is True


def test_run_tsetmc_pipeline_builds_a_default_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no injected connector it builds the registry-backed default."""
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        "src.etl.pipeline.run_pipeline",
        lambda connector, spec, **kwargs: captured.update(connector=connector, spec=spec, **kwargs),
    )

    run_tsetmc_pipeline(dry_run=True)

    connector = captured["connector"]
    assert isinstance(connector, TsetmcConnector)
    assert connector.config.indicators == DEFAULT_INDICATORS
    assert captured["indicators"] == DEFAULT_INDICATORS


def test_run_tsetmc_pipeline_builds_a_default_connector_with_a_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an injected connector an explicit selection still reaches it."""
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        "src.etl.pipeline.run_pipeline",
        lambda connector, spec, **kwargs: captured.update(connector=connector, **kwargs),
    )

    run_tsetmc_pipeline(indicators=(TEDPIX,), dry_run=True)

    assert captured["connector"].config.indicators == (TEDPIX,)
    assert captured["indicators"] == (TEDPIX,)


def test_run_tsetmc_pipeline_selects_indicators(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller-provided selection narrows the connector and the runner."""
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        "src.etl.pipeline.run_pipeline",
        lambda connector, spec, **kwargs: captured.update(connector=connector, **kwargs),
    )
    connector = build_connector()

    run_tsetmc_pipeline(indicators=(TEDPIX,), connector=connector, dry_run=True)

    assert captured["connector"].config.indicators == (TEDPIX,)
    assert captured["indicators"] == (TEDPIX,)


def test_run_tsetmc_pipeline_only_closes_a_connector_it_owns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An injected connector belongs to the caller and must stay open."""
    closed: list[bool] = []

    monkeypatch.setattr("src.etl.pipeline.run_pipeline", lambda connector, spec, **kwargs: None)
    connector = build_connector()
    monkeypatch.setattr(connector, "disconnect", lambda: closed.append(True))

    run_tsetmc_pipeline(connector=connector, dry_run=True)

    assert closed == []


def test_run_tsetmc_pipeline_closes_the_default_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connector the wrapper built itself is released after the run."""
    closed: list[bool] = []

    monkeypatch.setattr("src.etl.pipeline.run_pipeline", lambda connector, spec, **kwargs: None)
    monkeypatch.setattr(TsetmcConnector, "disconnect", lambda self: closed.append(True))

    run_tsetmc_pipeline(dry_run=True)

    assert closed == [True]


def test_run_tsetmc_pipeline_initializes_the_database_for_a_real_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-dry programmatic run opens a DB engine before persisting."""
    initialized: list[tuple[str, bool]] = []
    app_config = get_config()

    def missing_db() -> Any:
        message = "database not initialized"
        raise RuntimeError(message)

    monkeypatch.setattr("src.etl.pipeline.run_pipeline", lambda *a, **k: None)
    monkeypatch.setattr("src.database.connection.get_db", missing_db)
    monkeypatch.setattr(
        "src.database.connection.init_database",
        lambda url, echo=False: initialized.append((url, echo)),
    )

    run_tsetmc_pipeline(connector=build_connector(), dry_run=False)

    assert initialized == [(app_config.database.url, app_config.debug)]


def test_run_tsetmc_pipeline_reuses_an_existing_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already-initialized singleton is not re-initialized."""
    initialized: list[object] = []

    monkeypatch.setattr("src.etl.pipeline.run_pipeline", lambda *a, **k: None)
    monkeypatch.setattr("src.database.connection.get_db", lambda: object())
    monkeypatch.setattr(
        "src.database.connection.init_database", lambda *a, **k: initialized.append(a)
    )

    run_tsetmc_pipeline(connector=build_connector(), dry_run=False)

    assert initialized == []


# ------------------------------------------------------------- raw payload rows


def test_index_payload_rows_filters_non_mapping_entries() -> None:
    """Only dict records are surfaced; scalars are dropped, not parsed."""
    payload = TsetmcIndexPayload(
        raw={"indexB2": [{"dEven": 20250101}, "junk", 7, None, {"dEven": 20250102}]},
        request_url="http://cdn.example/api/Index/GetIndexB2History/1",
    )

    assert payload.rows() == [{"dEven": 20250101}, {"dEven": 20250102}]


@pytest.mark.parametrize("raw", [{}, {"indexB2": "not-a-list"}, {"indexB2": None}])
def test_index_payload_rows_is_empty_for_malformed_shapes(raw: dict[str, Any]) -> None:
    """A payload without an ``indexB2`` array yields no rows."""
    payload = TsetmcIndexPayload(raw=raw, request_url="http://cdn.example/x")

    assert payload.rows() == []


def test_fetch_series_handles_an_empty_payload() -> None:
    """An empty history is a valid result: no rows, but full provenance."""
    result = build_connector(FakeTsetmcClient({"indexB2": []})).fetch_series(TEDPIX)

    assert result.frame.empty
    assert result.raw_envelope["rows"] == []
    assert result.raw_envelope["meta"]["rows_returned"] == 0
    assert result.raw_envelope["meta"]["rows_usable"] == 0


def test_fetch_series_propagates_a_transport_failure() -> None:
    """A malformed cdn response surfaces as a retrieval error, not empty data."""
    client = FakeTsetmcClient(DataRetrievalError("payload had no indexB2 array"))

    with pytest.raises(DataRetrievalError, match="no indexB2"):
        build_connector(client).fetch_series(TEDPIX)
