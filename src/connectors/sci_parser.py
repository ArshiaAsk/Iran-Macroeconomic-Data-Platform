"""
Statistical Center of Iran (SCI) publication parser - pure functions, no I/O.

Turns the Excel workbooks, PDFs and HTML tables published on ``amar.org.ir``
into tidy observation frames. Kept separate from the connector (as with TGJU and
IMF) so every layout is unit-testable from captured fixtures with no browser and
no network.

Observed publication shapes (reconnaissance 2026-09-13, ``tests/fixtures/sci``)
-------------------------------------------------------------------------------
* **Wide monthly index** (``جدول 1`` in the national/urban/rural/base-1395
  workbooks): row 1 is the table title, row 2 carries Jalali **year** markers
  merged over each 12-month block, row 3 the Persian **month** names, and rows
  4+ one series each. Rural workbooks open with **season** labels
  (بهار/تابستان/…) before switching to months.
* **Tidy long** (``جدول 3`` of the base-1395 workbook): ``سال | ماه | عدد شاخص``.
* **Transposed decile** (decile workbook ``جدول 1``): columns are the ten
  expenditure deciles, rows are periods (``سال ۱۳۹۵`` then month names).
* **Labour-force tables**: a label in the first column and values across
  population scopes, with the whole-country "both sexes" figure in the first
  value column.

Rules honoured here
-------------------
* Digits are normalised and Jalali periods are converted to Gregorian month-end
  UTC (``src.utils.periods.month_period_end``); the original Persian label is
  kept in ``record_metadata``.
* The **index** series is parsed for chain-linking; inflation sheets are
  percentages and must never be spliced (``unit`` distinguishes them).
* Base years are taken from explicit markers only (``سال پایه``, ``100=1400``,
  ``1395=100``); they are never guessed from values.
* All failures raise :class:`~src.utils.exceptions.ParsingError`, never a bare
  ``ValueError``; the parser never returns a silently empty frame.
"""

import re
from collections.abc import Mapping
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import jdatetime
import openpyxl
import pandas as pd
import xlrd
from bs4 import BeautifulSoup

from src.utils.exceptions import ParsingError
from src.utils.periods import month_period_end
from src.utils.persian import (
    ARABIC_INDIC_TO_ASCII,
    PERSIAN_MONTHS,
    PERSIAN_TO_ASCII,
    parse_price,
)

UNIT_INDEX = "index"
UNIT_PERCENT = "percent"
FREQUENCY_MONTHLY = "monthly"
FREQUENCY_QUARTERLY = "quarterly"
OBS_STATUS_ACTUAL = "A"

HEADLINE_LABEL = "شاخص کل"
UNEMPLOYMENT_MEASURE = "نرخ بیکاری"

FRAME_COLUMNS = (
    "timestamp",
    "value",
    "indicator_id",
    "unit",
    "obs_status",
    "base_year",
    "period_label",
    "frequency",
    "record_metadata",
)

_MIN_MONTH_COLUMNS = 6
_MIN_JALALI_YEAR = 1300
_MAX_JALALI_YEAR = 1500
_TIDY_YEAR_HEADERS = ("سال",)
_TIDY_MONTH_HEADERS = ("ماه",)
_TIDY_VALUE_HEADERS = ("عدد شاخص", "شاخص", "مقدار", "value")
_MISSING_MARKERS = frozenset({"", "-", "—", "–", "…", ".."})

# Arabic letter forms used interchangeably with Persian ones in SCI workbooks.
_LETTER_TRANSLATION = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": " "})

_SEASON_END_MONTH: dict[str, int] = {
    "بهار": 3,
    "تابستان": 6,
    "پاییز": 9,
    "زمستان": 12,
}


def _normalise_label(text: Any) -> str:
    """Normalise a Persian label for matching (letter variants, ZWNJ, spaces)."""
    if text is None:
        return ""
    normalised = str(text).translate(_LETTER_TRANSLATION)
    return re.sub(r"\s+", " ", normalised).strip()


_MONTH_LOOKUP: dict[str, int] = {
    _normalise_label(name): num for name, num in PERSIAN_MONTHS.items()
}
_SEASON_LOOKUP: dict[str, int] = {
    _normalise_label(name): num for name, num in _SEASON_END_MONTH.items()
}

