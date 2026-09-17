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
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
)
from src.utils.periods import annual_period_end
from src.utils.persian import iranian_year_end

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

#: Jalali survey years the HBSIR fixture covers. 1402 is a common year (Esfand has
#: 29 days) and 1403 is a leap year (Esfand has 30): the boundary the survey-year
#: label has to round-trip.
SURVEY_YEARS = (1402, 1403)
SURVEY_TIMESTAMPS = tuple(pd.Timestamp(iranian_year_end(year)) for year in SURVEY_YEARS)
POPULATION_TIMESTAMP = pd.Timestamp(annual_period_end(2022))

#: English catalog names, mirroring the production catalog (the Persian display
#: labels live in ``dashboard.labels``).
HBSIR_NAMES = {
    GINI_INDICATOR: "Gini of household income (weighted)",
    POVERTY_INDICATOR: "Relative poverty rate (relative to the weighted median)",
    **{
        indicator: f"Income share of weighted decile {indicator.rsplit('D', 1)[-1]}"
        for indicator in DECILE_INDICATORS
    },
}
#: Gini, relative poverty and the ten decile shares (which sum to 100 by
#: construction).
HBSIR_VALUES = {
    GINI_INDICATOR: 0.37,
    POVERTY_INDICATOR: 16.0,
    **dict.fromkeys(DECILE_INDICATORS, 10.0),
}
#: The non-HBSIR members of the `welfare` domain, as (id, name, value, unit,
#: source, availability start) tuples.
WELFARE_CONTEXT_ROWS = (
    ("SP.POP.TOTL", "Population, total", 88_000_000.0, "people", "world_bank", 1960),
    ("SP.POP.GROW", "Population growth (annual %)", 1.2, "annual %", "world_bank", 1961),
    ("LUR", "Unemployment rate", 9.0, "percent", "imf", 1990),
)


def _availability_start(year: int) -> pd.Timestamp:
    """Availability start of a context indicator, at its annual period end."""
    return pd.Timestamp(annual_period_end(year))


def _with_welfare(frame: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """Append the welfare fixture rows, keeping the base frame's column dtypes.

    Casting first avoids pandas' all-NA concat ``FutureWarning``: the optional
    columns (``original_value``, ``chain_linking_confidence``, ``record_metadata``)
    are entirely null in the welfare rows, so pandas would otherwise exclude them
    from dtype determination.
    """
    dtypes = frame.dtypes.astype(str).to_dict()
    return pd.concat([frame, extra.astype(dtypes)], ignore_index=True)


def welfare_catalog() -> pd.DataFrame:
    """Catalog rows for the `welfare` domain: HBSIR plus population and IMF LUR."""
    rows: list[dict[str, object]] = [
        {
            "indicator_id": indicator,
            "name": HBSIR_NAMES[indicator],
            "description": None,
            "unit": "index (0-1)" if indicator == GINI_INDICATOR else "percent",
            "frequency": "annual",
            "domain": "welfare",
            "source_name": "hbsir",
            "source_url": None,
            "availability_start": SURVEY_TIMESTAMPS[0],
            "availability_end": SURVEY_TIMESTAMPS[-1],
            "has_base_year_changes": False,
            "base_years": None,
            "is_active": True,
        }
        for indicator in DEFAULT_INDICATORS
    ]
    rows += [
        {
            "indicator_id": indicator_id,
            "name": name,
            "description": None,
            "unit": unit,
            "frequency": "annual",
            "domain": "welfare",
            "source_name": source,
            "source_url": None,
            "availability_start": _availability_start(start_year),
            "availability_end": POPULATION_TIMESTAMP,
            "has_base_year_changes": False,
            "base_years": None,
            "is_active": True,
        }
        for indicator_id, name, _, unit, source, start_year in WELFARE_CONTEXT_ROWS
    ]
    return pd.DataFrame(rows)


def welfare_series() -> pd.DataFrame:
    """Gold-shaped `welfare` rows: two HBSIR survey years plus annual context."""
    rows: list[dict[str, object]] = [
        {
            "indicator_id": indicator,
            "name": HBSIR_NAMES[indicator],
            "timestamp": period_end,
            "value": HBSIR_VALUES[indicator],
            "original_value": None,
            "is_chain_linked": False,
            "chain_linking_confidence": None,
            "unit": "index (0-1)" if indicator == GINI_INDICATOR else "percent",
            "frequency": "annual",
            "domain": "welfare",
            "source_name": "hbsir",
            "source_url": None,
            "record_metadata": None,
        }
        for period_end in SURVEY_TIMESTAMPS
        for indicator in DEFAULT_INDICATORS
    ]
    rows += [
        {
            "indicator_id": indicator_id,
            "name": name,
            "timestamp": POPULATION_TIMESTAMP,
            "value": value,
            "original_value": None,
            "is_chain_linked": False,
            "chain_linking_confidence": None,
            "unit": unit,
            "frequency": "annual",
            "domain": "welfare",
            "source_name": source,
            "source_url": None,
            "record_metadata": None,
        }
        for indicator_id, name, value, unit, source, _ in WELFARE_CONTEXT_ROWS
    ]
    return pd.DataFrame(rows)


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
        # The `welfare` domain (HBSIR's twelve survey series plus World Bank
        # population and IMF LUR) is appended so the Welfare & Survey page renders
        # real rows; the frames above are left untouched for the other pages.
        self.catalog = _with_welfare(self.catalog, welfare_catalog())
        self.series = _with_welfare(self.series, welfare_series())

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
