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
