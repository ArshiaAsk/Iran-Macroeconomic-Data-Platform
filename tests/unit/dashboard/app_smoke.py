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
    cached_series_inventory,
    cached_source_freshness,
)
from dashboard.repository import SERIES_KIND_BASE, SERIES_KIND_DERIVED, DashboardRepository
from src.connectors.hbsir_parser import (
    DECILE_INDICATORS,
    DEFAULT_INDICATORS,
    GINI_INDICATOR,
    POVERTY_INDICATOR,
)
from src.connectors.sci_scraper import SCI_CANONICAL_INDICATORS, SCI_INDICATOR_REGISTRY
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


#: SCI CPI fixture: the ten household-expenditure deciles plus the three
#: canonical chain-linked series, all domain `inflation`. The ids come from the
#: connector registry, exactly as the Inflation page discovers them, so the
#: fixture cannot drift from the page's metadata-driven source.
SCI_DECILE_IDS = tuple(SCI_INDICATOR_REGISTRY["cpi_decile"].member_ids)
SCI_CANONICAL_IDS = tuple(SCI_CANONICAL_INDICATORS)
SCI_CPI_IDS = (*SCI_DECILE_IDS, *SCI_CANONICAL_IDS)
SCI_CPI_TIMESTAMPS = (
    pd.Timestamp("2024-01-31", tz="UTC"),
    pd.Timestamp("2024-02-29", tz="UTC"),
    pd.Timestamp("2024-03-31", tz="UTC"),
)
SCI_CPI_NAMES = {
    **{
        indicator: f"CPI by household expenditure decile {indicator.rsplit('D', 1)[-1]}, base 1400=2021"
        for indicator in SCI_DECILE_IDS
    },
    **{indicator: SCI_CANONICAL_INDICATORS[indicator].name for indicator in SCI_CANONICAL_IDS},
}
#: One index level per (indicator, month). The deciles fan out by one point each
#: so a comparison is visibly a comparison, not ten identical lines.
SCI_CPI_VALUES = {
    **{
        indicator: (100.0 + rank, 101.0 + rank, 102.0 + rank)
        for rank, indicator in enumerate(SCI_DECILE_IDS, start=1)
    },
    "SCI.CPI.NATIONAL": (200.0, 205.0, 210.0),
    "SCI.CPI.URBAN": (210.0, 215.0, 220.0),
    "SCI.CPI.RURAL": (190.0, 194.0, 198.0),
}


def inflation_catalog() -> pd.DataFrame:
    """Catalog rows for the SCI decile and canonical chain-linked CPI series.

    The canonical series carry base-year changes; the deciles do not. Every row
    is domain `inflation`, so the Inflation page owns them through the same
    domain query as the World Bank headline CPI.
    """
    return pd.DataFrame(
        [
            {
                "indicator_id": indicator,
                "name": SCI_CPI_NAMES[indicator],
                "description": None,
                "unit": "index",
                "frequency": "monthly",
                "domain": "inflation",
                "source_name": "sci",
                "source_url": None,
                "availability_start": SCI_CPI_TIMESTAMPS[0],
                "availability_end": SCI_CPI_TIMESTAMPS[-1],
                "has_base_year_changes": indicator in SCI_CANONICAL_IDS,
                "base_years": "[2016, 2021]" if indicator in SCI_CANONICAL_IDS else None,
                "is_active": True,
            }
            for indicator in SCI_CPI_IDS
        ]
    )


def inflation_series() -> pd.DataFrame:
    """Gold-shaped SCI CPI rows: the ten deciles plus the three canonicals."""
    return pd.DataFrame(
        [
            _gold_row(
                indicator,
                SCI_CPI_NAMES[indicator],
                timestamp,
                value,
                "index",
                "monthly",
                "inflation",
                "sci",
            )
            for indicator in SCI_CPI_IDS
            for timestamp, value in zip(SCI_CPI_TIMESTAMPS, SCI_CPI_VALUES[indicator], strict=True)
        ]
    )


