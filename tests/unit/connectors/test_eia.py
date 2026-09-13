"""
Unit tests for the EIA Open Data API v2 connector.

Every HTTP call is served from captured fixtures in ``tests/fixtures/eia``; the
suite passes with no network access. The auth contract (403 for a missing or
invalid key), the string ``total``, and ``length``/``offset`` paging were
verified live against the real API on 2026-09-12.
"""

from datetime import UTC, datetime

import pytest
import requests
from requests import HTTPError

from src.connectors.base import DataConnector
from src.connectors.eia import (
    DEFAULT_INDICATORS,
    DEFAULT_START,
    EIA_INDICATORS,
    PLACEHOLDER_API_KEY,
    SOURCE_NAME,
    EiaConfig,
    EiaConnector,
    build_spec,
    is_configured,
)
from src.connectors.eia_parser import eia_parser
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.periods import FREQUENCY_MONTHLY
from src.utils.retry import RateLimiter, RetryPolicy
from tests.conftest import (
    EIA_TEST_KEY,
    FakeHTTPSession,
    FakeResponse,
    eia_session_for,
    load_eia_fixture,
    make_eia_session,
)

CRUDE = "EIA.IRN.CRUDE_PRODUCTION"
LIQUIDS = "EIA.IRN.TOTAL_LIQUIDS"
FIXTURE_ROWS = 29


class _LeakyResponse(FakeResponse):
    """A response whose HTTPError text embeds the query string, like requests."""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            msg = (
                f"{self.status_code} Server Error for url: "
                f"https://api.eia.gov/v2/international/data/?api_key={EIA_TEST_KEY}"
            )
            raise HTTPError(msg, response=self)


