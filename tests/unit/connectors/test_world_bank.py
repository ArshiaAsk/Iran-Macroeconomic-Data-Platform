"""
Unit tests for the World Bank Indicators API connector.

Every HTTP call is served from the captured fixtures in
``tests/fixtures/world_bank`` -- this suite passes with no network access.
"""

from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from src.connectors.base import DataConnector
from src.connectors.world_bank import (
    DEFAULT_INDICATORS,
    FREQUENCY_ANNUAL,
    SOURCE_NAME,
    UNIT_MAX_LENGTH,
    WorldBankConfig,
    WorldBankConnector,
    domain_for,
    empty_frame,
    extract_unit,
    rows_to_frame,
)
from src.connectors.world_bank import _parse_annual_timestamp as parse_annual_timestamp
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.retry import RateLimiter, RetryPolicy
from tests.conftest import (
    FakeHTTPSession,
    FakeResponse,
    load_world_bank_fixture,
    make_world_bank_session,
)

GDP = "NY.GDP.MKTP.CD"
CPI = "FP.CPI.TOTL.ZG"
ENERGY = "EG.USE.PCAP.KG.OE"

EXPECTED_ANNUAL_ROWS = 66


def build_connector(
    session: FakeHTTPSession,
    indicators: tuple[str, ...] = (GDP,),
) -> WorldBankConnector:
    """Connector wired to a fake session with instant retries and no throttling."""
    config = WorldBankConfig(indicators=indicators)
    return WorldBankConnector(
        config=config,
        http_session=session,  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_attempts=2, sleep=lambda _: None),
        rate_limiter=RateLimiter(min_interval=0.0, sleep=lambda _: None),
    )


# ------------------------------------------------------------------- pure logic


def test_world_bank_connector_is_a_data_connector() -> None:
    """The connector implements the shared ABC, not an ad-hoc interface."""
    assert issubclass(WorldBankConnector, DataConnector)


def test_default_indicators_cover_the_registry() -> None:
    """Every registered indicator is collected by default."""
    assert len(DEFAULT_INDICATORS) == 12
    assert GDP in DEFAULT_INDICATORS


def test_domain_for_known_and_unknown_indicators() -> None:
    """Registry lookups fall back to a labelled default, never a guess."""
    assert domain_for(GDP) == "gdp"
    assert domain_for(CPI) == "inflation"
    assert domain_for("SP.POP.TOTL") == "welfare"
    assert domain_for(ENERGY) == "energy"
    assert domain_for("NOT.A.REAL.CODE") == "unclassified"


def test_config_builds_both_endpoint_urls() -> None:
    """Data and metadata live on different paths of the same API."""
    config = WorldBankConfig(base_url="https://api.example/v2", country="IRN")

    assert config.data_url(GDP) == "https://api.example/v2/country/IRN/indicator/NY.GDP.MKTP.CD"
    assert config.indicator_url(GDP) == "https://api.example/v2/indicator/NY.GDP.MKTP.CD"


def test_config_timeout_never_drops_below_thirty_seconds() -> None:
    """One observed probe took 25s; a shorter timeout guarantees failures."""
    assert WorldBankConfig().timeout >= 30


def test_extract_unit_prefers_a_real_api_unit() -> None:
    """When the API ever starts populating ``unit``, use it."""
    assert extract_unit("percent", "Inflation (annual %)") == "percent"


def test_extract_unit_falls_back_to_the_name_parenthetical() -> None:
    """The API sends ``unit: ''``, so the name carries the real unit."""
    assert extract_unit("", "GDP (current US$)") == "current US$"
    assert extract_unit(None, "Inflation, consumer prices (annual %)") == "annual %"


def test_extract_unit_returns_none_when_nothing_is_derivable() -> None:
    """A name with no parenthetical yields no unit rather than a bad guess."""
    assert extract_unit("", "Population, total") is None


def test_extract_unit_truncates_to_the_column_width() -> None:
    """``unit`` columns are String(50); a longer value would fail to insert."""
    long_unit = "x" * 80
    assert extract_unit(long_unit, "irrelevant") == "x" * UNIT_MAX_LENGTH


def test_parse_annual_timestamp_uses_period_end() -> None:
    """An annual observation is stamped at December 31, timezone-aware."""
    assert parse_annual_timestamp("2022") == datetime(2022, 12, 31, tzinfo=UTC)


