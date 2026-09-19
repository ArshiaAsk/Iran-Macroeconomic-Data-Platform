"""Display-direction formatting: Persian digits, separators, Jalali and Tehran time.

Storage stays exactly what the ETL wrote: timezone-aware UTC timestamps and
ISO-8601 Gregorian values. ``Asia/Tehran`` is applied **only** when a value is
rendered for a human, and every formatter here is pure so it can be unit-tested
without Streamlit or a database.

Two conventions are worth stating explicitly, because both are easy to get wrong:

- Period ends are stored at midnight UTC (``annual_period_end`` /
  ``month_period_end``). Tehran is ahead of UTC, so the Tehran-local calendar date
  of a period end is the same Gregorian date and the Jalali day is stable.
- Daily snapshot sources (TGJU) store the scrape instant, which may be late
  evening UTC. The Jalali day is therefore determined *after* converting to
  ``Asia/Tehran``, and :func:`tehran_day_bounds` / :func:`jalali_day_bounds`
  produce the UTC filter bounds that round-trip back to the same Jalali day.

Digit tables and the ingestion-direction helpers are shared with
``src.utils.persian`` rather than re-declared: the ingestion contract (Persian →
ASCII, Jalali → Gregorian UTC) must not change, and the display direction must
agree with it.
"""

import math
import zoneinfo
from datetime import UTC, date, datetime, time
from typing import Final, Literal, TypeGuard

import jdatetime

from src.utils.persian import (
    ARABIC_INDIC_TO_ASCII,
    ASCII_DIGITS,
    PERSIAN_DIGITS,
    PERSIAN_MONTHS,
    PERSIAN_TO_ASCII,
)

__all__ = [
    "JALALI_SEASONS",
    "JALALI_MONTH_NAMES",
    "MISSING_VALUE",
    "PERSIAN_DECIMAL_SEPARATOR",
    "PERSIAN_PERCENT_SIGN",
    "PERSIAN_THOUSANDS_SEPARATOR",
    "TEHRAN_TIMEZONE",
    "DigitMode",
    "format_large_number",
    "format_number",
    "format_percent",
    "gregorian_year_label",
    "gregorian_to_jalali",
    "jalali_date_label",
    "jalali_day_bounds",
    "jalali_month_label",
    "jalali_period_label",
    "jalali_year_label",
    "tehran_day_bounds",
    "tehran_timestamp_label",
    "to_ascii_digits",
    "to_persian_digits",
    "to_tehran",
]

DigitMode = Literal["fa", "latin"]
"""Display direction for numerals: Persian digits or Latin/export digits."""

TEHRAN_TIMEZONE: Final[str] = "Asia/Tehran"
"""IANA zone used for display interpretation; never for storage."""

TEHRAN_TZ: Final[zoneinfo.ZoneInfo] = zoneinfo.ZoneInfo(TEHRAN_TIMEZONE)

PERSIAN_THOUSANDS_SEPARATOR: Final[str] = "٬"
PERSIAN_DECIMAL_SEPARATOR: Final[str] = "٫"
PERSIAN_PERCENT_SIGN: Final[str] = "٪"
MISSING_VALUE: Final[str] = "—"
"""Placeholder for ``None``/NaN: shown as unknown, never invented as zero."""

#: Jalali month names in calendar order, derived from the shared month map so the
#: two directions cannot drift.
JALALI_MONTH_NAMES: Final[tuple[str, ...]] = tuple(
    name for name, _ in sorted(PERSIAN_MONTHS.items(), key=lambda item: item[1])
)

#: Jalali seasons in calendar order (Farvardin starts the year).
JALALI_SEASONS: Final[tuple[str, ...]] = ("بهار", "تابستان", "پاییز", "زمستان")

_ASCII_TO_PERSIAN: Final[dict[int, int]] = str.maketrans(ASCII_DIGITS, PERSIAN_DIGITS)


