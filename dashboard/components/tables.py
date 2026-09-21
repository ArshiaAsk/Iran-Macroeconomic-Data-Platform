"""Shared table display helpers: bounded rows and Persian localization.

Two presentation concerns live here, both of which the page layer composes:

- :func:`cap_table_rows` bounds how many rows the interactive grid renders
  (Task 15): Gold frames can hold thousands of daily rows, so the grid is a
  preview while the downloads carry the full selection.
- :func:`localize_table_frame` turns a raw data frame into a display frame with
  Persian headers, Persian digits and Jalali dates (Task 20). The same header
  registry and per-column formatters back :func:`dashboard.components.exports.
  prepare_export_frame`, so the grid and the exports cannot drift.

Nothing here changes a stored value: localization is a *display* transform, the
underlying Gold frame is what the exports and the quality logic consume, and the
column-header registry is the single home for table chrome (``table.*`` keys in
:mod:`dashboard.i18n`).
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Final

import pandas as pd

from dashboard.formatting import (
    MISSING_VALUE,
    DigitMode,
    format_number,
    jalali_date_label,
    tehran_timestamp_label,
)
from dashboard.i18n import t
from dashboard.labels import domain_label, frequency_label, indicator_label, source_label
from dashboard.repository import SERIES_KIND_BASE, SERIES_KIND_DERIVED

#: Documented maximum number of observations rows a dashboard table renders.
#: A larger frame keeps its first ``OBSERVATIONS_ROW_LIMIT`` rows for display and
#: the caller shows a "narrow the date range" hint; nothing is dropped from the
#: data, the quality summary or the exports.
OBSERVATIONS_ROW_LIMIT: Final[int] = 500

#: Row height (px) of the observations ``st.dataframe`` (D1): the ``st.dataframe``
#: class uses ``row_height`` as its density control, exactly as the RTL HTML table
#: uses a density class. The value matches the HTML table's **compact** row height
#: (``.dt.compact td { height: 40px }`` in :mod:`dashboard.components.direction`),
#: so a dense observation grid and a dense HTML table read at one density. It
#: changes nothing about which rows or values are shown.
OBSERVATIONS_ROW_HEIGHT: Final[int] = 40

#: Raw column name -> ``dashboard.i18n`` key for its Persian header. Shared by the
#: on-screen grids and the exports; an unmapped column keeps its raw name (a
#: data-level English identifier, never a UI literal).
COLUMN_HEADER_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "indicator_id": "table.indicator_id",
        "name": "table.name",
        "description": "table.description",
        "unit": "table.unit",
        "frequency": "table.frequency",
        "domain": "table.domain",
        "source_name": "table.source_name",
        "source_url": "table.source_url",
        "availability_start": "table.availability_start",
        "availability_end": "table.availability_end",
        "observed_start": "table.observed_start",
        "observed_end": "table.observed_end",
        "observation_count": "table.observation_count",
        "chain_linked_count": "table.chain_linked_count",
        "chain_linked_rows": "table.chain_linked_count",
        "confidence": "table.confidence",
        "average_confidence": "table.confidence",
        "has_base_year_changes": "table.has_base_year_changes",
        "base_years": "table.base_years",
        "is_active": "table.is_active",
        "timestamp": "table.timestamp",
        "timestamp_jalali": "table.jalali_date",
        "value": "table.value",
        "original_value": "table.original_value",
        "is_chain_linked": "table.is_chain_linked",
        "chain_linking_confidence": "table.chain_linking_confidence",
        "record_metadata": "table.record_metadata",
        "series_kind": "table.series_kind",
        "derived_from": "table.derived_from",
        "has_catalog_metadata": "table.has_catalog_metadata",
        "rows_returned": "table.rows_returned",
        "expected_observations": "table.expected_observations",
        "expected_is_estimated": "table.expected_is_estimated",
        "missing_periods": "table.missing_periods",
        "collection_timestamp": "table.collection_timestamp",
        "status": "table.status",
        "records_collected": "table.records_collected",
        "error_message": "table.error_message",
        "indicator_count": "table.indicator_count",
        "survey_year": "table.survey_year",
        "survey_year_end": "table.survey_year_end",
        "period_end": "table.period_end",
        "hbsir_indicators": "table.hbsir_indicators",
        "hbsir_observations": "table.hbsir_observations",
        "staleness": "table.staleness",
        "base_year_segments": "table.base_year_segments",
        "indicator_pair": "table.indicator_pair",
        "matched_observations": "table.matched_observations",
        "meets_minimum": "table.meets_minimum_overlap",
    }
)

#: Columns whose timestamp is rendered as a Jalali date.
JALALI_DATE_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "timestamp",
        "observed_start",
        "observed_end",
        "availability_start",
        "availability_end",
    }
)

#: Columns rendered as a Tehran-local Jalali date and time.
JALALI_TIMESTAMP_COLUMNS: Final[frozenset[str]] = frozenset({"collection_timestamp"})

#: Numeric columns rendered with Persian digit grouping and separators.
NUMBER_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "value",
        "original_value",
        "chain_linking_confidence",
        "observation_count",
        "chain_linked_count",
        "chain_linked_rows",
        "confidence",
        "average_confidence",
        "rows_returned",
        "expected_observations",
        "missing_periods",
        "records_collected",
        "indicator_count",
        "matched_observations",
    }
)

#: Boolean columns rendered as yes/no.
BOOLEAN_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "is_chain_linked",
        "is_active",
        "has_base_year_changes",
        "expected_is_estimated",
        "meets_minimum",
    }
)

_LABEL_COLUMNS: Final[Mapping[str, Callable[[str], str]]] = MappingProxyType(
    {
        "domain": domain_label,
        "source_name": source_label,
        "frequency": frequency_label,
    }
)


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


def localized_header(column: str) -> str:
    """Persian header of a data column, or the raw column name when unmapped.

    Examples:
        >>> localized_header("value") == t("table.value")
        True
        >>> localized_header("custom_column")
        'custom_column'
    """
    key = COLUMN_HEADER_KEYS.get(column)
    return column if key is None else t(key)


def indicator_display_names(frame: pd.DataFrame) -> list[str]:
    """Persian display name per row, resolved through :mod:`dashboard.labels`.

    A derived row is named after its parent plus the derivation fragment, and an
    unmapped indicator falls back to the catalog ``name`` and then the raw id, so
    no row is ever hidden or labelled with a null.

    Examples:
        >>> frame = pd.DataFrame({"indicator_id": ["X"], "name": ["Catalog X"]})
        >>> indicator_display_names(frame)
        ['Catalog X']
    """
    ids = frame.get("indicator_id")
    names = frame.get("name")
    parents = frame.get("derived_from")
    labels: list[str] = []
    for index in range(len(frame)):
        indicator_id = _optional_text(ids.iloc[index] if ids is not None else None)
        if indicator_id is None:
            labels.append(MISSING_VALUE)
            continue
        catalog_name = _optional_text(names.iloc[index] if names is not None else None)
        parent = _optional_text(parents.iloc[index] if parents is not None else None)
        labels.append(indicator_label(indicator_id, catalog_name, parent))
    return labels


def localized_column_values(
    frame: pd.DataFrame,
    column: str,
    *,
    digit_mode: DigitMode = "fa",
) -> list[object]:
    """Localize one column's values for display, preserving row order.

    Timestamps become Jalali labels, numeric and boolean cells become Persian
    strings, label columns (domain/source/frequency/name) resolve through
    :mod:`dashboard.labels`, and every other column is stringified. ``None``/NaN
    renders as the unknown placeholder rather than an invented zero.

    Args:
        frame: Frame carrying ``column``
        column: Raw column name to localize
        digit_mode: ``"fa"`` for display, ``"latin"`` for exports and tests

    Returns:
        A list of display values, one per row
    """
    if column == "name":
        return list(indicator_display_names(frame))
    if column in _LABEL_COLUMNS:
        label = _LABEL_COLUMNS[column]
        return [label(text) for text in _text_values(frame[column])]
    formatter = _cell_formatter(column, digit_mode)
    return [formatter(value) for value in frame[column]]


def _cell_formatter(column: str, digit_mode: DigitMode) -> Callable[[object], str]:
    """Per-value display formatter for one column, by column kind."""
    if column in JALALI_DATE_COLUMNS:
        return lambda value: _jalali_date(value, digit_mode)
    if column in JALALI_TIMESTAMP_COLUMNS:
        return lambda value: _jalali_timestamp(value, digit_mode)
    if column in NUMBER_COLUMNS:
        return lambda value: _number(value, digit_mode)
    if column in BOOLEAN_COLUMNS:
        return _boolean
    if column in ("series_kind", "derived_from"):
        return _series_kind if column == "series_kind" else _derived_from
    return _text


def localize_table_frame(
    frame: pd.DataFrame,
    *,
    digit_mode: DigitMode = "fa",
) -> pd.DataFrame:
    """Return a display frame with Persian headers, digits and Jalali dates.

    The raw frame is never mutated, so the exports and the quality logic keep the
    stored values; only the rendered grid is localized. An empty frame yields an
    empty frame with the same (localized) columns rather than an invented row.

    Args:
        frame: Raw data frame destined for an interactive table
        digit_mode: ``"fa"`` for the UI (default); ``"latin"`` for tests

    Returns:
        A new frame whose columns are the Persian headers and whose cells are
        display strings
    """
    display: dict[str, list[object]] = {}
    for column in frame.columns:
        header = localized_header(str(column))
        if header in display:
            header = f"{header} ({column})"
        display[header] = localized_column_values(frame, str(column), digit_mode=digit_mode)
    return pd.DataFrame(display)


def _optional_text(value: object) -> str | None:
    """A non-empty stripped string, or ``None`` for null/blank/non-text values."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _text_values(series: pd.Series) -> list[str]:
    """Raw values of a label column as strings, unknown when null."""
    return [MISSING_VALUE if _is_null(value) else str(value) for value in series]


