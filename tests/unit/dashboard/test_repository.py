"""Unit tests for the dashboard repository's DataFrame shaping."""

from typing import Any

import pandas as pd

from dashboard.repository import DashboardRepository


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
        {
            "indicator_id": "second",
            "name": "Second",
            "timestamp": pd.Timestamp("2020-01-01", tz="UTC"),
            "value": 2.0,
            "original_value": 1.0,
            "is_chain_linked": True,
            "chain_linking_confidence": 0.9,
            "unit": "index",
            "frequency": "annual",
            "domain": "gdp",
            "source_name": "test",
            "source_url": None,
            "record_metadata": {"source": "test"},
        },
        {
            "indicator_id": "first",
            "name": "First",
            "timestamp": pd.Timestamp("2021-01-01", tz="UTC"),
            "value": 1.0,
            "original_value": None,
            "is_chain_linked": False,
            "chain_linking_confidence": None,
            "unit": "index",
            "frequency": "annual",
            "domain": "gdp",
            "source_name": "test",
            "source_url": None,
            "record_metadata": None,
        },
    ]
    frame = DashboardRepository(FakeSession(rows)).load_series(["first", "second"])

    assert frame["indicator_id"].tolist() == ["first", "second"]


def test_load_series_empty_selection_has_stable_columns() -> None:
    frame = DashboardRepository(FakeSession([])).load_series([])

    assert frame.empty
    assert "chain_linking_confidence" in frame.columns
    assert "record_metadata" in frame.columns
