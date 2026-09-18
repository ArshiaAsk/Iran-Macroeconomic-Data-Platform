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
    cached_list_derived_ids,
    cached_list_indicators,
    cached_load_series,
    cached_source_freshness,
)
from dashboard.repository import SERIES_KIND_BASE, SERIES_KIND_DERIVED, DashboardRepository
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


def _append_rows(frame: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """Append fixture rows, keeping the base frame's columns and dtypes.

    The extra frame is reindexed to the base columns (a fixture that omits an
    optional column gets a null one) and cast first, which avoids pandas' all-NA
    concat ``FutureWarning``: columns such as ``original_value``,
    ``chain_linking_confidence`` and ``record_metadata`` are entirely null in the
    appended rows, so pandas would otherwise exclude them from dtype
    determination.
    """
    dtypes = frame.dtypes.astype(str).to_dict()
    aligned = extra.reindex(columns=frame.columns)
    return pd.concat([frame, aligned.astype(dtypes)], ignore_index=True)


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
    """Gold-shaped `welfare` rows: two HBSIR survey years plus annual context.

    Every row has a catalog row, so the repository's classification columns read
    ``base`` / ``derived_from = None`` / ``has_catalog_metadata = True``.
    """

    def welfare_row(
        indicator_id: str,
        name: str,
        timestamp: pd.Timestamp,
        value: float,
        unit: str,
        source: str,
    ) -> dict[str, object]:
        return {
            "indicator_id": indicator_id,
            "name": name,
            "timestamp": timestamp,
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
            "series_kind": SERIES_KIND_BASE,
            "derived_from": None,
            "has_catalog_metadata": True,
        }

    rows: list[dict[str, object]] = [
        welfare_row(
            indicator,
            HBSIR_NAMES[indicator],
            period_end,
            HBSIR_VALUES[indicator],
            "index (0-1)" if indicator == GINI_INDICATOR else "percent",
            "hbsir",
        )
        for period_end in SURVEY_TIMESTAMPS
        for indicator in DEFAULT_INDICATORS
    ]
    rows += [
        welfare_row(indicator_id, name, POPULATION_TIMESTAMP, value, unit, source)
        for indicator_id, name, value, unit, source, _ in WELFARE_CONTEXT_ROWS
    ]
    return pd.DataFrame(rows)


#: Derived inflation series: a parent with a `record_metadata["derived_from"]`
#: Gold row but **no catalog row**, which is exactly how the ETL publishes the
#: derived `YOY` series. It exists so the Inflation page's "Include derived
#: series" toggle has something metadata-driven to discover; the toggle stays off
#: by default, so the page renders unchanged when it is not requested.
INFLATION_INDICATOR = "FP.CPI.TOTL.ZG"
INFLATION_DERIVED_ID = "WB.FP.CPI.TOTL.ZG.YOY"
INFLATION_DERIVED_UNIT = "annual %"
INFLATION_TIMESTAMPS = (
    pd.Timestamp("2020-01-01", tz="UTC"),
    pd.Timestamp("2021-01-01", tz="UTC"),
    pd.Timestamp("2022-01-01", tz="UTC"),
)
INFLATION_DERIVED_VALUES = (100.0, 50.0)


def inflation_derived_series() -> pd.DataFrame:
    """Gold-shaped derived (`YOY`) rows for the inflation parent."""
    return pd.DataFrame(
        [
            {
                "indicator_id": INFLATION_DERIVED_ID,
                "name": "Inflation",
                "timestamp": timestamp,
                "value": value,
                "original_value": None,
                "is_chain_linked": False,
                "chain_linking_confidence": None,
                "unit": INFLATION_DERIVED_UNIT,
                "frequency": "annual",
                "domain": "inflation",
                "source_name": "world_bank",
                "source_url": None,
                "record_metadata": {"derived_from": INFLATION_INDICATOR},
                "series_kind": SERIES_KIND_DERIVED,
                "derived_from": INFLATION_INDICATOR,
                "has_catalog_metadata": False,
            }
            for timestamp, value in zip(
                INFLATION_TIMESTAMPS[1:], INFLATION_DERIVED_VALUES, strict=True
            )
        ]
    )


#: SCI fixture: the labour-force unemployment rate for one quarter. SCI publishes
#: one quarter per release, so the domain is legitimately a single observation and
#: the page must present it without implying a trend.
LABOR_INDICATOR = "SCI.UNEMPLOYMENT.QUARTERLY"
LABOR_NAME = "Unemployment rate (labour force survey, quarterly)"
LABOR_UNIT = "percent"
LABOR_TIMESTAMP = pd.Timestamp("2026-05-31", tz="UTC")
LABOR_VALUE = 9.0


def labor_catalog() -> pd.DataFrame:
    """Catalog row for the `labor` domain: the quarterly SCI unemployment rate."""
    return pd.DataFrame(
        [
            {
                "indicator_id": LABOR_INDICATOR,
                "name": LABOR_NAME,
                "description": None,
                "unit": LABOR_UNIT,
                "frequency": "quarterly",
                "domain": "labor",
                "source_name": "sci",
                "source_url": None,
                "availability_start": LABOR_TIMESTAMP,
                "availability_end": LABOR_TIMESTAMP,
                "has_base_year_changes": False,
                "base_years": None,
                "is_active": True,
            }
        ]
    )


def labor_series() -> pd.DataFrame:
    """Gold-shaped `labor` rows: a single published quarter (spring 1405)."""
    return pd.DataFrame(
        [
            {
                "indicator_id": LABOR_INDICATOR,
                "name": LABOR_NAME,
                "timestamp": LABOR_TIMESTAMP,
                "value": LABOR_VALUE,
                "original_value": None,
                "is_chain_linked": False,
                "chain_linking_confidence": None,
                "unit": LABOR_UNIT,
                "frequency": "quarterly",
                "domain": "labor",
                "source_name": "sci",
                "source_url": None,
                "record_metadata": None,
                "series_kind": SERIES_KIND_BASE,
                "derived_from": None,
                "has_catalog_metadata": True,
            }
        ]
    )


#: Trade and energy fixture: one World Bank trade indicator and one EIA energy
#: indicator, so the Trade & Energy page has a catalog and can exercise the same
#: derived toggle as every other domain page. The trade indicator carries a
#: derived `YOY` row; the energy indicator stays monthly and undriven.
TRADE_INDICATOR = "NE.EXP.GNFS.CD"
TRADE_DERIVED_ID = "WB.NE.EXP.GNFS.CD.YOY"
TRADE_NAME = "Exports of goods and services (current US$)"
ENERGY_INDICATOR = "EIA.IRN.CRUDE_PRODUCTION"
ENERGY_NAME = "Crude oil, NGPL, and other liquids production"
TRADE_TIMESTAMPS = (
    pd.Timestamp("2020-01-01", tz="UTC"),
    pd.Timestamp("2021-01-01", tz="UTC"),
    pd.Timestamp("2022-01-01", tz="UTC"),
)
ENERGY_TIMESTAMPS = (
    pd.Timestamp("2026-08-31", tz="UTC"),
    pd.Timestamp("2026-09-30", tz="UTC"),
)


def _gold_row(
    indicator_id: str,
    name: str,
    timestamp: pd.Timestamp,
    value: float,
    unit: str,
    frequency: str,
    domain: str,
    source_name: str,
    *,
    derived_from: str | None = None,
) -> dict[str, object]:
    """One Gold-shaped row, base by default and metadata-derived when a parent is given."""
    return {
        "indicator_id": indicator_id,
        "name": name,
        "timestamp": timestamp,
        "value": value,
        "original_value": None,
        "is_chain_linked": False,
        "chain_linking_confidence": None,
        "unit": unit,
        "frequency": frequency,
        "domain": domain,
        "source_name": source_name,
        "source_url": None,
        "record_metadata": {"derived_from": derived_from} if derived_from else None,
        "series_kind": SERIES_KIND_DERIVED if derived_from else SERIES_KIND_BASE,
        "derived_from": derived_from,
        "has_catalog_metadata": derived_from is None,
    }


def trade_energy_catalog() -> pd.DataFrame:
    """Catalog rows for the `trade` and `energy` domains."""
    return pd.DataFrame(
        [
            {
                "indicator_id": TRADE_INDICATOR,
                "name": TRADE_NAME,
                "description": None,
                "unit": "current US$",
                "frequency": "annual",
                "domain": "trade",
                "source_name": "world_bank",
                "source_url": None,
                "availability_start": TRADE_TIMESTAMPS[0],
                "availability_end": TRADE_TIMESTAMPS[-1],
                "has_base_year_changes": False,
                "base_years": None,
                "is_active": True,
            },
            {
                "indicator_id": ENERGY_INDICATOR,
                "name": ENERGY_NAME,
                "description": None,
                "unit": "thousand barrels per day",
                "frequency": "monthly",
                "domain": "energy",
                "source_name": "eia",
                "source_url": None,
                "availability_start": ENERGY_TIMESTAMPS[0],
                "availability_end": ENERGY_TIMESTAMPS[-1],
                "has_base_year_changes": False,
                "base_years": None,
                "is_active": True,
            },
        ]
    )


def trade_energy_series() -> pd.DataFrame:
    """Gold-shaped `trade` / `energy` rows, including one derived trade series."""
    rows = [
        _gold_row(
            TRADE_INDICATOR,
            TRADE_NAME,
            timestamp,
            value,
            "current US$",
            "annual",
            "trade",
            "world_bank",
        )
        for timestamp, value in zip(TRADE_TIMESTAMPS, (1.0, 2.0, 3.0), strict=True)
    ]
    rows += [
        _gold_row(
            ENERGY_INDICATOR,
            ENERGY_NAME,
            timestamp,
            value,
            "thousand barrels per day",
            "monthly",
            "energy",
            "eia",
        )
        for timestamp, value in zip(ENERGY_TIMESTAMPS, (100.0, 110.0), strict=True)
    ]
    rows += [
        _gold_row(
            TRADE_DERIVED_ID,
            TRADE_NAME,
            timestamp,
            value,
            "annual %",
            "annual",
            "trade",
            "world_bank",
            derived_from=TRADE_INDICATOR,
        )
        for timestamp, value in zip(TRADE_TIMESTAMPS[1:], (100.0, 50.0), strict=True)
    ]
    return pd.DataFrame(rows)


#: TSETMC fixture: trading sessions for the market domain. The Thursday/Friday
#: weekend and a one-day holiday (2026-09-08) are **absent**, exactly as the
#: source reports them -- the platform never fills a session, so the page must
#: never show a zero for one. The session density stays at or above the
#: calibrated session rate, so the level raises no missing-period warning.
MARKET_SESSIONS = (
    pd.Timestamp("2026-08-29", tz="UTC"),
    pd.Timestamp("2026-08-30", tz="UTC"),
    pd.Timestamp("2026-08-31", tz="UTC"),
    pd.Timestamp("2026-09-01", tz="UTC"),
    pd.Timestamp("2026-09-02", tz="UTC"),
    pd.Timestamp("2026-09-05", tz="UTC"),
    pd.Timestamp("2026-09-06", tz="UTC"),
    pd.Timestamp("2026-09-07", tz="UTC"),
    pd.Timestamp("2026-09-09", tz="UTC"),
    pd.Timestamp("2026-09-12", tz="UTC"),
    pd.Timestamp("2026-09-13", tz="UTC"),
)
#: Dates the source never reported: the Iranian weekend and the holiday above.
MARKET_ABSENT_DATES = (
    pd.Timestamp("2026-09-03", tz="UTC"),
    pd.Timestamp("2026-09-04", tz="UTC"),
    pd.Timestamp("2026-09-08", tz="UTC"),
    pd.Timestamp("2026-09-10", tz="UTC"),
    pd.Timestamp("2026-09-11", tz="UTC"),
)
MARKET_LEVEL_VALUES = (
    7_050_000.0,
    7_090_000.0,
    7_120_000.0,
    7_100_000.0,
    7_150_000.0,
    7_090_000.0,
    7_240_000.0,
    7_310_000.0,
    7_280_000.0,
    7_350_000.0,
    7_330_000.0,
)
#: ``RET1D`` (percent): one observation fewer than the level, because the first
#: session has no previous close to compare against.
MARKET_RET1D_VALUES = (
    0.5674,
    0.4231,
    -0.2809,
    0.7042,
    -0.8392,
    2.1157,
    0.9669,
    -0.4104,
    0.9615,
    -0.2721,
)
#: ``MA30`` (index points) over a shortened warm-up: the real series starts 29
#: sessions after the level, which the fixture compresses to three so the smoke
#: test stays small (the production span is asserted in ``test_quality``).
MARKET_MA30_VALUES = (
    7_094_000.0,
    7_104_000.0,
    7_112_000.0,
    7_130_000.0,
    7_158_000.0,
    7_184_000.0,
    7_208_000.0,
    7_226_000.0,
)
#: ``.ME``: the month-end downsample, stamped at the calendar month end (monthly
#: frequency), not at the last session it was taken from.
MARKET_MONTH_ENDS = (pd.Timestamp("2026-08-31", tz="UTC"), pd.Timestamp("2026-09-30", tz="UTC"))
MARKET_ME_VALUES = (7_120_000.0, 7_330_000.0)
MARKET_INDICATOR = "TSETMC.TEDPIX"
MARKET_RET1D_ID = f"{MARKET_INDICATOR}.RET1D"
MARKET_MA30_ID = f"{MARKET_INDICATOR}.MA30"
MARKET_ME_ID = f"{MARKET_INDICATOR}.ME"
MARKET_NAME = "Tehran Stock Exchange total index (TEDPIX)"
MARKET_UNIT = "index points"
MARKET_SOURCE_URL = "http://cdn.tsetmc.com/api"
MARKET_MA30_START = MARKET_SESSIONS[3]
MARKET_DERIVED_IDS = (MARKET_RET1D_ID, MARKET_MA30_ID, MARKET_ME_ID)


def _market_row(
    indicator_id: str,
    timestamp: pd.Timestamp,
    value: float,
    frequency: str,
    derived_from: str | None,
    unit: str = MARKET_UNIT,
) -> dict[str, object]:
    """One Gold-shaped market row, with the parent provenance a derived row gets."""
    return {
        "indicator_id": indicator_id,
        "name": MARKET_NAME,
        "timestamp": timestamp,
        "value": value,
        "original_value": None,
        "is_chain_linked": False,
        "chain_linking_confidence": None,
        "unit": unit,
        "frequency": frequency,
        "domain": "market",
        "source_name": "tsetmc",
        "source_url": MARKET_SOURCE_URL,
        "record_metadata": {"derived_from": derived_from} if derived_from else None,
        "series_kind": SERIES_KIND_DERIVED if derived_from else SERIES_KIND_BASE,
        "derived_from": derived_from,
        "has_catalog_metadata": derived_from is None,
    }


def market_catalog() -> pd.DataFrame:
    """Catalog rows for the `market` domain: the collected level series only.

    The derived series deliberately have no catalog row -- ``discover()`` never
    emits a derived id -- which is why the page finds them in Gold metadata.
    """
    return pd.DataFrame(
        [
            {
                "indicator_id": MARKET_INDICATOR,
                "name": MARKET_NAME,
                "description": None,
                "unit": MARKET_UNIT,
                "frequency": "daily",
                "domain": "market",
                "source_name": "tsetmc",
                "source_url": MARKET_SOURCE_URL,
                "availability_start": MARKET_SESSIONS[0],
                "availability_end": MARKET_SESSIONS[-1],
                "has_base_year_changes": False,
                "base_years": None,
                "is_active": True,
            }
        ]
    )


def market_series() -> pd.DataFrame:
    """Gold-shaped `market` rows: the daily level plus its three derived series."""
    rows = [
        _market_row(MARKET_INDICATOR, timestamp, value, "daily", None)
        for timestamp, value in zip(MARKET_SESSIONS, MARKET_LEVEL_VALUES, strict=True)
    ]
    rows += [
        _market_row(MARKET_RET1D_ID, timestamp, value, "daily", MARKET_INDICATOR, unit="%")
        for timestamp, value in zip(MARKET_SESSIONS[1:], MARKET_RET1D_VALUES, strict=True)
    ]
    rows += [
        _market_row(MARKET_MA30_ID, timestamp, value, "daily", MARKET_INDICATOR)
        for timestamp, value in zip(MARKET_SESSIONS[3:], MARKET_MA30_VALUES, strict=True)
    ]
    rows += [
        _market_row(MARKET_ME_ID, timestamp, value, "monthly", MARKET_INDICATOR)
        for timestamp, value in zip(MARKET_MONTH_ENDS, MARKET_ME_VALUES, strict=True)
    ]
    return pd.DataFrame(rows)


def app_test(page_filename: str) -> AppTest:
    """Create an AppTest for a dashboard page using an absolute path."""
    return AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "pages" / page_filename)


