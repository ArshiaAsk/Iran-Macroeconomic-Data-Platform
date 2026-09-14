"""
Phase 6 registration / wiring tests (Task 6).

Tasks 4 and 5 built the TSETMC and HBSIR connectors; this module locks the
*integration* surface the plan calls out: both sources register their approved
indicators in the existing catalog, their ``SourceSpec`` inputs are accepted
unchanged by ``run_pipeline``, and the approved domains/frequencies/derivations
are wired without re-enabling the deferred TSETMC indicators.

Nothing here needs the optional ``finpy-tse``/``hbsir`` packages, a network, or
Postgres: discovery is registry/config-only and persistence is stubbed.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from src.connectors import hbsir, tsetmc
from src.etl import pipeline
from src.etl.pipeline import (
    WORLD_BANK_SPEC,
    IndicatorDerivation,
    _catalog_values,
    _derivation_for,
    run_pipeline,
)

GINI = hbsir.GINI_INDICATOR
POVERTY = hbsir.POVERTY_INDICATOR
TEDPIX = "TSETMC.TEDPIX"


@dataclass
class FakeFetchResult:
    """Minimal ``FetchResult`` for the wiring tests."""

    indicator_id: str
    frame: pd.DataFrame
    raw_envelope: dict[str, Any] = field(default_factory=lambda: {"rows": []})
    request_url: str | None = "https://example.test"
    http_status_code: int | None = None

    def collection_metadata(self) -> dict[str, Any]:
        return {"indicator_id": self.indicator_id}


class RegistrationConnector:
    """
    Drive the real ``discover()`` output through the real runner.

    Discovery comes from the actual connector registry; only ``fetch_series`` is
    faked, so the test proves the spec is accepted without a package or network.
    """

    def __init__(self, real_connector: Any) -> None:
        self._metadata = real_connector.discover()
        self.connected = False
        self.disconnected = False
        self.discover_calls = 0

    def connect(self) -> bool:
        self.connected = True
        return True

    def discover(self) -> list[Any]:
        self.discover_calls += 1
        return self._metadata

    def fetch_series(self, indicator_id: str) -> FakeFetchResult:
        return FakeFetchResult(
            indicator_id=indicator_id,
            frame=pd.DataFrame({"timestamp": [1], "value": [1.0]}),
        )

    def disconnect(self) -> None:
        self.disconnected = True


class FakeDatabase:
    """Stand-in for the global database handle."""

    def __init__(self) -> None:
        self.sessions = 0

    @contextmanager
    def get_session(self) -> Any:
        self.sessions += 1
        yield object()


def stub_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, tuple[Any, ...]], dict[str, Any], FakeDatabase]:
    """Replace persistence + catalog upsert; return recorders and the database."""
    recorded: dict[str, tuple[Any, ...]] = {}
    captured: dict[str, Any] = {}

    def fake_persist(
        session: Any,
        spec: Any,
        fetched: Any,
        outcome: Any,
        domain: str | None,
        unit: str | None,
    ) -> None:
        recorded[fetched.indicator_id] = (spec, domain, unit)

    def fake_catalog(session: Any, discovered: list[Any]) -> int:
        captured["discovered"] = list(discovered)
        return len(discovered)

    monkeypatch.setattr(pipeline, "_persist_indicator", fake_persist)
    monkeypatch.setattr(pipeline, "upsert_indicator_catalog", fake_catalog)
    database = FakeDatabase()
    monkeypatch.setattr(pipeline, "get_db", lambda: database)
    return recorded, captured, database


# --------------------------------------------------------------- catalog registry


def test_tsetmc_discovery_registers_only_tedpix_in_the_market_domain() -> None:
    """Phase 6 opens TEDPIX alone; the market domain is the catalog bucket."""
    discovered = tsetmc.TsetmcConnector().discover()

    assert [item.indicator_id for item in discovered] == [TEDPIX]
    metadata = discovered[0]
    assert metadata.domain == "market"
    assert metadata.frequency == "daily"
    assert metadata.source_name == "tsetmc"
    assert metadata.source_url is not None
    assert metadata.has_base_year_changes is False
    assert metadata.is_active is True


def test_hbsir_discovery_registers_the_twelve_welfare_indicators() -> None:
    """Gini + relative poverty + ten decile shares, all in the welfare domain."""
    discovered = hbsir.HbsirConnector().discover()

    ids = [item.indicator_id for item in discovered]
    assert ids == list(hbsir.DEFAULT_INDICATORS)
    assert len(ids) == 12
    assert ids[0] == GINI
    assert ids[1] == POVERTY
    assert ids[2:] == [f"HBSIR.INCOME.DECILE.D{index}" for index in range(1, 11)]
    for metadata in discovered:
        assert metadata.domain == "welfare"
        assert metadata.frequency == "annual"
        assert metadata.source_name == "hbsir"
        assert metadata.has_base_year_changes is False
        assert metadata.is_active is True


def test_discovered_availability_is_left_unset_for_both_sources() -> None:
    """Coverage is never fabricated: the pipeline fills it from stored rows."""
    for connector in (tsetmc.TsetmcConnector(), hbsir.HbsirConnector()):
        for metadata in connector.discover():
            assert metadata.availability_start is None
            assert metadata.availability_end is None


def test_catalog_values_map_tsetmc_metadata() -> None:
    """The catalog row carries the market domain, daily cadence and unit."""
    values = _catalog_values(tsetmc.TsetmcConnector().discover()[0])

    assert values["indicator_id"] == TEDPIX
    assert values["domain"] == "market"
    assert values["frequency"] == "daily"
    assert values["source_name"] == "tsetmc"
    assert values["unit"] == "index points"
    assert values["availability_start"] is None
    assert values["availability_end"] is None


def test_catalog_values_map_hbsir_metadata() -> None:
    """Gini is an index and every other HBSIR series is a percent."""
    values = {
        item.indicator_id: _catalog_values(item) for item in hbsir.HbsirConnector().discover()
    }

    assert values[GINI]["domain"] == "welfare"
    assert values[GINI]["frequency"] == "annual"
    assert values[GINI]["unit"] == "index (0-1)"
    assert values[POVERTY]["unit"] == "percent"
    assert values["HBSIR.INCOME.DECILE.D10"]["unit"] == "percent"
    assert all(row["availability_start"] is None for row in values.values())


def test_deferred_tsetmc_indicators_are_not_registered() -> None:
    """Trading value, market P/E and market cap stay deferred in Phase 6."""
    registered = set(tsetmc.TSETMC_INDICATORS)
    deferred_markers = ("VALUE", "PE", "P_E", "CAP", "MARKET")

    assert registered == {TEDPIX}
    assert not any(marker in indicator for indicator in registered for marker in deferred_markers)
    assert tsetmc.build_spec().indicators == (TEDPIX,)


# --------------------------------------------------------------- spec derivation


def test_tsetmc_spec_drives_daily_growth_and_month_end_derivations() -> None:
    """TEDPIX gets RET1D/MA30 and the opt-in month-end series."""
    spec = tsetmc.build_spec()

    assert spec.source_name == "tsetmc"
    assert spec.source_type == "package"
    assert spec.frequency == "daily"
    assert spec.derived_prefix == "TSETMC"
    assert spec.indicators == (TEDPIX,)
    assert spec.supports_forecasts is False

    derivation = _derivation_for(spec, TEDPIX)
    assert derivation.derivation_strategy == "daily"
    assert derivation.include_growth is True
    assert derivation.include_monthly is True


def test_hbsir_spec_opts_every_indicator_out_of_growth() -> None:
    """Rates and shares are not given derived growth or a monthly series."""
    spec = hbsir.build_spec()

    assert spec.source_name == "hbsir"
    assert spec.source_type == "package"
    assert spec.frequency == "annual"
    assert spec.derived_prefix == "HBSIR"
    assert spec.supports_forecasts is False

    for indicator_id in spec.indicators:
        derivation = _derivation_for(spec, indicator_id)
        assert derivation.include_growth is False
        assert derivation.include_monthly is False


# --------------------------------------------------------------- runner wiring


def test_tsetmc_pipeline_accepts_its_spec_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real spec + real discovery run through run_pipeline untouched."""
    recorded, captured, _ = stub_writes(monkeypatch)
    connector = RegistrationConnector(tsetmc.TsetmcConnector())

    summary = run_pipeline(connector, tsetmc.build_spec())

    assert connector.connected is True
    assert connector.discover_calls == 1
    assert summary.source_name == "tsetmc"
    assert [outcome.indicator_id for outcome in summary.outcomes] == [TEDPIX]
    assert summary.exit_code == 0

    spec, domain, unit = recorded[TEDPIX]
    assert spec.source_name == "tsetmc"
    assert domain == "market"
    assert unit == "index points"

    catalog_meta = captured["discovered"][0]
    assert catalog_meta.indicator_id == TEDPIX
    assert catalog_meta.domain == "market"