_BASE_YEAR_PATTERNS = (
    re.compile(r"سال\s*پایه\s*[:=]?\s*(\d{4})"),
    re.compile(r"(\d{4})\s*=\s*100"),
    re.compile(r"100\s*=\s*(\d{4})"),
)
_JALALI_YEAR_PATTERN = re.compile(r"سال\s*(\d{4})")

ExcelSource = str | Path | bytes


def _ascii_digits(text: Any) -> str:
    """Translate Persian/Arabic-Indic digits only, leaving spacing intact."""
    return str(text).translate(PERSIAN_TO_ASCII).translate(ARABIC_INDIC_TO_ASCII)


def detect_base_year(text: Any) -> int | None:
    """
    Extract an explicit Jalali base year from a title or filename.

    Only explicit markers count (``سال پایه``, ``100=1400``, ``1395=100``) so a
    data year such as ``سال ۱۳۹۵`` in a decile workbook is **not** mistaken for
    a base year (chain-linking never guesses rebases from values).

    Args:
        text: Title, sheet name or filename, e.g. ``"... 100=1395"``

    Returns:
        The base year as an int, or ``None`` when no explicit marker is present
    """
    candidate = _ascii_digits(text)
    for pattern in _BASE_YEAR_PATTERNS:
        match = pattern.search(candidate)
        if match and _MIN_JALALI_YEAR <= int(match.group(1)) <= _MAX_JALALI_YEAR:
            return int(match.group(1))
    return None


def detect_unit(text: Any) -> str | None:
    """
    Classify a publication title as an index or a percentage series.

    Percentage sheets ("درصد تغییر شاخص …", "نرخ تورم …") are checked first
    because their titles also contain the word شاخص.
    """
    label = _normalise_label(text)
    if any(hint in label for hint in ("تورم", "درصد", "٪", "%")):
        return UNIT_PERCENT
    if any(hint in label for hint in ("شاخص", "عدد شاخص")):
        return UNIT_INDEX
    return None


def _read_bytes(source: ExcelSource) -> bytes:
    if isinstance(source, bytes):
        return source
    try:
        return Path(source).read_bytes()
    except OSError as e:
        msg = f"Cannot read SCI workbook: {source!r}"
        raise ParsingError(msg) from e


def _load_sheets(source: ExcelSource) -> dict[str, list[list[Any]]]:
    """Load every sheet of a workbook (xlsx via openpyxl, legacy xls via xlrd)."""
    data = _read_bytes(source)
    if data[:2] == b"PK":
        return _load_xlsx(data)
    if data[:4] == b"\xd0\xcf\x11\xe0":
        return _load_xls(data)
    msg = "Unsupported SCI workbook format (expected .xlsx or legacy .xls)"
    raise ParsingError(msg)


def _load_xlsx(data: bytes) -> dict[str, list[list[Any]]]:
    try:
        workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as e:  # openpyxl raises a variety of workbook errors
        msg = "Cannot open SCI workbook as .xlsx"
        raise ParsingError(msg) from e

    sheets: dict[str, list[list[Any]]] = {}
    for name in workbook.sheetnames:
        sheets[name] = [list(row) for row in workbook[name].iter_rows(values_only=True)]
    return sheets


def _load_xls(data: bytes) -> dict[str, list[list[Any]]]:
    try:
        workbook = xlrd.open_workbook(file_contents=data)
    except Exception as e:  # xlrd raises XLRDError and friends
        msg = "Cannot open SCI workbook as legacy .xls"
        raise ParsingError(msg) from e

    sheets: dict[str, list[list[Any]]] = {}
    for name in workbook.sheet_names():
        sheet = workbook.sheet_by_name(name)
        sheets[name] = [sheet.row_values(index) for index in range(sheet.nrows)]
    return sheets


def _cell(grid: list[list[Any]], row: int, col: int) -> Any:
    if 0 <= row < len(grid) and 0 <= col < len(grid[row]):
        return grid[row][col]
    return None


