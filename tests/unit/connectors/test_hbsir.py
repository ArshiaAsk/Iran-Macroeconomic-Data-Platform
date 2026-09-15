"""
Unit tests for the HBSIR connector.

Every test injects a fake loader, so the suite never imports ``hbsir`` and never
touches the network. The statistics themselves are covered by
``test_hbsir_parser.py``.
"""

import os
import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from src.connectors.base import DataConnector
from src.connectors.hbsir import (
    DEFAULT_INDICATORS,
    DERIVED_PREFIX,
    HBSIR_INDICATORS,
    INCOME_TABLE,
    MISSING_EXTRA_MESSAGE,
    SOURCE_NAME,
    SOURCE_TYPE,
    WEIGHT_TABLE,
    HbsirConfig,
    HbsirConnector,
    HbsirPackageLoader,
    build_spec,
    is_available,
    main,
)
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
    hbsir_parser,
)
from src.utils.exceptions import ConnectionError as PlatformConnectionError
from src.utils.exceptions import DataRetrievalError, ParsingError
from tests.conftest import FakeHbsirLoader

YEARS = (1400, 1403)
INCOME = [0.0, 10.0, 100.0, 1000.0]


def extract_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two survey years of four unit-weighted households each."""
    income = pd.DataFrame(
        {
            "Year": [year for year in YEARS for _ in INCOME],
            "ID": [1, 2, 3, 4] * len(YEARS),
            "Income": INCOME * len(YEARS),
        }
    )
    weights = income[["Year", "ID"]].copy()
    weights["Weight"] = 1.0
    return income, weights


def build_loader(**kwargs: object) -> FakeHbsirLoader:
    """A fake loader over the synthetic two-year extract."""
    income, weights = extract_frames()
    loader = FakeHbsirLoader(tables={INCOME_TABLE: income, WEIGHT_TABLE: weights})
    for key, value in kwargs.items():
        setattr(loader, key, value)
    return loader


def build_connector(
    loader: FakeHbsirLoader | None = None, **config_kwargs: object
) -> HbsirConnector:
    """Connector wired to a fake loader and the full indicator registry."""
    return HbsirConnector(
        config=HbsirConfig(**config_kwargs),  # type: ignore[arg-type]
        loader=loader or build_loader(),
    )


# ------------------------------------------------------------------- registry


def test_connector_is_a_data_connector() -> None:
    """The connector implements the shared ABC, not an ad-hoc interface."""
    assert issubclass(HbsirConnector, DataConnector)


def test_registry_has_the_twelve_planned_indicators() -> None:
    """Gini, relative poverty, and ten decile shares are registered."""
    assert tuple(HBSIR_INDICATORS) == DEFAULT_INDICATORS
    assert len(DEFAULT_INDICATORS) == 12
    assert GINI_INDICATOR in DEFAULT_INDICATORS
    assert POVERTY_INDICATOR in DEFAULT_INDICATORS
    assert tuple(DECILE_INDICATORS) == tuple(
        f"HBSIR.INCOME.DECILE.D{index}" for index in range(1, 11)
    )


def test_registry_describes_the_welfare_domain_and_units() -> None:
    """Every indicator is a welfare series with an explicit unit."""
    for indicator_id, registry in HBSIR_INDICATORS.items():
        assert registry.domain == "welfare"
        assert registry.unit
        assert registry.indicator_id == indicator_id
    assert HBSIR_INDICATORS[GINI_INDICATOR].unit == "index (0-1)"
    assert HBSIR_INDICATORS[POVERTY_INDICATOR].unit == "percent"


def test_build_spec_is_annual_and_opts_out_of_growth() -> None:
    """Rates and shares must not receive derived year-over-year growth."""
    spec = build_spec()

    assert spec.source_name == SOURCE_NAME
    assert spec.source_type == SOURCE_TYPE
    assert spec.frequency == "annual"
    assert spec.derived_prefix == DERIVED_PREFIX
    assert spec.indicators == DEFAULT_INDICATORS
    assert spec.supports_forecasts is False
    assert spec.default_derivation.include_growth is False
    assert spec.default_derivation.include_monthly is False


# ------------------------------------------------------------------- connectivity


def test_default_connector_uses_the_package_loader() -> None:
    """With no injected loader the connector builds the package transport."""
    assert isinstance(HbsirConnector().loader, HbsirPackageLoader)


def test_connect_raises_when_the_extra_is_missing() -> None:
    """A missing optional package gives one actionable error."""
    connector = build_connector(build_loader(available=False))

    with pytest.raises(PlatformConnectionError, match="hbsir"):
        connector.connect()


def test_missing_extra_message_is_actionable() -> None:
    """The missing-extra error names the install command."""
    assert "poetry install -E hbsir" in MISSING_EXTRA_MESSAGE


def test_connect_succeeds_with_an_available_loader() -> None:
    """The availability check is the whole connectivity contract."""
    assert build_connector().connect() is True


def test_disconnect_leaves_an_injected_loader_open() -> None:
    """An injected loader belongs to the caller and is not closed."""
    loader = build_loader()
    build_connector(loader).disconnect()

    assert loader.closed is False


# ------------------------------------------------------------------- discovery


def test_discover_describes_annual_welfare_indicators() -> None:
    """Discovery reports the registry with availability left to the pipeline."""
    discovered = build_connector().discover()

    assert len(discovered) == 12
    for meta in discovered:
        assert meta.frequency == "annual"
        assert meta.domain == "welfare"
        assert meta.source_name == SOURCE_NAME
        assert meta.availability_start is None
        assert meta.availability_end is None
        assert meta.has_base_year_changes is False


def test_discover_skips_unregistered_indicators() -> None:
    """An unknown code is skipped rather than fabricated."""
    connector = build_connector(build_loader(), indicators=("HBSIR.NOT_REAL",))

    assert connector.discover() == []


# ------------------------------------------------------------------- fetching


def test_fetch_series_returns_an_annual_frame() -> None:
    """One row per survey year, stamped at the Gregorian year-end."""
    connector = build_connector()

    frame = connector.fetch_series(GINI_INDICATOR).frame

    assert len(frame) == 2
    assert [row.date().isoformat() for row in frame["timestamp"]] == [
        "2022-03-20",
        "2025-03-20",
    ]
    assert set(frame["indicator_id"]) == {GINI_INDICATOR}
    assert frame["timestamp"].dt.tz is not None


def test_fetch_series_carries_the_jalali_year_and_weighted_counts() -> None:
    """Per-observation metadata keeps the survey year and household counts."""
    frame = build_connector().fetch_series(POVERTY_INDICATOR).frame

    metadata = frame["record_metadata"].iloc[0]
    assert metadata["jalali_year"] == 1400
    assert metadata["weighted_households"] == pytest.approx(4.0)
    assert metadata["poverty_line_rule"] == "50% of weighted median household income"
    assert metadata["is_official_poverty_line"] is False


def test_fetch_series_persists_no_microdata() -> None:
    """Bronze rows are derived aggregates; the extract stays in memory."""
    result = build_connector().fetch_series(GINI_INDICATOR)

    rows = result.raw_envelope["rows"]
    assert len(rows) == 2
    for row in rows:
        assert set(row) == {"Year", "indicator_id", "value", "unit", "record_metadata"}
        assert "Income" not in row
        assert "Weight" not in row


def test_fetch_series_manifest_binds_the_extract() -> None:
    """The manifest records the source, years, and a microdata-free checksum."""
    result = build_connector().fetch_series(GINI_INDICATOR)

    meta = result.raw_envelope["meta"]
    assert meta["package"] == "hbsir"
    assert meta["package_version"] == "0.6.6"
    assert meta["source_tables"] == [INCOME_TABLE, WEIGHT_TABLE]
    assert meta["survey_years_jalali"] == [1400, 1403]
    assert [entry["jalali_year"] for entry in meta["years"]] == [1400, 1403]
    assert meta["years"][0]["n_households"] == 4
    assert meta["microdata_persisted"] is False
    assert meta["is_official_poverty_line"] is False
    assert len(meta["extract_checksum_sha256"]) == 64


def test_collection_metadata_records_package_provenance() -> None:
    """Bronze metadata names the package, checksum, and poverty rule."""
    metadata = build_connector().fetch_series(POVERTY_INDICATOR).collection_metadata()

    assert metadata["package"] == "hbsir"
    assert metadata["package_version"] == "0.6.6"
    assert metadata["microdata_persisted"] is False
    assert metadata["poverty_line_rule"] == "50% of weighted median household income"
    assert metadata["source_tables"] == [INCOME_TABLE, WEIGHT_TABLE]
    assert len(metadata["extract_checksum_sha256"]) == 64


def test_fetch_series_loads_the_extract_only_once() -> None:
    """Repeated indicator fetches reuse the cached aggregate."""
    loader = build_loader()
    connector = build_connector(loader)

    connector.fetch_series(GINI_INDICATOR)
    connector.fetch_series(POVERTY_INDICATOR)
    connector.fetch_series(DECILE_INDICATORS[0])

    assert loader.calls == [(INCOME_TABLE, "all"), (WEIGHT_TABLE, "all")]


def test_fetch_series_passes_configured_years_to_the_loader() -> None:
    """An explicit year window is forwarded to both table loads."""
    loader = build_loader()
    connector = build_connector(loader, years=(1400, 1403))

    connector.fetch_series(GINI_INDICATOR)

    assert loader.calls == [(INCOME_TABLE, (1400, 1403)), (WEIGHT_TABLE, (1400, 1403))]


def test_fetch_series_requires_a_registered_indicator() -> None:
    """An unknown indicator fails before any table load."""
    loader = build_loader()

    with pytest.raises(DataRetrievalError, match="not registered"):
        build_connector(loader).fetch_series("HBSIR.NOT_REAL")
    assert loader.calls == []


def test_fetch_series_requires_sampling_weights() -> None:
    """A weight table without a Weight column fails loudly."""
    income, weights = extract_frames()
    loader = FakeHbsirLoader(
        tables={INCOME_TABLE: income, WEIGHT_TABLE: weights.drop(columns=["Weight"])}
    )

    with pytest.raises(ParsingError, match="Weight"):
        build_connector(loader).fetch_series(GINI_INDICATOR)


def test_fetch_ignores_the_protocol_date_range() -> None:
    """The ABC date arguments do not window the annual series."""
    connector = build_connector()

    frame = connector.fetch(GINI_INDICATOR, datetime(2020, 1, 1, tzinfo=UTC), datetime.now(UTC))

    assert len(frame) == 2


# ------------------------------------------------------------------- validation


def test_validate_accepts_a_valid_gini_series() -> None:
    """A Gini in [0, 1] validates cleanly."""
    connector = build_connector()
    frame = connector.fetch_series(GINI_INDICATOR).frame

    assert connector.validate(frame).is_valid is True


def test_validate_rejects_an_out_of_range_gini() -> None:
    """A Gini above 1 is invalid."""
    connector = build_connector()
    frame = hbsir_parser(
        [{"Year": 1400, "indicator_id": GINI_INDICATOR, "value": 1.5}],
        GINI_INDICATOR,
        "index (0-1)",
    )

    result = connector.validate(frame)

    assert result.is_valid is False
    assert any("out of range" in error for error in result.errors)


def test_validate_rejects_an_out_of_range_poverty_rate() -> None:
    """A poverty rate above 100% is invalid."""
    connector = build_connector()
    frame = hbsir_parser(
        [{"Year": 1400, "indicator_id": POVERTY_INDICATOR, "value": 150.0}],
        POVERTY_INDICATOR,
        "percent",
    )

    assert connector.validate(frame).is_valid is False


# ------------------------------------------------------------------- cli


def test_main_parses_indicators_and_years(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI selects indicators and years and hands the run to the runner."""
    captured: dict[str, object] = {}

    def fake_run_cli(**kwargs: object) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("src.etl.pipeline.run_cli", fake_run_cli)

    exit_code = main(["--indicators", GINI_INDICATOR, "--years", "1395,1400-1403", "--dry-run"])

    assert exit_code == 0
    assert captured["indicators"] == (GINI_INDICATOR,)
    assert captured["dry_run"] is True
    connector = captured["connector"]
    assert isinstance(connector, HbsirConnector)
    assert connector.config.years == (1395, 1400, 1401, 1402, 1403)


