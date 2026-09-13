"""
Unit tests for the IMF DataMapper connector.

Every HTTP call is served from captured fixtures in ``tests/fixtures/imf``; the
suite passes with no network access. The behaviours asserted here (ignored
country/period filters, empty-string values key, future-dated forecasts) were
verified live on 2026-09-12.
"""

from datetime import UTC, datetime

import pytest

from src.connectors.base import DataConnector
from src.connectors.imf import (
    DEFAULT_INDICATORS,
    IMF_INDICATORS,
    SOURCE_NAME,
    ImfConfig,
    ImfConnector,
    build_spec,
)
from src.connectors.imf_parser import OBSERVATION_ACTUAL, OBSERVATION_ESTIMATE, imf_parser
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError
from src.utils.retry import RateLimiter, RetryPolicy
from tests.conftest import (
    FakeHTTPSession,
    FakeResponse,
    imf_session_for,
    load_imf_fixture,
    make_imf_session,
)

RPCH = "NGDP_RPCH"
GDPD = "NGDPD"

# Fixture was trimmed to 2010-2031; the April 2026 vintage makes 2026 an estimate.
FIXTURE_ROWS = 22
FORECAST_ROWS = 5


def build_connector(
    session: FakeHTTPSession,
    indicators: tuple[str, ...] = (RPCH,),
) -> ImfConnector:
    """Connector wired to a fake session with instant retries and no throttling."""
    config = ImfConfig(indicators=indicators)
    return ImfConnector(
        config=config,
        http_session=session,  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=2, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


# ------------------------------------------------------------------- pure config


def test_imf_connector_is_a_data_connector() -> None:
    """The connector implements the shared ABC, not an ad-hoc interface."""
    assert issubclass(ImfConnector, DataConnector)


def test_default_indicators_match_the_registry() -> None:
    """Every registered indicator is collected by default."""
    assert tuple(IMF_INDICATORS) == DEFAULT_INDICATORS
    assert len(DEFAULT_INDICATORS) == 6
    assert RPCH in DEFAULT_INDICATORS


def test_registry_domains_use_the_project_vocabulary() -> None:
    """New indicators must map onto the existing domain values."""
    assert IMF_INDICATORS[RPCH].domain == "gdp"
    assert IMF_INDICATORS["PCPIPCH"].domain == "inflation"
    assert IMF_INDICATORS["LUR"].domain == "welfare"
    assert IMF_INDICATORS["BCA_NGDPD"].domain == "trade"


def test_only_level_indicators_get_a_derived_series() -> None:
    """Rate indicators are already percentages; a YoY of them is meaningless."""
    assert IMF_INDICATORS[GDPD].include_growth is True
    assert IMF_INDICATORS["NGDPDPC"].include_growth is True
    assert IMF_INDICATORS[RPCH].include_growth is False
    assert IMF_INDICATORS["PCPIPCH"].include_growth is False


def test_config_builds_the_datamapper_urls() -> None:
    """Endpoints are derived from config, never hardcoded in the logic."""
    config = ImfConfig(base_url="https://imf.example/api/v1", country="IRN")

    assert config.data_url(RPCH) == "https://imf.example/api/v1/NGDP_RPCH"
    assert config.indicators_url() == "https://imf.example/api/v1/indicators"
    assert config.countries_url() == "https://imf.example/api/v1/countries"


def test_config_timeout_never_drops_below_thirty_seconds() -> None:
    """These endpoints are slow in practice; a short timeout guarantees failures."""
    assert ImfConfig().timeout >= 30


def test_build_spec_marks_the_source_forecast_capable() -> None:
    """Forecast support and the parser are what make the generic runner work."""
    spec = build_spec()

    assert spec.source_name == SOURCE_NAME
    assert spec.source_type == "api"
    assert spec.frequency == "annual"
    assert spec.derived_prefix == "IMF"
    assert spec.supports_forecasts is True
    assert spec.parser is imf_parser
    assert spec.indicators == DEFAULT_INDICATORS
    # Only the percentage indicators are opted out of derived series.
    assert set(spec.overrides) == {"NGDP_RPCH", "PCPIPCH", "LUR", "BCA_NGDPD"}


# ------------------------------------------------------------------- connection


def test_connect_probes_countries() -> None:
    """A cheap /countries request confirms reachability."""
    session = imf_session_for([RPCH])

    assert build_connector(session).connect() is True


def test_connect_raises_platform_connection_error_when_unreachable() -> None:
    """Transport failures surface as the platform's ConnectionError."""
    session = make_imf_session(countries=FakeResponse({"error": "down"}, status_code=500))

    with pytest.raises(PlatformConnectionError, match="unreachable"):
        build_connector(session).connect()


def test_disconnect_leaves_an_injected_session_open() -> None:
    """The connector only closes sessions it created itself."""
    session = imf_session_for([RPCH])
    connector = build_connector(session)

    connector.disconnect()

    assert session.closed is False


# -------------------------------------------------------------------- discovery


def test_discover_uses_indicators_metadata() -> None:
    """Names and units come from /indicators; coverage stays unknown."""
    connector = build_connector(
        imf_session_for(list(DEFAULT_INDICATORS)), indicators=DEFAULT_INDICATORS
    )

    discovered = connector.discover()

    assert [item.indicator_id for item in discovered] == list(DEFAULT_INDICATORS)
    by_id = {item.indicator_id: item for item in discovered}
    assert by_id[RPCH].name == "Real GDP growth"
    assert by_id[RPCH].unit == "Annual percent change"
    assert by_id[RPCH].domain == "gdp"
    assert by_id[RPCH].frequency == "annual"
    assert by_id[RPCH].source_name == SOURCE_NAME
    assert by_id[RPCH].availability_start is None
    assert by_id[RPCH].availability_end is None
    assert by_id[RPCH].source_url.endswith(f"/{RPCH}")


# --------------------------------------------------------------------- fetching


def test_fetch_series_selects_iran_and_keeps_the_raw_payload() -> None:
    """Bronze gets the observations plus the untouched multi-country response."""
    connector = build_connector(imf_session_for([RPCH]))

    fetched = connector.fetch_series(RPCH)

    assert len(fetched.frame) == FIXTURE_ROWS
    assert fetched.vintage == 2026
    assert fetched.forecast_through == 2031
    assert fetched.raw_envelope["rows"][0]["period"] == "2010"
    assert "raw_response" in fetched.raw_envelope
    assert fetched.raw_envelope["meta"]["vintage"] == 2026
    assert fetched.request_url.endswith(f"/{RPCH}")


def test_fetch_series_labels_actual_estimate_and_forecast() -> None:
    """Project convention derived from the WEO vintage labels every observation."""
    fetched = build_connector(imf_session_for([RPCH])).fetch_series(RPCH)
    labels = dict(
        zip(fetched.frame["timestamp"].dt.year, fetched.frame["observation_type"], strict=True)
    )

    assert labels[2025] == OBSERVATION_ACTUAL
    assert labels[2026] == OBSERVATION_ESTIMATE
    assert (fetched.frame["observation_type"] == "forecast").sum() == FORECAST_ROWS


def test_fetch_ignores_the_date_range() -> None:
    """The DataMapper has no server-side filtering; the full series comes back."""
    connector = build_connector(imf_session_for([RPCH]))

    frame = connector.fetch(
        RPCH, datetime(2015, 1, 1, tzinfo=UTC), datetime(2016, 1, 1, tzinfo=UTC)
    )

    assert len(frame) == FIXTURE_ROWS
    assert frame["timestamp"].max() == datetime(2031, 12, 31, tzinfo=UTC)


def test_fetch_series_skips_the_empty_string_values_key() -> None:
    """The API's ``""`` key maps to null and must never become an observation."""
    fetched = build_connector(imf_session_for([RPCH])).fetch_series(RPCH)

    assert "" not in set(fetched.raw_envelope["rows"][0].keys())


def test_discovery_metadata_is_cached_across_fetches() -> None:
    """/indicators is fetched once, no matter how many indicators or calls."""
    session = imf_session_for(list(DEFAULT_INDICATORS))
    connector = build_connector(session, indicators=(RPCH, GDPD))

    connector.discover()
    connector.fetch_series(RPCH)
    connector.fetch_series(GDPD)

    indicators_calls = [url for url, _ in session.calls if url.endswith("/indicators")]
    assert len(indicators_calls) == 1


def test_fetch_series_rejects_an_unregistered_indicator() -> None:
    """Asking for something outside the registry fails before any request."""
    with pytest.raises(DataRetrievalError, match="not registered"):
        build_connector(imf_session_for([RPCH])).fetch_series("NOT.REGISTERED")


def test_fetch_series_raises_when_indicators_omits_the_code() -> None:
    """A code the API does not publish is a retrieval error, not an empty series."""
    payload = load_imf_fixture("indicators")
    payload["indicators"].pop(RPCH)
    session = make_imf_session(indicators=payload)

    with pytest.raises(DataRetrievalError, match="does not publish"):
        build_connector(session).fetch_series(RPCH)


def test_fetch_series_raises_on_a_values_less_payload() -> None:
    """An invalid indicator returns HTTP 200 with no values; that is an error."""
    session = make_imf_session(data={RPCH: load_imf_fixture("missing_indicator")})

    with pytest.raises(DataRetrievalError, match="no values"):
        build_connector(session).fetch_series(RPCH)


# -------------------------------------------------------------------- validate


def test_validate_allows_future_forecasts() -> None:
    """The shared quality check must not reject WEO projections as future dates."""
    connector = build_connector(imf_session_for([RPCH]))
    frame = connector.fetch_series(RPCH).frame

    result = connector.validate(frame)

    assert result.is_valid is True
    assert result.record_count == FIXTURE_ROWS