class FakeDashboardRepository:
    def __init__(self) -> None:
        timestamps = list(INFLATION_TIMESTAMPS)
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
                # Repository classification columns (Task 7): the fake carries
                # them so a page can split level and derived rows exactly as it
                # does against the real LEFT-JOINed query.
                "series_kind": [SERIES_KIND_BASE] * 6,
                "derived_from": [None] * 6,
                "has_catalog_metadata": [True] * 6,
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
        # population and IMF LUR) and the `market` domain (TSETMC's level plus its
        # three derived series) are appended so the Welfare & Survey and Market
        # pages render real rows; the frames above are left untouched for the
        # other pages. The derived inflation series and the single-observation
        # `labor` domain are appended for the derived-toggle and Labor page tests;
        # the `trade`/`energy` pair keeps the Trade & Energy page non-empty too.
        self.catalog = _append_rows(self.catalog, welfare_catalog())
        self.catalog = _append_rows(self.catalog, market_catalog())
        self.catalog = _append_rows(self.catalog, labor_catalog())
        self.catalog = _append_rows(self.catalog, trade_energy_catalog())
        self.series = _append_rows(self.series, welfare_series())
        self.series = _append_rows(self.series, market_series())
        self.series = _append_rows(self.series, inflation_derived_series())
        self.series = _append_rows(self.series, labor_series())
        self.series = _append_rows(self.series, trade_energy_series())
        # The `fx` domain needs Gold rows too: the FX & Gold page defaults to
        # selecting `USD_FREE`, and without observations it renders its empty
        # state, so the shared chart-mode control never registers.
        self.series = _append_rows(
            self.series,
            pd.DataFrame(
                [
                    _gold_row(
                        "USD_FREE",
                        "USD",
                        timestamp,
                        value,
                        "IRR",
                        "daily",
                        "fx",
                        "tgju",
                    )
                    for timestamp, value in zip(
                        INFLATION_TIMESTAMPS, (420_000.0, 423_000.0, 430_000.0), strict=True
                    )
                ]
            ),
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

    def list_derived_ids(self, parent_ids: list[str]) -> list[str]:
        """Derived ids whose ``record_metadata['derived_from']`` is a given parent."""
        if not parent_ids:
            return []
        parents = self.series["derived_from"]
        matched = self.series[parents.isin(parent_ids)]
        return sorted(str(indicator) for indicator in matched["indicator_id"].unique())

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
        cached_list_derived_ids,
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
