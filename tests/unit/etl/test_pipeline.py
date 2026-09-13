"""
Unit tests for the generic pipeline runner.

The ETL roundtrip is covered by the integration suites; these tests pin the
runner's own contract: a :class:`SourceSpec` drives source name, frequency and
targets, per-indicator failures are contained, and a dry run writes nothing.
The database and persistence are stubbed so nothing here needs Postgres.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from src.connectors.base import IndicatorMetadata
from src.etl import pipeline
from src.etl.lineage import STATUS_FAILED, STATUS_SUCCESS
from src.etl.pipeline import (
    WORLD_BANK_SPEC,
    IndicatorDerivation,
    SourceSpec,
    _derivation_for,
    run_pipeline,
)
from src.utils.exceptions import DataRetrievalError

IMF = SourceSpec(
    source_name="imf",
    source_type="api",
    frequency="annual",
    derived_prefix="IMF",
    indicators=("IMF.A", "IMF.B"),
    overrides={"IMF.A": IndicatorDerivation(derivation_strategy="yoy", include_growth=True)},
)


@dataclass
class FakeFetchResult:
    """Minimal ``FetchResult`` implementation for the fake connector."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: dict[str, Any] = field(default_factory=lambda: {"rows": []})
    request_url: str | None = "https://example.test"
    http_status_code: int | None = 200

    def collection_metadata(self) -> dict[str, Any]:
        return {"indicator_id": self.indicator_id}


class FakeConnector:
    """In-memory connector: no network, optional per-indicator failure."""

    def __init__(
        self,
        indicator_ids: tuple[str, ...],
        fail: tuple[str, ...] = (),
    ) -> None:
        self.connected = False
        self.disconnected = False
        self.discover_calls = 0
        self._fail = fail
        self._metadata = [_metadata(indicator_id) for indicator_id in indicator_ids]

    def connect(self) -> bool:
        self.connected = True
        return True

    def discover(self) -> list[IndicatorMetadata]:
        self.discover_calls += 1
        return self._metadata

    def fetch_series(self, indicator_id: str) -> FakeFetchResult:
        if indicator_id in self._fail:
            msg = f"{indicator_id} unavailable"
            raise DataRetrievalError(msg)
        return FakeFetchResult(
            indicator_id=indicator_id,
            frame=pd.DataFrame({"timestamp": [1], "value": [1.0]}),
        )

    def disconnect(self) -> None:
        self.disconnected = True


def _metadata(indicator_id: str) -> IndicatorMetadata:
    return IndicatorMetadata(
        indicator_id=indicator_id,
        name=indicator_id,
        description=None,
        unit="percent",
        frequency="annual",
        domain="gdp",
        source_name="imf",
        source_url=None,
        availability_start=None,
        availability_end=None,
        has_base_year_changes=False,
        base_years=None,
    )


class FakeDatabase:
    """Stand-in for the global ``DatabaseConnection`` handle."""

    def __init__(self) -> None:
        self.sessions = 0

    @contextmanager
    def get_session(self) -> Any:
        self.sessions += 1
        yield object()


def stub_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, tuple[Any, ...]], FakeDatabase]:
    """Replace persistence and the database handle; return the recorders."""
    recorded: dict[str, tuple[Any, ...]] = {}

    def fake_persist(
        session: Any,
        spec: SourceSpec,
        fetched: Any,
        outcome: Any,
        domain: str | None,
        unit: str | None,
    ) -> None:
        recorded[fetched.indicator_id] = (spec, domain, unit)

    monkeypatch.setattr(pipeline, "_persist_indicator", fake_persist)
    monkeypatch.setattr(
        pipeline, "upsert_indicator_catalog", lambda session, discovered: len(discovered)
    )
    database = FakeDatabase()
    monkeypatch.setattr(pipeline, "get_db", lambda: database)
    return recorded, database


def test_spec_drives_source_name_and_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SourceSpec` is the only source-specific input the runner needs."""
    recorded, _ = stub_writes(monkeypatch)
    connector = FakeConnector(("IMF.A", "IMF.B"))

    summary = run_pipeline(connector, IMF)

    assert connector.connected is True
    assert connector.discover_calls == 1
    assert summary.source_name == "imf"
    assert [outcome.indicator_id for outcome in summary.outcomes] == ["IMF.A", "IMF.B"]
    assert set(recorded) == {"IMF.A", "IMF.B"}
    assert recorded["IMF.A"][0] is IMF
    assert recorded["IMF.A"][1] == "gdp"
    assert recorded["IMF.A"][2] == "percent"


def test_explicit_indicators_override_the_spec_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI ``--indicators`` selection narrows the run."""
    stub_writes(monkeypatch)
    connector = FakeConnector(("IMF.A", "IMF.B"))

    summary = run_pipeline(connector, IMF, indicators=("IMF.B",))

    assert [outcome.indicator_id for outcome in summary.outcomes] == ["IMF.B"]


def test_one_failure_does_not_abort_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bad indicator is counted; its neighbours still complete."""
    stub_writes(monkeypatch)
    connector = FakeConnector(("IMF.A", "IMF.B"), fail=("IMF.A",))

    summary = run_pipeline(connector, IMF)

    assert [outcome.status for outcome in summary.outcomes] == [STATUS_FAILED, STATUS_SUCCESS]
    assert summary.outcomes[0].error is not None
    assert summary.outcomes[1].rows_fetched == 1
    assert summary.exit_code == 1


def test_dry_run_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dry run fetches and reports but never touches the database."""
    stub_writes(monkeypatch)

    def fail_get_db() -> Any:
        msg = "dry run must not open a session"
        raise AssertionError(msg)

    monkeypatch.setattr(pipeline, "get_db", fail_get_db)
    connector = FakeConnector(("IMF.A",))

    summary = run_pipeline(connector, IMF, dry_run=True)

    assert summary.dry_run is True
    assert summary.outcomes[0].rows_fetched == 1
    assert summary.outcomes[0].rows_written_silver == 0
    assert "1 rows fetched" in summary.report()


def test_catalog_session_is_separate_from_per_indicator_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery seeds the catalog once, then each indicator gets its own session."""
    _, database = stub_writes(monkeypatch)
    connector = FakeConnector(("IMF.A", "IMF.B"))

    run_pipeline(connector, IMF)

    # One session for the catalog, then one per indicator (persistence is stubbed).
    assert database.sessions == 3


def test_derivation_override_falls_back_to_the_source_default() -> None:
    """An override wins; a partial override still inherits the default strategy."""
    assert _derivation_for(IMF, "IMF.A") == IMF.overrides["IMF.A"]
    assert _derivation_for(IMF, "IMF.B") == IMF.default_derivation
    assert IMF.default_derivation.derivation_strategy is None


def test_world_bank_spec_matches_the_reference_source() -> None:
    """The wrapper's spec must keep the World Bank namespace and annual cadence."""
    assert WORLD_BANK_SPEC.source_name == "world_bank"
    assert WORLD_BANK_SPEC.source_type == "api"
    assert WORLD_BANK_SPEC.frequency == "annual"
    assert WORLD_BANK_SPEC.derived_prefix == "WB"
    assert WORLD_BANK_SPEC.supports_forecasts is False
    assert WORLD_BANK_SPEC.overrides == {}
