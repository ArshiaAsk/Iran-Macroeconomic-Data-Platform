"""Display-direction formatting tests for dashboard/formatting.py.

Covers the two policies that are easy to get subtly wrong: period ends are stored
at UTC midnight (so the Tehran-local Jalali day is stable), while daily snapshot
sources store a scrape instant that must be converted to Tehran *before* the
displayed Jalali day is decided. The Jalali-day round trip is asserted end to end.
"""

from datetime import UTC, date, datetime, timedelta

import jdatetime
import pytest

from dashboard.formatting import (
    JALALI_MONTH_NAMES,
    JALALI_SEASONS,
    MISSING_VALUE,
    PERSIAN_DECIMAL_SEPARATOR,
    PERSIAN_PERCENT_SIGN,
    PERSIAN_THOUSANDS_SEPARATOR,
    TEHRAN_TIMEZONE,
    format_large_number,
    format_number,
    format_percent,
    gregorian_to_jalali,
    gregorian_year_label,
    jalali_date_label,
    jalali_day_bounds,
    jalali_month_label,
    jalali_period_label,
    jalali_year_label,
    range_label,
    relative_time_label,
    tehran_clock_label,
    tehran_day_bounds,
    tehran_timestamp_label,
    to_ascii_digits,
    to_persian_digits,
    to_tehran,
)
from src.utils.periods import annual_period_end, month_period_end
from src.utils.persian import iranian_year_end

# A Jalali leap year (Esfand has 30 days) inside the retained survey window.
JALALI_LEAP_YEAR = 1403
EVENING_UTC = datetime(2026, 9, 8, 20, 30, tzinfo=UTC)
EVENING_JALALI_DAY = jdatetime.date(1405, 6, 18)


def test_digit_round_trip() -> None:
    latin = "1405-06-18 12:34:56"
    persian = "۱۴۰۵-۰۶-۱۸ ۱۲:۳۴:۵۶"

    assert to_persian_digits(latin) == persian
    assert to_ascii_digits(persian) == latin
    assert to_persian_digits(to_ascii_digits(persian)) == persian


def test_to_ascii_digits_keeps_separators() -> None:
    # Display normalisation must not strip separators the way the ingestion
    # normaliser does; only the numerals change.
    assert to_ascii_digits("١٢٣٬٤٥٦") == "123٬456"


def test_format_number_uses_persian_digits_and_separators() -> None:
    assert PERSIAN_THOUSANDS_SEPARATOR == "٬"
    assert PERSIAN_DECIMAL_SEPARATOR == "٫"
    assert format_number(1234567.5) == "۱٬۲۳۴٬۵۶۷٫۵"


def test_format_number_latin_digits_for_exports() -> None:
    assert format_number(1234.5, digit_mode="latin") == "1,234.5"


def test_format_number_handles_negatives() -> None:
    assert format_number(-1234.5) == "-۱٬۲۳۴٫۵"
    assert format_number(-1234.5, digit_mode="latin") == "-1,234.5"


def test_format_number_decimal_places_and_thousands_toggle() -> None:
    assert format_number(2, decimal_places=2) == "۲٫۰۰"
    assert format_number(1234, thousands=False) == "۱۲۳۴"
    assert format_number(1234, thousands=False, digit_mode="latin") == "1234"


def test_missing_values_are_shown_as_unknown() -> None:
    assert format_number(None) == MISSING_VALUE
    assert format_number(float("nan")) == MISSING_VALUE
    assert format_percent(None) == MISSING_VALUE
    assert format_large_number(None) == MISSING_VALUE
    assert MISSING_VALUE == "—"


def test_format_percent() -> None:
    assert PERSIAN_PERCENT_SIGN == "٪"
    assert format_percent(2.5) == "۲٫۵٪"
    assert format_percent(2.5, digit_mode="latin") == "2.5%"
    assert format_percent(-0.5) == "-۰٫۵٪"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "۰"),
        (950, "۹۵۰"),
        (1500, "۱٫۵ هزار"),
        (2_000_000, "۲ میلیون"),
        (1_500_000_000, "۱٫۵ میلیارد"),
        (2_000_000_000_000, "۲ هزار میلیارد"),
        (-1_500_000_000, "-۱٫۵ میلیارد"),
    ],
)
def test_format_large_number(value: float, expected: str) -> None:
    assert format_large_number(value) == expected