def _is_null(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return False


def _text(value: object) -> str:
    if _is_null(value):
        return MISSING_VALUE
    return str(value)


def _number(value: object, digit_mode: DigitMode) -> str:
    if _is_null(value) or isinstance(value, bool):
        return MISSING_VALUE
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return MISSING_VALUE
    if math.isnan(numeric):
        return MISSING_VALUE
    return format_number(numeric, digit_mode=digit_mode)


def _boolean(value: object) -> str:
    if _is_null(value):
        return MISSING_VALUE
    return t("value.yes") if bool(value) else t("value.no")


def _series_kind(value: object) -> str:
    if value == SERIES_KIND_DERIVED:
        return t("value.derived")
    if value == SERIES_KIND_BASE:
        return t("value.base")
    return _text(value)


def _derived_from(value: object) -> str:
    parent = _optional_text(value)
    if parent is None:
        return MISSING_VALUE
    return indicator_label(parent)


def _jalali_date(value: object, digit_mode: DigitMode) -> str:
    timestamp = _timestamp(value)
    if timestamp is None:
        return MISSING_VALUE
    return jalali_date_label(timestamp, digit_mode=digit_mode)


def _jalali_timestamp(value: object, digit_mode: DigitMode) -> str:
    timestamp = _timestamp(value)
    if timestamp is None:
        return MISSING_VALUE
    return tehran_timestamp_label(timestamp, digit_mode=digit_mode)


def _timestamp(value: object) -> datetime | None:
    """A timezone-aware ``datetime`` for a stored value, or ``None``."""
    if _is_null(value):
        return None
    try:
        timestamp = pd.Timestamp(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.to_pydatetime()
