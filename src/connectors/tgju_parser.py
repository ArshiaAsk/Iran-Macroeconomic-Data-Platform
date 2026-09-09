"""
TGJU HTML parser - pure functions for parsing Persian-language financial data.

This module provides pure parsing functions with no I/O dependencies:
- Persian/Arabic-Indic digit normalization
- Jalali (Persian) to Gregorian date conversion
- HTML parsing for TGJU price pages

All functions are deterministic and side-effect-free for easy testing.
"""

import re
from datetime import datetime, timezone

import jdatetime
import pandas as pd
from bs4 import BeautifulSoup

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
    normalized = normalized.replace(" ", "")  # Whitespace
    
    return normalized


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
    # Month names in Persian (Jalali calendar)
    persian_months = {
        "فروردین": 1, "اردیبهشت": 2, "خرداد": 3,
        "تیر": 4, "مرداد": 5, "شهریور": 6,
        "مهر": 7, "آبان": 8, "آذر": 9,
        "دی": 10, "بهمن": 11, "اسفند": 12,
    }
    
    # Find month name in the text
    month = None
    for month_name, month_num in persian_months.items():
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
        msg = f"Cannot parse day/year from date text: '{date_text}' (normalized: '{normalized_date}')"
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
    
    try:
        # Create Jalali datetime
        jalali_dt = jdatetime.datetime(year, month, day, hour, minute, second)
        
        # Convert to Gregorian
        gregorian_dt = jalali_dt.togregorian()
        
        # Make timezone-aware (assume Tehran timezone for input, convert to UTC)
        # jdatetime returns naive datetime, so we localize it first
        import zoneinfo
        tehran_tz = zoneinfo.ZoneInfo(tz)
        localized_dt = gregorian_dt.replace(tzinfo=tehran_tz)
        
        # Convert to UTC
        utc_dt: datetime = localized_dt.astimezone(timezone.utc)
        
        return utc_dt
        
    except ValueError as e:
        msg = f"Cannot convert Jalali date to Gregorian: y={year}, m={month}, d={day}"
        raise ParsingError(msg) from e


def parse_tgju_html(
    html: str,
    indicator_id: str,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """
    Parse TGJU price page HTML to extract price data.

    Extracts the current price from the "در یک نگاه" (at a glance) table.
    Returns a single-row DataFrame with the most recent price observation.

    Args:
        html: Raw HTML content from TGJU price page
        indicator_id: Indicator identifier (e.g., "TGJU.USD.FREE")
        now: Current timestamp (for testing; defaults to utcnow)

    Returns:
        DataFrame with columns: timestamp, value, indicator_id, unit, obs_status

    Raises:
        ParsingError: If required price data cannot be found in HTML

    Examples:
        >>> html = '<table><tr><td>نرخ فعلی</td><td>۲,۲۵۵,۰۰۰</td></tr></table>'
        >>> df = parse_tgju_html(html, "TGJU.USD.FREE")
        >>> df['value'].iloc[0]
        2255000.0
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Look for the "در یک نگاه" section (at a glance)
    # This section contains the main price table
    
    # Strategy: Find table cells with the label "نرخ فعلی" (current rate)
    # and extract the adjacent cell value
    
    price_value = None
    timestamp_text = None
    date_text = None
    
    # Find all table rows
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            
            if "نرخ فعلی" in label and price_value is None:
                # Found current price
                price_value = value
            elif "زمان ثبت آخرین نرخ" in label:
                # Found timestamp
                timestamp_text = value
    
    # Also look for date in metadata section
    date_div = soup.find("div", class_="date")
    if date_div:
        date_text = date_div.get_text(strip=True)
    
    # If no price found, raise error
    if price_value is None:
        # Check if this is an error page
        error_msg = soup.find("div", class_="error-message")
        if error_msg:
            msg = f"TGJU page shows error: {error_msg.get_text(strip=True)}"
            raise ParsingError(msg)
        
        msg = f"Cannot find price data for {indicator_id} in HTML"
        raise ParsingError(msg)
    
    # Parse the price
    try:
        price = parse_price(price_value)
    except ParsingError:
        msg = f"Found price cell but cannot parse value: '{price_value}'"
        raise ParsingError(msg) from None
    
    # Determine timestamp
    if date_text and timestamp_text:
        # Have both date and time
        try:
            timestamp = jalali_to_gregorian(date_text, time_text=timestamp_text)
        except ParsingError:
            # Fall back to current time
            timestamp = now or datetime.now(timezone.utc)
    else:
        # No date/time found, use current time
        timestamp = now or datetime.now(timezone.utc)
    
    # Build DataFrame
    # All TGJU prices are in Iranian Rials (IRR)
    data = {
        "timestamp": [timestamp],
        "value": [price],
        "indicator_id": [indicator_id],
        "unit": ["IRR"],
        "obs_status": ["A"],  # A = actual/observed
    }
    
    return pd.DataFrame(data)
