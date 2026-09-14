"""
Pytest configuration and shared fixtures.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pandas as pd
import pytest
from requests import HTTPError
from sqlalchemy.dialects import postgresql

from src.connectors.base import IndicatorMetadata
from src.database.connection import DatabaseConnection

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
WORLD_BANK_FIXTURES = FIXTURE_ROOT / "world_bank"
IMF_FIXTURES = FIXTURE_ROOT / "imf"
EIA_FIXTURES = FIXTURE_ROOT / "eia"
TSETMC_FIXTURES = FIXTURE_ROOT / "tsetmc"
HBSIR_FIXTURES = FIXTURE_ROOT / "hbsir"

HTTP_OK = 200
HTTP_NOT_FOUND = 404
CLIENT_ERROR_MIN = 400

# Minimal stand-in for the /country/IRN probe `connect()` performs.
COUNTRY_PROBE_PAYLOAD: list[Any] = [
    {"page": 1, "pages": 1, "per_page": 1, "total": 1},
    [{"id": "IRN", "iso2Code": "IR", "name": "Iran, Islamic Rep."}],
]


def load_world_bank_fixture(name: str) -> Any:
    """
    Load one captured World Bank response by fixture stem.

    Args:
        name: File stem under ``tests/fixtures/world_bank`` (no ``.json``)

    Returns:
        The parsed JSON payload, exactly as the API returned it
    """
    return json.loads((WORLD_BANK_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_imf_fixture(name: str) -> Any:
    """
    Load one captured IMF DataMapper response by fixture stem.

    Args:
        name: File stem under ``tests/fixtures/imf`` (no ``.json``)

    Returns:
        The parsed JSON payload, exactly as the API returned it
    """
    return json.loads((IMF_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_eia_fixture(name: str) -> Any:
    """
    Load one captured EIA v2 response by fixture stem.

    Args:
        name: File stem under ``tests/fixtures/eia`` (no ``.json``)

    Returns:
        The parsed JSON payload, exactly as the API returned it
    """
    return json.loads((EIA_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_tsetmc_fixture(name: str) -> Any:
    """
    Load one captured TSETMC cdn response by fixture stem.

    Args:
        name: File stem under ``tests/fixtures/tsetmc`` (no ``.json``)

    Returns:
        The parsed JSON payload, exactly as the cdn returned it
    """
    return json.loads((TSETMC_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def load_hbsir_csv(name: str) -> pd.DataFrame:
    """
    Load one captured HBSIR CSV fixture by stem.

    Args:
        name: File stem under ``tests/fixtures/hbsir`` (no ``.csv``)

    Returns:
        The parsed CSV as a DataFrame
    """
    return pd.read_csv(HBSIR_FIXTURES / f"{name}.csv")


def load_hbsir_json(name: str) -> Any:
    """
    Load one captured HBSIR JSON fixture by stem.

    Args:
        name: File stem under ``tests/fixtures/hbsir`` (no ``.json``)

    Returns:
        The parsed JSON payload
    """
    return json.loads((HBSIR_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@dataclass
class FakeResponse:
    """Stand-in for ``requests.Response`` carrying a captured payload."""

    payload: Any
    status_code: int = HTTP_OK

    def json(self) -> Any:
        """Return the captured payload."""
        return self.payload

    def raise_for_status(self) -> None:
        """Mirror requests' behaviour for error statuses."""
        if self.status_code >= CLIENT_ERROR_MIN:
            msg = f"{self.status_code} error"
            raise HTTPError(msg, response=self)  # type: ignore[arg-type]


@dataclass
class FakeHTTPSession:
    """
    Offline stand-in for ``requests.Session``.

    Routing is delegated to ``router`` so each test decides what the API
    "returns"; every call is recorded for assertions about pagination and
    request spacing.
    """

    router: Callable[[str, dict[str, Any]], Any]
    headers: dict[str, str] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    closed: bool = False

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        """Record the call and return whatever the router provides."""
        resolved = dict(params or {})
        self.calls.append((url, resolved))
        payload = self.router(url, resolved)
        return payload if isinstance(payload, FakeResponse) else FakeResponse(payload)

    def close(self) -> None:
        """Mark the session closed so ``disconnect()`` can be asserted."""
        self.closed = True


