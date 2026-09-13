# Data Dictionary

**Status:** ✅ OBSERVED — recorded from a real end-to-end run on August 19, 2026.

Every number below was read out of the database after
`poetry run python -m src.connectors.world_bank` completed, not copied from a
source catalogue. Where the World Bank advertises coverage that Iran's series
does not actually have, this document records what landed.

## Provenance

| Field | Value |
|-------|-------|
| Source | World Bank Indicators API v2 (World Development Indicators) |
| Endpoint | `https://api.worldbank.org/v2/country/IRN/indicator/<indicator_id>` |
| Country | `IRN` (Islamic Republic of Iran) |
| Frequency | `annual` for all 12 indicators |
| Source `lastupdated` | **2026-07-13** — identical for all 12 indicators |
| Collected | 2026-08-19 |
| Rows fetched | 66 per indicator (1960–2025), 792 total |
| Rows in Silver | 758 (34 null observations skipped, not imputed) |
| Rows in Gold | 1,504 (758 levels + 746 derived growth rates) |

`lastupdated` comes from the API's own `meta` block and is stored on every
Bronze row (`raw_data -> 'meta' ->> 'lastupdated'`, mirrored into
`metadata ->> 'source_last_updated'`), so staleness is auditable without
re-querying the API: if a later run reports the same date, the World Bank has
not refreshed the series.

## Indicators

Coverage is the **observed** span of non-null observations for Iran, taken from
`silver.silver_cleaned`. "Silver" is the number of stored observations;
"Levels"/"YoY" are the level and derived-growth row counts in
`gold.gold_analytical`.

| Indicator ID | Name | Unit | Domain | Coverage | Silver | Levels | YoY |
|--------------|------|------|--------|----------|-------:|-------:|----:|
| `NY.GDP.MKTP.CD` | GDP (current US$) | current US$ | `gdp` | 1960–2025 | 66 | 66 | 65 |
| `NY.GDP.MKTP.KD` | GDP (constant 2015 US$) | constant 2015 US$ | `gdp` | 1960–2025 | 66 | 66 | 65 |
| `NY.GDP.MKTP.KN` | GDP (constant LCU) | constant LCU | `gdp` | 1960–2025 | 66 | 66 | 65 |
| `NY.GDP.MKTP.KD.ZG` | GDP growth (annual %) | annual % | `gdp` | 1961–2025 | 65 | 65 | 64 |
| `NY.GDP.PCAP.KD` | GDP per capita (constant 2015 US$) | constant 2015 US$ | `gdp` | 1960–2025 | 66 | 66 | 65 |
| `FP.CPI.TOTL.ZG` | Inflation, consumer prices (annual %) | annual % | `inflation` | 1960–2025 | 66 | 66 | 65 |
| `NE.EXP.GNFS.CD` | Exports of goods and services (current US$) | current US$ | `trade` | 1960–2025 | 66 | 66 | 65 |
| `NE.IMP.GNFS.CD` | Imports of goods and services (current US$) | current US$ | `trade` | 1960–2025 | 66 | 66 | 65 |
| `NE.RSB.GNFS.CD` | External balance on goods and services (current US$) | current US$ | `trade` | 1960–2025 | 66 | 66 | 65 |
| `SP.POP.TOTL` | Population, total | — | `welfare` | 1960–2025 | 66 | 66 | 65 |
| `SP.POP.GROW` | Population growth (annual %) | annual % | `welfare` | 1961–2025 | 65 | 65 | 64 |
| `EG.USE.PCAP.KG.OE` | Energy use (kg of oil equivalent per capita) | kg of oil equivalent per capita | `energy` | 1990–2023 | 34 | 34 | 33 |

Names and units are the catalogue values written by `discover()`, which reads
them from `https://api.worldbank.org/v2/indicator/<indicator_id>`. The API
returns `unit: ""` for every WDI indicator, so the unit is derived from the
parenthetical in the indicator name. `SP.POP.TOTL` ("Population, total") has no
parenthetical and therefore **no unit** — stored as `NULL` rather than an
invented "people", in both Silver and Gold.

### Gaps and base years

| Indicator ID | Known gaps | Base-year note | Source URL |
|--------------|------------|----------------|------------|
| `NY.GDP.MKTP.CD` | None | Current prices — no base year | `https://api.worldbank.org/v2/country/IRN/indicator/NY.GDP.MKTP.CD` |
| `NY.GDP.MKTP.KD` | None | Constant **2015** US$, pre-rebased by the World Bank — one base throughout | `https://api.worldbank.org/v2/country/IRN/indicator/NY.GDP.MKTP.KD` |
| `NY.GDP.MKTP.KN` | None | Constant local currency, pre-rebased — one base throughout | `https://api.worldbank.org/v2/country/IRN/indicator/NY.GDP.MKTP.KN` |
| `NY.GDP.MKTP.KD.ZG` | 1960 (no prior year to difference against) | Derived from the constant-price series; no base year of its own | `https://api.worldbank.org/v2/country/IRN/indicator/NY.GDP.MKTP.KD.ZG` |
| `NY.GDP.PCAP.KD` | None | Constant **2015** US$, pre-rebased | `https://api.worldbank.org/v2/country/IRN/indicator/NY.GDP.PCAP.KD` |
| `FP.CPI.TOTL.ZG` | None | A rate of change, not an index — carries no base year even though the underlying CPI does | `https://api.worldbank.org/v2/country/IRN/indicator/FP.CPI.TOTL.ZG` |
| `NE.EXP.GNFS.CD` | None | Current prices — no base year | `https://api.worldbank.org/v2/country/IRN/indicator/NE.EXP.GNFS.CD` |
| `NE.IMP.GNFS.CD` | None | Current prices — no base year | `https://api.worldbank.org/v2/country/IRN/indicator/NE.IMP.GNFS.CD` |
| `NE.RSB.GNFS.CD` | None | Current prices — no base year; legitimately negative in deficit years | `https://api.worldbank.org/v2/country/IRN/indicator/NE.RSB.GNFS.CD` |
| `SP.POP.TOTL` | None | Not an index | `https://api.worldbank.org/v2/country/IRN/indicator/SP.POP.TOTL` |
| `SP.POP.GROW` | 1961 is the first year (1960 has no prior year) | Not an index | `https://api.worldbank.org/v2/country/IRN/indicator/SP.POP.GROW` |
| `EG.USE.PCAP.KG.OE` | **Discontinued.** The API returns 66 rows but only 1990–2023 carry values; 1960–1989 and 2024–2025 are null | Not an index | `https://api.worldbank.org/v2/country/IRN/indicator/EG.USE.PCAP.KG.OE` |

