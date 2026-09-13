"""
Pure parsing helpers for the IMF DataMapper API.

Kept separate from the connector (as with TGJU) so payload handling is unit
testable from captured fixtures with no network.

Observed payload shape (probed 2026-09-12)
------------------------------------------
``GET /{CODE}`` returns ``{"values": {CODE: {COUNTRY: {"YYYY": value, ...}}},
"api": {...}}``. The ``values`` map always contains an empty-string key mapped to
``null``; it is skipped. Values are JSON numbers or ``null``.

Design notes
------------
* **Forecasts are retained.** IMF WEO history runs to the vintage year and the
  following five years are projections, so this parser deliberately ignores the
  ``now`` cutoff that the World Bank parser applies.
* **Actual/estimate/forecast is a project convention, not an IMF field.** The
  API does not label which years are projections; the label is derived from the
  WEO vintage parsed out of the indicator's ``source`` string. The rule is:
  years before the vintage are ``actual``, the vintage year is ``estimate``, and
  later years are ``forecast``.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import pandas as pd

from src.utils.exceptions import DataRetrievalError, ParsingError
from src.utils.periods import FREQUENCY_ANNUAL, parse_period

OBSERVATION_ACTUAL = "actual"
OBSERVATION_ESTIMATE = "estimate"
OBSERVATION_FORECAST = "forecast"

VINTAGE_PATTERN = re.compile(r"(\d{4})\)")

FRAME_COLUMNS = ("timestamp", "value", "indicator_id", "unit", "obs_status", "observation_type")


def empty_frame() -> pd.DataFrame:
    """An empty series frame with the connector's column contract."""
    return pd.DataFrame(
        {
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "value": pd.Series(dtype="float64"),
            "indicator_id": pd.Series(dtype="object"),
            "unit": pd.Series(dtype="object"),
            "obs_status": pd.Series(dtype="object"),
            "observation_type": pd.Series(dtype="object"),
        }
    )


def parse_indicator_metadata(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """
    Extract the ``indicators`` map from a ``/indicators`` payload.

    Args:
        payload: Parsed ``/indicators`` response

    Returns:
        Indicator code -> metadata mapping (empty when the key is absent)
    """
    indicators = payload.get("indicators")
    if not isinstance(indicators, Mapping):
        return {}
    return {str(code): meta for code, meta in indicators.items() if isinstance(meta, Mapping)}


def vintage_year(source: Any) -> int | None:
    """
    Parse the WEO vintage year out of an indicator's ``source`` label.

    Args:
        source: e.g. ``"World Economic Outlook (April 2026)"``

    Returns:
        Four-digit year, or None when it cannot be parsed
    """
    if not isinstance(source, str):
        return None
    match = VINTAGE_PATTERN.search(source)
    return int(match.group(1)) if match else None


def observation_type(period_year: int, vintage: int | None) -> str | None:
    """
    Classify a period relative to the WEO vintage (project convention).

    Args:
        period_year: Year of the observation
        vintage: WEO vintage year, if known

    Returns:
        ``actual`` / ``estimate`` / ``forecast``, or None without a vintage
    """
    if vintage is None:
        return None
    if period_year < vintage:
        return OBSERVATION_ACTUAL
    if period_year == vintage:
        return OBSERVATION_ESTIMATE
    return OBSERVATION_FORECAST


def flatten_values(
    values: Mapping[str, Any],
    indicator_id: str,
    country: str = "IRN",
    vintage: int | None = None,
) -> list[dict[str, Any]]:
    """
    Flatten one country's series into ``{period, value, observation_type}`` rows.

    Args:
        values: The ``values`` map from a DataMapper response
        indicator_id: Indicator code to extract
        country: ISO3 country code
        vintage: WEO vintage year used to label observations

    Returns:
        Rows sorted ascending by year; nulls are kept so Silver can count them

    Raises:
        DataRetrievalError: If the indicator or country series is missing
    """
    code_map = values.get(indicator_id)
    if not isinstance(code_map, Mapping):
        msg = f"IMF response had no values for {indicator_id}"
        raise DataRetrievalError(msg)

    country_series = code_map.get(country)
    if not isinstance(country_series, Mapping):
        msg = f"IMF response had no {country} series for {indicator_id}"
        raise DataRetrievalError(msg)

    rows: list[dict[str, Any]] = []
    for period, value in country_series.items():
        text = str(period)
        if not text.isdigit():
            continue
        rows.append(
            {
                "period": text,
                "value": value,
                "observation_type": observation_type(int(text), vintage),
            }
        )
    rows.sort(key=lambda row: int(row["period"]))
    return rows


def imf_parser(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,  # noqa: ARG001 - forecasts are intentionally kept
) -> pd.DataFrame:
    """
    Convert flattened IMF rows into the Silver input frame.

    Args:
        rows: Rows from :func:`flatten_values`
        indicator_id: Indicator these rows belong to
        unit: Resolved unit to stamp on each observation
        now: Ignored; IMF forecasts are intentionally future-dated

    Returns:
        DataFrame with columns timestamp, value, indicator_id, unit, obs_status,
        observation_type

    Raises:
        ParsingError: If a period or value cannot be parsed
    """
    if not rows:
        return empty_frame()

    records = [
        {
            "timestamp": parse_period(row.get("period"), FREQUENCY_ANNUAL),
            "value": _coerce_value(row.get("value")),
            "indicator_id": indicator_id,
            "unit": unit,
            "obs_status": None,
            "observation_type": row.get("observation_type"),
        }
        for row in rows
    ]
    frame = pd.DataFrame.from_records(records, columns=list(FRAME_COLUMNS))
    frame["value"] = frame["value"].astype("float64")
    return frame.sort_values("timestamp").reset_index(drop=True)


def _coerce_value(raw_value: Any) -> float | None:
    """Convert an observation value to float, preserving nulls as None."""
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"non-numeric IMF observation value {raw_value!r}"
        raise ParsingError(msg) from exc