def test_format_large_number_keeps_latin_digits_for_exports() -> None:
    assert format_large_number(1_500_000, digit_mode="latin") == "1.5 میلیون"


def test_to_tehran_uses_the_iana_zone_and_treats_naive_as_utc() -> None:
    assert TEHRAN_TIMEZONE == "Asia/Tehran"
    naive = datetime(2026, 9, 8, 20, 30)  # noqa: DTZ001 - naive input is the case under test
    assert to_tehran(naive) == to_tehran(EVENING_UTC)
    assert to_tehran(EVENING_UTC).utcoffset() == timedelta(hours=3, minutes=30)


def test_gregorian_to_jalali_of_an_evening_instant_uses_tehran() -> None:
    assert gregorian_to_jalali(datetime(2026, 9, 8, tzinfo=UTC)) == jdatetime.date(1405, 6, 17)
    assert gregorian_to_jalali(EVENING_UTC) == EVENING_JALALI_DAY


def test_jalali_month_names_follow_the_shared_month_map() -> None:
    assert JALALI_MONTH_NAMES[0] == "فروردین"
    assert JALALI_MONTH_NAMES[5] == "شهریور"
    assert JALALI_MONTH_NAMES[-1] == "اسفند"
    assert JALALI_SEASONS == ("بهار", "تابستان", "پاییز", "زمستان")


def test_month_period_end_labelling() -> None:
    end = month_period_end(2026, 7)

    assert gregorian_to_jalali(end) == jdatetime.date(1405, 5, 9)
    assert jalali_date_label(end) == "۹ مرداد ۱۴۰۵"
    assert jalali_month_label(end) == "مرداد ۱۴۰۵"
    assert jalali_period_label(end, "monthly") == "مرداد ۱۴۰۵"


def test_annual_period_end_labelling() -> None:
    end = annual_period_end(2021)

    assert gregorian_to_jalali(end) == jdatetime.date(1400, 10, 10)
    assert jalali_year_label(end) == "۱۴۰۰"
    assert gregorian_year_label(end) == "۲۰۲۱"
    assert jalali_period_label(end, "annual") == "۱۴۰۰"


def test_leap_esfand_and_hbsir_year_end_round_trip() -> None:
    end = iranian_year_end(JALALI_LEAP_YEAR)

    assert jdatetime.date(JALALI_LEAP_YEAR, 12, 30).togregorian() == end.date()
    assert gregorian_to_jalali(end) == jdatetime.date(JALALI_LEAP_YEAR, 12, 30)
    assert jalali_date_label(end) == "۳۰ اسفند ۱۴۰۳"
    assert jalali_period_label(end, "annual") == "۱۴۰۳"


def test_jalali_period_label_for_other_frequencies_falls_back_to_the_date() -> None:
    assert jalali_period_label(EVENING_UTC, "quarterly") == "تابستان ۱۴۰۵"
    assert jalali_period_label(EVENING_UTC, "daily") == jalali_date_label(EVENING_UTC)
    assert jalali_period_label(EVENING_UTC, "hourly") == jalali_date_label(EVENING_UTC)


def test_latin_digit_mode_keeps_text_persian() -> None:
    assert jalali_period_label(EVENING_UTC, "annual", digit_mode="latin") == "1405"
    assert jalali_date_label(EVENING_UTC, digit_mode="latin") == "18 شهریور 1405"


def test_tehran_timestamp_label_localizes_the_instant() -> None:
    assert tehran_timestamp_label(EVENING_UTC) == "۱۸ شهریور ۱۴۰۵، ۰۰:۰۰"
    assert (
        tehran_timestamp_label(datetime(2026, 9, 8, 12, 5, tzinfo=UTC), digit_mode="latin")
        == "17 شهریور 1405، 15:35"
    )