def make_world_bank_session(
    data: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    probe: Any = None,
) -> FakeHTTPSession:
    """
    Build a fake World Bank session backed by captured payloads.

    Args:
        data: Indicator code -> data payload. A **tuple** of payloads is served
            as consecutive pages, keyed on the ``page`` query parameter.
        metadata: Indicator code -> ``/indicator/{id}`` payload
        probe: Payload for the ``/country/{code}`` connectivity probe

    Returns:
        A session that answers only the routes it was given; anything else 404s
    """
    data_routes = dict(data or {})
    metadata_routes = dict(metadata or {})
    probe_payload = COUNTRY_PROBE_PAYLOAD if probe is None else probe

    def router(url: str, params: dict[str, Any]) -> Any:
        if "/indicator/" in url:
            indicator_id = url.rsplit("/indicator/", 1)[1]
            routes = data_routes if "/country/" in url else metadata_routes
            payload = routes.get(indicator_id)
            if payload is None:
                return FakeResponse({"message": "not routed"}, status_code=HTTP_NOT_FOUND)
            if isinstance(payload, tuple):
                page = int(params.get("page", 1))
                return payload[page - 1]
            return payload
        if "/country/" in url:
            return probe_payload
        return FakeResponse({"message": "not routed"}, status_code=HTTP_NOT_FOUND)

    return FakeHTTPSession(router=router)


def world_bank_session_for(
    indicators: Sequence[str],
    include_metadata: bool = True,
) -> FakeHTTPSession:
    """
    Convenience builder: serve the ``*_normal`` fixture for each indicator.

    Args:
        indicators: Indicator codes with a captured ``{id}_normal.json`` fixture
        include_metadata: Also serve ``{id}_metadata.json`` when it exists

    Returns:
        A fake session covering discovery, the probe, and each data fetch
    """
    data = {code: load_world_bank_fixture(f"{code}_normal") for code in indicators}
    metadata: dict[str, Any] = {}
    if include_metadata:
        for code in indicators:
            path = WORLD_BANK_FIXTURES / f"{code}_metadata.json"
            if path.exists():
                metadata[code] = load_world_bank_fixture(f"{code}_metadata")
    return make_world_bank_session(data=data, metadata=metadata)


def make_imf_session(
    data: Mapping[str, Any] | None = None,
    indicators: Any = None,
    countries: Any = None,
) -> FakeHTTPSession:
    """
    Build a fake IMF DataMapper session backed by captured payloads.

    Args:
        data: Indicator code -> ``/{code}`` payload. Unrouted codes get the
            captured invalid-indicator payload (HTTP 200, no ``values``).
        indicators: Payload for ``/indicators``; defaults to the captured fixture
        countries: Payload for ``/countries``; defaults to the captured fixture

    Returns:
        A session that answers the DataMapper routes the connector uses
    """
    data_routes = dict(data or {})
    indicators_payload = load_imf_fixture("indicators") if indicators is None else indicators
    countries_payload = load_imf_fixture("countries_normal") if countries is None else countries

    def router(url: str, params: dict[str, Any]) -> Any:
        if url.endswith("/indicators"):
            return indicators_payload
        if url.endswith("/countries"):
            return countries_payload
        code = url.rsplit("/", 1)[1]
        if code in data_routes:
            return data_routes[code]
        return load_imf_fixture("missing_indicator")

    return FakeHTTPSession(router=router)


def imf_session_for(indicators: Sequence[str]) -> FakeHTTPSession:
    """
    Convenience builder: serve the ``{id}_normal`` fixture for each indicator.

    Args:
        indicators: Indicator codes with a captured ``{id}_normal.json`` fixture

    Returns:
        A fake session covering the probe, discovery, and each data fetch
    """
    data = {code: load_imf_fixture(f"{code}_normal") for code in indicators}
    return make_imf_session(data=data)