def build_connector(
    session: FakeHTTPSession,
    indicators: tuple[str, ...] = (CRUDE,),
    **config_kwargs: object,
) -> EiaConnector:
    """Connector wired to a fake session with instant retries and no throttling."""
    config = EiaConfig(
        api_key=EIA_TEST_KEY,
        indicators=indicators,
        **config_kwargs,  # type: ignore[arg-type]
    )
    return EiaConnector(
        config=config,
        http_session=session,  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=2, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


def crude_session() -> FakeHTTPSession:
    """A fake API serving the captured crude-production payload."""
    return make_eia_session(data={"55": load_eia_fixture("CRUDE_PRODUCTION_normal")})


# ------------------------------------------------------------------- pure config


def test_eia_connector_is_a_data_connector() -> None:
    """The connector implements the shared ABC, not an ad-hoc interface."""
    assert issubclass(EiaConnector, DataConnector)


def test_default_indicators_match_the_registry() -> None:
    """Every registered indicator is collected by default."""
    assert tuple(EIA_INDICATORS) == DEFAULT_INDICATORS
    assert len(DEFAULT_INDICATORS) == 2
    assert CRUDE in DEFAULT_INDICATORS


def test_registry_describes_energy_production_facets() -> None:
    """Facet ids and units are the ones verified against the live API."""
    crude = EIA_INDICATORS[CRUDE]
    liquids = EIA_INDICATORS[LIQUIDS]

    assert crude.domain == "energy"
    assert (crude.product_id, crude.activity_id) == ("55", "1")
    assert (liquids.product_id, liquids.activity_id) == ("53", "1")
    assert crude.unit == "thousand barrels per day"


def test_config_builds_the_international_data_url() -> None:
    """The base URL and route compose without a double slash."""
    config = EiaConfig(base_url="https://api.example/v2/")

    assert config.data_url() == "https://api.example/v2/international/data/"


def test_config_timeout_never_drops_below_thirty_seconds() -> None:
    """EIA can be slow; a shorter timeout guarantees seasonal failures."""
    assert EiaConfig().timeout >= 30


def test_default_start_is_the_phase_four_window() -> None:
    """Without bounds the series reaches 1993; the scope is a recent window."""
    assert EiaConfig().start == DEFAULT_START == "2024-01"


def test_is_configured_rejects_placeholders_and_blanks() -> None:
    """A missing/placeholder key must be caught before any request."""
    assert is_configured(None) is False
    assert is_configured("") is False
    assert is_configured("   ") is False
    assert is_configured(PLACEHOLDER_API_KEY) is False
    assert is_configured("DEMO_KEY") is True
    assert is_configured("abc123") is True


def test_build_spec_describes_a_monthly_energy_source() -> None:
    """The spec carries monthly frequency, the EIA namespace, and the parser."""
    spec = build_spec()

    assert spec.source_name == SOURCE_NAME
    assert spec.frequency == FREQUENCY_MONTHLY
    assert spec.derived_prefix == "EIA"
    assert spec.indicators == DEFAULT_INDICATORS
    assert spec.supports_forecasts is False
    assert spec.parser is eia_parser
    assert spec.default_derivation.include_growth is True


# -------------------------------------------------------------------- auth/connect


def test_connect_without_a_key_raises_before_any_request() -> None:
    """An unconfigured key aborts once with an actionable message."""
    session = crude_session()
    connector = EiaConnector(
        config=EiaConfig(api_key=None, indicators=(CRUDE,)),
        http_session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(PlatformConnectionError) as excinfo:
        connector.connect()

    assert "EIA_API_KEY" in str(excinfo.value)
    assert "register" in str(excinfo.value)
    assert session.calls == []


def test_connect_with_the_placeholder_key_raises() -> None:
    """The ``.env.example`` placeholder is not a key."""
    session = crude_session()
    connector = EiaConnector(
        config=EiaConfig(api_key=PLACEHOLDER_API_KEY, indicators=(CRUDE,)),
        http_session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(PlatformConnectionError) as excinfo:
        connector.connect()

    assert PLACEHOLDER_API_KEY in str(excinfo.value)
    assert session.calls == []


def test_connect_rejects_an_invalid_key_without_retrying() -> None:
    """A 403 is permanent: one request, one actionable error, no retries."""
    session = crude_session()
    connector = build_connector(session)
    connector.config.api_key = "WRONG_KEY"

    with pytest.raises(PlatformConnectionError) as excinfo:
        connector.connect()

    assert "403" in str(excinfo.value)
    assert "API_KEY_INVALID" in str(excinfo.value)
    assert len(session.calls) == 1


def test_connect_probes_the_data_endpoint() -> None:
    """A valid key yields a reachable probe and a length=1 request."""
    session = crude_session()
    connector = build_connector(session)

    assert connector.connect() is True
    assert len(session.calls) == 1
    _, params = session.calls[0]
    assert params["length"] == 1
    assert params["facets[productId][]"] == "55"


def test_connect_wraps_transient_failures() -> None:
    """A network failure surfaces as an actionable platform error."""

    def router(url: str, params: dict[str, object]) -> FakeResponse:
        msg = "boom"
        raise requests.ConnectionError(msg)

    connector = build_connector(FakeHTTPSession(router=router))

    with pytest.raises(PlatformConnectionError, match="unreachable"):
        connector.connect()


def test_disconnect_leaves_an_injected_session_open() -> None:
    """The connector only closes a session it created."""
    session = crude_session()
    connector = build_connector(session)

    connector.disconnect()

    assert session.closed is False


# -------------------------------------------------------------------- discovery


def test_discover_describes_monthly_energy_indicators() -> None:
    """Discovery comes from the committed registry: no network call needed."""
    session = make_eia_session()
    connector = build_connector(session, indicators=(CRUDE, LIQUIDS))

    discovered = connector.discover()

    assert [item.indicator_id for item in discovered] == [CRUDE, LIQUIDS]
    assert session.calls == []
    for item in discovered:
        assert item.frequency == FREQUENCY_MONTHLY
        assert item.domain == "energy"
        assert item.unit == "thousand barrels per day"
        assert item.availability_start is None
        assert item.has_base_year_changes is False


def test_discover_skips_unregistered_indicators() -> None:
    """A typo in the CLI selection must not produce a phantom catalog row."""
    connector = build_connector(make_eia_session(), indicators=("EIA.NOPE",))

    assert connector.discover() == []


# -------------------------------------------------------------------- fetching


def test_fetch_series_selects_iran_and_sorts_ascending() -> None:
    """The fixture-served series is Iran's crude production, oldest first."""
    session = eia_session_for([CRUDE])
    connector = build_connector(session)

    fetched = connector.fetch_series(CRUDE)

    assert len(fetched.frame) == FIXTURE_ROWS
    assert fetched.request_url.startswith("https://")
    assert fetched.frame["timestamp"].is_monotonic_increasing
    assert fetched.frame["value"].notna().all()
    assert set(fetched.frame["unit"]) == {"thousand barrels per day"}
    assert fetched.total_reported == FIXTURE_ROWS

    _, params = session.calls[-1]
    assert params["facets[countryRegionId][]"] == "IRN"
    assert params["facets[activityId][]"] == "1"
    assert params["frequency"] == "monthly"
    assert params["sort[0][direction]"] == "asc"


def test_fetch_series_pages_until_total_is_reached() -> None:
    """``length``/``offset`` paging collects every month exactly once."""
    session = eia_session_for([CRUDE])
    connector = build_connector(session, page_length=10)

    fetched = connector.fetch_series(CRUDE)

    assert len(fetched.frame) == FIXTURE_ROWS
    assert fetched.pages_fetched == 3
    assert [params.get("offset") for _, params in session.calls] == [0, 10, 20]
    assert isinstance(fetched.raw_envelope["raw_response"], list)
    assert len(fetched.raw_envelope["raw_response"]) == 3


def test_fetch_series_handles_an_unknown_facet_as_empty() -> None:
    """HTTP 200 with ``total: "0"`` is an empty series, not an error."""
    connector = build_connector(make_eia_session(data={}))

    fetched = connector.fetch_series(CRUDE)

    assert fetched.frame.empty
    assert fetched.total_reported == 0
    assert fetched.pages_fetched == 1


def test_fetch_series_rejects_a_malformed_payload() -> None:
    """A response without a ``response`` object cannot be interpreted."""
    session = FakeHTTPSession(router=lambda url, params: {"apiVersion": "2.1.13"})
    connector = build_connector(session)

    with pytest.raises(ParsingError):
        connector.fetch_series(CRUDE)


def test_fetch_series_rejects_a_response_without_data() -> None:
    """A missing ``data`` array is malformed, unlike an empty one."""
    payload = {"response": {"total": "0"}, "apiVersion": "2.1.13"}
    session = FakeHTTPSession(router=lambda url, params: payload)
    connector = build_connector(session)

    with pytest.raises(DataRetrievalError):
        connector.fetch_series(CRUDE)


def test_fetch_series_rejects_an_unregistered_indicator() -> None:
    """Only registry entries can be collected."""
    connector = build_connector(eia_session_for([CRUDE]))

    with pytest.raises(DataRetrievalError, match="not registered"):
        connector.fetch_series("EIA.NOPE")


def test_fetch_series_requires_a_key() -> None:
    """Calling the fetch directly with no key still gives the actionable error."""
    connector = EiaConnector(
        config=EiaConfig(api_key=None, indicators=(CRUDE,)),
        http_session=make_eia_session(),  # type: ignore[arg-type]
    )

    with pytest.raises(PlatformConnectionError, match="EIA_API_KEY"):
        connector.fetch_series(CRUDE)


def test_fetch_ignores_the_protocol_date_range() -> None:
    """The configured window wins over the ABC's datetime arguments."""
    connector = build_connector(eia_session_for([CRUDE]))

    frame = connector.fetch(
        CRUDE, datetime(2000, 1, 1, tzinfo=UTC), datetime(2001, 1, 1, tzinfo=UTC)
    )

    assert len(frame) == FIXTURE_ROWS


# ------------------------------------------------------------------ provenance


def test_request_url_never_leaks_the_api_key() -> None:
    """Bronze is append-only and long-lived; the secret must not be in it."""
    connector = build_connector(eia_session_for([CRUDE]))

    fetched = connector.fetch_series(CRUDE)

    assert EIA_TEST_KEY not in fetched.request_url
    assert "api_key" not in fetched.request_url


def test_collection_metadata_never_leaks_the_api_key() -> None:
    """Neither provenance dict may carry the credential."""
    connector = build_connector(eia_session_for([CRUDE]))

    fetched = connector.fetch_series(CRUDE)
    metadata = fetched.collection_metadata()

    assert EIA_TEST_KEY not in str(metadata)
    assert metadata["country"] == "IRN"
    assert metadata["pages_fetched"] == 1
    assert metadata["rows_returned"] == FIXTURE_ROWS
    assert metadata["total_reported"] == FIXTURE_ROWS


def test_validate_accepts_the_fetched_series() -> None:
    """The shared quality check passes a clean, complete monthly series."""
    connector = build_connector(eia_session_for([CRUDE]))

    result = connector.validate(connector.fetch(CRUDE, datetime.now(UTC), datetime.now(UTC)))

    assert result.is_valid is True
    assert result.record_count == FIXTURE_ROWS


def test_retry_errors_do_not_leak_the_api_key() -> None:
    """requests puts the prepared URL -- key included -- in its error text."""
    connector = build_connector(
        FakeHTTPSession(router=lambda url, params: _LeakyResponse({}, status_code=500))
    )

    with pytest.raises(DataRetrievalError) as excinfo:
        connector.fetch_series(CRUDE)

    assert EIA_TEST_KEY not in str(excinfo.value)
    assert "***" in str(excinfo.value)


def test_server_errors_are_retried_then_reported() -> None:
    """A 500 is transient: it is retried and, if it persists, reported."""
    attempts = 0

    def router(url: str, params: dict[str, object]) -> FakeResponse:
        nonlocal attempts
        attempts += 1
        return FakeResponse({"error": {"code": "SERVER"}}, status_code=500)

    connector = build_connector(FakeHTTPSession(router=router))

    with pytest.raises(DataRetrievalError, match="failed after"):
        connector.fetch_series(CRUDE)

    assert attempts == 2