**No indicator has an interior gap.** Every missing observation is at the start
or the end of the series, verified by generating the full year range per
indicator and looking for absent years — the result was empty for all 12. A
future run that introduces a hole will show up in the same query (see
[Reproducing these numbers](#reproducing-these-numbers)).

`EG.USE.PCAP.KG.OE` is kept deliberately, as a documented sparse series rather
than a silent omission: it is the only Iranian energy series the WDI carries,
and 34 years of it is still usable. Consumers should not assume it extends to
the present.

## Bronze: the `raw_data` wrapping convention

`bronze.bronze_raw.raw_data` is typed as a JSON **object**, but the World Bank
API answers with a two-element **array** — `[meta, rows]`. Storing the array
would need a schema change, and flattening it would throw away the pagination
and freshness metadata. The connector therefore wraps it:

```json
{
  "meta": {"page": 1, "pages": 1, "per_page": 20000, "total": 66,
           "sourceid": "2", "lastupdated": "2026-07-13"},
  "rows": [ { "date": "2025", "value": 4.6e+11, "...": "..." } ]
}
```

The convention is self-describing: every Bronze row records
`metadata ->> 'envelope_convention' = 'raw_data = {meta, rows}'` so a reader
does not have to infer it. `rows` is the API's payload **verbatim**, in the
order the API sent it (newest first) — Bronze is immutable and append-only, so
re-running the pipeline adds a new envelope rather than replacing one. For a
paginated fetch, `rows` is the concatenation of all pages and `meta` is the last
page's meta block; `metadata ->> 'pages_fetched'` records how many requests it
took.

Alongside the envelope, each Bronze row carries collection provenance in its
`metadata` column:

| Key | Meaning |
|-----|---------|
| `indicator_id` | Which indicator this envelope is for |
| `country` | Country code requested (`IRN`) |
| `rows_returned` | Observations the API sent |
| `rows_usable` | Observations that parsed into the frame (future periods dropped) |
| `pages_fetched` | HTTP requests made for this indicator |
| `total_reported` | The API's own `meta.total` |
| `source_last_updated` | The API's own `meta.lastupdated` |
| `envelope_convention` | The literal string `raw_data = {meta, rows}` |

## Silver: cleaned observations

- **Timestamps are period-end and timezone-aware.** An annual observation for
  2025 is stored as `2025-12-31 00:00:00+00`. Period-end keeps annual, monthly
  and daily sources sortable against each other.
- **Nulls are skipped, never imputed.** `silver_cleaned.value` is `NOT NULL`, so
  a null observation produces no row; the count is recorded as
  `records_failed` on the `metadata.transformation_log` row for that hop. The
  2026-08-19 run skipped 34 observations across 3 indicators, which is why those
  three hops are logged as `partial` rather than `success`.
- **Outliers are flagged, not dropped.** `is_outlier` was set on 7 observations
  (`NE.RSB.GNFS.CD` 4, `NY.GDP.MKTP.KD.ZG` 2, `FP.CPI.TOTL.ZG` 1) and all 7 are
  still present with their values intact. Iranian macro series legitimately
  contain extreme values — hyperinflation, sanctions shocks, war years — so
  removing them would be removing the signal.
- **`unit` comes from the catalogue**, not from a per-row guess, so every
  observation of an indicator carries the same unit its catalogue row does.
- **Re-runs upsert on `(indicator_id, timestamp)`** (constraint
  `uq_silver_indicator_timestamp`): a second collection of the same period
  updates the existing row in place and re-points `bronze_id` at the newest
  envelope. Row ids are stable across runs, so Gold's foreign keys survive.
- **`metadata` carries `obs_status`** when the API supplies one. The WDI sends
  `obs_status: ""` for every Iranian observation, so it is null throughout the
  current data.

## Gold: analytical layer

- **Derived indicators are namespaced `WB.<indicator_id>.YOY`** — for example
  `WB.NY.GDP.MKTP.KD.YOY` is the year-over-year growth of
  `NY.GDP.MKTP.KD`. The `WB.` prefix guarantees a derived id can never collide
  with a World Bank source id, and the suffix says what the derivation is. Every
  derived series has exactly one row fewer than its parent: the first period has
  no prior period to difference against.
- **Derived growth is always `annual %`**, whatever the parent's unit. Growth of
  a series that is *already* a rate (`WB.FP.CPI.TOTL.ZG.YOY`,
  `WB.SP.POP.GROW.YOY`, `WB.NY.GDP.MKTP.KD.ZG.YOY`) is the change in that rate
  and is rarely what an analyst wants — prefer the parent series.
- **`original_value` always holds the pre-linking value** and is never null,
  even when nothing was linked (in which case it equals `value`). Comparing the
  two columns is the audit trail for any transformation Gold applied.
- **Each derived row attributes itself to the later period's Silver row** via
  `silver_id`, with the derivation recorded in `metadata`. There is no single
  natural parent for a growth rate; this makes the FK non-null and the choice
  explicit rather than arbitrary.
- **Re-runs delete and reinsert per indicator.** `gold.gold_analytical` is a
  TimescaleDB hypertable whose primary key is `(id, timestamp)`, which rules out
  an upsert on `(indicator_id, timestamp)`. Row counts are stable across runs
  but row **ids change** — do not persist a Gold `id` as a long-lived reference.
- **Storage.** Annual period-end timestamps and a one-month chunk interval mean
  one chunk per year: 66 chunks for 1960–2025.

## Chain-linking confidence

`is_chain_linked`, `chain_linking_confidence` and the
`metadata.chain_linking_log` table describe base-year splicing. **In the
2026-08-19 run nothing was chain-linked**: `is_chain_linked` is `false` on all
1,504 Gold rows, `chain_linking_confidence` is `NULL` throughout, and
`chain_linking_log` is empty. This is correct, not a failure — the World Bank
publishes its constant-price series already rebased to a single base year
(2015 US$ / constant LCU), so there is no internal discontinuity to remove. The
machinery is exercised on synthetic series in
`tests/unit/chain_linking/test_splice.py`; real multi-base series arrive with
CBI/SCI in Phase 5.

When a link *is* performed, confidence is a score in `[0, 1]` — not a
probability. It answers "how much evidence backs the scale factor?" and is the
product of two factors:

| Factor | Behaviour |
|--------|-----------|
| Overlap | Rises linearly from a floor of **0.2** at zero overlap to **1.0** at 36 months (3 annual periods) of shared history |
| Growth agreement | `1 / (1 + 50 × variance)` of the per-period ratio estimates — falls as the two segments disagree about growth |

Reading the result:

| Value | Interpretation |
|-------|----------------|
| `NULL` | No link was attempted or needed. `value = original_value`. |
| ~0.2 | A `level_shift` link: the scale factor came from a single junction observation with no overlap to measure against. Directionally right, quantitatively an assumption. |
| 0.5–0.8 | An `overlap` link with either short overlap or noticeable growth disagreement. Usable; state it when publishing. |
| > 0.8 | Long overlap, consistent growth. The scale factor is well identified. |

Two guarantees hold regardless of the score: within-segment growth rates are
preserved to within **±1%** or `ChainLinkingError` is raised instead of emitting
a distorted series, and an `overlap` link needs at least 3 annual (6 quarterly,
12 monthly) shared periods or it refuses to link at all. `linking_method` on the
`chain_linking_log` row records which of the two methods produced the factor.

## Reproducing these numbers

```bash
poetry run python -m src.connectors.world_bank
```

Then, against the same database:

```sql
-- Observed coverage per indicator
SELECT indicator_id, count(*), min(timestamp)::date, max(timestamp)::date
FROM silver.silver_cleaned GROUP BY 1 ORDER BY 1;

-- Levels vs derived rows, and whether anything was linked
SELECT indicator_id, count(*), bool_or(is_chain_linked)
FROM gold.gold_analytical GROUP BY 1 ORDER BY 1;

-- Interior gaps: expect zero rows in the "missing" array for every indicator
WITH bounds AS (
    SELECT indicator_id,
           extract(year FROM min(timestamp))::int AS lo,
           extract(year FROM max(timestamp))::int AS hi
    FROM silver.silver_cleaned GROUP BY 1
)
SELECT b.indicator_id, array_agg(y ORDER BY y) FILTER (
           WHERE NOT EXISTS (SELECT 1 FROM silver.silver_cleaned s
                             WHERE s.indicator_id = b.indicator_id
                               AND extract(year FROM s.timestamp)::int = y)) AS missing
FROM bounds b, generate_series(b.lo, b.hi) AS y
GROUP BY 1 ORDER BY 1;

-- Source freshness
SELECT DISTINCT raw_data -> 'meta' ->> 'lastupdated' FROM bronze.bronze_raw;

-- Skipped observations and per-hop status
SELECT source_layer, target_layer, status, count(*), sum(records_failed)
FROM metadata.transformation_log GROUP BY 1, 2, 3 ORDER BY 1, 2;
```


---

# TGJU Indicators (Phase 3)

**Status:** ✅ IMPLEMENTED — scraper + parser + integration tests complete (September 2026).

TGJU (tgju.org) provides **daily market prices** for foreign exchange, gold, and
coins. Unlike the World Bank API, TGJU does **not provide historical data** — it
shows the **current price only**. Time series are built by scraping daily and
accumulating observations over time.

## Provenance

| Field | Value |
|-------|-------|
| Source | TGJU.org (Iran's leading FX/gold market tracker) |
| Method | Web scraping (Playwright + headless browser) |
| Update frequency | Daily (market business days) |
| Language | Persian (Farsi) — prices use Persian digits |
| Coverage | Current price only (1 observation per scrape) |
| Historical data | Not available from source — built by daily runs |

## Indicators

**Phase 3 Implementation** covers 3 representative indicators for integration tests:

| Indicator ID | Name | Unit | Domain | Type |
|--------------|------|------|--------|------|
| `price_dollar_rl` | US Dollar (Free Market) | IRR | `fx` | Currency |
| `geram18` | 18-Karat Gold | IRR/gram | `gold` | Commodity |
| `sekee` | Emami Gold Coin | IRR/coin | `gold` | Coin |

**Full implementation** (Airflow orchestration, Phase 3 completion) will add:
- Additional FX pairs (EUR, GBP, AED, TRY, CNY)
- Gold varieties (24K, 17K)
- Other coins (Azadi, Gerami, Half-Bahar)

## Scraper Architecture

### Single-Observation Reality

TGJU pages show **one price** — the current market value. Each scrape produces:
- 1 Bronze envelope (HTML + metadata)
- 1 Silver observation (parsed price + timestamp)
- 1 Gold level (published, no derived metrics from single observation)

**Historical series** are built by running the scraper daily and accumulating
observations. A 30-day moving average requires 30 daily runs, not one scrape.

### Bronze Structure

Unlike the World Bank API, TGJU scrapers store **HTML** in Bronze:

```json
{
  "rows": [
    {
      "html": "<html>...</html>",
      "url": "https://www.tgju.org/profile/price_dollar_rl",
      "scraped_at": "2026-09-08T19:44:29.137+03:30"
    }
  ]
}
```

The `rows` wrapper follows the Bronze convention: `extract_rows()` expects a
list, even when the scraper produces one observation. The `metadata` column
carries:

| Key | Meaning |
|-----|---------|
| `indicator_id` | TGJU instrument identifier |
| `scraped_at` | Collection timestamp (Tehran time) |
| `user_agent` | Browser user-agent (rotated for politeness) |
| `envelope_convention` | `raw_data = {rows: [{html, url, scraped_at}]}` |

### Parser: Persian Number Handling

TGJU displays prices in **Persian (Farsi) digits** (`۰۱۲۳۴۵۶۷۸۹` instead of
`0123456789`). The parser (`src/connectors/tgju_parser.py`) converts them to
Arabic numerals before parsing:

```python
PERSIAN_TO_ARABIC = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
cleaned = text.translate(PERSIAN_TO_ARABIC).replace(",", "")
```

Prices are extracted from structured `<div>` or `<span>` elements with
`data-col="info.last_update.price"` or similar attributes. The parser is
tested with 45 unit tests covering:
- Normal prices (millions with commas)
- Persian digit conversion
- Missing/malformed elements
- Timestamp extraction (Persian date → Gregorian)

### Silver: Daily Observations

- **Timestamps are scraped-time, not period-end.** A daily scrape at 11 PM
  Tehran time is stored as that instant, not end-of-day. This preserves the
  intraday sequencing for high-frequency sources.
- **Units come from the parser.** TGJU does not provide a metadata API, so units
  are inferred from the page structure (e.g., "IRR" for FX, "IRR/gram" for
  gold).
- **Re-runs upsert on `(indicator_id, timestamp)`** — if the same indicator is
  scraped twice on the same day (e.g., morning + evening), the later observation
  replaces the earlier one.

### Gold: Levels Only (Initially)

When only **one observation** exists for an indicator, Gold publishes the level
but **does not derive** growth metrics (RET1D, MA7, MA30) — there is no prior
day to difference against. Derived metrics appear after multiple daily runs
accumulate history:

| Metric | Requires | Status (Phase 3) |
|--------|----------|------------------|
| Level | 1 observation | ✅ Published |
| RET1D (daily return) | 2+ observations | ⏳ After daily runs |
| MA7 (7-day MA) | 7+ observations | ⏳ After weekly runs |
| MA30 (30-day MA) | 30+ observations | ⏳ After monthly runs |

The derivation strategy (`daily` for TGJU) is recorded in
`metadata.transformation_log`. Once sufficient history exists, re-runs will
publish derived series.

## Testing

**Integration tests** (`tests/integration/test_tgju_pipeline.py`, 16 tests):
- Use **fixture HTML** (no live scraping) for reproducibility
- Mock Playwright browser with synchronous `FakePage`/`FakeBrowser`
- Verify Bronze→Silver→Gold roundtrip with FK integrity
- Verify hypertable storage and audit trails
- Include `@pytest.mark.live` test for real scraping (skipped by default)

**Unit tests** (84 tests across parser + scraper):
- Parser: 45 tests with fixture HTML (Persian digits, missing elements, dates)
- Scraper: 39 tests with mocked Playwright (retries, discovery, validation)

## Orchestration (Pending)

Phase 3 **Airflow DAGs** (not yet implemented):
- **Daily scrape:** Run at 11 PM Tehran time (market close)
- **Retry logic:** 3 attempts with exponential backoff
- **Alerting:** Slack/email on consecutive failures
- **Rate limiting:** 1-2 requests/second, respect robots.txt

## Known Limitations

1. **No historical data:** TGJU does not provide archives — first run creates
   only current prices. Wait 30 days to calculate 30-day MA.
2. **Market hours:** TGJU reflects Tehran market hours (Sat–Wed, 9 AM–6 PM Iran
   time). Prices outside market hours may be stale.
3. **Website fragility:** TGJU may change HTML structure without notice. Parser
   must be maintained when selectors break.
4. **Sanctions impact:** International payment disruptions can create temporary
   gaps in data availability.

## Reproducing TGJU Tests

```bash
# Start database
make db-up

# Run integration tests (fixture-based, no network)
poetry run pytest tests/integration/test_tgju_pipeline.py -v

# Run live scraper test (hits real TGJU website)
RUN_LIVE_API_TESTS=1 poetry run pytest tests/integration/test_tgju_pipeline.py::test_live_tgju_scrape_returns_daily_prices -v

# Check what landed in the database
docker compose exec postgres psql -U iran_macro -d iran_macro_db_test -c "
  SELECT indicator_id, count(*) FROM silver.silver_cleaned
  WHERE indicator_id LIKE '%dollar%' OR indicator_id LIKE '%gold%'
  GROUP BY 1 ORDER BY 1;
"
```

---

# IMF Indicators (Phase 4)

**Status:** ✅ OBSERVED — recorded from a real end-to-end run on September 12,
2026.

Every number below was read out of the database after
`poetry run python -m src.connectors.imf` completed. The IMF DataMapper returns
one vintage of the World Economic Outlook; the **April 2026** vintage was
fetched, so each series contains one estimate year and five projection years.

## Provenance

| Field | Value |
|-------|-------|
| Source | IMF DataMapper API v1 (World Economic Outlook) |
| Endpoint | `https://www.imf.org/external/datamapper/api/v1/<INDICATOR>` |
| Country | `IRN`, selected client-side (the API ignores the country path) |
| Frequency | `annual` for all 6 indicators |
| Vintage | **April 2026** — `metadata ->> 'vintage'` = `2026` on Bronze |
| Collected | 2026-09-12 |
| Rows fetched | 52 per indicator (1980–2031); 42 for `LUR` (1990–2031); 302 total |
| Rows in Silver | 302 (no null observations for Iran in this vintage) |
| Rows in Gold | 404 (302 levels + 102 derived growth rates) |

## Indicators

Coverage is the **observed** span of observations for Iran in
`silver.silver_cleaned`; because forecasts are stored, it extends past today.

| Indicator ID | Name | Unit | Domain | Coverage | Silver | Levels | YoY |
|--------------|------|------|--------|----------|-------:|-------:|----:|
| `NGDP_RPCH` | Real GDP growth | Annual percent change | `gdp` | 1980–2031 | 52 | 52 | — |
| `PCPIPCH` | Inflation, average consumer prices | Annual percent change | `inflation` | 1980–2031 | 52 | 52 | — |
| `NGDPD` | GDP, current prices | Billions of U.S. dollars | `gdp` | 1980–2031 | 52 | 52 | 51 |
| `NGDPDPC` | GDP per capita, current prices | U.S. dollars per capita | `gdp` | 1980–2031 | 52 | 52 | 51 |
| `LUR` | Unemployment rate | Percent | `welfare` | 1990–2031 | 42 | 42 | — |
| `BCA_NGDPD` | Current account balance, % of GDP | Percent of GDP | `trade` | 1980–2031 | 52 | 52 | — |

Units and labels come from the `/indicators` metadata endpoint and are written
by `discover()`; the analytical domain is the committed registry (the API does
not publish one). Rate indicators (`NGDP_RPCH`, `PCPIPCH`, `LUR`, `BCA_NGDPD`)
deliberately get **no** derived series — a percent change of a percent is not a
meaningful metric. Only the level series (`NGDPD`, `NGDPDPC`) get `.YOY`.

## Forecast convention (project-defined, not IMF-provided)

The API does not label which years are projections. This project derives the
label by parsing the WEO vintage year from the indicator's `source` string and
comparing it to each period year:

| Period year | `observation_type` | Observed count (52-row series) |
|-------------|--------------------|-------------------------------:|
| before the vintage | `actual` | 46 |
| the vintage year | `estimate` | 1 |
| after the vintage | `forecast` | 5 |

For `LUR` (42 rows) the split is 36 / 1 / 5. The label is stored in
`silver.silver_cleaned.metadata ->> 'observation_type'` and in the Silver
transformation counters (`forecast_records`). Forecast rows are future-dated by
design and are **retained**, not dropped: the pipeline marks the source
`supports_forecasts=True`, which flips Silver's future-period check from reject
to count.

**This is an explicit project convention.** It is not an IMF semantic, and it
should be revisited if the DataMapper ever exposes a projection flag.

## Bronze: the `{rows, meta, raw_response}` convention

The connector stores one envelope per indicator:

```json
{
  "rows": [{"period": "2031", "value": 123.4, "observation_type": "forecast"}, "..."],
  "meta": {"indicator_id": "NGDPD", "country": "IRN", "vintage": 2026,
           "source": "World Economic Outlook (April 2026)",
           "unit": "Billions of U.S. dollars", "rows_returned": 52,
           "forecast_through": 2031},
  "raw_response": {"values": {"NGDPD": {"IRN": {"1980": 1.2, "...": "..."}}}, "api": {}}
}
```

`raw_response` is the untouched multi-country payload (the API has no
server-side filtering), so `rows` is the IRN slice while the full response stays
auditable. `metadata ->> 'rows_usable'` equals the number of parsed
observations; `metadata ->> 'envelope_convention'` records the shape.

### API quirks absorbed

| Quirk | Behaviour |
|-------|-----------|
| Country path ignored | `/NGDPD/IRN` returns the same 229-country payload; Iran is selected client-side |
| `periods` parameter ignored | The full series is always returned |
| Invalid code | HTTP **200** with only an `api` key — a missing `values[code]` is treated as a retrieval error, not an empty series |
| Empty-string values key | `values[""] = null`; skipped by the parser |
| Values are numbers | Keyed by four-digit **string** years |

## Silver and Gold

- **Timestamps** are annual period-end (`YYYY-12-31 00:00:00+00`).
- **Forecasts are retained** and tagged (see above); no null observations were
  skipped in this vintage.
- **Derived ids are namespaced** `IMF.<indicator_id>.YOY` (e.g.
  `IMF.NGDPD.YOY`). The derived unit is always `annual %`.
- **YoY is prior-year aligned**, so 51 rates are published for a 52-year series
  (1980 has no prior year to compare against).
- **No chain-linking**: `is_chain_linked` is `false` on all 404 Gold rows and
  `metadata.chain_linking_log` is empty — WEO series carry a single vintage and
  no rebasing.

## Known limitations

1. **One vintage, five-year horizon.** The stored series is April 2026 WEO; a
   later vintage restates history and extends the horizon, and a re-run will
   upsert Silver on `(indicator_id, timestamp)`.
2. **No projection flag from the source.** The actual/estimate/forecast label is
   the project convention above.
3. **`discover()` cannot report coverage.** `availability_start` /
   `availability_end` are filled by the pipeline from what it stored.
4. **Catalog label whitespace.** The API returns `"GDP per capita, current
   prices\n"` for `NGDPDPC`, so the catalog name carries a trailing newline
   (cosmetic; see Phase 4 technical debt).

## Reproducing these numbers

```bash
poetry run python -m src.connectors.imf            # full run
poetry run python -m src.connectors.imf --dry-run  # fetch + report, no writes
```

```sql
SELECT indicator_id, count(*), min(timestamp)::date, max(timestamp)::date
FROM silver.silver_cleaned WHERE source_name = 'imf' GROUP BY 1 ORDER BY 1;

SELECT metadata ->> 'observation_type' AS kind, count(*)
FROM silver.silver_cleaned WHERE source_name = 'imf' GROUP BY 1 ORDER BY 1;

SELECT indicator_id, count(*) FROM gold.gold_analytical
WHERE indicator_id IN (SELECT indicator_id FROM metadata.indicator_catalog
                       WHERE source_name = 'imf') OR indicator_id LIKE 'IMF.%.YOY'
GROUP BY 1 ORDER BY 1;
```

---

# EIA Indicators (Phase 4)

**Status:** ⚠️ PARTIAL — fixture-verified end to end; **no live run yet** because
no real `EIA_API_KEY` is configured in this environment. The payload schema,
auth contract, facets, paging, sorting, and date bounds were verified live on
September 12, 2026 (see `docs/phase-4/VALIDATION.md`).

## Provenance

| Field | Value |
|-------|-------|
| Source | EIA Open Data API v2, international dataset |
| Endpoint | `https://api.eia.gov/v2/international/data/` |
| Auth | `api_key` required; missing → HTTP 403 `API_KEY_MISSING`, invalid → 403 `API_KEY_INVALID` |
| Country facet | `facets[countryRegionId][]=IRN` |
| Frequency | `monthly` for both indicators |
| Default window | `start=2024-01`, no `end` (unbounded fetches reach back to 1993) |
| Fixture window | 2024-01 … 2026-05 (29 months) |

## Indicators

| Indicator ID | Name | Facets | Unit | Domain |
|--------------|------|--------|------|--------|
| `EIA.IRN.CRUDE_PRODUCTION` | Crude oil, NGPL, and other liquids production | `productId=55`, `activityId=1` | thousand barrels per day | `energy` |
| `EIA.IRN.TOTAL_LIQUIDS` | Total petroleum and other liquids production | `productId=53`, `activityId=1` | thousand barrels per day | `energy` |

Coverage from the captured fixtures is **2024-01 … 2026-05 (29 months)** per
indicator; each yields 29 Gold levels and, because YoY is prior-year aligned,
**17** derived `.YOY` rows (2025-01 … 2026-05). Live coverage for Iran is
expected to track the same window and is unverified until a key is supplied.

## Bronze: the `{rows, meta, raw_response}` convention

Paged responses are stored losslessly: `rows` is the concatenation of every
`response.data` page, `raw_response` is the **list** of raw page payloads (one
entry per request), and `meta` records `pages_fetched`, `total_reported`,
`product_id`, `activity_id`, `start`, `end`, and `country`. The API key is
**never** stored: `request_url` is rebuilt without it, and the connector scrubs
it from retry/error text.

## Silver and Gold

- **Timestamps** are month-end (`YYYY-MM-<last day> 00:00:00+00`).
- **`value` and `response.total` are strings**; blank/null values become null
  observations (skipped and counted), non-numeric strings raise `ParsingError`.
- **`dataFlagDescription`** (falling back to `dataFlagId`) is stored as
  `metadata ->> 'obs_status'`.
- **Derived ids are namespaced** `EIA.<indicator_id>.YOY`, unit `annual %`, and
  a genuine **prior-year month** comparison (e.g. 2025-05 vs 2024-05), not a
  lag-1 month difference.
- **No chain-linking**: production is a level series with no base year.

## Known limitations

1. **Live ingestion unverified.** A real `EIA_API_KEY` is required; the public
   `DEMO_KEY` is rate-limited (HTTP 429). All coverage above is fixture-based.
2. **Unknown facets are empty, not errors.** The API answers HTTP 200 with
   `total: "0"`; the connector treats that as an empty series.
3. **Credentials are mandatory.** An unconfigured key aborts the run once,
   before any layer is written, with an actionable `PlatformConnectionError`.

## Reproducing these numbers

```bash
# Requires a real key in EIA_API_KEY
poetry run python -m src.connectors.eia --dry-run
poetry run python -m src.connectors.eia
```

```sql
SELECT indicator_id, count(*), min(timestamp)::date, max(timestamp)::date
FROM silver.silver_cleaned WHERE source_name = 'eia' GROUP BY 1 ORDER BY 1;
```

---

# OPEC Basket (Phase 4 — DEFERRED)

**Status:** ❌ NOT INGESTED — the source blocks programmatic access.

The OPEC Reference Basket was evaluated and the decision gate **failed**:
`.xlsx`/`.csv` downloads return a Cloudflare challenge page (HTML, not a
workbook), direct JSON endpoints return **HTTP 403**, and even
`https://www.opec.org/robots.txt` is blocked. A browser session can reach
`/basket/basketDay.json` (daily values since 2003), but only by bypassing the
403 bot block, which this project will not do.

Consequently there is **no OPEC connector, parser, fixture, DAG, or
configuration**, and no OPEC indicator appears in the catalog. Full evidence
and the decision record are in
[docs/phase-4/VALIDATION.md](../phase-4/VALIDATION.md).

---

# SCI Indicators (Phase 5)

**Status:** ✅ OBSERVED — recorded from a live run on September 13, 2026.

Every number below was read out of the database after
`poetry run python -m src.connectors.sci_scraper` completed (6/6 publications),
not copied from an SCI catalogue. Where SCI advertises a series the connector
does not register, this document says so.

## Provenance

| Field | Value |
|-------|-------|
| Source | Statistical Center of Iran (SCI), `https://www.amar.org.ir` |
| Type | File scraper (Excel `.xlsx` + legacy `.xls`; PDF/HTML inspected, not registered) |
| Index page | `https://www.amar.org.ir/prices` |
| Collected | 2026-09-13 |
| Bronze rows | 6 (one per downloaded file) |
| Rows in Silver | 2,649 |
| Rows in Gold | 4,639 (2,398 levels + 2,241 derived YoY) |
| TLS note | `www.amar.org.ir` serves an incomplete chain; the missing `Certum DV TLS G2 R39 CA` intermediate is pinned in `src/connectors/certs/` — verification is never disabled |

## Indicators

Canonical (linked) series are **active** in the catalog; the `B<year>`
base-year segments live in Silver and are seeded **inactive**. Coverage is the
**observed** span of Gold level rows; "Silver" counts `silver.silver_cleaned`,
"Levels"/"YoY" count `gold.gold_analytical` level and `.YOY` rows.

| Indicator ID | Name | Unit | Domain | Frequency | Coverage (Gold) | Silver | Levels | YoY |
|--------------|------|------|--------|-----------|-----------------|-------:|-------:|----:|
| `SCI.CPI.URBAN` | CPI, urban households (chain-linked) | index | `inflation` | monthly | 1982-03-31 … 2026-07-31 | 784 (2 segments) | 533 | 521 |
| `SCI.CPI.NATIONAL` | CPI, national (all households) | index | `inflation` | monthly | 2011-03-31 … 2026-07-31 | 185 | 185 | 173 |
| `SCI.CPI.RURAL` | CPI, rural households | index | `inflation` | monthly | 1982-05-31 … 2026-07-31 | 429 | 429 | 417 |
| `SCI.CPI.DECILE.B2021.D1…D10` | CPI by household expenditure decile (10 series) | index | `inflation` | monthly | 2016-03-31 … 2026-07-31 | 125 each | 125 each | 113 each |
| `SCI.UNEMPLOYMENT.QUARTERLY` | Unemployment rate (labour-force survey) | percent | `labor` | quarterly | 2026-05-31 (spring 1405) | 1 | 1 | 0 |

The canonical urban series has no Silver rows of its own: its 784 Silver
observations are the two published base-year segments below, which overlap by
251 months.

### Published base-year segments (inactive)

| Segment ID | Base (Jalali = Gregorian) | Silver | Coverage |
|------------|---------------------------|-------:|----------|
| `SCI.CPI.URBAN.B2016` | 1395 = 2016 | 491 | 1982-03-31 … 2023-01-31 |
| `SCI.CPI.URBAN.B2021` | 1400 = 2021 | 293 | 2002-03-31 … 2026-07-31 |
| `SCI.CPI.NATIONAL.B2021` | 1400 = 2021 | 185 | 2011-03-31 … 2026-07-31 |
| `SCI.CPI.RURAL.B2021` | 1400 = 2021 | 429 | 1982-05-31 … 2026-07-31 |

## Chain-linking and base years

SCI publishes only **two** CPI bases (1395 = 2016 and 1400 = 2021); no 1390
publication exists. The 1395 urban workbook's tidy `جدول 3` sheet reaches back to
**1361-01 (1982-03-31)** — earlier than the wide `جدول 1` sheet (which starts at
1381) — so the 1395→1400 splice rescales real history rather than nothing.

Catalog `base_years` for the canonicals: `SCI.CPI.URBAN` = `[2016, 2021]`,
`SCI.CPI.NATIONAL` = `[2021]`, `SCI.CPI.RURAL` = `[2021]`; `has_base_year_changes`
is true only for the urban series, which is the only one with two segments.

Observed `metadata.chain_linking_log` row:

| indicator_id | method | records_linked | overlap_months | avg_confidence | status |
|--------------|--------|---------------:|---------------:|---------------:|--------|
| `SCI.CPI.URBAN` | `overlap` | 240 | 251 | 0.9985 | `success` |

The 240 rescaled rows are the observations **before** the 1400 base begins
(`is_chain_linked = true` in Gold); everything from the 1400 base onward keeps
its original value (`is_chain_linked = false`). National and rural publish a
single base and are passthroughs — no chain-linking row is written for them.

## Bronze: the `{rows, meta}` file convention

The **file** is the unit of Bronze: six downloads produce six rows, each with no
more than the raw workbook. `rows` holds the parsed observations (JSON-safe) and
`meta` carries the provenance plus the raw bytes:

```json
{
  "rows": [ {"timestamp": "2026-07-31T00:00:00+00:00", "value": 1234.5,
             "indicator_id": "SCI.CPI.URBAN.B2021", "unit": "index",
             "record_metadata": {"base_year": 1400, "period_label": "1405/05"}} ],
  "meta": {"filename": "ts_urban….xlsx", "content_type": "…sheet",
           "byte_length": 1248356, "sha256": "b28e3375…", "url": "https://…",
           "downloaded_at": "…", "indicator_id": "SCI.CPI.URBAN.B2021",
           "base_year": 1400, "base_year_gregorian": 2021,
           "parser": "cpi_excel", "raw_file_base64": "<base64>"}
}
```

`meta.raw_file_base64` is the raw workbook, kept under the configured size guard
(`scraper_max_download_bytes`) so a re-parse never needs a re-scrape. The decile
publication is one Bronze row carrying ten series; the runner scopes Silver's
per-series parse to that series' rows so the sibling series are not logged as
skipped.

## Silver and Gold

- **Timestamps** are month-end (monthly) or quarter-end (quarterly), stored UTC.
  SCI's Jalali `YYYY/MM` labels are converted to Gregorian; the original period
  label and base year are kept in `record_metadata`.
- **Persian digits** are normalised before parsing; thousands separators are
  stripped (`src/utils/persian.py`).
- **Units** are `index` for every CPI series and `percent` for unemployment.
- **Derived ids** are namespaced `SCI.<indicator_id>.YOY` with unit `annual %`.
- **Idempotent re-runs:** Silver upserts on `(indicator_id, timestamp)`; Gold
  deletes and reinserts per indicator. A second run leaves Silver ids unchanged
  and refreshes Gold ids.

## Known limitations and findings

1. **Base-year discontinuity is handled for the urban series only.** National and
   rural publish just the 1400 base, so their canonical series is a passthrough
   (single base, no splice).
2. **`ChainLinkingLog.base_year_from`/`base_year_to` are not the nominal bases.**
   The observed row stores `2023` and `2002` — the last year of the older
   segment and the first year of the newer one, i.e. the splice's overlap
   boundary — rather than the 2016→2021 bases. The catalog's `base_years` and the
   segment ids (`B2016`/`B2021`) carry the nominal bases correctly. **Flagged as
   a pre-existing chain-linking defect** (`src/chain_linking/splice.py`), not
   fixed in Phase 5's documentation task.
3. **Inactive segment metadata is over-broad.** `SCI.CPI.NATIONAL.B2021` and
   `SCI.CPI.RURAL.B2021` carry `base_years = [2016, 2021]` copied from the
   publication registry even though only 1400 = 2021 is published for them. The
   canonical rows are correct.
4. **Unemployment is a single observation.** SCI publishes the spring 1405 rate
   (9.1%) only; there is no history in the registered publication, so the Gold
   series is one point and derives no YoY. A time series accumulates from
   periodic runs.
5. **PDF and cross-tab publications are not registered.** The monthly CPI report
   PDF and the labour-force PDF expose no extractable tables, and the annual
   unemployment cross-tab has no clean rate row, so they contribute no
   indicators.
6. **CBI is gated.** No CBI indicator exists in the catalog (see below).

## Reproducing these numbers

```bash
poetry run python -m src.connectors.sci_scraper --dry-run   # fetch + report, no writes
poetry run python -m src.connectors.sci_scraper             # full Bronze → Silver → Gold
```

```sql
SELECT indicator_id, count(*), min(timestamp)::date, max(timestamp)::date
FROM silver.silver_cleaned WHERE source_name = 'sci' GROUP BY 1 ORDER BY 1;

SELECT indicator_id, count(*) AS levels,
       sum(CASE WHEN is_chain_linked THEN 1 ELSE 0 END) AS linked
FROM gold.gold_analytical
WHERE indicator_id LIKE 'SCI.%' AND indicator_id NOT LIKE '%.YOY'
GROUP BY 1 ORDER BY 1;

SELECT * FROM metadata.chain_linking_log WHERE indicator_id LIKE 'SCI.%';
```

---

# CBI Indicators (Phase 5 — GATED)

**Status:** ❌ NOT INGESTED — the Central Bank of Iran blocks programmatic access.

The CBI decision gate was evaluated in Task 1 and re-probed in Tasks 6–7.
`https://www.cbi.ir/` answers every request with an F5 TSPD JavaScript challenge
rather than content (with both `curl` and a normal headless Chromium), and
`https://tsd.cbi.ir/` does not resolve/answer at all. Per the project's rule
(AGENTS.md, and the OPEC precedent) the block is **not worked around**.

Consequently there is **no `cbi_parser.py`, `cbi_scraper.py`, CBI DAG, fixture
with data, or CBI indicator in the catalog**. The `CBI.M0`, `CBI.M2`,
`CBI.MONEY.MULTIPLIER`, and `CBI.HOUSING.TEHRAN` ids from the plan remain
unimplemented. Evidence: `tests/fixtures/cbi/_gate_task6.json`,
`tests/fixtures/cbi/_gate_task7.json`, and
[docs/phase-5/VALIDATION.md](../phase-5/VALIDATION.md).