def test_hbsir_pipeline_accepts_its_spec_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All twelve survey indicators register and resolve their catalog domain."""
    recorded, captured, _ = stub_writes(monkeypatch)
    connector = RegistrationConnector(hbsir.HbsirConnector())

    summary = run_pipeline(connector, hbsir.build_spec())

    assert summary.source_name == "hbsir"
    assert len(summary.outcomes) == 12
    assert summary.exit_code == 0
    assert {item.source_name for item in captured["discovered"]} == {"hbsir"}
    assert len(captured["discovered"]) == 12
    assert all(recorded[outcome.indicator_id][1] == "welfare" for outcome in summary.outcomes)


def test_catalog_is_seeded_once_per_run_with_discovery_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registration is a single catalog upsert keyed off discover()."""
    _, captured, database = stub_writes(monkeypatch)
    connector = RegistrationConnector(hbsir.HbsirConnector())

    run_pipeline(connector, hbsir.build_spec())

    # One session seeds the catalog, then one per indicator (persistence stubbed).
    assert database.sessions == 13
    assert captured["discovered"] == connector.discover()


# --------------------------------------------------- existing behavior untouched


def test_default_derivation_keeps_month_end_off() -> None:
    """The opt-in field must default off so no source changes behavior."""
    assert IndicatorDerivation().include_monthly is False
    assert IndicatorDerivation().include_growth is True


def test_existing_sources_do_not_opt_into_month_end() -> None:
    """World Bank, IMF and EIA keep their pre-Phase-6 derivation behavior."""
    from src.connectors.eia import build_spec as eia_spec
    from src.connectors.imf import build_spec as imf_spec

    assert WORLD_BANK_SPEC.default_derivation.include_monthly is False
    assert imf_spec().default_derivation.include_monthly is False
    assert eia_spec().default_derivation.include_monthly is False