EIA_TEST_KEY = "TEST_KEY"


def _page_eia_payload(payload: Any, params: Mapping[str, Any]) -> Any:
    """Serve ``length``/``offset`` slices of a captured EIA payload."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("response"), Mapping):
        return payload
    response = dict(payload["response"])
    rows = response.get("data")
    if not isinstance(rows, list):
        return payload
    offset = int(params.get("offset", 0) or 0)
    length = int(params.get("length", len(rows)) or len(rows))
    paged = dict(payload)
    paged["response"] = {**response, "data": rows[offset : offset + length]}
    return paged


def make_eia_session(
    data: Mapping[str, Any] | None = None,
    valid_key: str = EIA_TEST_KEY,
) -> FakeHTTPSession:
    """
    Build a fake EIA v2 session backed by captured payloads.

    The router enforces the same auth contract as the real API (403 for a
    missing or wrong key) and honours ``length``/``offset`` so paging is
    genuinely exercised rather than mocked away.

    Args:
        data: ``productId`` -> captured ``/international/data/`` payload
        valid_key: The key the fake API accepts

    Returns:
        A session that answers the DataMapper routes the connector uses
    """
    fixtures = {str(key): value for key, value in (data or {}).items()}

    def router(url: str, params: dict[str, Any]) -> Any:
        key = params.get("api_key")
        if not key:
            return FakeResponse(load_eia_fixture("API_KEY_MISSING"), status_code=403)
        if key != valid_key:
            return FakeResponse(load_eia_fixture("API_KEY_INVALID"), status_code=403)
        product_id = params.get("facets[productId][]")
        payload = fixtures.get(str(product_id)) if product_id is not None else None
        if payload is None:
            return load_eia_fixture("unknown_facet")
        return _page_eia_payload(payload, params)

    return FakeHTTPSession(router=router)


def eia_session_for(indicators: Sequence[str]) -> FakeHTTPSession:
    """
    Convenience builder: serve the ``{NAME}_normal`` fixture for each indicator.

    Args:
        indicators: Platform indicator ids (``EIA.IRN.CRUDE_PRODUCTION``)

    Returns:
        A fake session covering the auth probe and each indicator's pages
    """
    from src.connectors.eia import EIA_INDICATORS

    data = {}
    for code in indicators:
        registry = EIA_INDICATORS[code]
        fixture = code.rsplit(".", 1)[-1]
        data[registry.product_id] = load_eia_fixture(f"{fixture}_normal")
    return make_eia_session(data=data)


TSETMC_FIXTURE_VERSION = "1.2.10"
TSETMC_FIXTURE_URL = "http://cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957"


@dataclass
class FakeTsetmcClient:
    """
    Offline stand-in for the injectable TSETMC transport.

    Mirrors :class:`src.connectors.tsetmc.TsetmcClient` without importing
    ``finpy_tse``: it replays a captured ``indexB2`` payload (or raises a
    configured exception) and records the ``ins_code`` values it was asked for.
    """

    payload: Any
    package_version: str | None = TSETMC_FIXTURE_VERSION
    available: bool = True
    request_url: str = TSETMC_FIXTURE_URL
    status_code: int | None = HTTP_OK
    calls: list[str] = field(default_factory=list)
    closed: bool = False

    def is_available(self) -> bool:
        """Whether the (fake) package is importable."""
        return self.available

    def fetch_index_history(self, ins_code: str) -> Any:
        """Record the call and return the configured raw payload."""
        from src.connectors.tsetmc import TsetmcIndexPayload

        self.calls.append(ins_code)
        if isinstance(self.payload, Exception):
            raise self.payload
        return TsetmcIndexPayload(
            raw=self.payload,
            request_url=self.request_url,
            http_status_code=self.status_code,
        )

    def close(self) -> None:
        """Mark the client closed so ``disconnect()`` can be asserted."""
        self.closed = True


HBSIR_FIXTURE_VERSION = "0.6.6"


@dataclass
class FakeHbsirLoader:
    """
    Offline stand-in for the injectable HBSIR loader.

    Mirrors :class:`src.connectors.hbsir.HbsirLoader` without importing
    ``hbsir``: it returns pre-seeded income/weight tables and records the
    ``(table_name, years)`` it was asked for.
    """

    tables: dict[str, pd.DataFrame]
    package_version: str | None = HBSIR_FIXTURE_VERSION
    available: bool = True
    calls: list[tuple[str, Any]] = field(default_factory=list)
    closed: bool = False

    def is_available(self) -> bool:
        """Whether the (fake) package is importable."""
        return self.available

    def load_table(self, table_name: str, years: Any) -> pd.DataFrame:
        """Record the call and return the seeded table."""
        self.calls.append((table_name, years))
        return self.tables[table_name]

    def close(self) -> None:
        """Mark the loader closed so ``disconnect()`` can be asserted."""
        self.closed = True


class FakeResult:
    """Stand-in for a SQLAlchemy ``Result`` -- the ETL code ignores the body."""

    rowcount: int = 0


@dataclass
class FakeQuery:
    """Chainable stand-in for ``Session.query`` that replays seeded rows."""

    rows: list[Any]

    def filter(self, *criteria: Any) -> "FakeQuery":
        """Filtering is real-database behaviour; the integration suite covers it."""
        return self

    def order_by(self, *criteria: Any) -> "FakeQuery":
        """Rows are seeded in ascending order already."""
        return self

    def all(self) -> list[Any]:
        """Return the seeded rows."""
        return list(self.rows)


@dataclass
class FakeSession:
    """
    In-memory stand-in for ``sqlalchemy.orm.Session``.

    Only the surface the ETL modules actually use is implemented: ``add``,
    ``flush``, ``get``, ``query``, and ``execute``. ``flush`` assigns primary
    keys because ``default=uuid4`` is applied at INSERT time by the real
    database, and code under test reads ``row.id`` straight after flushing.
    """

    stored: dict[tuple[type, Any], Any] = field(default_factory=dict)
    rows: dict[type, list[Any]] = field(default_factory=dict)
    added: list[Any] = field(default_factory=list)
    executed: list[tuple[Any, Any]] = field(default_factory=list)
    flushes: int = 0
    committed: int = 0

    # ----------------------------------------------------------- Session API

    def add(self, instance: Any) -> None:
        """Stage an ORM instance."""
        self.added.append(instance)

    def flush(self) -> None:
        """Assign the server-side defaults the code under test reads back."""
        self.flushes += 1
        for instance in self.added:
            if getattr(instance, "id", None) is None:
                instance.id = uuid4()

    def commit(self) -> None:
        """Record that a commit happened."""
        self.committed += 1

    def get(self, model: type, primary_key: Any) -> Any:
        """Return a seeded instance, or None as the real session would."""
        return self.stored.get((model, primary_key))

    def query(self, model: type) -> FakeQuery:
        """Return a query over the rows seeded for ``model``."""
        return FakeQuery(rows=self.rows.get(model, []))

    def execute(self, statement: Any, params: Any = None) -> FakeResult:
        """Record a Core statement instead of executing it."""
        self.executed.append((statement, params))
        return FakeResult()

    # --------------------------------------------------------- test helpers

    def seed(self, model: type, instances: Sequence[Any], primary_key: str = "id") -> None:
        """Make ``instances`` visible to both ``get`` and ``query``."""
        self.rows[model] = list(instances)
        for instance in instances:
            self.stored[(model, getattr(instance, primary_key))] = instance

    def added_of(self, model: type) -> list[Any]:
        """Every staged instance of one model, in insertion order."""
        return [instance for instance in self.added if isinstance(instance, model)]

    def inserted(self, model: type) -> list[dict[str, Any]]:
        """Row dicts passed to ``execute(insert(model), [...])``."""
        table = model.__tablename__  # type: ignore[attr-defined]
        collected: list[dict[str, Any]] = []
        for statement, params in self.executed:
            if getattr(statement, "is_insert", False) and statement.table.name == table:
                collected.extend(params or [])
        return collected

    def statement_kinds(self, model: type) -> list[str]:
        """``insert``/``delete`` in execution order, for ordering assertions."""
        table = model.__tablename__  # type: ignore[attr-defined]
        kinds: list[str] = []
        for statement, _ in self.executed:
            if getattr(statement, "table", None) is None or statement.table.name != table:
                continue
            if getattr(statement, "is_delete", False):
                kinds.append("delete")
            elif getattr(statement, "is_insert", False):
                kinds.append("insert")
        return kinds


def compiled_sql(statement: Any) -> str:
    """Render a Core statement as PostgreSQL text (for ON CONFLICT assertions)."""
    return str(statement.compile(dialect=postgresql.dialect()))


@pytest.fixture()
def fake_session() -> FakeSession:
    """A database-free session for the pure-logic ETL tests."""
    return FakeSession()


@pytest.fixture()
def world_bank_fixture() -> Callable[[str], Any]:
    """Loader for captured World Bank JSON fixtures."""
    return load_world_bank_fixture


@pytest.fixture()
def world_bank_session() -> Callable[..., FakeHTTPSession]:
    """Factory for offline World Bank HTTP sessions."""
    return make_world_bank_session


@pytest.fixture()
def sample_indicator() -> IndicatorMetadata:
    """Fixture for sample indicator metadata."""
    return IndicatorMetadata(
        indicator_id="TEST_GDP",
        name="GDP Growth Rate",
        description="Annual GDP growth rate",
        unit="percent",
        frequency="annual",
        domain="gdp",
        source_name="test_source",
        source_url="https://example.com/data",
        availability_start=datetime(1970, 1, 1, tzinfo=UTC),
        availability_end=datetime(2023, 12, 31, tzinfo=UTC),
        has_base_year_changes=True,
        base_years=[1997, 2011, 2016],
    )


@pytest.fixture()
def sample_timeseries() -> pd.DataFrame:
    """Fixture for sample time-series data."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2020-01-01", periods=12, freq="ME", tz="UTC"),
            "value": [
                100.0,
                102.5,
                105.0,
                103.2,
                106.8,
                108.5,
                110.2,
                112.0,
                114.5,
                116.8,
                118.2,
                120.0,
            ],
            "metadata": [{"source": "test"} for _ in range(12)],
        }
    )