@pytest.mark.parametrize("bad_date", ["2022-01", "22", "twenty", "", None])
def test_parse_annual_timestamp_rejects_non_annual_dates(bad_date: Any) -> None:
    """Anything but a bare four-digit year is a parsing failure, not a guess."""
    with pytest.raises(ParsingError, match="four-digit annual date"):
        parse_annual_timestamp(bad_date)


def test_empty_frame_has_the_column_contract() -> None:
    """Downstream code can rely on the columns even with no observations."""
    frame = empty_frame()

    assert list(frame.columns) == ["timestamp", "value", "indicator_id", "unit", "obs_status"]
    assert frame.empty


def test_rows_to_frame_sorts_ascending_and_preserves_nulls() -> None:
    """Rows arrive newest-first; nulls survive so validate() can measure them."""
    rows = [
        {"date": "2022", "value": None},
        {"date": "2021", "value": 2.0},
        {"date": "2020", "value": 1.0},
    ]

    frame = rows_to_frame(rows, GDP, unit="current US$")

    assert list(frame["timestamp"].dt.year) == [2020, 2021, 2022]
    assert frame["value"].isna().sum() == 1
    assert set(frame["indicator_id"]) == {GDP}
    assert set(frame["unit"]) == {"current US$"}


def test_rows_to_frame_drops_future_periods() -> None:
    """A period that has not ended would fail validate_date_range()."""
    rows = [{"date": "2030", "value": 5.0}, {"date": "2020", "value": 1.0}]

    frame = rows_to_frame(rows, GDP, now=datetime(2026, 6, 30, tzinfo=UTC))

    assert list(frame["timestamp"].dt.year) == [2020]


def test_rows_to_frame_keeps_obs_status_when_present() -> None:
    """``obs_status`` is provenance and is carried into Silver metadata."""
    rows = [{"date": "2020", "value": 1.0, "obs_status": "P"}]

    frame = rows_to_frame(rows, GDP)

    assert frame["obs_status"].iloc[0] == "P"


def test_rows_to_frame_normalises_blank_obs_status_to_none() -> None:
    """The API sends ``""``; storing that as a status would be noise."""
    rows = [{"date": "2020", "value": 1.0, "obs_status": ""}]

    assert rows_to_frame(rows, GDP)["obs_status"].iloc[0] is None


def test_rows_to_frame_handles_no_rows() -> None:
    """An indicator with no data returns the empty contract, not an error."""
    assert rows_to_frame([], GDP).empty


def test_rows_to_frame_rejects_non_numeric_values() -> None:
    """A non-numeric observation is a parsing failure worth surfacing."""
    with pytest.raises(ParsingError, match="non-numeric observation value"):
        rows_to_frame([{"date": "2020", "value": "n/a"}], GDP)


# ---------------------------------------------------------------- fetch_series


def test_fetch_series_parses_a_captured_response() -> None:
    """The normal fixture yields one ascending row per year, 1960-2025."""
    session = make_world_bank_session(data={GDP: load_world_bank_fixture(f"{GDP}_normal")})
    connector = build_connector(session)

    result = connector.fetch_series(GDP)

    assert len(result.frame) == EXPECTED_ANNUAL_ROWS
    assert result.frame["timestamp"].is_monotonic_increasing
    assert result.frame["timestamp"].iloc[0] == pd.Timestamp("1960-12-31", tz="UTC")
    assert result.pages_fetched == 1
    assert result.http_status_code == 200
    assert result.source_last_updated == "2026-07-13"
    assert result.total_reported == EXPECTED_ANNUAL_ROWS


def test_fetch_series_keeps_the_raw_envelope_for_bronze() -> None:
    """Bronze stores what the API said, so the envelope must survive intact."""
    payload = load_world_bank_fixture(f"{GDP}_normal")
    session = make_world_bank_session(data={GDP: payload})

    result = build_connector(session).fetch_series(GDP)

    assert result.raw_envelope[0] == payload[0]
    assert len(result.raw_envelope[1]) == len(payload[1])


def test_fetch_series_reports_collection_metadata() -> None:
    """Provenance recorded on the Bronze row describes this exact fetch."""
    session = make_world_bank_session(data={ENERGY: load_world_bank_fixture(f"{ENERGY}_normal")})

    metadata = build_connector(session).fetch_series(ENERGY).collection_metadata()

    assert metadata["indicator_id"] == ENERGY
    assert metadata["country"] == "IRN"
    assert metadata["rows_returned"] == EXPECTED_ANNUAL_ROWS
    assert metadata["rows_usable"] == EXPECTED_ANNUAL_ROWS
    assert metadata["envelope_convention"] == "raw_data = {meta, rows}"