def to_persian_digits(text: str) -> str:
    """Translate ASCII digits to Persian digits (display direction).

    Args:
        text: Text that may contain ASCII digits

    Returns:
        Text with every ASCII digit replaced by its Persian counterpart

    Examples:
        >>> to_persian_digits("1405-06-18")
        '۱۴۰۵-۰۶-۱۸'
    """
    return text.translate(_ASCII_TO_PERSIAN)


def to_ascii_digits(text: str) -> str:
    """Translate Persian and Arabic-Indic digits to ASCII (input/export direction).

    Unlike ``src.utils.persian.normalise_digits`` this keeps separators and
    whitespace: it normalises numerals for display and for round-tripping, not for
    parsing a source value.

    Args:
        text: Text that may contain Persian or Arabic-Indic digits

    Returns:
        Text with every digit replaced by its ASCII counterpart

    Examples:
        >>> to_ascii_digits("۱۴۰۵/۰۶/۱۸")
        '1405/06/18'
        >>> to_ascii_digits("٣٬٥٠٠")
        '3٬500'
    """
    return text.translate(PERSIAN_TO_ASCII).translate(ARABIC_INDIC_TO_ASCII)


def _is_number(value: float | int | None) -> TypeGuard[float | int]:
    """Report whether a value is a real number rather than ``None``/NaN.

    A ``TypeGuard`` so a formatter can narrow ``float | int | None`` to a number
    after the unknown-value check and still be type-checked under mypy strict.
    """
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def format_number(
    value: float | int | None,
    *,
    decimal_places: int | None = None,
    digit_mode: DigitMode = "fa",
    thousands: bool = True,
) -> str:
    """Format a number with Persian (or Latin) digits and separators.

    ``decimal_places=None`` keeps every significant decimal and trims trailing
    zeros, so an integer stays an integer.

    Args:
        value: Number to format, or ``None``/NaN for the unknown placeholder
        decimal_places: Fixed decimal places, or ``None`` to trim
        digit_mode: ``"fa"`` for display, ``"latin"`` for exports and tests
        thousands: Whether to group thousands

    Returns:
        Formatted number (``MISSING_VALUE`` when the value is unknown)

    Examples:
        >>> format_number(1234567.5)
        '۱٬۲۳۴٬۵۶۷٫۵'
        >>> format_number(-1234.5, digit_mode="latin")
        '-1,234.5'
        >>> format_number(None)
        '—'
        >>> format_number(2, decimal_places=2)
        '۲٫۰۰'
    """
    if not _is_number(value):
        return MISSING_VALUE

    if decimal_places is None:
        text = f"{value:,.10f}".rstrip("0").rstrip(".")
    else:
        text = f"{value:,.{decimal_places}f}"
    if not thousands:
        text = text.replace(",", "")

    if digit_mode == "latin":
        return text
    return (
        to_persian_digits(text)
        .replace(",", PERSIAN_THOUSANDS_SEPARATOR)
        .replace(".", PERSIAN_DECIMAL_SEPARATOR)
    )


def format_percent(
    value: float | int | None,
    *,
    decimal_places: int = 1,
    digit_mode: DigitMode = "fa",
) -> str:
    """Format a percentage value with the matching percent sign.

    Args:
        value: Percentage value (``2.5`` means 2.5 percent)
        decimal_places: Fixed decimal places
        digit_mode: ``"fa"`` for display, ``"latin"`` for exports and tests

    Returns:
        Formatted percentage (``MISSING_VALUE`` when the value is unknown)

    Examples:
        >>> format_percent(2.5)
        '۲٫۵٪'
        >>> format_percent(2.5, digit_mode="latin")
        '2.5%'
        >>> format_percent(None)
        '—'
    """
    if not _is_number(value):
        return MISSING_VALUE
    sign = PERSIAN_PERCENT_SIGN if digit_mode == "fa" else "%"
    return f"{format_number(value, decimal_places=decimal_places, digit_mode=digit_mode)}{sign}"