# --------------------------------------------------------- package loader


def test_package_loader_raises_the_missing_extra_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing ``hbsir`` extra gives one actionable, package-free error."""
    monkeypatch.setitem(sys.modules, "hbsir", None)
    loader = HbsirPackageLoader(HbsirConfig())

    with pytest.raises(PlatformConnectionError, match="poetry install -E hbsir"):
        loader.load_table(WEIGHT_TABLE, 1400)


def test_package_loader_delegates_to_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default loader requests a download for missing years and returns it."""
    table = pd.DataFrame({"Year": [1400], "Weight": [1.0]})
    calls: dict[str, object] = {}

    def load_table(table_name: str, years: object, on_missing: str | None = None) -> pd.DataFrame:
        calls.update(name=table_name, years=years, on_missing=on_missing)
        return table

    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr(loader, "_load_module", lambda: SimpleNamespace(load_table=load_table))

    result = loader.load_table(WEIGHT_TABLE, 1400)

    assert result is table
    assert calls == {"name": WEIGHT_TABLE, "years": 1400, "on_missing": "download"}


def test_package_loader_keeps_the_bulk_path_when_all_years_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A working ``"all"`` call is returned as-is; no per-year probing happens."""
    table = pd.DataFrame({"Year": [1400, 1401], "Weight": [1.0, 2.0]})
    calls: list[object] = []

    def load_table(table_name: str, years: object, on_missing: str | None = None) -> pd.DataFrame:
        calls.append(years)
        return table

    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr(loader, "_load_module", lambda: SimpleNamespace(load_table=load_table))

    assert loader.load_table(WEIGHT_TABLE, "all") is table
    assert calls == ["all"]


def test_package_loader_skips_unconstructible_years(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``"all"`` falls back to per-year loads and drops the years that fail."""

    def load_table(table_name: str, years: object, on_missing: str | None = None) -> pd.DataFrame:
        if years == "all":
            message = "assertion inside the package"
            raise RuntimeError(message)
        year = years[0] if isinstance(years, list) else years
        if year < 1369:
            message = "no versioned metadata for this year"
            raise RuntimeError(message)
        return pd.DataFrame({"Year": [year], "Income": [1.0]})

    module = SimpleNamespace(
        load_table=load_table,
        api=SimpleNamespace(defaults=SimpleNamespace(years=[1363, 1368, 1369, 1370])),
    )
    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr(loader, "_load_module", lambda: module)

    result = loader.load_table(INCOME_TABLE, "all")

    assert sorted(result["Year"]) == [1369, 1370]


