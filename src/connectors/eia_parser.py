"""
Pure parsing helpers for the EIA Open Data API v2 international dataset.

Kept separate from the connector (as with TGJU and IMF) so payload handling is
unit testable from captured fixtures with no network.

Observed payload shape (probed 2026-09-12)
------------------------------------------
``GET /v2/international/data/`` returns::

    {"warnings": [],
     "response": {"total": "29", "dateFormat": "YYYY-MM", "frequency": "monthly",
                  "description": "...", "data": [ {...}, ... ]},
     "request": {...},
     "apiVersion": "2.1.13"}

Each data object carries the observation alongside its facet labels::

    {"period": "2026-05", "productId": "55",
     "productName": "Crude oil, NGPL, and other liquids",
     "activityId": "1", "activityName": "Production",
     "countryRegionId": "IRN", "countryRegionName": "Iran",
     "dataFlagId": null, "dataFlagDescription": null,
     "unitName": "thousand barrels per day", "unit": "TBPD",
     "value": "3430"}

Design notes
------------
* **Values are strings.** ``value`` is coerced to ``float``; a blank string or
  JSON ``null`` becomes ``None`` (Silver drops it and counts the loss), while a
  genuinely non-numeric string is a :class:`ParsingError` rather than silent data
  loss.
* **Periods are months.** ``period`` is ``YYYY-MM`` and is stamped at the end of
  the month (project convention), matching the World Bank annual rule.
* **No forecast concept.** Unlike IMF WEO, EIA reports history only, so the
  parser does not annotate an ``observation_type``.
* **Observation flags are preserved.** ``dataFlagDescription`` (falling back to
  the raw ``dataFlagId``) is surfaced as ``obs_status`` so Silver stores it in
  ``metadata`` for auditability.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import pandas as pd

from src.utils.exceptions import ParsingError
from src.utils.periods import FREQUENCY_MONTHLY, parse_period

FRAME_COLUMNS = ("timestamp", "value", "indicator_id", "unit", "obs_status")


def empty_frame() -> pd.DataFrame:
    """An empty series frame with the connector's column contract."""
    return pd.DataFrame(
        {
            "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
            "value": pd.Series(dtype="float64"),
            "indicator_id": pd.Series(dtype="object"),
            "unit": pd.Series(dtype="object"),
            "obs_status": pd.Series(dtype="object"),
        }
    )


def eia_parser(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,  # noqa: ARG001 - EIA reports no projections
) -> pd.DataFrame:
    """
    Convert EIA observation rows into the Silver input frame.

    Args:
        rows: ``response.data`` objects from the API (or a Bronze re-read)
        indicator_id: Platform indicator id these rows belong to
        unit: Fallback unit when a row has no ``unitName``
        now: Ignored; EIA publishes history only

    Returns:
        DataFrame with columns timestamp, value, indicator_id, unit, obs_status,
        sorted ascending by timestamp

    Raises:
        ParsingError: If a period or value cannot be parsed
    """
    if not rows:
        return empty_frame()

    records = [
        {
            "timestamp": parse_period(row.get("period"), FREQUENCY_MONTHLY),
            "value": _coerce_value(row.get("value")),
            "indicator_id": indicator_id,
            "unit": _row_unit(row, unit),
            "obs_status": _row_flag(row),
        }
        for row in rows
    ]
    frame = pd.DataFrame.from_records(records, columns=list(FRAME_COLUMNS))
    frame["value"] = frame["value"].astype("float64")
    return frame.sort_values("timestamp").reset_index(drop=True)


def _coerce_value(raw_value: Any) -> float | None:
    """Convert an observation value to float, preserving blank/null as None."""
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and not raw_value.strip():
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"non-numeric EIA observation value {raw_value!r}"
        raise ParsingError(msg) from exc


def _row_unit(row: Mapping[str, Any], fallback: str | None) -> str | None:
    """Per-row unit name, falling back to the discovered unit."""
    unit = row.get("unitName")
    if isinstance(unit, str) and unit.strip():
        return unit.strip()
    return fallback


def _row_flag(row: Mapping[str, Any]) -> str | None:
    """Observation flag (EIA's data-flag description, then raw id)."""
    for key in ("dataFlagDescription", "dataFlagId"):
        flag = row.get(key)
        if isinstance(flag, str) and flag.strip():
            return flag.strip()
    return None
