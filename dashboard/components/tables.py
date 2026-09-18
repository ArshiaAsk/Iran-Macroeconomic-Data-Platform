"""Shared table display helpers: bounded row rendering.

The dashboard's observation tables are a preview, not the export: Gold frames
can hold thousands of daily rows (TSETMC records ~4,300 trading sessions), and
Streamlit renders every row it is handed. The cap here keeps the on-screen grid
bounded while the download paths still carry the full selection.
"""

from dataclasses import dataclass
from typing import Final

import pandas as pd

#: Documented maximum number of observations rows a dashboard table renders.
#: A larger frame keeps its first ``OBSERVATIONS_ROW_LIMIT`` rows for display and
#: the caller shows a "narrow the date range" hint; nothing is dropped from the
#: data, the quality summary or the exports.
OBSERVATIONS_ROW_LIMIT: Final[int] = 500


@dataclass(frozen=True)
class CappedTable:
    """A display frame truncated to a documented row limit."""

    frame: pd.DataFrame
    total_rows: int
    shown_rows: int
    truncated: bool


def cap_table_rows(
    frame: pd.DataFrame,
    *,
    limit: int = OBSERVATIONS_ROW_LIMIT,
) -> CappedTable:
    """Truncate a frame to the display row limit without changing any values.

    The rows and columns are returned exactly as loaded; only the row count is
    bounded, and the caller decides whether to surface the truncation. The
    underlying ``timestamp`` column stays timezone-aware.

    Args:
        frame: Frame destined for a dashboard table
        limit: Positive row cap; defaults to :data:`OBSERVATIONS_ROW_LIMIT`

    Returns:
        The display frame plus the total/shown counts and whether it was capped

    Raises:
        ValueError: If ``limit`` is not positive

    Examples:
        >>> result = cap_table_rows(pd.DataFrame({"value": [1, 2, 3]}), limit=2)
        >>> result.truncated, result.shown_rows, result.total_rows
        (True, 2, 3)
    """
    if limit <= 0:
        msg = "limit must be positive"
        raise ValueError(msg)
    total_rows = len(frame)
    if total_rows <= limit:
        return CappedTable(frame, total_rows, total_rows, truncated=False)
    return CappedTable(
        frame.head(limit).copy(),
        total_rows,
        limit,
        truncated=True,
    )