def test_fetch_series_preserves_null_gaps() -> None:
    """Iran's energy series stops in 2014; the gap must reach validate()."""
    session = make_world_bank_session(data={ENERGY: load_world_bank_fixture(f"{ENERGY}_normal")})

    result = build_connector(session).fetch_series(ENERGY)

    assert result.frame["value"].isna().sum() > 0
    assert result.frame["value"].notna().sum() < EXPECTED_ANNUAL_ROWS


def test_fetch_series_follows_pagination() -> None:
    """A 50-per-page response is fetched to completion."""
    pages = (
        load_world_bank_fixture(f"{CPI}_page1"),
        load_world_bank_fixture(f"{CPI}_page2"),
    )
    session = make_world_bank_session(data={CPI: pages})

    result = build_connector(session, indicators=(CPI,)).fetch_series(CPI)

    assert result.pages_fetched == 2
    assert len(result.frame) == EXPECTED_ANNUAL_ROWS
    assert [params.get("page") for _, params in session.calls] == [1, 2]


def test_fetch_series_raises_on_the_http_200_error_payload() -> None:
    """An invalid indicator returns HTTP 200 with a ``message`` envelope."""
    session = make_world_bank_session(
        data={"BAD.CODE": load_world_bank_fixture("invalid_indicator")}
    )

    with pytest.raises(DataRetrievalError, match="Invalid value"):
        build_connector(session, indicators=("BAD.CODE",)).fetch_series("BAD.CODE")


def test_fetch_series_rejects_an_unexpected_envelope() -> None:
    """The API contract is ``[meta, rows]``; anything else is unparseable."""
    session = make_world_bank_session(data={GDP: {"unexpected": "object"}})

    with pytest.raises(ParsingError, match="unexpected World Bank envelope"):
        build_connector(session).fetch_series(GDP)


def test_fetch_series_honours_an_explicit_date_range() -> None:
    """Start and end dates are translated into the API's ``date`` parameter."""
    session = make_world_bank_session(data={GDP: load_world_bank_fixture(f"{GDP}_normal")})

    result = build_connector(session).fetch_series(
        GDP,
        start_date=datetime(1990, 1, 1, tzinfo=UTC),
        end_date=datetime(2000, 12, 31, tzinfo=UTC),
    )

    assert session.calls[0][1]["date"] == "1990:2000"
    assert "date=1990:2000" in result.request_url


def test_fetch_returns_only_the_frame() -> None:
    """The ABC's ``fetch`` signature returns a DataFrame and writes nothing."""
    session = make_world_bank_session(data={GDP: load_world_bank_fixture(f"{GDP}_normal")})

    frame = build_connector(session).fetch(
        GDP,
        datetime(1960, 1, 1, tzinfo=UTC),
        datetime(2025, 12, 31, tzinfo=UTC),
    )

    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == EXPECTED_ANNUAL_ROWS


def test_fetch_series_retries_a_transient_failure() -> None:
    """One 503 then success: the retry policy absorbs it."""
    payload = load_world_bank_fixture(f"{GDP}_normal")
    attempts: list[int] = []

    def router(url: str, params: dict[str, Any]) -> Any:
        attempts.append(1)
        if len(attempts) == 1:
            return FakeResponse({"message": "unavailable"}, status_code=503)
        return payload

    connector = build_connector(FakeHTTPSession(router=router))

    assert len(connector.fetch_series(GDP).frame) == EXPECTED_ANNUAL_ROWS
    assert len(attempts) == 2


# -------------------------------------------------------------------- discover


