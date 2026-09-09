# TGJU Fixture Sources

## Reconnaissance Date
**Captured:** 2026-09-08 (۱۴۰۵/۰۶/۱۷) at approximately 16:27 Iran time

## robots.txt Check
**URL:** https://www.tgju.org/robots.txt

**Status:** ✅ Allowed
- General scraping is permitted
- Only specific paths disallowed: `/events/`, `/channel/`, `/shop/`, `/product/`, etc.
- Main price pages are explicitly allowed

## Source URLs

### USD Free Market (دلار آزاد)
**URL:** https://www.tgju.org/profile/price_dollar_rl
**Indicator ID:** `TGJU.USD.FREE`
**Meaning:** USD free-market exchange rate in Iranian Rials
**Fixture:** `usd_normal.html`

### Gold Emami Coin (سکه امامی)
**URL:** https://www.tgju.org/profile/sekee
**Indicator ID:** `TGJU.GOLD.EMAMI`
**Meaning:** Emami gold coin price in Iranian Rials
**Fixture:** `coin_emami_normal.html`

### 18-Karat Gold (طلای ۱۸ عیار)
**URL:** https://www.tgju.org/profile/geram18
**Indicator ID:** `TGJU.GOLD.18K`
**Meaning:** 18-karat gold price per gram in Iranian Rials
**Fixture:** `gold_18k_normal.html`

## HTML Structure Observations

### Price Display Pattern
The current price appears in the main header with this pattern:
```
نرخ فعلی:: 2,255,000 1.53
```
Where:
- `نرخ فعلی::` means "Current Rate:"
- First number is the price (with comma separators)
- Second number is the percentage change

### Table Structure ("در یک نگاه" - At a Glance)
A table showing key statistics:
- `نرخ فعلی` - Current rate
- `بالاترین قیمت روز` - Highest price of the day
- `پایین ترین قیمت روز` - Lowest price of the day
- `نرخ بازگشایی بازار` - Market opening rate
- `زمان ثبت آخرین نرخ` - Time of last rate registration (in Persian: `۱۵:۲۶:۲۴`)
- `نرخ روز گذشته` - Previous day's rate
- `درصد تغییر نسبت به روز گذشته` - Percentage change compared to previous day

### Date and Time Format
- **Date:** `سه شنبه ۱۷ شهریور` (Tuesday 17 Shahrivar)
  - Format: `{weekday} {day} {month}` 
  - Year (1405) is implicit in the Jalali calendar context
- **Time:** `۱۶:۲۷:۲۲` (16:27:22 in Asia/Tehran timezone)
  - Format: `HH:MM:SS` in Persian digits

## Character Encoding

### Persian Digits (U+06F0–U+06F9)
Used throughout: `۰۱۲۳۴۵۶۷۸۹`

### Thousand Separators
- ASCII comma: `,` (common in prices like `2,255,000`)
- Arabic comma: `،` (U+060C) seen in some contexts
- Persian thousands separator: `٬` (U+066C) less common

### Decimal Points
ASCII period `.` is used (e.g., `1.53%`)

## Key Selectors (Hypothesis - To Be Refined in Parser)

Based on visual inspection of the HTML structure:

1. **Current Price:**
   - Look for text containing `نرخ فعلی:` followed by a number
   - Pattern: Find the numeric value after this label
   
2. **Price Table:**
   - Contains rows with Persian labels on the left, values on the right
   - Table format with `─` characters as borders
   
3. **Timestamp:**
   - Look for `زمان ثبت آخرین نرخ` row in the table
   - Extract the time value in Persian digits

## Sample Values Captured

### USD (2026-09-08 15:26:24 IRST)
- Current: `۲,۲۵۵,۰۰۰` (2,255,000 IRR)
- Change: `۱.۵۳%` (1.53%)
- Previous: `۲,۲۲۱,۰۰۰` (2,221,000 IRR)

### Emami Coin (2026-09-08 15:27:13 IRST)
- Current: `۲,۳۴۰,۱۰۰,۰۰۰` (2,340,100,000 IRR)
- Change: `۱.۷۴%` (1.74%)
- Previous: `۲,۳۰۰,۰۵۰,۰۰۰` (2,300,050,000 IRR)

## Notes

- **JavaScript Rendering:** Pages appear to be server-rendered with prices already present in the initial HTML, so Playwright's `wait_for_selector` should target static content rather than dynamic updates.

- **Update Frequency:** Prices update every ~25 seconds based on the auto-refresh timer shown on the page.

- **Unit:** All prices are in Iranian Rials (IRR/ریال).

- **Trading Hours:** Based on timestamps, the market appears active during Tehran business hours.

- **Missing Indicator Scenario:** When an instrument is not available or market is closed, the page structure changes (to be captured separately).

## Validation Method

All fixtures were captured by:
1. Fetching the live URL via browser
2. Saving the complete HTML response
3. Verifying that prices visible in fixtures match the observed values
4. Checking that Persian/Jalali dates are present and correctly formatted

## Coin Premium Calculation (Open Question)

The plan mentions `TGJU.COIN.PREMIUM` as a potential indicator. Based on the Emami coin page, there is a section showing "حباب سکه امامی" (coin bubble/premium). This may be:
- **Scraped directly** if TGJU calculates and displays it
- **Derived** from: `coin_price - (8.133g × gold_18k_price_per_gram)`

**Decision:** To be determined during Task 4 (parser implementation).