#: The four inactive SCI base-year segments the catalog keeps for the segment
#: view. They are seeded inactive, so they only appear when the catalog page's
#: inactive-segment toggle is on (``active_only=False``).
INACTIVE_SEGMENT_IDS = (
    "SCI.CPI.URBAN.B2016",
    "SCI.CPI.URBAN.B2021",
    "SCI.CPI.NATIONAL.B2021",
    "SCI.CPI.RURAL.B2021",
)


def inactive_segment_catalog() -> pd.DataFrame:
    """Catalog rows for the inactive SCI base-year segments."""
    return pd.DataFrame(
        [
            {
                "indicator_id": indicator,
                "name": f"CPI base-year segment {indicator}",
                "description": None,
                "unit": "index",
                "frequency": "monthly",
                "domain": "inflation",
                "source_name": "sci",
                "source_url": None,
                "availability_start": SCI_CPI_TIMESTAMPS[0],
                "availability_end": SCI_CPI_TIMESTAMPS[-1],
                "has_base_year_changes": True,
                "base_years": "[2016, 2021]",
                "is_active": False,
            }
            for indicator in INACTIVE_SEGMENT_IDS
        ]
    )


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


#: IMF fixture: a World Economic Outlook series whose payload legitimately
#: carries future-dated forecast rows. The platform does not label forecasts in
#: this release (the labeling item needs an ETL change and is deferred), so the
#: future-dated row exists only to prove two things: a future-dated Gold row
#: renders like any other observation, and the Overview's indistinguishability
#: disclaimer is shown. No forecast-specific behaviour is asserted.
IMF_INDICATOR = "NGDP_RPCH"
IMF_NAME = "Real GDP growth"
IMF_UNIT = "Annual percent change"
IMF_TIMESTAMPS = (
    pd.Timestamp(annual_period_end(2021)),
    pd.Timestamp(annual_period_end(2022)),
    pd.Timestamp(annual_period_end(2027)),  # future-dated WEO forecast
)
IMF_VALUES = (2.5, 3.0, 2.1)
#: The single future-dated row, isolated so a test can assert it renders and is
#: never filtered out.
IMF_FORECAST_TIMESTAMP = IMF_TIMESTAMPS[-1]


def imf_forecast_catalog() -> pd.DataFrame:
    """Catalog row for the IMF WEO growth series (domain ``gdp``)."""
    return pd.DataFrame(
        [
            {
                "indicator_id": IMF_INDICATOR,
                "name": IMF_NAME,
                "description": None,
                "unit": IMF_UNIT,
                "frequency": "annual",
                "domain": "gdp",
                "source_name": "imf",
                "source_url": None,
                "availability_start": IMF_TIMESTAMPS[0],
                "availability_end": IMF_TIMESTAMPS[-1],
                "has_base_year_changes": False,
                "base_years": None,
                "is_active": True,
            }
        ]
    )


def imf_forecast_series() -> pd.DataFrame:
    """Gold-shaped IMF rows including one future-dated forecast observation."""
    return pd.DataFrame(
        [
            _gold_row(
                IMF_INDICATOR,
                IMF_NAME,
                timestamp,
                value,
                IMF_UNIT,
                "annual",
                "gdp",
                "imf",
            )
            for timestamp, value in zip(IMF_TIMESTAMPS, IMF_VALUES, strict=True)
        ]
    )


#: A Gold series with no catalog row and no resolvable parent: a genuine orphan.
#: It must be reported by the inventory and never dropped, and its provenance
#: stays ``NULL`` by design (no source is guessed). It is not reachable from any
#: catalog-driven page, so it only exercises the Overview inventory.
ORPHAN_INDICATOR = "ORPHAN.GOLD.ONLY"
ORPHAN_TIMESTAMPS = (
    pd.Timestamp(annual_period_end(2020)),
    pd.Timestamp(annual_period_end(2021)),
)