def test_discover_maps_metadata_fields() -> None:
    """Discovery fills the catalog columns, including the derived unit."""
    session = make_world_bank_session(
        metadata={
            GDP: load_world_bank_fixture(f"{GDP}_metadata"),
            CPI: load_world_bank_fixture(f"{CPI}_metadata"),
        }
    )

    discovered = build_connector(session, indicators=(GDP, CPI)).discover()

    assert [item.indicator_id for item in discovered] == [GDP, CPI]
    gdp = discovered[0]
    assert gdp.name == "GDP (current US$)"
    assert gdp.unit == "current US$"
    assert gdp.frequency == FREQUENCY_ANNUAL
    assert gdp.domain == "gdp"
    assert gdp.source_name == SOURCE_NAME
    assert gdp.source_url.endswith(f"/country/IRN/indicator/{GDP}")
    assert gdp.description is not None
    # The API cannot report per-country coverage; the pipeline fills these in.
    assert gdp.availability_start is None
    assert gdp.availability_end is None
    # WDI constant-price series are pre-rebased, so no internal break.
    assert gdp.has_base_year_changes is False
    assert gdp.base_years is None


def test_discover_caches_the_unit_for_later_fetches() -> None:
    """A fetch after discovery stamps the discovered unit on every row."""
    session = make_world_bank_session(
        data={GDP: load_world_bank_fixture(f"{GDP}_normal")},
        metadata={GDP: load_world_bank_fixture(f"{GDP}_metadata")},
    )
    connector = build_connector(session)

    connector.discover()
    result = connector.fetch_series(GDP)

    assert result.unit == "current US$"
    assert set(result.frame["unit"]) == {"current US$"}


def test_discover_raises_when_metadata_is_missing() -> None:
    """An indicator with no metadata row cannot be catalogued."""
    session = make_world_bank_session(metadata={GDP: [{"page": 1, "total": 0}, []]})

    with pytest.raises(DataRetrievalError, match="no metadata"):
        build_connector(session).discover()


# --------------------------------------------------------- connect / disconnect


def test_connect_reports_reachability() -> None:
    """The probe hits a cheap endpoint and confirms usable rows come back."""
    session = make_world_bank_session()

    assert build_connector(session).connect() is True
    assert session.calls[0][0].endswith("/country/IRN")


def test_connect_returns_false_on_an_empty_probe() -> None:
    """A reachable API that returns nothing is not usable."""
    session = make_world_bank_session(probe=[{"page": 1, "total": 0}, []])

    assert build_connector(session).connect() is False


def test_connect_raises_platform_connection_error_when_unreachable() -> None:
    """Transport failures surface as the platform's ConnectionError."""
    session = make_world_bank_session(probe={"message": [{"key": "down", "value": "maintenance"}]})

    with pytest.raises(PlatformConnectionError, match="unreachable"):
        build_connector(session).connect()


def test_disconnect_leaves_an_injected_session_open() -> None:
    """The connector only closes sessions it created itself."""
    session = make_world_bank_session()
    connector = build_connector(session)

    connector.disconnect()

    assert session.closed is False


def test_context_manager_disconnects_on_exit() -> None:
    """``with`` cleanup runs the connector's disconnect hook."""
    session = make_world_bank_session(data={GDP: load_world_bank_fixture(f"{GDP}_normal")})
    connector = build_connector(session)

    with connector as active:
        assert active is connector

    # The injected session stays open; ownership is what disconnect respects.
    assert session.closed is False


def test_owned_session_is_created_and_closed() -> None:
    """A connector with no injected session builds and closes its own."""
    connector = WorldBankConnector(config=WorldBankConfig(indicators=(GDP,)))
    # Reaching into the private session is the point: ownership is the behaviour
    # under test, and it is not observable through the public surface.
    session = connector._ensure_session()

    assert session.headers["Accept"] == "application/json"
    assert "iran-macro-platform" in session.headers["User-Agent"]

    connector.disconnect()

    assert connector._http_session is None


# -------------------------------------------------------------------- validate


def test_validate_reports_nulls_as_warnings_not_errors() -> None:
    """A sparse but real series must still be collectable."""
    session = make_world_bank_session(data={ENERGY: load_world_bank_fixture(f"{ENERGY}_normal")})
    connector = build_connector(session, indicators=(ENERGY,))

    result = connector.validate(connector.fetch_series(ENERGY).frame)

    assert result.null_percentage > 0
    assert result.record_count == EXPECTED_ANNUAL_ROWS
    assert result.warnings


def test_validate_accepts_a_complete_series() -> None:
    """Population has no gaps, so validation is clean."""
    code = "SP.POP.TOTL"
    session = make_world_bank_session(data={code: load_world_bank_fixture(f"{code}_normal")})
    connector = build_connector(session, indicators=(code,))

    result = connector.validate(connector.fetch_series(code).frame)

    assert result.null_percentage == 0.0
    assert result.is_valid is True
