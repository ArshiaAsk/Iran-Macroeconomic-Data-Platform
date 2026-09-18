"""Unit tests for the dashboard repository's DataFrame shaping."""

from typing import Any

import pandas as pd
import pytest

from dashboard.repository import (
    SERIES_CLASSIFICATION_COLUMNS,
    SERIES_KIND_BASE,
    SERIES_KIND_DERIVED,
    DashboardRepository,
)


class FakeMappings:
    """Minimal SQLAlchemy mappings result."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class FakeResult:
    """Minimal SQLAlchemy execute result."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self.rows)


class FakeSession:
    """Session double that serves one captured result."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.statements: list[Any] = []

    def execute(self, statement: Any) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self.rows)


def gold_row(
    indicator_id: str,
    *,
    catalog: bool = True,
    name: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    record_metadata: Any = None,
    parent_name: str | None = None,
    parent_source_name: str | None = None,
    parent_source_url: str | None = None,
    timestamp: str = "2021-01-01T00:00:00+00:00",
    value: float = 1.0,
) -> dict[str, Any]:
    """Build one row shaped like the LEFT JOIN select in ``load_series``.

    ``catalog=False`` models a Gold series without its own catalog row: the direct
    catalog fields are ``NULL`` while the ``parent_*`` fields still carry whatever
    the parent join found.
    """
    return {
        "indicator_id": indicator_id,
        "name": name if catalog else None,
        "timestamp": pd.Timestamp(timestamp),
        "value": value,
        "original_value": None,
        "is_chain_linked": False,
        "chain_linking_confidence": None,
        "unit": "index",
        "frequency": "annual",
        "domain": "gdp",
        "source_name": source_name if catalog else None,
        "source_url": source_url if catalog else None,
        "record_metadata": record_metadata,
        "catalog_indicator_id": indicator_id if catalog else None,
        "parent_name": parent_name,
        "parent_source_name": parent_source_name,
        "parent_source_url": parent_source_url,
    }


def load_rows(rows: list[dict[str, Any]], indicator_ids: list[str]) -> pd.DataFrame:
    """Run ``load_series`` over fabricated join rows."""
    return DashboardRepository(FakeSession(rows)).load_series(indicator_ids)


def test_series_inventory_classifies_catalog_derived_and_orphan_series() -> None:
    rows = [
        {"indicator_id": "level", "derived_from": None, "catalog_indicator_id": "level"},
        {"indicator_id": "derived", "derived_from": "level", "catalog_indicator_id": None},
        {"indicator_id": "orphan", "derived_from": None, "catalog_indicator_id": None},
    ]

    frame = DashboardRepository(FakeSession(rows)).series_inventory()

    assert list(frame.columns) == [
        "indicator_id",
        "derived_from",
        "series_kind",
        "has_catalog_metadata",
    ]
    indexed = frame.set_index("indicator_id")
    assert indexed.loc["level", "series_kind"] == SERIES_KIND_BASE
    assert bool(indexed.loc["level", "has_catalog_metadata"]) is True
    assert indexed.loc["derived", "series_kind"] == SERIES_KIND_DERIVED
    assert indexed.loc["derived", "derived_from"] == "level"
    assert bool(indexed.loc["derived", "has_catalog_metadata"]) is False
    assert indexed.loc["orphan", "series_kind"] == SERIES_KIND_BASE
    assert bool(indexed.loc["orphan", "has_catalog_metadata"]) is False


def test_series_inventory_is_empty_safe() -> None:
    frame = DashboardRepository(FakeSession([])).series_inventory()

    assert frame.empty
    assert list(frame.columns) == [
        "indicator_id",
        "derived_from",
        "series_kind",
        "has_catalog_metadata",
    ]


def test_list_indicators_returns_catalog_frame() -> None:
    rows = [
        {
            "indicator_id": "FP.CPI.TOTL.ZG",
            "name": "Inflation",
            "description": None,
            "unit": "%",
            "frequency": "annual",
            "domain": "inflation",
            "source_name": "world_bank",
            "source_url": "https://example.test",
            "availability_start": pd.Timestamp("2020-01-01", tz="UTC"),
            "availability_end": pd.Timestamp("2024-01-01", tz="UTC"),
            "has_base_year_changes": False,
            "base_years": None,
            "is_active": True,
        }
    ]
    frame = DashboardRepository(FakeSession(rows)).list_indicators(search="inflation")

    assert frame.loc[0, "indicator_id"] == "FP.CPI.TOTL.ZG"
    assert list(frame.columns) == list(rows[0])


def test_load_series_preserves_requested_indicator_order() -> None:
    rows = [
        gold_row("second", name="Second", timestamp="2020-01-01T00:00:00+00:00", value=2.0),
        gold_row("first", name="First", timestamp="2021-01-01T00:00:00+00:00"),
    ]
    frame = load_rows(rows, ["first", "second"])

    assert frame["indicator_id"].tolist() == ["first", "second"]


def test_load_series_keeps_requested_order_then_ascending_timestamp() -> None:
    rows = [
        gold_row(
            "derived",
            catalog=False,
            record_metadata={"derived_from": "base"},
            timestamp="2021-01-01T00:00:00+00:00",
        ),
        gold_row("base", name="Base", timestamp="2022-01-01T00:00:00+00:00"),
        gold_row("base", name="Base", timestamp="2020-01-01T00:00:00+00:00"),
    ]
    frame = load_rows(rows, ["base", "derived"])

    assert frame["indicator_id"].tolist() == ["base", "base", "derived"]
    assert frame["timestamp"].dt.year.tolist() == [2020, 2022, 2021]


def test_load_series_classifies_catalog_backed_row_as_base() -> None:
    rows = [
        gold_row(
            "NY.GDP.MKTP.CD",
            name="GDP",
            source_name="world_bank",
            source_url="https://api.worldbank.test",
        )
    ]
    row = load_rows(rows, ["NY.GDP.MKTP.CD"]).iloc[0]

    assert row["name"] == "GDP"
    assert row["source_name"] == "world_bank"
    assert row["source_url"] == "https://api.worldbank.test"
    assert row["series_kind"] == SERIES_KIND_BASE
    assert row["derived_from"] is None
    assert bool(row["has_catalog_metadata"]) is True


def test_load_series_classifies_row_without_metadata_as_base() -> None:
    rows = [gold_row("NY.GDP.MKTP.CD", name="GDP", source_name="world_bank")]
    row = load_rows(rows, ["NY.GDP.MKTP.CD"]).iloc[0]

    assert row["series_kind"] == SERIES_KIND_BASE
    assert row["derived_from"] is None


def test_load_series_inherits_parent_provenance_for_derived_series() -> None:
    rows = [
        gold_row(
            "WB.NY.GDP.MKTP.CD.YOY",
            catalog=False,
            record_metadata={"derived_from": "NY.GDP.MKTP.CD", "method": "yoy_growth"},
            parent_name="GDP",
            parent_source_name="world_bank",
            parent_source_url="https://api.worldbank.test",
        )
    ]
    row = load_rows(rows, ["WB.NY.GDP.MKTP.CD.YOY"]).iloc[0]

    assert row["indicator_id"] == "WB.NY.GDP.MKTP.CD.YOY"
    assert row["series_kind"] == SERIES_KIND_DERIVED
    assert row["derived_from"] == "NY.GDP.MKTP.CD"
    assert row["name"] == "GDP"
    assert row["source_name"] == "world_bank"
    assert row["source_url"] == "https://api.worldbank.test"
    assert bool(row["has_catalog_metadata"]) is False


def test_load_series_inherits_tsetmc_source_for_a_derived_series() -> None:
    """A derived TSETMC row carries the parent source slug, not a null."""
    rows = [
        gold_row(
            "TSETMC.TEDPIX.RET1D",
            catalog=False,
            record_metadata={"derived_from": "TSETMC.TEDPIX", "method": "daily_return"},
            parent_name="Tehran Stock Exchange total index (TEDPIX)",
            parent_source_name="tsetmc",
            parent_source_url="http://cdn.tsetmc.com/api",
        )
    ]
    row = load_rows(rows, ["TSETMC.TEDPIX.RET1D"]).iloc[0]

    assert row["series_kind"] == SERIES_KIND_DERIVED
    assert row["derived_from"] == "TSETMC.TEDPIX"
    assert row["source_name"] == "tsetmc"
    assert row["name"] == "Tehran Stock Exchange total index (TEDPIX)"
    assert bool(row["has_catalog_metadata"]) is False


def test_load_series_prefers_direct_catalog_over_parent_catalog() -> None:
    rows = [
        gold_row(
            "WB.NY.GDP.MKTP.CD.YOY",
            name="GDP growth",
            source_name="dashboard",
            source_url="https://dashboard.test",
            record_metadata={"derived_from": "NY.GDP.MKTP.CD"},
            parent_name="GDP",
            parent_source_name="world_bank",
            parent_source_url="https://api.worldbank.test",
        )
    ]
    row = load_rows(rows, ["WB.NY.GDP.MKTP.CD.YOY"]).iloc[0]

    assert row["series_kind"] == SERIES_KIND_DERIVED
    assert row["name"] == "GDP growth"
    assert row["source_name"] == "dashboard"
    assert row["source_url"] == "https://dashboard.test"
    assert bool(row["has_catalog_metadata"]) is True


def test_load_series_leaves_unresolved_parent_provenance_empty() -> None:
    rows = [
        gold_row(
            "WB.NY.GDP.MKTP.CD.YOY",
            catalog=False,
            record_metadata={"derived_from": "MISSING.PARENT"},
        )
    ]
    row = load_rows(rows, ["WB.NY.GDP.MKTP.CD.YOY"]).iloc[0]

    assert row["series_kind"] == SERIES_KIND_DERIVED
    assert row["derived_from"] == "MISSING.PARENT"
    assert pd.isna(row["name"])
    assert pd.isna(row["source_name"])
    assert pd.isna(row["source_url"])
    assert bool(row["has_catalog_metadata"]) is False


def test_load_series_keeps_orphan_base_row_and_flags_it() -> None:
    rows = [gold_row("ORPHAN.LEVEL", catalog=False)]
    row = load_rows(rows, ["ORPHAN.LEVEL"]).iloc[0]

    assert row["indicator_id"] == "ORPHAN.LEVEL"
    assert row["series_kind"] == SERIES_KIND_BASE
    assert bool(row["has_catalog_metadata"]) is False
    assert pd.isna(row["name"])


@pytest.mark.parametrize(
    "record_metadata",
    [
        None,
        {},
        {"method": "yoy_growth"},
        {"derived_from": None},
        {"derived_from": ""},
        {"derived_from": "   "},
        {"derived_from": 1405},
        {"derived_from": ["NY.GDP.MKTP.CD"]},
        "NY.GDP.MKTP.CD",
    ],
    ids=[
        "none",
        "empty",
        "absent",
        "json-null",
        "empty-string",
        "blank",
        "number",
        "list",
        "string",
    ],
)
def test_load_series_treats_unusable_derived_from_as_base(record_metadata: Any) -> None:
    rows = [gold_row("ODD.METADATA", name="Odd", record_metadata=record_metadata)]
    row = load_rows(rows, ["ODD.METADATA"]).iloc[0]

    assert row["series_kind"] == SERIES_KIND_BASE
    assert row["derived_from"] is None


def test_load_series_drops_only_the_parent_helper_columns() -> None:
    rows = [gold_row("NY.GDP.MKTP.CD", name="GDP", source_name="world_bank")]
    frame = load_rows(rows, ["NY.GDP.MKTP.CD"])

    assert not [column for column in frame.columns if column.startswith("parent_")]
    assert "catalog_indicator_id" not in frame.columns
    assert frame.columns.tolist() == [
        "indicator_id",
        "name",
        "timestamp",
        "value",
        "original_value",
        "is_chain_linked",
        "chain_linking_confidence",
        "unit",
        "frequency",
        "domain",
        "source_name",
        "source_url",
        "record_metadata",
        *SERIES_CLASSIFICATION_COLUMNS,
    ]


def test_load_series_empty_selection_has_stable_columns() -> None:
    frame = DashboardRepository(FakeSession([])).load_series([])

    assert frame.empty
    assert "chain_linking_confidence" in frame.columns
    assert "record_metadata" in frame.columns
    assert set(SERIES_CLASSIFICATION_COLUMNS) <= set(frame.columns)


def test_load_series_without_matching_rows_has_stable_columns() -> None:
    frame = DashboardRepository(FakeSession([])).load_series(["missing"])

    assert frame.empty
    assert set(SERIES_CLASSIFICATION_COLUMNS) <= set(frame.columns)


def test_list_derived_ids_without_parents_queries_nothing() -> None:
    session = FakeSession([])
    repository = DashboardRepository(session)

    assert repository.list_derived_ids([]) == []
    assert session.statements == []


def test_list_derived_ids_returns_discovered_ids() -> None:
    repository = DashboardRepository(FakeSession([{"indicator_id": "WB.NY.GDP.MKTP.CD.YOY"}]))

    assert repository.list_derived_ids(["NY.GDP.MKTP.CD"]) == ["WB.NY.GDP.MKTP.CD.YOY"]