def format_large_number(
    value: float | int | None,
    *,
    precision: int = 1,
    digit_mode: DigitMode = "fa",
) -> str:
    """Format a large number with the Persian scale word (هزار/میلیون/میلیارد).

    The scale word is Persian regardless of ``digit_mode``; ``digit_mode`` only
    controls the digits, so exports keep Latin numerals.

    Args:
        value: Number to format, or ``None``/NaN for the unknown placeholder
        precision: Decimal places for the scaled amount (trailing zeros trimmed)
        digit_mode: ``"fa"`` for display, ``"latin"`` for exports and tests

    Returns:
        Scaled, formatted number (``MISSING_VALUE`` when the value is unknown)

    Examples:
        >>> format_large_number(1_500_000_000)
        '۱٫۵ میلیارد'
        >>> format_large_number(2_000_000)
        '۲ میلیون'
        >>> format_large_number(950, digit_mode="latin")
        '950'
    """
    if not _is_number(value):
        return MISSING_VALUE
    scales: tuple[tuple[float, str], ...] = (
        (1e12, "هزار میلیارد"),
        (1e9, "میلیارد"),
        (1e6, "میلیون"),
        (1e3, "هزار"),
    )
    magnitude = abs(float(value))
    for threshold, label in scales:
        if magnitude >= threshold:
            scaled = round(float(value) / threshold, precision)
            return f"{format_number(scaled, digit_mode=digit_mode)} {label}"
    return format_number(value, digit_mode=digit_mode)


def to_tehran(value: datetime) -> datetime:
    """Convert a timestamp to ``Asia/Tehran`` for display interpretation.

    A naive datetime is treated as UTC (the storage convention) rather than as
    local time, so a caller who forgets the zone cannot silently shift a date.

    Args:
        value: Timezone-aware timestamp, or naive UTC

    Returns:
        The same instant expressed in ``Asia/Tehran``

    Examples:
        >>> to_tehran(datetime(2026, 9, 8, 20, 30, tzinfo=UTC)).isoformat()
        '2026-09-09T00:00:00+03:30'
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(TEHRAN_TZ)


def gregorian_to_jalali(value: datetime) -> jdatetime.date:
    """Convert a stored timestamp to the Jalali day it falls on in Tehran.

    Args:
        value: Timezone-aware timestamp, or naive UTC

    Returns:
        Jalali calendar date of the Tehran-localized instant

    Examples:
        >>> gregorian_to_jalali(datetime(2026, 9, 8, tzinfo=UTC)).isoformat()
        '1405-06-17'
        >>> gregorian_to_jalali(datetime(2026, 9, 8, 20, 30, tzinfo=UTC)).isoformat()
        '1405-06-18'
    """
    return jdatetime.date.fromgregorian(date=to_tehran(value).date())


def jalali_date_label(value: datetime, *, digit_mode: DigitMode = "fa") -> str:
    """Label a timestamp with its Jalali date, e.g. ``۱۸ شهریور ۱۴۰۵``."""
    jalali = gregorian_to_jalali(value)
    text = f"{jalali.day} {JALALI_MONTH_NAMES[jalali.month - 1]} {jalali.year}"
    return to_persian_digits(text) if digit_mode == "fa" else text


def jalali_year_label(value: datetime, *, digit_mode: DigitMode = "fa") -> str:
    """Label the Jalali year containing a timestamp's Tehran-localized period end."""
    year = str(gregorian_to_jalali(value).year)
    return to_persian_digits(year) if digit_mode == "fa" else year


def gregorian_year_label(value: datetime, *, digit_mode: DigitMode = "fa") -> str:
    """Label the Gregorian year of a timestamp's Tehran-localized date.

    Kept alongside :func:`jalali_year_label` so a Persian label can carry the
    auditable Gregorian year without recomputing it in a page.
    """
    year = str(to_tehran(value).year)
    return to_persian_digits(year) if digit_mode == "fa" else year


