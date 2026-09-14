"""
Pure parsing helpers for the TSETMC cdn ``indexB2`` payload.

Kept separate from the connector (as with TGJU, IMF, and EIA) so payload
handling is unit testable from captured fixtures with no network.

Observed payload shape (probed 2026-09-13)
------------------------------------------
``GET http://cdn.tsetmc.com/api/Index/GetIndexB2History/{insCode}`` returns::

    {"indexB2": [
        {"insCode": 32097828799138957, "dEven": 20260913,
         "xNivInuClMresIbs": 7431451.1, "xNivInuPbMresIbs": 7431450.0,
         "xNivInuPhMresIbs": 7464390.0}, ...]}

Each record is one trading session. ``dEven`` is a Gregorian ``yyyymmdd``
integer and ``xNivInuClMresIbs`` is the closing index level (the field
``finpy-tse`` labels ``"Adj Close"``; see ``tests/fixtures/tsetmc/SOURCES.md``).

Design notes
------------
* **Holidays are absent, never filled.** The exchange is closed Thu/Fri and on
  Iranian holidays, so the payload simply omits those sessions. The parser keeps
  that shape: it never inserts or forward-fills a missing day.
* **Timestamps are the session's period end in UTC.** ``dEven`` is a date, and
  the project convention stamps a period end, so each row is dated at midnight
  UTC of the session day (matching ``annual_period_end`` / ``month_period_end``).
  The Gold month-end downsample then re-stamps the last session of each month.
* **No future rows.** A row dated after ``now`` is dropped, mirroring the World
  Bank parser, so the Silver future-date guard can never fire on this source.
* **Nulls are preserved.** A blank/JSON-null level becomes ``None`` and Silver
  drops it (counting the loss); a genuinely non-numeric level is a
  :class:`ParsingError` rather than silent data loss.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.database.schema import utc_now
from src.utils.exceptions import ParsingError

FRAME_COLUMNS = ("timestamp", "value", "indicator_id", "unit", "obs_status")

#: Raw cdn field names for the closing index level and the session date.
INDEX_CLOSE_FIELD = "xNivInuClMresIbs"
SESSION_DATE_FIELD = "dEven"

DEFAULT_UNIT = "index points"

GREGORIAN_YMD_LENGTH = 8


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


def parse_session_date(value: Any) -> datetime:
    """
    Convert a cdn ``dEven`` integer to its UTC session-period-end timestamp.

    Args:
        value: Gregorian ``yyyymmdd`` date, as an int or a string

    Returns:
        Midnight UTC on that session day

    Raises:
        ParsingError: If the value is not a valid ``yyyymmdd`` date
    """
    text = str(value).strip()
    if len(text) != GREGORIAN_YMD_LENGTH or not text.isdigit():
        msg = f"expected an eight-digit TSETMC session date, got {value!r}"
        raise ParsingError(msg)
    try:
        return datetime(int(text[:4]), int(text[4:6]), int(text[6:]), tzinfo=UTC)
    except ValueError as exc:
        msg = f"invalid TSETMC session date {value!r}: {exc}"
        raise ParsingError(msg) from exc


def tsetmc_parser(
    rows: Sequence[Mapping[str, Any]],
    indicator_id: str,
    unit: str | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Convert TSETMC ``indexB2`` records into the Silver input frame.

    Args:
        rows: ``indexB2`` objects from the cdn (or a Bronze re-read)
        indicator_id: Platform indicator id these rows belong to
        unit: Resolved unit; falls back to ``DEFAULT_UNIT``
        now: Clock override for the future-session cutoff

    Returns:
        DataFrame with columns timestamp, value, indicator_id, unit, obs_status,
        sorted ascending by timestamp; missing sessions stay absent

    Raises:
        ParsingError: If a session date or index level cannot be parsed
    """
    if not rows:
        return empty_frame()

    cutoff = now or utc_now()
    resolved_unit = unit or DEFAULT_UNIT
    records = [
        {
            "timestamp": parse_session_date(row.get(SESSION_DATE_FIELD)),
            "value": _coerce_value(row.get(INDEX_CLOSE_FIELD)),
            "indicator_id": indicator_id,
            "unit": resolved_unit,
            "obs_status": None,
        }
        for row in rows
    ]

    frame = pd.DataFrame.from_records(records, columns=list(FRAME_COLUMNS))
    frame["value"] = frame["value"].astype("float64")
    frame = frame[frame["timestamp"] <= cutoff]
    return frame.sort_values("timestamp").reset_index(drop=True)


def _coerce_value(raw_value: Any) -> float | None:
    """Convert an index level to float, preserving blank/null as None."""
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and not raw_value.strip():
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        msg = f"non-numeric TSETMC index value {raw_value!r}"
        raise ParsingError(msg) from exc