def test_tehran_clock_label_is_the_clock_without_the_date() -> None:
    """Task 30: the freshness two-line cell shows the date above time · age."""
    assert tehran_clock_label(EVENING_UTC) == "۰۰:۰۰"
    assert (
        tehran_clock_label(datetime(2026, 9, 8, 12, 5, tzinfo=UTC), digit_mode="latin") == "15:35"
    )
    # The date-bearing label still starts with the date and ends with this clock.
    assert tehran_timestamp_label(EVENING_UTC).endswith(tehran_clock_label(EVENING_UTC))


def test_tehran_day_bounds_are_inclusive_utc_bounds() -> None:
    start, end = tehran_day_bounds(date(2026, 9, 8))

    assert start == datetime(2026, 9, 7, 20, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 8, 20, 29, 59, 999999, tzinfo=UTC)
    assert to_tehran(start).date() == date(2026, 9, 8)
    assert to_tehran(end).date() == date(2026, 9, 8)


@pytest.mark.parametrize(
    "jalali_day",
    [
        jdatetime.date(1405, 1, 1),
        jdatetime.date(1405, 6, 18),
        jdatetime.date(1403, 12, 30),
        jdatetime.date(1400, 10, 10),
    ],
)
def test_jalali_day_bounds_round_trip(jalali_day: jdatetime.date) -> None:
    start, end = jalali_day_bounds(jalali_day)

    assert start <= end
    assert gregorian_to_jalali(start) == jalali_day
    assert gregorian_to_jalali(end) == jalali_day
    assert to_tehran(start).date() == jalali_day.togregorian()
    assert to_tehran(end).date() == jalali_day.togregorian()


def test_an_evening_instant_falls_inside_its_jalali_day_bounds() -> None:
    start, end = jalali_day_bounds(EVENING_JALALI_DAY)

    assert start <= EVENING_UTC <= end
    assert gregorian_to_jalali(EVENING_UTC) == EVENING_JALALI_DAY


# --- relative_time_label (Task 11) -----------------------------------------

_RELATIVE_NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(0), "امروز"),
        (timedelta(minutes=30), "امروز"),
        (timedelta(seconds=3599), "امروز"),
        (timedelta(hours=1), "۱ ساعت پیش"),
        (timedelta(hours=5), "۵ ساعت پیش"),
        (timedelta(hours=23), "۲۳ ساعت پیش"),
        (timedelta(hours=24), "۱ روز پیش"),
        (timedelta(days=5), "۵ روز پیش"),
        (timedelta(days=29), "۲۹ روز پیش"),
        (timedelta(days=30), "۱ ماه پیش"),
        (timedelta(days=60), "۲ ماه پیش"),
        (timedelta(days=365), "۱۲ ماه پیش"),
    ],
)
def test_relative_time_label_boundaries(delta: timedelta, expected: str) -> None:
    value = _RELATIVE_NOW - delta
    assert relative_time_label(value, now=_RELATIVE_NOW) == expected


def test_relative_time_label_future_clamps_to_today() -> None:
    future = _RELATIVE_NOW + timedelta(hours=5)
    assert relative_time_label(future, now=_RELATIVE_NOW) == "امروز"


def test_relative_time_label_latin_digits() -> None:
    value = _RELATIVE_NOW - timedelta(hours=5)
    assert relative_time_label(value, now=_RELATIVE_NOW, digit_mode="latin") == "5 ساعت پیش"

    value = _RELATIVE_NOW - timedelta(days=10)
    assert relative_time_label(value, now=_RELATIVE_NOW, digit_mode="latin") == "10 روز پیش"


# --- range_label (Task 13) -------------------------------------------------