def orphan_series() -> pd.DataFrame:
    """Gold-shaped orphan rows: no catalog row, no parent, no provenance."""
    return pd.DataFrame(
        [
            {
                "indicator_id": ORPHAN_INDICATOR,
                "name": None,
                "timestamp": timestamp,
                "value": float(index),
                "original_value": None,
                "is_chain_linked": False,
                "chain_linking_confidence": None,
                "unit": "index",
                "frequency": "annual",
                "domain": "inflation",
                "source_name": None,
                "source_url": None,
                "record_metadata": None,
                "series_kind": SERIES_KIND_BASE,
                "derived_from": None,
                "has_catalog_metadata": False,
            }
            for index, timestamp in enumerate(ORPHAN_TIMESTAMPS, start=1)
        ]
    )


def app_test(page_filename: str, *, use_router: bool = True) -> AppTest:
    """Create an AppTest for a dashboard page.

    By default the page is exercised through the router entrypoint
    (``AppTest.from_file(app).switch_page("pages/<name>").run()``), which is the
    path a real session takes: ``app.py`` renders the registry's default page and
    then the requested page is switched in. The Wave-0 spike
    (``docs/phase-7.1/wave-0-spike.md``) showed that ``switch_page`` resolves the
    page by filename and executes it directly, so this does not re-run
    ``st.navigation`` per page -- but it does keep the smoke harness on the same
    entrypoint and page paths the app actually serves.

    ``use_router=False`` keeps the Wave-0 fallback: the page file is loaded
    directly as the main script. Use it when a page must be rendered without the
    router (for example to prove a page is standalone-runnable).

    Args:
        page_filename: Page file name under ``dashboard/pages/`` (e.g.
            ``"2_Inflation.py"``)
        use_router: Route through ``dashboard/app.py`` and ``switch_page`` (default)
            rather than loading the page file directly

    Returns:
        An :class:`AppTest` with the requested page already run once.
    """
    if not use_router:
        return AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "pages" / page_filename)
    app = AppTest.from_file(REPOSITORY_ROOT / "dashboard" / "app.py", default_timeout=20)
    app.run()
    return app.switch_page(f"pages/{page_filename}").run()


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
        self.catalog = _append_rows(self.catalog, inflation_catalog())
        self.catalog = _append_rows(self.catalog, inactive_segment_catalog())
        self.catalog = _append_rows(self.catalog, imf_forecast_catalog())
        self.series = _append_rows(self.series, welfare_series())
        self.series = _append_rows(self.series, market_series())
        self.series = _append_rows(self.series, inflation_derived_series())
        self.series = _append_rows(self.series, labor_series())
        self.series = _append_rows(self.series, trade_energy_series())
        self.series = _append_rows(self.series, inflation_series())
        self.series = _append_rows(self.series, imf_forecast_series())
        self.series = _append_rows(self.series, orphan_series())
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
        if active_only:
            result = result[result["is_active"].astype(bool)]
        if domains:
            result = result[result["domain"].isin(domains)]
        if search:
            needle = search.strip().casefold()
            result = result[
                result["indicator_id"].str.casefold().str.contains(needle, regex=False)
                | result["name"].fillna("").str.casefold().str.contains(needle, regex=False)
                | result["description"].fillna("").str.casefold().str.contains(needle, regex=False)
            ]
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
        active = self.catalog[self.catalog["is_active"].astype(bool)]
        return active.groupby("domain").size().reset_index(name="indicator_count")

    def series_inventory(self) -> pd.DataFrame:
        """Distinct Gold series classified by catalog presence and derivedness."""
        columns = ["indicator_id", "derived_from", "series_kind", "has_catalog_metadata"]
        return self.series[columns].drop_duplicates("indicator_id").reset_index(drop=True)


@pytest.fixture()
def fake_streamlit_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = FakeDashboardRepository()
    for cached_query in (
        cached_available_domains,
        cached_coverage_summary,
        cached_list_derived_ids,
        cached_list_indicators,
        cached_load_series,
        cached_series_inventory,
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
