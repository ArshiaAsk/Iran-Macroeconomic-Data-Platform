"""
Unit tests for the shared Persian/Farsi text helpers.

Covers ``src/utils/persian.py`` directly (the TGJU parser re-exports the same
functions). The numeric Jalali ``YYYY/MM/DD`` helpers are SCI-specific and are
exercised here rather than through a connector parser.
"""

from datetime import UTC, datetime

import pytest

from src.utils.exceptions import ParsingError
from src.utils.persian import (
    ARABIC_INDIC_DIGITS,
    PERSIAN_DIGITS,
    PERSIAN_MONTHS,
    jalali_to_gregorian,
    normalise_digits,
    parse_jalali_ymd,
    parse_price,
)


class TestNormaliseDigits:
    """Persian / Arabic-Indic digits and non-ASCII separators."""

    def test_persian_digits_map_is_complete(self):
        assert normalise_digits(PERSIAN_DIGITS) == "0123456789"

    def test_arabic_indic_digits_map_is_complete(self):
        assert normalise_digits(ARABIC_INDIC_DIGITS) == "0123456789"

    def test_mixed_scripts(self):
        assert normalise_digits("۱٢3") == "123"

    @pytest.mark.parametrize("separator", [",", "،", "٬"])
    def test_thousand_separators_removed(self, separator):
        assert normalise_digits(f"1{separator}234{separator}567") == "1234567"

    def test_regular_spaces_removed(self):
        assert normalise_digits("1 234 567") == "1234567"

    def test_decimal_point_preserved(self):
        assert normalise_digits("۱۲۳.۴۵") == "123.45"

    def test_empty_string(self):
        assert normalise_digits("") == ""

    def test_no_digits_still_strips_separators(self):
        assert normalise_digits("abc,def") == "abcdef"


class TestParsePrice:
    """Prices arrive as Persian text with separators."""

    def test_persian_price(self):
        assert parse_price("۲،۲۵۵،۰۰۰") == 2_255_000.0

    def test_arabic_indic_price(self):
        assert parse_price("٣٬٥٠٠") == 3500.0

    def test_ascii_price(self):
        assert parse_price("2,255,000") == 2_255_000.0

    def test_decimal_price(self):
        assert parse_price("۱.۵۳") == 1.53

    def test_large_price(self):
        assert parse_price("۲،۳۴۰،۱۰۰،۰۰۰") == 2_340_100_000.0

    def test_zero(self):
        assert parse_price("۰") == 0.0

    @pytest.mark.parametrize("text", ["", "   ", "not a number", "123.45.67", "Price: ۱۲۳"])
    def test_unparseable_text_raises(self, text):
        with pytest.raises(ParsingError, match="Cannot parse price"):
            parse_price(text)


class TestParseJalaliYmd:
    """SCI's numeric Jalali dates -> Gregorian UTC."""

    def test_persian_digits_slash(self):
        assert parse_jalali_ymd("۱۴۰۵/۰۶/۱۸").isoformat() == "2026-09-08T20:30:00+00:00"

    def test_ascii_digits_slash(self):
        assert parse_jalali_ymd("1405/06/18").isoformat() == "2026-09-08T20:30:00+00:00"

    def test_dash_separator(self):
        assert parse_jalali_ymd("1405-06-18").isoformat() == "2026-09-08T20:30:00+00:00"

    def test_dot_separator(self):
        assert parse_jalali_ymd("۱۴۰۵.۰۶.۱۸").isoformat() == "2026-09-08T20:30:00+00:00"

    def test_spaces_around_separators(self):
        assert parse_jalali_ymd("1405 / 06 / 18").isoformat() == "2026-09-08T20:30:00+00:00"

    def test_time_component_is_applied(self):
        assert parse_jalali_ymd("1405/06/18", time_text="15:26:24").isoformat() == (
            "2026-09-09T11:56:24+00:00"
        )

    def test_utc_timezone_override(self):
        # Midnight Tehran (UTC+03:30) is the previous UTC day at 20:30.
        assert parse_jalali_ymd("1405/06/18", tz="UTC").isoformat() == ("2026-09-09T00:00:00+00:00")

    def test_result_is_timezone_aware_utc(self):
        result = parse_jalali_ymd("1405/06/18")
        assert result.tzinfo is UTC
        assert isinstance(result, datetime)

    @pytest.mark.parametrize(
        ("jalali", "expected"),
        [
            ("1361/01/01", "1982-03-20T20:30:00+00:00"),
            ("1395/01/01", "2016-03-19T20:30:00+00:00"),
            ("1400/01/01", "2021-03-20T20:30:00+00:00"),
            ("1405/01/01", "2026-03-20T20:30:00+00:00"),
            # 1403 is a leap year, so 12/30 exists.
            ("1403/12/30", "2025-03-19T20:30:00+00:00"),
        ],
    )
    def test_known_conversions(self, jalali, expected):
        assert parse_jalali_ymd(jalali).isoformat() == expected

    def test_non_leap_year_12_30_raises(self):
        # 1404 is not a leap year.
        with pytest.raises(ParsingError, match="Cannot convert Jalali date"):
            parse_jalali_ymd("1404/12/30")

    def test_invalid_month_raises(self):
        with pytest.raises(ParsingError, match="Cannot convert Jalali date"):
            parse_jalali_ymd("1405/13/01")

    @pytest.mark.parametrize("text", ["", "no date here", "1405", "1405/06"])
    def test_missing_or_partial_date_raises(self, text):
        with pytest.raises(ParsingError, match="Cannot parse Jalali YYYY/MM/DD"):
            parse_jalali_ymd(text)


class TestJalaliToGregorian:
    """Weekday + Persian month-name dates (TGJU-style)."""

    def test_weekday_and_month_name(self):
        assert jalali_to_gregorian("سه شنبه ۱۷ شهریور ۱۴۰۵").isoformat() == (
            "2026-09-07T20:30:00+00:00"
        )

    def test_ascii_digits(self):
        assert jalali_to_gregorian("17 شهریور 1405").isoformat() == ("2026-09-07T20:30:00+00:00")

    def test_time_component_is_applied(self):
        assert jalali_to_gregorian("۱۷ شهریور ۱۴۰۵", time_text="15:26:24").isoformat() == (
            "2026-09-08T11:56:24+00:00"
        )

    def test_result_is_utc_aware(self):
        assert jalali_to_gregorian("۱۷ شهریور ۱۴۰۵").tzinfo is UTC

    def test_all_month_names_resolve(self):
        for month_name, month_number in PERSIAN_MONTHS.items():
            assert month_number in range(1, 13)
            # Every month name resolves to a real Gregorian date in 1405.
            assert jalali_to_gregorian(f"۱۵ {month_name} ۱۴۰۵").tzinfo is UTC

    def test_missing_month_name_raises(self):
        with pytest.raises(ParsingError, match="Cannot find month name"):
            jalali_to_gregorian("17 روز 1405")

    def test_missing_digits_raises(self):
        with pytest.raises(ParsingError, match="Cannot parse day/year"):
            jalali_to_gregorian("شهریور")

    def test_day_out_of_range_raises(self):
        with pytest.raises(ParsingError, match="Cannot convert Jalali date"):
            jalali_to_gregorian("۳۲ شهریور ۱۴۰۵")