def test_package_loader_raises_when_no_year_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bulk error surfaces when the fallback cannot construct any year."""

    def load_table(table_name: str, years: object, on_missing: str | None = None) -> pd.DataFrame:
        message = "mirror offline"
        raise RuntimeError(message)

    module = SimpleNamespace(
        load_table=load_table,
        api=SimpleNamespace(defaults=SimpleNamespace(years=[1369, 1370])),
    )
    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr(loader, "_load_module", lambda: module)

    with pytest.raises(DataRetrievalError, match="mirror offline"):
        loader.load_table(INCOME_TABLE, "all")


def test_package_loader_raises_when_the_calendar_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a year calendar there is nothing to probe, so the bulk error stands."""

    def load_table(table_name: str, years: object, on_missing: str | None = None) -> pd.DataFrame:
        message = "bulk failed"
        raise RuntimeError(message)

    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr(loader, "_load_module", lambda: SimpleNamespace(load_table=load_table))

    with pytest.raises(DataRetrievalError, match="bulk failed"):
        loader.load_table(INCOME_TABLE, "all")


def test_package_loader_wraps_package_load_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """A download/read failure becomes a retrieval error, not a crash."""
    loader = HbsirPackageLoader(HbsirConfig())

    def boom(*_args: object, **_kwargs: object) -> pd.DataFrame:
        message = "mirror offline"
        raise RuntimeError(message)

    monkeypatch.setattr(loader, "_load_module", lambda: SimpleNamespace(load_table=boom))

    with pytest.raises(DataRetrievalError, match="could not load"):
        loader.load_table(WEIGHT_TABLE, 1400)