_ANNUAL_START = datetime(1960, 12, 31, tzinfo=UTC)
_ANNUAL_END = datetime(2025, 12, 31, tzinfo=UTC)
_MONTHLY_START = datetime(1982, 3, 31, tzinfo=UTC)
_MONTHLY_END = datetime(2023, 1, 31, tzinfo=UTC)
_DAILY_START = datetime(2026, 9, 9, tzinfo=UTC)
_DAILY_END = datetime(2026, 9, 11, tzinfo=UTC)


@pytest.mark.parametrize(
    ("frequency", "start", "end", "expected"),
    [
        # Golden values captured from jalali_period_label before range_label
        # existed: the default must reproduce them byte-for-byte.
        ("annual", _ANNUAL_START, _ANNUAL_END, "۱۳۳۹ – ۱۴۰۴"),
        ("monthly", _MONTHLY_START, _MONTHLY_END, "فروردین ۱۳۶۱ – بهمن ۱۴۰۱"),
        ("daily", _DAILY_START, _DAILY_END, "۱۸ شهریور ۱۴۰۵ – ۲۰ شهریور ۱۴۰۵"),
    ],
)
def test_range_label_default_reproduces_the_existing_jalali_output(
    frequency: str, start: datetime, end: datetime, expected: str
) -> None:
    assert range_label(start, end, frequency=frequency) == expected
    # The default is explicit: naming "jalali" changes nothing.
    assert range_label(start, end, frequency=frequency, calendar="jalali") == expected


def test_range_label_jalali_is_the_composition_of_the_existing_period_labels() -> None:
    assert range_label(_MONTHLY_START, _MONTHLY_END, frequency="monthly") == (
        f"{jalali_period_label(_MONTHLY_START, 'monthly')} – "
        f"{jalali_period_label(_MONTHLY_END, 'monthly')}"
    )


@pytest.mark.parametrize(
    ("frequency", "start", "end", "expected"),
    [
        # Annual → year only; every sub-annual frequency → year-month (AM-27(e)).
        ("annual", _ANNUAL_START, _ANNUAL_END, "۱۹۶۰ – ۲۰۲۵"),
        (
            "monthly",
            datetime(2023, 5, 31, tzinfo=UTC),
            datetime(2024, 1, 31, tzinfo=UTC),
            "۲۰۲۳-۰۵ – ۲۰۲۴-۰۱",
        ),
        (
            "quarterly",
            datetime(2026, 6, 30, tzinfo=UTC),
            datetime(2026, 9, 30, tzinfo=UTC),
            "۲۰۲۶-۰۶ – ۲۰۲۶-۰۹",
        ),
        (
            "daily",
            datetime(2023, 5, 31, tzinfo=UTC),
            datetime(2023, 6, 15, tzinfo=UTC),
            "۲۰۲۳-۰۵ – ۲۰۲۳-۰۶",
        ),
    ],
)
def test_range_label_gregorian_follows_the_annual_vs_subannual_rule(
    frequency: str, start: datetime, end: datetime, expected: str
) -> None:
    assert range_label(start, end, frequency=frequency, calendar="gregorian") == expected


def test_range_label_gregorian_never_renders_a_jalali_period_or_bare_year() -> None:
    label = range_label(
        datetime(2023, 5, 31, tzinfo=UTC),
        datetime(2024, 1, 31, tzinfo=UTC),
        frequency="monthly",
        calendar="gregorian",
    )

    # No Jalali month name, and no bare year for a sub-annual series.
    assert not any(month in label for month in JALALI_MONTH_NAMES)
    assert "۲۰۲۳-۰۵" in label
    assert "۲۰۲۴-۰۱" in label


def test_range_label_gregorian_latin_digits() -> None:
    assert (
        range_label(
            _ANNUAL_START,
            _ANNUAL_END,
            frequency="annual",
            calendar="gregorian",
            digit_mode="latin",
        )
        == "1960 – 2025"
    )
    assert (
        range_label(
            datetime(2023, 5, 31, tzinfo=UTC),
            datetime(2024, 1, 31, tzinfo=UTC),
            frequency="monthly",
            calendar="gregorian",
            digit_mode="latin",
        )
        == "2023-05 – 2024-01"
    )
