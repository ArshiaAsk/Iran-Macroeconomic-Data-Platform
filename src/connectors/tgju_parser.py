"""
TGJU HTML parser - pure functions for parsing Persian-language financial data.

This module provides pure parsing functions with no I/O dependencies:
- Persian/Arabic-Indic digit normalization
- Jalali (Persian) to Gregorian date conversion
- HTML parsing for TGJU price pages

The Persian text helpers live in ``src.utils.persian`` (shared with the
SCI/CBI parsers) and are imported and re-exported here so this module's public
surface is unchanged.

All functions are deterministic and side-effect-free for easy testing.
"""

from datetime import UTC, datetime

import pandas as pd
from bs4 import BeautifulSoup

from src.utils.exceptions import ParsingError
from src.utils.persian import (
    ARABIC_INDIC_DIGITS,
    ARABIC_INDIC_TO_ASCII,
    ASCII_DIGITS,
    PERSIAN_DIGITS,
    PERSIAN_MONTHS,
    PERSIAN_TO_ASCII,
    jalali_to_gregorian,
    normalise_digits,
    parse_price,
)

__all__ = [
    "ARABIC_INDIC_DIGITS",
    "ARABIC_INDIC_TO_ASCII",
    "ASCII_DIGITS",
    "PERSIAN_DIGITS",
    "PERSIAN_MONTHS",
    "PERSIAN_TO_ASCII",
    "ParsingError",
    "jalali_to_gregorian",
    "normalise_digits",
    "parse_price",
    "parse_tgju_html",
]


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

    **Idempotency:** The observation timestamp is normalized to the start of the
    day (00:00 UTC) so multiple scrapes on the same day update the same Silver
    row rather than creating duplicates. TGJU provides "today's price", not
    "this second's price". The Silver upsert will replace earlier scrapes from
    the same day with the latest value, preserving idempotency.

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

    # Determine timestamp and normalize to start of day for idempotency
    if date_text and timestamp_text:
        # Have both date and time - parse it
        try:
            raw_timestamp = jalali_to_gregorian(date_text, time_text=timestamp_text)
        except ParsingError:
            # Fall back to current time
            raw_timestamp = now or datetime.now(UTC)
    else:
        # No date/time found, use current time
        raw_timestamp = now or datetime.now(UTC)

    # Normalize to start of day (00:00 UTC) for idempotent daily scraping.
    # Multiple scrapes on the same day will share the same timestamp and trigger
    # the Silver upsert, updating the existing row with the latest price.
    timestamp = raw_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

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