def jalali_month_label(value: datetime, *, digit_mode: DigitMode = "fa") -> str:
    """Label a timestamp with its Jalali month and year, e.g. ``شهریور ۱۴۰۵``."""
    jalali = gregorian_to_jalali(value)
    text = f"{JALALI_MONTH_NAMES[jalali.month - 1]} {jalali.year}"
    return to_persian_digits(text) if digit_mode == "fa" else text


def jalali_period_label(
    value: datetime,
    frequency: str,
    *,
    digit_mode: DigitMode = "fa",
) -> str:
    """Label a period end for a catalog frequency, never inventing a period.

    Annual series label as the Jalali year of the stored period end, monthly and
    quarterly series as their month/season, and anything else (including daily
    snapshots) as the full Jalali date.

    Args:
        value: Stored period end (UTC)
        frequency: Catalog frequency slug
        digit_mode: ``"fa"`` for display, ``"latin"`` for exports and tests

    Returns:
        Persian period label

    Examples:
        >>> jalali_period_label(datetime(2025, 3, 20, tzinfo=UTC), "annual")
        '۱۴۰۳'
        >>> jalali_period_label(datetime(2026, 9, 8, tzinfo=UTC), "monthly")
        'شهریور ۱۴۰۵'
        >>> jalali_period_label(datetime(2026, 9, 8, tzinfo=UTC), "quarterly")
        'تابستان ۱۴۰۵'
    """
    if frequency == "annual":
        return jalali_year_label(value, digit_mode=digit_mode)
    if frequency == "monthly":
        return jalali_month_label(value, digit_mode=digit_mode)
    if frequency == "quarterly":
        jalali = gregorian_to_jalali(value)
        season = JALALI_SEASONS[(jalali.month - 1) // 3]
        text = f"{season} {jalali.year}"
        return to_persian_digits(text) if digit_mode == "fa" else text
    return jalali_date_label(value, digit_mode=digit_mode)


def tehran_timestamp_label(value: datetime, *, digit_mode: DigitMode = "fa") -> str:
    """Label a stored instant as a Tehran-local Jalali date and time.

    Examples:
        >>> tehran_timestamp_label(datetime(2026, 9, 8, 20, 30, tzinfo=UTC))
        '۱۸ شهریور ۱۴۰۵، ۰۰:۰۰'
    """
    local = to_tehran(value)
    clock = f"{local.hour:02d}:{local.minute:02d}"
    if digit_mode == "fa":
        clock = to_persian_digits(clock)
    return f"{jalali_date_label(value, digit_mode=digit_mode)}، {clock}"


def tehran_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Return the inclusive UTC bounds of one Tehran-local calendar day.

    Args:
        day: Gregorian calendar date as observed in Tehran

    Returns:
        ``(start, end)`` UTC bounds, inclusive to the microsecond

    Examples:
        >>> start, end = tehran_day_bounds(date(2026, 9, 8))
        >>> start.isoformat()
        '2026-09-07T20:30:00+00:00'
        >>> end.isoformat()
        '2026-09-08T20:29:59.999999+00:00'
    """
    start_local = datetime.combine(day, time.min, tzinfo=TEHRAN_TZ)
    end_local = datetime.combine(day, time(23, 59, 59, 999999), tzinfo=TEHRAN_TZ)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def jalali_day_bounds(jalali_date: jdatetime.date) -> tuple[datetime, datetime]:
    """Return the UTC bounds that round-trip back to one Jalali day.

    Args:
        jalali_date: Jalali calendar date

    Returns:
        ``(start, end)`` UTC bounds for the Tehran-local Gregorian day

    Examples:
        >>> start, end = jalali_day_bounds(jdatetime.date(1405, 6, 18))
        >>> start.isoformat()
        '2026-09-08T20:30:00+00:00'
        >>> gregorian_to_jalali(start) == gregorian_to_jalali(end) == jdatetime.date(1405, 6, 18)
        True
    """
    return tehran_day_bounds(jalali_date.togregorian())