def test_package_loader_rejects_a_non_dataframe_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """A package that returns something other than a DataFrame is a failure."""
    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr(
        loader,
        "_load_module",
        lambda: SimpleNamespace(load_table=lambda *a, **k: {"not": "a frame"}),
    )

    with pytest.raises(DataRetrievalError, match="did not return a DataFrame"):
        loader.load_table(WEIGHT_TABLE, 1400)


def test_package_loader_reports_availability_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The loader delegates the module-level probes it wraps."""
    loader = HbsirPackageLoader(HbsirConfig())
    monkeypatch.setattr("src.connectors.hbsir.is_available", lambda: True)
    monkeypatch.setattr("src.connectors.hbsir.package_version", lambda: "9.9.9")

    assert loader.is_available() is True
    assert loader.package_version == "9.9.9"


def test_package_loader_imports_the_module_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real ``_load_module`` imports lazily and caches the module handle."""
    sentinel = SimpleNamespace(load_table=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "hbsir", sentinel)
    loader = HbsirPackageLoader(HbsirConfig())

    assert loader._load_module() is sentinel
    assert loader._load_module() is sentinel  # cached, no re-import


# ------------------------------------------------------------------- live

LIVE_FLAG = "RUN_LIVE_API_TESTS"
MIN_LIVE_YEARS = 10


