"""
Persian/Farsi text helpers shared by the domestic-source parsers.

TGJU, SCI and CBI all publish in Persian and hit the same three problems:

- digits written in Persian (U+06F0–U+06F9) or Arabic-Indic (U+0660–U+0669) form
- thousands separators that are not the ASCII comma
- Jalali (Solar Hijri) dates that must be stored as Gregorian UTC

These helpers are pure: no I/O, no database, no logging. ``src/connectors/
tgju_parser.py`` imports and re-exports them so the TGJU parser keeps its public
surface; the SCI/CBI parsers import them from here directly.
"""

import re
import zoneinfo
from datetime import UTC, datetime

import jdatetime

from src.utils.exceptions import ParsingError

# Persian digit mapping (U+06F0–U+06F9)
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
# Arabic-Indic digit mapping (U+0660–U+0669)
ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
# ASCII digits for translation
ASCII_DIGITS = "0123456789"

# Build translation tables
PERSIAN_TO_ASCII = str.maketrans(PERSIAN_DIGITS, ASCII_DIGITS)
ARABIC_INDIC_TO_ASCII = str.maketrans(ARABIC_INDIC_DIGITS, ASCII_DIGITS)

# Jalali month names -> month number (1 = فروردین … 12 = اسفند)
PERSIAN_MONTHS: dict[str, int] = {
    "فروردین": 1,
    "اردیبهشت": 2,
    "خرداد": 3,
    "تیر": 4,
    "مرداد": 5,
    "شهریور": 6,
    "مهر": 7,
    "آبان": 8,
    "آذر": 9,
    "دی": 10,
    "بهمن": 11,
    "اسفند": 12,
}

# Numeric Jalali date: YYYY/MM/DD, YYYY-MM-DD or YYYY.MM.DD (month/day 1-2 digits)
JALALI_YMD_PATTERN = re.compile(r"(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})")


def normalise_digits(text: str) -> str:
    """
    Normalize Persian and Arabic-Indic digits to ASCII digits.

    Converts:
    - Persian digits (۰-۹, U+06F0–U+06F9) → ASCII (0-9)
    - Arabic-Indic digits (٠-٩, U+0660–U+0669) → ASCII (0-9)
    - Removes Persian/Arabic thousand separators: ، (U+060C) and ٬ (U+066C)
    - Removes ASCII comma and whitespace

    Args:
        text: Input text containing Persian or Arabic-Indic digits

    Returns:
        Normalized text with ASCII digits only

    Examples:
        >>> normalise_digits("۱,۲۳۴,۵۶۷")
        '1234567'
        >>> normalise_digits("٣٬٥٠٠")
        '3500'
        >>> normalise_digits("1,000.50")
        '1000.50'
    """
    # Translate Persian and Arabic-Indic digits to ASCII
    normalized = text.translate(PERSIAN_TO_ASCII).translate(ARABIC_INDIC_TO_ASCII)

    # Remove thousand separators: comma, Arabic comma, Persian separator
    # Keep decimal point (.)
    normalized = normalized.replace(",", "")  # ASCII comma
    normalized = normalized.replace("،", "")  # Arabic comma U+060C
    normalized = normalized.replace("٬", "")  # Persian separator U+066C
    return normalized.replace(" ", "")  # Whitespace


def parse_price(text: str) -> float:
    """
    Parse a price string with Persian/Arabic digits to float.

    Args:
        text: Price string (may contain Persian digits and separators)

    Returns:
        Parsed price as float

    Raises:
        ParsingError: If the text cannot be parsed as a number

    Examples:
        >>> parse_price("۲,۲۵۵,۰۰۰")
        2255000.0
        >>> parse_price("۱.۵۳")
        1.53
    """
    normalized = normalise_digits(text)
    try:
        return float(normalized)
    except ValueError as e:
        msg = f"Cannot parse price from text: '{text}' (normalized: '{normalized}')"
        raise ParsingError(msg) from e


def _jalali_components_to_utc(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    *,
    tz: str = "Asia/Tehran",
) -> datetime:
    """
    Convert Jalali date/time components to a timezone-aware UTC datetime.

    Args:
        year: Jalali year (e.g. 1405)
        month: Jalali month (1-12)
        day: Jalali day (1-31)
        hour: Hour in local wall-clock time
        minute: Minute in local wall-clock time
        second: Second in local wall-clock time
        tz: Timezone the wall-clock time is expressed in (default: Asia/Tehran)

    Returns:
        Timezone-aware Gregorian datetime in UTC

    Raises:
        ParsingError: If the components do not form a valid Jalali datetime
    """
    try:
        jalali_dt = jdatetime.datetime(year, month, day, hour, minute, second)
        gregorian_dt = jalali_dt.togregorian()

        # jdatetime returns a naive datetime, so localize it before converting
        tehran_tz = zoneinfo.ZoneInfo(tz)
        localized_dt = gregorian_dt.replace(tzinfo=tehran_tz)
        utc_dt: datetime = localized_dt.astimezone(UTC)
        return utc_dt
    except ValueError as e:
        msg = f"Cannot convert Jalali date to Gregorian: y={year}, m={month}, d={day}"
        raise ParsingError(msg) from e


