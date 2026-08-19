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
