"""
Frequency conversion for time-series aggregation.

Sources publish at their native cadence (daily for TGJU/OPEC prices, monthly for
EIA, annual for IMF/World Bank). The Gold layer stores each series at the
frequency it was collected at, and this module performs the one conversion the
project rules call for: **daily -> monthly** using the **end-of-month**
observation for price data, and never forward-filling absent days.

Month-end aggregation is a genuine resampling step, not interpolation: a month
with no observation produces no row, which later surfaces as a gap.
"""

import pandas as pd

from src.utils.periods import month_period_end

VALUE_COLUMN = "value"
TIMESTAMP_COLUMN = "timestamp"

MONTH_END = "month_end"


def to_month_end(
    frame: pd.DataFrame,
    *,
    value_column: str = VALUE_COLUMN,
    timestamp_column: str = TIMESTAMP_COLUMN,
) -> pd.DataFrame:
    """
    Reduce daily observations to the last observation of each calendar month.

    The retained value keeps its native unit and is stamped at the period end
    (UTC), matching the Silver/Gold timestamp contract. Months with no
    observation are absent from the output rather than filled.

    Args:
        frame: Frame with timestamp and value columns
        value_column: Name of the observation value column
        timestamp_column: Name of the observation timestamp column

    Returns:
        A new frame, sorted ascending, with only ``timestamp`` and ``value``
    """
    columns = [timestamp_column, value_column]
    if frame.empty:
        return frame.loc[:, columns].copy()

    working = frame.loc[:, columns].copy()
    working[timestamp_column] = pd.to_datetime(working[timestamp_column], utc=True)
    working = (
        working.dropna(subset=[value_column])
        .sort_values(timestamp_column)
        .drop_duplicates(subset=[timestamp_column], keep="last")
    )

    # Group on a tz-free month key: ``to_period`` would warn about dropping the
    # timezone, and the timezone is irrelevant once the month is the unit.
    month = working[timestamp_column].dt.strftime("%Y-%m")
    last_of_month = working.groupby(month, observed=True)[timestamp_column].idxmax()
    result = working.loc[last_of_month].copy()
    result[timestamp_column] = [
        month_period_end(ts.year, ts.month) for ts in result[timestamp_column]
    ]
    result[value_column] = result[value_column].astype("float64")
    return result.sort_values(timestamp_column).reset_index(drop=True)[columns]


def aggregate_to_monthly(frame: pd.DataFrame, method: str = MONTH_END) -> pd.DataFrame:
    """
    Aggregate a series to monthly frequency using a named method.

    Only ``month_end`` (last observation of the month) is implemented for now;
    the seam exists so volume-style ``mean`` aggregation can be added without
    changing callers.

    Args:
        frame: Frame with timestamp and value columns
        method: Aggregation method; currently ``month_end``

    Returns:
        Monthly frame with the same column contract as :func:`to_month_end`

    Raises:
        ValueError: If the method is not supported
    """
    if method != MONTH_END:
        msg = f"unsupported monthly aggregation method {method!r}"
        raise ValueError(msg)
    return to_month_end(frame)