def _coerce_number(raw: Any) -> float | None:
    """Parse a numeric cell; missing markers and blanks become ``None``."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return None if pd.isna(raw) else float(raw)
    text = str(raw).strip()
    if text in _MISSING_MARKERS:
        return None
    try:
        return parse_price(text)
    except ParsingError:
        return None


def _month_at(label: Any) -> tuple[int, str] | None:
    """Return ``(month_number, frequency)`` for a month or season label."""
    key = _normalise_label(label)
    if key in _MONTH_LOOKUP:
        return _MONTH_LOOKUP[key], FREQUENCY_MONTHLY
    if key in _SEASON_LOOKUP:
        return _SEASON_LOOKUP[key], FREQUENCY_QUARTERLY
    return None


def _jalali_month_period_end(jalali_year: int, jalali_month: int) -> datetime:
    """Convert a Jalali year/month to the Gregorian month-end timestamp in UTC."""
    try:
        gregorian = jdatetime.date(jalali_year, jalali_month, 1).togregorian()
    except ValueError as e:
        msg = f"Invalid Jalali period: {jalali_year}/{jalali_month}"
        raise ParsingError(msg) from e
    return month_period_end(gregorian.year, gregorian.month)


def _match_year(raw: Any) -> int | None:
    text = _ascii_digits(raw).strip()
    if len(text) == 4 and text.isdigit() and _MIN_JALALI_YEAR <= int(text) <= _MAX_JALALI_YEAR:
        return int(text)
    return None


def _find_tidy_header(grid: list[list[Any]]) -> tuple[int, int, int, int] | None:
    """Locate a ``سال | ماه | <value>`` header row; returns row/year/month/value cols."""
    for index, row in enumerate(grid):
        labels = [_normalise_label(cell) for cell in row]
        if not any(label in _TIDY_YEAR_HEADERS for label in labels):
            continue
        if not any(label in _TIDY_MONTH_HEADERS for label in labels):
            continue
        value_col = next(
            (col for col, label in enumerate(labels) if label in _TIDY_VALUE_HEADERS), None
        )
        if value_col is None:
            continue
        return (
            index,
            labels.index("سال"),
            labels.index("ماه"),
            value_col,
        )
    return None


def _find_wide_header(grid: list[list[Any]]) -> tuple[int, list[int]] | None:
    """Locate a month-name header row; returns row index and month column indices."""
    for index, row in enumerate(grid):
        columns = [col for col, cell in enumerate(row) if _month_at(cell) is not None]
        if len(columns) >= _MIN_MONTH_COLUMNS:
            return index, columns
    return None


def _find_row(grid: list[list[Any]], start: int, label: str) -> int | None:
    target = _normalise_label(label)
    for index in range(start, len(grid)):
        candidate = _normalise_label(_cell(grid, index, 0))
        if candidate == target or candidate.startswith(target):
            return index
    return None


def _records_to_frame(
    records: list[dict[str, Any]],
    *,
    context: str,
) -> pd.DataFrame:
    if not records:
        msg = f"No observations parsed from {context}"
        raise ParsingError(msg)
    frame = pd.DataFrame(records)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame[list(FRAME_COLUMNS)]


def _record_metadata(base_year: int, period_label: str, source_period_label: str) -> dict[str, Any]:
    return {
        "base_year": base_year,
        "period_label": period_label,
        "source_period_label": source_period_label,
    }


def _parse_wide_grid(
    grid: list[list[Any]],
    *,
    header_row: int,
    month_columns: list[int],
    row_label: str,
    indicator_id: str,
    base_year: int,
    unit: str,
) -> pd.DataFrame:
    target_row = _find_row(grid, header_row + 1, row_label)
    if target_row is None:
        msg = f"Series row {row_label!r} not found in sheet"
        raise ParsingError(msg)

    year_row = grid[header_row - 1] if header_row > 0 else []
    records: list[dict[str, Any]] = []
    current_year: int | None = None
    for column in month_columns:
        marker = _match_year(_cell([year_row], 0, column) if year_row else None)
        if marker is not None:
            current_year = marker
        month = _month_at(_cell(grid, header_row, column))
        value = _coerce_number(_cell(grid, target_row, column))
        if current_year is None or month is None or value is None:
            continue
        month_number, frequency = month
        period_label = f"{current_year}/{month_number:02d}"
        records.append(
            {
                "timestamp": _jalali_month_period_end(current_year, month_number),
                "value": value,
                "indicator_id": indicator_id,
                "unit": unit,
                "obs_status": OBS_STATUS_ACTUAL,
                "base_year": base_year,
                "period_label": period_label,
                "frequency": frequency,
                "record_metadata": _record_metadata(
                    base_year, period_label, f"{_cell(grid, header_row, column)} {current_year}"
                ),
            }
        )
    return _records_to_frame(records, context=f"{indicator_id} wide sheet")


def _parse_tidy_grid(
    grid: list[list[Any]],
    *,
    header: tuple[int, int, int, int],
    indicator_id: str,
    base_year: int,
    unit: str,
) -> pd.DataFrame:
    header_row, year_col, month_col, value_col = header
    records: list[dict[str, Any]] = []
    current_year: int | None = None
    for index in range(header_row + 1, len(grid)):
        marker = _match_year(_cell(grid, index, year_col))
        if marker is not None:
            current_year = marker
        month = _month_at(_cell(grid, index, month_col))
        value = _coerce_number(_cell(grid, index, value_col))
        if current_year is None or month is None or value is None:
            continue
        month_number, frequency = month
        period_label = f"{current_year}/{month_number:02d}"
        records.append(
            {
                "timestamp": _jalali_month_period_end(current_year, month_number),
                "value": value,
                "indicator_id": indicator_id,
                "unit": unit,
                "obs_status": OBS_STATUS_ACTUAL,
                "base_year": base_year,
                "period_label": period_label,
                "frequency": frequency,
                "record_metadata": _record_metadata(
                    base_year, period_label, f"{_cell(grid, index, month_col)} {current_year}"
                ),
            }
        )
    return _records_to_frame(records, context=f"{indicator_id} tidy sheet")


def _select_sheet(
    sheets: Mapping[str, list[list[Any]]],
    sheet: str | None,
    *,
    prefer: tuple[str, ...],
) -> tuple[str, list[list[Any]]]:
    if sheet is not None:
        if sheet not in sheets:
            msg = f"Sheet {sheet!r} not found (available: {', '.join(sheets)})"
            raise ParsingError(msg)
        return sheet, sheets[sheet]

    for name in prefer:
        if name in sheets:
            return name, sheets[name]
    for name, grid in sheets.items():
        if _find_tidy_header(grid) is not None or _find_wide_header(grid) is not None:
            return name, grid
    msg = "No parsable SCI data sheet found in workbook"
    raise ParsingError(msg)


def _resolve_unit(unit: str | None, grid: list[list[Any]]) -> str:
    if unit is not None:
        return unit
    title = _cell(grid, 0, 0)
    return detect_unit(title) or UNIT_INDEX


def parse_cpi_excel(
    source: ExcelSource,
    *,
    base_year: int,
    indicator_id: str,
    sheet: str | None = None,
    row_label: str | None = HEADLINE_LABEL,
    unit: str | None = None,
) -> pd.DataFrame:
    """
    Parse a CPI Excel workbook into a tidy observation frame.

    Handles both the wide monthly layout (``جدول 1``) and the tidy long layout
    (``جدول 3`` of the base-1395 workbook). The requested ``row_label`` selects
    the series inside a wide sheet (default headline ``شاخص کل``); the tidy
    layout carries a single headline series and ignores ``row_label``.

    Args:
        source: Path, ``Path`` or raw bytes of an ``.xlsx`` / legacy ``.xls`` file
        base_year: Jalali base year of the publication (explicit, never guessed)
        indicator_id: Indicator id to stamp on each observation
        sheet: Sheet name; defaults to ``جدول 1`` then the first data sheet
        row_label: Series row to extract from a wide sheet
        unit: ``index`` or ``percent``; auto-detected from the title when omitted

    Returns:
        Frame with columns timestamp, value, indicator_id, unit, obs_status,
        base_year, period_label, frequency, record_metadata

    Raises:
        ParsingError: If the workbook cannot be read or the series is not found
    """
    sheets = _load_sheets(source)
    name, grid = _select_sheet(sheets, sheet, prefer=("جدول 1",))
    resolved_unit = _resolve_unit(unit, grid)

    tidy = _find_tidy_header(grid)
    if tidy is not None:
        return _parse_tidy_grid(
            grid, header=tidy, indicator_id=indicator_id, base_year=base_year, unit=resolved_unit
        )

    wide = _find_wide_header(grid)
    if wide is None:
        msg = f"No monthly CPI table found in sheet {name!r}"
        raise ParsingError(msg)
    return _parse_wide_grid(
        grid,
        header_row=wide[0],
        month_columns=wide[1],
        row_label=row_label or HEADLINE_LABEL,
        indicator_id=indicator_id,
        base_year=base_year,
        unit=resolved_unit,
    )


def parse_cpi_decile_excel(
    source: ExcelSource,
    *,
    base_year: int,
    indicator_id_prefix: str,
    sheet: str | None = None,
    unit: str | None = None,
) -> pd.DataFrame:
    """
    Parse the transposed decile CPI workbook (columns = expenditure deciles).

    Args:
        source: Path, ``Path`` or raw bytes of the decile workbook
        base_year: Jalali base year of the publication
        indicator_id_prefix: Prefix for per-decile ids (``<prefix>.D1`` … ``.D10``)
        sheet: Sheet name; defaults to ``جدول 1`` then the first data sheet
        unit: ``index`` or ``percent``; auto-detected from the title when omitted

    Returns:
        Tidy frame with an ``indicator_id`` per decile

    Raises:
        ParsingError: If no decile table is found
    """
    sheets = _load_sheets(source)
    name, grid = _select_sheet(sheets, sheet, prefer=("جدول 1",))
    resolved_unit = _resolve_unit(unit, grid)

    header_row, decile_columns = _find_decile_header(grid)
    if header_row is None:
        msg = f"No decile table found in sheet {name!r}"
        raise ParsingError(msg)

    records: list[dict[str, Any]] = []
    current_year: int | None = None
    for index in range(header_row + 1, len(grid)):
        year_marker = _JALALI_YEAR_PATTERN.search(_ascii_digits(_cell(grid, index, 0)))
        if year_marker:
            current_year = int(year_marker.group(1))
            continue
        month = _month_at(_cell(grid, index, 0))
        if month is None or current_year is None:
            continue
        month_number, frequency = month
        for column, decile in decile_columns.items():
            value = _coerce_number(_cell(grid, index, column))
            if value is None:
                continue
            period_label = f"{current_year}/{month_number:02d}"
            records.append(
                {
                    "timestamp": _jalali_month_period_end(current_year, month_number),
                    "value": value,
                    "indicator_id": f"{indicator_id_prefix}.D{decile}",
                    "unit": resolved_unit,
                    "obs_status": OBS_STATUS_ACTUAL,
                    "base_year": base_year,
                    "period_label": period_label,
                    "frequency": frequency,
                    "record_metadata": {
                        "base_year": base_year,
                        "period_label": period_label,
                        "source_period_label": f"{_cell(grid, index, 0)} {current_year}",
                        "decile": decile,
                    },
                }
            )
    return _records_to_frame(records, context=f"{indicator_id_prefix} decile sheet")


def _find_decile_header(grid: list[list[Any]]) -> tuple[int | None, dict[int, int]]:
    for index, row in enumerate(grid):
        columns: dict[int, int] = {}
        for column, cell in enumerate(row):
            match = re.fullmatch(r"دهک\s+(.+)", _normalise_label(cell))
            if match:
                decile = _DECILE_ORDINALS.get(match.group(1))
                if decile is not None:
                    columns[column] = decile
        if len(columns) >= 2:
            return index, columns
    return None, {}


_DECILE_ORDINALS: dict[str, int] = {
    "اول": 1,
    "دوم": 2,
    "سوم": 3,
    "چهارم": 4,
    "پنجم": 5,
    "ششم": 6,
    "هفتم": 7,
    "هشتم": 8,
    "نهم": 9,
    "دهم": 10,
}


def parse_cpi_html(
    html: str,
    *,
    base_year: int,
    indicator_id: str,
    row_label: str = HEADLINE_LABEL,
    unit: str | None = None,
) -> pd.DataFrame:
    """
    Parse a CPI HTML table into a tidy frame (wide monthly layout only).

    Args:
        html: Raw HTML of a page containing a monthly CPI table
        base_year: Jalali base year of the publication
        indicator_id: Indicator id to stamp on each observation
        row_label: Series row to extract (default headline)
        unit: ``index`` or ``percent``; defaults to ``index``

    Returns:
        Tidy observation frame

    Raises:
        ParsingError: If no monthly table with the requested series is present
    """
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        grid = [
            [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
            for row in table.find_all("tr")
        ]
        wide = _find_wide_header(grid)
        if wide is None:
            continue
        return _parse_wide_grid(
            grid,
            header_row=wide[0],
            month_columns=wide[1],
            row_label=row_label,
            indicator_id=indicator_id,
            base_year=base_year,
            unit=unit or _resolve_unit(None, grid),
        )
    msg = f"No monthly CPI table found in HTML for {indicator_id}"
    raise ParsingError(msg)


def parse_cpi_pdf(
    source: ExcelSource,
    *,
    base_year: int,
    indicator_id: str,
    row_label: str = HEADLINE_LABEL,
    unit: str | None = None,
) -> pd.DataFrame:
    """
    Parse a CPI PDF via ``pdfplumber.extract_tables()``.

    Persian RTL government PDFs frequently expose no machine-readable table
    (the captured monthly CPI report extracts blank grids). That is treated as a
    hard ``ParsingError`` rather than a silent empty success.

    Args:
        source: Path, ``Path`` or raw bytes of the PDF
        base_year: Jalali base year of the publication
        indicator_id: Indicator id to stamp on each observation
        row_label: Series row to extract (default headline)
        unit: ``index`` or ``percent``; defaults to ``index``

    Returns:
        Tidy observation frame

    Raises:
        ParsingError: If the PDF has no extractable monthly table
    """
    import pdfplumber

    data = _read_bytes(source)
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    grid = [[("" if cell is None else str(cell)) for cell in row] for row in table]
                    wide = _find_wide_header(grid)
                    if wide is None:
                        continue
                    return _parse_wide_grid(
                        grid,
                        header_row=wide[0],
                        month_columns=wide[1],
                        row_label=row_label,
                        indicator_id=indicator_id,
                        base_year=base_year,
                        unit=unit or _resolve_unit(None, grid),
                    )
    except Exception as e:  # pdfplumber/pdfminer raise various errors
        msg = f"Cannot extract tables from CPI PDF for {indicator_id}"
        raise ParsingError(msg) from e

    msg = f"No extractable monthly CPI table in PDF for {indicator_id}"
    raise ParsingError(msg)


def parse_unemployment_excel(
    source: ExcelSource,
    *,
    indicator_id: str,
    jalali_year: int,
    season: str,
    measure: str = UNEMPLOYMENT_MEASURE,
    scope_column: int = 1,
    unit: str = UNIT_PERCENT,
) -> pd.DataFrame:
    """
    Extract a labour-force rate for one quarter from an SCI workbook.

    Scans every sheet for a row labelled with ``measure`` and reads the chosen
    population scope (column 1 is the whole-country "both sexes" figure in the
    published table).

    Args:
        source: Path, ``Path`` or raw bytes of the labour-force workbook
        indicator_id: Indicator id to stamp on the observation
        jalali_year: Jalali year of the survey
        season: Persian season name (``بهار`` … ``زمستان``)
        measure: Row label to find (default ``نرخ بیکاری``)
        scope_column: Column holding the desired population scope
        unit: Measurement unit (``percent``)

    Returns:
        Single-row tidy observation frame

    Raises:
        ParsingError: If the season is unknown or the measure row is not found
    """
    season_key = _normalise_label(season)
    if season_key not in _SEASON_LOOKUP:
        msg = f"Unknown SCI season label: {season!r}"
        raise ParsingError(msg)
    period_month = _SEASON_LOOKUP[season_key]

    sheets = _load_sheets(source)
    target = _normalise_label(measure)
    fallback: list[dict[str, Any]] = []

    for grid in sheets.values():
        for row in grid:
            label = _normalise_label(_cell([row], 0, 0))
            if not label:
                continue
            value = _coerce_number(_cell([row], 0, scope_column))
            if value is None or not label.startswith(target):
                continue
            record = _unemployment_record(
                indicator_id=indicator_id,
                jalali_year=jalali_year,
                period_month=period_month,
                season=season,
                value=value,
                unit=unit,
            )
            if label == target:
                return _records_to_frame([record], context=f"{indicator_id} labour force")
            fallback.append(record)

    if fallback:
        return _records_to_frame([fallback[0]], context=f"{indicator_id} labour force")
    msg = f"Measure {measure!r} not found in SCI labour-force workbook"
    raise ParsingError(msg)


def _unemployment_record(
    *,
    indicator_id: str,
    jalali_year: int,
    period_month: int,
    season: str,
    value: float,
    unit: str,
) -> dict[str, Any]:
    period_label = f"{jalali_year}/{period_month:02d}"
    return {
        "timestamp": _jalali_month_period_end(jalali_year, period_month),
        "value": value,
        "indicator_id": indicator_id,
        "unit": unit,
        "obs_status": OBS_STATUS_ACTUAL,
        "base_year": None,
        "period_label": period_label,
        "frequency": FREQUENCY_QUARTERLY,
        "record_metadata": {
            "period_label": period_label,
            "source_period_label": f"{season} {jalali_year}",
        },
    }


def parse_unemployment_pdf(
    source: ExcelSource,
    *,
    indicator_id: str,
    jalali_year: int,
    season: str,
    measure: str = UNEMPLOYMENT_MEASURE,
    scope_column: int = 1,
    unit: str = UNIT_PERCENT,
) -> pd.DataFrame:
    """
    Extract a quarterly labour-force rate from an SCI PDF report.

    Args:
        source: Path, ``Path`` or raw bytes of the PDF
        indicator_id: Indicator id to stamp on the observation
        jalali_year: Jalali year of the survey
        season: Persian season name (``بهار`` … ``زمستان``)
        measure: Row label to find (default ``نرخ بیکاری``)
        scope_column: Column holding the desired population scope
        unit: Measurement unit (``percent``)

    Returns:
        Single-row tidy observation frame

    Raises:
        ParsingError: If the season is unknown or no matching table row exists
    """
    import pdfplumber

    season_key = _normalise_label(season)
    if season_key not in _SEASON_LOOKUP:
        msg = f"Unknown SCI season label: {season!r}"
        raise ParsingError(msg)
    period_month = _SEASON_LOOKUP[season_key]

    data = _read_bytes(source)
    target = _normalise_label(measure)
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        label = _normalise_label(row[0] if row else None)
                        value = _coerce_number(
                            row[scope_column] if len(row) > scope_column else None
                        )
                        if label == target and value is not None:
                            return _records_to_frame(
                                [
                                    _unemployment_record(
                                        indicator_id=indicator_id,
                                        jalali_year=jalali_year,
                                        period_month=period_month,
                                        season=season,
                                        value=value,
                                        unit=unit,
                                    )
                                ],
                                context=f"{indicator_id} labour force PDF",
                            )
    except Exception as e:  # pdfplumber/pdfminer raise various errors
        msg = f"Cannot extract tables from labour-force PDF for {indicator_id}"
        raise ParsingError(msg) from e

    msg = f"Measure {measure!r} not found in SCI labour-force PDF"
    raise ParsingError(msg)


def split_segments(frame: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """
    Split a tidy frame into base-year segments, oldest base first.

    The order matches ``chain_link``'s expectation (oldest segment first, newest
    last) so Silver/Gold can link published base-year series.

    Args:
        frame: Tidy frame carrying a ``base_year`` column

    Returns:
        Mapping ``{base_year: segment_frame}`` sorted ascending by base year

    Raises:
        ParsingError: If the frame has no usable ``base_year`` column
    """
    if "base_year" not in frame.columns:
        msg = "Frame has no base_year column to split on"
        raise ParsingError(msg)
    values = frame["base_year"].dropna().unique().tolist()
    segments: dict[int, pd.DataFrame] = {}
    for raw in sorted(values):
        segments[int(raw)] = frame[frame["base_year"] == raw].reset_index(drop=True)
    if not segments:
        msg = "Frame contains no non-null base_year values"
        raise ParsingError(msg)
    return segments
