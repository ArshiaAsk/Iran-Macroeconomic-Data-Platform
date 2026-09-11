"""Shared offline fixtures for Streamlit AppTest smoke tests."""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import dashboard.connection as dashboard_connection
from dashboard.queries import (
    cached_available_domains,
    cached_coverage_summary,
    cached_list_indicators,
    cached_load_series,
    cached_source_freshness,
)
from dashboard.repository import DashboardRepository

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def app_test(page_filename: str) -> AppTest:
    """Create an AppTest for a dashboard page using an absolute path."""
    return AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "pages" / page_filename)


class FakeDashboardRepository:
    def __init__(self) -> None:
        timestamps = [
            pd.Timestamp("2020-01-01", tz="UTC"),
            pd.Timestamp("2021-01-01", tz="UTC"),
            pd.Timestamp("2022-01-01", tz="UTC"),
        ]
        self.catalog = pd.DataFrame(
            {
                "indicator_id": ["FP.CPI.TOTL.ZG", "NY.GDP.MKTP.CD", "USD_FREE"],
                "name": ["Inflation", "GDP", "USD"],
                "description": [None, None, None],
                "unit": ["%", "current US$", "IRR"],
                "frequency": ["annual", "annual", "daily"],
                "domain": ["inflation", "gdp", "fx"],
                "source_name": ["world_bank", "world_bank", "tgju"],
                "source_url": [None, None, None],
                "availability_start": [timestamps[0], timestamps[0], timestamps[-1]],
                "availability_end": [timestamps[-1], timestamps[-1], timestamps[-1]],
                "has_base_year_changes": [False, False, False],
                "base_years": [None, None, None],
                "is_active": [True, True, True],
            }
        )
        self.series = pd.DataFrame(
            {
                "indicator_id": ["FP.CPI.TOTL.ZG"] * 3 + ["NY.GDP.MKTP.CD"] * 3,
                "name": ["Inflation"] * 3 + ["GDP"] * 3,
                "timestamp": timestamps * 2,
                "value": [1.0, 2.0, 3.0, 10.0, 20.0, 30.0],
                "original_value": [None, 1.8, None, None, None, None],
                "is_chain_linked": [False, True, False, False, False, False],
                "chain_linking_confidence": [None, 0.9, None, None, None, None],
                "unit": ["%", "%", "%", "current US$"] * 1 + ["current US$", "current US$"],
                "frequency": ["annual"] * 6,
                "domain": ["inflation"] * 3 + ["gdp"] * 3,
                "source_name": ["world_bank"] * 6,
                "source_url": [None] * 6,
                "record_metadata": [None] * 6,
            }
        )
        self.coverage = pd.DataFrame(
            {
                "indicator_id": ["FP.CPI.TOTL.ZG", "NY.GDP.MKTP.CD"],
                "name": ["Inflation", "GDP"],
                "unit": ["%", "current US$"],
                "frequency": ["annual", "annual"],
                "domain": ["inflation", "gdp"],
                "source_name": ["world_bank", "world_bank"],
                "availability_start": [timestamps[0], timestamps[0]],
                "availability_end": [timestamps[-1], timestamps[-1]],
                "observed_start": [timestamps[0], timestamps[0]],
                "observed_end": [timestamps[-1], timestamps[-1]],
                "observation_count": [3, 3],
                "chain_linked_count": [1, 0],
                "confidence": [0.9, None],
            }
        )
        self.freshness = pd.DataFrame(
            {
                "source_name": ["world_bank"],
                "collection_timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
                "status": ["success"],
                "records_collected": [6],
                "error_message": [None],
            }
        )

    def list_indicators(
        self,
        search: str | None = None,
        domains: list[str] | None = None,
        frequencies: list[str] | None = None,
        sources: list[str] | None = None,
        active_only: bool = True,
    ) -> pd.DataFrame:
        result = self.catalog
        if domains:
            result = result[result["domain"].isin(domains)]
        return result.reset_index(drop=True)

    def load_series(
        self,
        indicator_ids: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        result = self.series[self.series["indicator_id"].isin(indicator_ids)]
        return result.reset_index(drop=True)

    def coverage_summary(self, indicator_ids: list[str] | None = None) -> pd.DataFrame:
        if indicator_ids:
            return self.coverage[self.coverage["indicator_id"].isin(indicator_ids)].reset_index(
                drop=True
            )
        return self.coverage

    def source_freshness(self) -> pd.DataFrame:
        return self.freshness

    def available_domains(self) -> pd.DataFrame:
        return self.catalog.groupby("domain").size().reset_index(name="indicator_count")


@pytest.fixture()
def fake_streamlit_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FakeDashboardRepository()
    for cached_query in (
        cached_available_domains,
        cached_coverage_summary,
        cached_list_indicators,
        cached_load_series,
        cached_source_freshness,
    ):
        cached_query.clear()

    @contextmanager
    def fake_repository_session() -> Generator[DashboardRepository, None, None]:
        yield repository  # type: ignore[arg-type]

    monkeypatch.setattr(dashboard_connection, "repository_session", fake_repository_session)
    monkeypatch.setattr("dashboard.queries.repository_session", fake_repository_session)
    monkeypatch.setattr(
        "dashboard.page_view.render_chart_downloads",
        lambda figure, file_prefix: None,
    )