@pytest.fixture()
def sample_timeseries_with_nulls() -> pd.DataFrame:
    """Fixture for time-series data with null values."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2020-01-01", periods=12, freq="ME", tz="UTC"),
            "value": [
                100.0,
                None,
                105.0,
                103.2,
                None,
                108.5,
                110.2,
                112.0,
                None,
                116.8,
                118.2,
                120.0,
            ],
        }
    )


@pytest.fixture()
def sample_timeseries_with_outliers() -> pd.DataFrame:
    """Fixture for time-series data with outliers."""
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2020-01-01", periods=12, freq="ME", tz="UTC"),
            "value": [
                100.0,
                102.5,
                105.0,
                103.2,
                500.0,
                108.5,
                110.2,
                112.0,
                114.5,
                1000.0,
                118.2,
                120.0,
            ],  # 500.0 and 1000.0 are outliers
        }
    )


@pytest.fixture()
def mock_db_connection() -> MagicMock:
    """Fixture for mocked database connection."""
    mock_db = MagicMock(spec=DatabaseConnection)
    mock_db.test_connection.return_value = True
    return mock_db


@pytest.fixture()
def test_config() -> dict[str, str]:
    """Fixture for test configuration."""
    return {
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "test_db",
        "DATABASE_USER": "test_user",
        "DATABASE_PASSWORD": "test_pass",
        "LOG_LEVEL": "DEBUG",
        "LOG_FORMAT": "text",
        "COLLECTION_RETRY_MAX": "3",
        "COLLECTION_TIMEOUT": "30",
    }