def jalali_to_gregorian(
    date_text: str,
    *,
    time_text: str | None = None,
    tz: str = "Asia/Tehran",
) -> datetime:
    """
    Convert Jalali (Persian) date/time to timezone-aware Gregorian datetime.

    Handles formats like:
    - Date: "سه شنبه ۱۷ شهریور ۱۴۰۵" or "۱۷ شهریور ۱۴۰۵"
    - Time: "۱۵:۲۶:۲۴" (optional)

    Args:
        date_text: Jalali date string (may include weekday)
        time_text: Optional time string in HH:MM:SS format
        tz: Timezone name (default: Asia/Tehran)

    Returns:
        Timezone-aware datetime in UTC

    Raises:
        ParsingError: If date/time cannot be parsed

    Examples:
        >>> dt = jalali_to_gregorian("سه شنبه ۱۷ شهریور ۱۴۰۵")
        >>> dt.tzinfo.tzname(dt)
        'UTC'
    """
    # Normalize digits first
    normalized_date = normalise_digits(date_text)
    normalized_time = normalise_digits(time_text) if time_text else None

    # Extract numeric components from date
    # Pattern: optional weekday, day (1-2 digits), month name, year (4 digits)
    month = None
    for month_name, month_num in PERSIAN_MONTHS.items():
        if month_name in date_text:
            month = month_num
            break

    if month is None:
        msg = f"Cannot find month name in date text: '{date_text}'"
        raise ParsingError(msg)

    # Extract year and day using regex on normalized text
    # Looking for 4-digit year and 1-2 digit day
    # Use non-word-boundary pattern since Persian text may not have clear boundaries
    year_match = re.search(r"(\d{4})", normalized_date)
    day_match = re.search(r"(\d{1,2})", normalized_date)

    if not year_match or not day_match:
        msg = (
            f"Cannot parse day/year from date text: '{date_text}' (normalized: '{normalized_date}')"
        )
        raise ParsingError(msg)

    year = int(year_match.group(1))
    day = int(day_match.group(1))

    # Parse time if provided
    hour, minute, second = 0, 0, 0
    if normalized_time:
        time_parts = normalized_time.split(":")
        if len(time_parts) >= 2:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            if len(time_parts) >= 3:
                second = int(time_parts[2])

    return _jalali_components_to_utc(year, month, day, hour, minute, second, tz=tz)


def parse_jalali_ymd(
    date_text: str,
    *,
    time_text: str | None = None,
    tz: str = "Asia/Tehran",
) -> datetime:
    """
    Parse a numeric Jalali ``YYYY/MM/DD`` date to timezone-aware Gregorian UTC.

    SCI publications label periods and files with numeric Jalali dates such as
    ``۱۴۰۵/۰۶/۱۸`` (or ASCII ``1405/06/18``); ``-`` and ``.`` separators are also
    accepted. Persian/Arabic-Indic digits and separators are normalized first.

    Args:
        date_text: Numeric Jalali date, e.g. ``"1405/06/18"``
        time_text: Optional time string in HH:MM:SS format
        tz: Timezone name (default: Asia/Tehran)

    Returns:
        Timezone-aware Gregorian datetime in UTC

    Raises:
        ParsingError: If no ``YYYY/MM/DD`` Jalali date is found or it is invalid

    Examples:
        >>> parse_jalali_ymd("۱۴۰۵/۰۶/۱۸").date().isoformat()
        '2026-09-08'
        >>> parse_jalali_ymd("1405-06-18").date().isoformat()
        '2026-09-08'
    """
    normalized_date = normalise_digits(date_text)
    match = JALALI_YMD_PATTERN.search(normalized_date)
    if match is None:
        msg = (
            f"Cannot parse Jalali YYYY/MM/DD date from text: '{date_text}' "
            f"(normalized: '{normalized_date}')"
        )
        raise ParsingError(msg)

    year, month, day = (int(part) for part in match.groups())

    hour, minute, second = 0, 0, 0
    if time_text:
        normalized_time = normalise_digits(time_text)
        time_parts = normalized_time.split(":")
        if len(time_parts) >= 2:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            if len(time_parts) >= 3:
                second = int(time_parts[2])

    return _jalali_components_to_utc(year, month, day, hour, minute, second, tz=tz)