@pytest.mark.live()
@pytest.mark.skipif(
    os.environ.get(LIVE_FLAG) != "1",
    reason=f"set {LIVE_FLAG}=1 to load the real HBSIR extract",
)
@pytest.mark.skipif(
    not is_available(),
    reason="the optional 'hbsir' extra is not installed",
)
def test_live_hbsir_derives_annual_welfare_series() -> None:
    """
    Compute the real indicators from the locally cached survey extract.

    ``hbsir`` is a loader, not an HTTP client: after the first download the
    cleaned Parquet lives in ``HBSIR_DATA_DIR`` (``Data/``) and is reused
    offline, so this test needs no network and does not persist microdata.
    It asserts the published contract (a decade-plus of annual, in-range,
    gap-preserving series) rather than any particular value.
    """
    connector = HbsirConnector(config=HbsirConfig(indicators=(GINI_INDICATOR,)))
    try:
        assert connector.connect() is True
        frame = connector.fetch(
            GINI_INDICATOR,
            datetime(1900, 1, 1, tzinfo=UTC),
            datetime(2100, 1, 1, tzinfo=UTC),
        )
        result = connector.validate(frame)
    finally:
        connector.disconnect()

    assert result.is_valid
    assert len(frame) >= MIN_LIVE_YEARS
    assert frame["value"].between(0.0, 1.0).all()
    assert frame["timestamp"].is_monotonic_increasing
    # One observation per survey year, snapped to the Iranian year end.
    assert frame["timestamp"].dt.month.eq(3).all()


def test_disconnect_closes_an_owned_loader() -> None:
    """A loader the connector created is released on disconnect."""
    loader = build_loader()
    connector = build_connector(loader)
    connector._owns_loader = True

    connector.disconnect()

    assert loader.closed is True


def test_validate_returns_the_quality_report_for_empty_and_value_less_frames() -> None:
    """Frames with nothing to range-check are reported, not crashed on."""
    connector = build_connector()

    empty = connector.validate(pd.DataFrame())
    assert empty.is_valid is False
    assert any("empty" in error.lower() for error in empty.errors)

    value_less = connector.validate(pd.DataFrame({"indicator_id": [GINI_INDICATOR]}))
    assert value_less.is_valid is False
    assert all("out of range" not in error for error in value_less.errors)


def test_fetch_series_rejects_an_empty_extract() -> None:
    """No income rows means no survey year to compute; fail loudly."""
    empty = pd.DataFrame({"Year": [], "ID": [], "Income": []})
    weights = pd.DataFrame({"Year": [], "ID": [], "Weight": []})
    loader = FakeHbsirLoader(tables={INCOME_TABLE: empty, WEIGHT_TABLE: weights})

    with pytest.raises(ParsingError):
        build_connector(loader).fetch_series(GINI_INDICATOR)


def test_json_safe_row_handles_numpy_and_nested_values() -> None:
    """Aggregate rows are JSON-serializable before they reach Bronze."""
    import json

    import numpy as np

    from src.connectors.hbsir import _json_safe_row

    safe = _json_safe_row(
        {
            "year": np.int64(1400),
            "gini": np.float64(0.37),
            "meta": {"nested": 2},
            "other": object(),
        }
    )

    assert safe["year"] == 1400
    assert isinstance(safe["year"], int)
    assert safe["gini"] == pytest.approx(0.37)
    assert safe["meta"] == {"nested": 2}
    json.dumps(safe)  # must not raise


def test_parse_years_handles_blank_and_empty_input() -> None:
    """Blank selections and empty tokens collapse to None/ignored."""
    from src.connectors.hbsir import _parse_years

    assert _parse_years(None) is None
    assert _parse_years("") is None
    assert _parse_years("  ,  ") is None
    assert _parse_years("1400, ,1403-1404") == (1400, 1403, 1404)
