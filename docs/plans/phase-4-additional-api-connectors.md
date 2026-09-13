# Task: Phase 4 — IMF, EIA & OPEC Connectors (Additional API Sources)

## Task Description

Build the second, third, and fourth data sources on top of the connector and
medallion pattern proven in Phase 2: an **IMF DataMapper** connector (annual
World Economic Outlook history **and five-year forecasts**), an **EIA API v2**
connector (monthly Iran crude oil production), and an **OPEC** connector
(basket price). Along the way, generalise the World-Bank-specific ETL runner so
a new source is a connector + a small `SourceSpec`, not a copy of
`src/etl/pipeline.py`.

**Why:** Phase 2 proved the architecture with one annual API; Phase 3 added one
daily scraper. Both are single-source code paths. Phase 4 is the first time the
platform ingests **multiple API sources with different frequencies, envelope
shapes, auth models, and time semantics** (IMF forecasts are deliberately
future-dated). Without the runner generalisation and forecast handling, every
future source (IMF/EIA/OPEC now; CBI/SCI/TSETMC later) would fork the pipeline.

**PRD mapping:** Phase 4 = PRD §9 Task 10 (IMF DataMapper Connector) and Task 11
(EIA and OPEC Energy Data Connectors). Timeline: Week 4–5.

**Verified API behaviour** in this plan was probed live on **2026-09-12**; see
`## Context` for the payload tables.

## Scope

### In Scope

- [ ] **Prerequisite fixes**: make derived-indicator ids idempotent about their
      source prefix (`TGJU.TGJU.…` → `TGJU.…`) and repair the daily-metrics test
      seed helper so the existing daily derivation is actually exercised
- [ ] **Generic pipeline runner**: a `FetchResult` protocol + `SourceSpec` in
      `src/etl/pipeline.py`, with `run_world_bank_pipeline` kept as a thin
      wrapper (no behaviour change for World Bank/TGJU)
- [ ] **Shared period helpers**: `src/utils/periods.py` for annual period-end,
      monthly period-end, and "one year earlier" alignment
- [ ] **Forecast-aware Silver validation**: intentional future periods (IMF
      forecasts) are retained and labelled, not dropped or flagged as errors
- [ ] **Frequency-aware YoY derivation**: `.YOY` means a genuine prior-year
      comparison for annual/quarterly/monthly series (currently a lag-1
      `pct_change`, which is MoM for monthly data)
- [ ] **IMF connector + parser** (`src/connectors/imf.py`, `imf_parser.py`)
      covering inflation, real GDP growth, and level series with 5-year
      forecasts; forecast rows tagged in metadata
- [ ] **EIA connector + parser** (`src/connectors/eia.py`, `eia_parser.py`) for
      monthly Iran crude oil production, API-key auth, pagination
- [ ] **OPEC scraper + parser** (`src/connectors/opec_scraper.py`,
      `opec_parser.py`) for the daily basket price, resampled to month-end in
      Gold — **gated**, see the decision gate below
- [ ] **Frequency conversion utility** (`src/etl/frequency.py`) for daily →
      monthly month-end price aggregation (AGENTS.md rule)
- [ ] Per-source CLI entry points: `python -m src.connectors.imf`,
      `python -m src.connectors.eia`, `python -m src.connectors.opec`
- [ ] Captured fixtures under `tests/fixtures/{imf,eia,opec}/`; unit +
      integration tests; live tests gated by `RUN_LIVE_API_TESTS=1`
- [ ] `docs/phase-4/` implementation/validation reports; data-dictionary,
      README, `AGENTS.md`, and `.env.example` updates

### Out of Scope

- [ ] Forecasting models, nowcasting, or any ML training (platform is still
      collection/analytics only)
- [ ] CBI TSD / SCI scrapers and real multi-base-year chain-linking (Phase 5)
- [ ] TSETMC / HBSIR (Phase 6)
- [ ] New dashboard pages; existing domain pages will pick up the new
      indicators automatically via `metadata.indicator_catalog.domain`
- [ ] CI/CD, backup automation, performance tuning (Phase 8)
- [ ] Airflow DAGs for the new sources (defer until the Phase 4 connectors are
      validated; monthly cadence is a small follow-up)
- [ ] Retrofitting the double-prefix bug in any already-published Gold rows
      beyond the one-off TGJU cleanup migration in Task 2

## Context

### Current state (verified 2026-09-12)

- Phases 1, 2, 3, and 7 are complete and committed on `development`; working
  tree clean, in sync with `origin/development`.
- The World Bank path is the reference implementation:
  `src/connectors/world_bank.py` (config dataclass with `get_config()` defaults,
  injected `http_session`/`RetryPolicy`/`RateLimiter`, `fetch_series()` returning
  a result object with `raw_envelope`/`request_url`/`http_status_code`,
  `discover()` describing indicators, `main()` delegating to
  `src/etl/pipeline.py`).
- `src/etl/pipeline.py` is **World Bank specific**: `_persist_indicator`
  (`src/etl/pipeline.py:282`) is typed to `WorldBankFetchResult` and hardcodes
  `frequency=FREQUENCY_ANNUAL`; `_collect_one` and `run_world_bank_pipeline`
  (`src/etl/pipeline.py:320`) are typed to `WorldBankConnector`.
- `src/etl/silver.py` already exposes the parser seam Phase 4 needs:
  `bronze_to_silver(..., parser=...)` / `prepare_silver_frame(..., parser=...)`.
  The default parser (`_default_parser`, `src/etl/silver.py:89`) assumes World
  Bank rows (`indicator.id`, `date`, `value`).
- `src/etl/bronze.py` stores `raw_data` as a dict and `extract_rows()` reads a
  top-level `rows` list of objects. `wrap_envelope()` passes dicts through
  unchanged, so per-source envelopes can be `{"rows": [...], "meta": {...}}`.
- `src/chain_linking/splice.py` already knows frequency: `monthly` → 12
  overlap periods, `months_per_period("monthly") == 1`.
- **No frequency-conversion utility exists anywhere in `src/`** (only a rolling
  MA in `gold.py`), despite AGENTS.md documenting end-of-month downsampling.
- `src/utils/config.py` already defines `APIConfig.imf_url`,
  `APIConfig.eia_url`, and `APIConfig.eia_api_key`; `.env.example` already
  lists the IMF and EIA vars. There is no OPEC URL setting yet.
- **Known test-harness defect (from `prime`)**: `tests/unit/etl/test_gold.py`
  has 10 failing daily-metrics tests. Two causes: `seed_daily_silver()` calls
  `session.add(...)` instead of `session.seed(SilverCleaned, ...)` so
  `load_silver_series` returns zero rows, and the derived-id helpers
  double-prefix (`derived_ret1d_indicator_id("TGJU.USD.FREE", "TGJU")` returns
  `TGJU.TGJU.USD.FREE.RET1D`, while the docstring and
  `tests/unit/etl/test_gold.py:793` expect `TGJU.USD.FREE.RET1D`).
- `README.md:308` reports "23 failing (13 Airflow DAG tests …)"; the Airflow DAG
  tests now pass (verified: 13 passed) and the README claim is stale.

### Data flow this phase must realise

```text
IMF DataMapper  (annual, IRN, 1980→2031 incl. WEO forecasts)
        ↓  ImfConnector.fetch_series()
EIA API v2      (monthly, IRN crude production, 2024→present)
        ↓  EiaConnector.fetch_series()
OPEC basket     (daily HTML/JS, month-end in Gold)          [gated]
        ↓  OpecScraper.fetch_series()
bronze.bronze_raw          {"rows": [...], "meta": {...}, "raw_response": {...}}
        ↓  src/etl/silver.py with a per-source parser
silver.silver_cleaned      validated, upsert on (indicator_id, timestamp)
        ↓  src/etl/gold.py (frequency-aware YoY; optional daily→monthly)
gold.gold_analytical       levels + derived series, domain/frequency tagged
```

### Verified IMF DataMapper behaviour (probed 2026-09-12)

| Property | Observed |
|----------|----------|
| Base | `https://www.imf.org/external/datamapper/api/v1` |
| Auth | None |
| `/indicators` | `{"indicators": {CODE: {label, description, source, unit, dataset, last-modified}}}` — **132** indicators, all WEO (April 2026 vintage) |
| `/NGDP_RPCH` | `{"values": {"NGDP_RPCH": {COUNTRY: {"1980": 1.2, …}}}, "api": {"version": "1", "output-method": "json"}}` |
| Country filter | **Ignored**: `/NGDP_RPCH/IRN` returns the same 229-country payload as `/NGDP_RPCH` (≈121 KB). Filter to `IRN` client-side |
| Period filter | **Ignored**: `?periods=2020,2022` returns the full series |
| `/countries` | `{"countries": {"IRN": {"label": "Iran"}, …}, "api": {…}}` |
| Quirk | `values` contains an empty-string key mapped to `null`; iterate defensively |
| Values | JSON numbers keyed by four-digit **string** years |
| IRN coverage | 1980–2031; 2026 is an estimate and 2027–2031 are WEO projections |
| Forecast flag | Not present in the payload; the vintage must be parsed from `source` (`"World Economic Outlook (April 2026)"`) |
| Invalid code | `/NOTAREALCODE` → **HTTP 200** with a `countries` payload, not an error — treat a missing `values[code]` as a retrieval error |
| Indicators selected | `NGDP_RPCH` (real GDP growth), `PCPIPCH` (inflation), `NGDPD` (GDP current US$), `NGDPDPC` (GDP per capita), `LUR` (unemployment), `BCA_NGDPD` (current account % GDP) |

### Verified EIA API v2 behaviour (probed 2026-09-12)

| Property | Observed |
|----------|----------|
| Base | `https://api.eia.gov/v2`, route `/international/data/` |
| Auth | `api_key` required. Missing → HTTP 403 `{"error":{"code":"API_KEY_MISSING"}}`; invalid → 403 `API_KEY_INVALID` |
| Key source | `get_config().api.eia_api_key`; register at <https://www.eia.gov/opendata/register.php>. `DEMO_KEY` works for a quick smoke only |
| Query | `frequency=monthly&data[0]=value&facets[countryRegionId][]=IRN&facets[productId][]=55&facets[activityId][]=1&start=YYYY-MM&end=YYYY-MM&length=N&offset=M` |
| Iran facets | `countryRegionId=IRN`; crude production is `productId=55` ("Crude oil, NGPL, and other liquids") or `53` ("Total petroleum and other liquids"), `activityId=1` ("Production") |
| Response | `{"response": {"total": "29", "frequency": "monthly", "data": [{period: "2026-05", productName: …, activityName: …, countryRegionName: "Iran", unitName: "thousand barrels per day", unit: "TBPD", value: "3430", dataFlagId: …}]}, "request": {…}, "apiVersion": "2.1.13"}` |
| Types | `response.total` and `value` are **strings**; `value` may be empty/`null` |
| Ordering | Newest period first by default; request `sort[0][column]=period&sort[0][direction]=asc` or sort client-side |
| Pagination | `length`/`offset`; default page 5000. Iran crude is ≈29 rows, but implement paging |
| No-data | Unknown facet → HTTP **200** with `total: "0"`, not an error |

### Verified OPEC behaviour (probed 2026-09-12) — blocker

| URL | Result |
|----|--------|
| `https://www.opec.org/opec_web/static_files_project/media/downloads/data/OPEC_Basket_Daily.xlsx` | HTTP 200 but `Content-Type: text/html`, 245,600 bytes — a **Cloudflare challenge page**, not a workbook (`zipfile` → `BadZipFile`) |
| `…/OPEC_Basket_Daily.csv` | Connection reset |
| `https://asb.opec.org/data/CSVData.php` | HTTP 403 (Cloudflare) |
| Browser `User-Agent` | Does not help; challenge markup (`challenge-platform`) is still returned |

**Decision gate (Task 13):** spend at most one implementation session trying a
Playwright fetch of the OPEC basket page with a fixture-first parser. If a real
browser cannot clear the challenge, ship the parser + fixtures and document the
limitation, and defer live OPEC extraction to Phase 5. IMF + EIA are the
committed Phase 4 deliverables and do not depend on OPEC.

### Storage constraints that shape the design

- `silver.silver_cleaned.value` is NOT NULL → null/blank observations are
  skipped and counted, never imputed.
- `silver.silver_cleaned` upserts on `uq_silver_indicator_timestamp` → IMF WEO
  re-releases (April/October) correct prior-year forecasts in place.
- `metadata.indicator_catalog.unit` is `String(50)`; IMF units
  (`"Annual percent change"`, `"Billions of U.S. dollars"`) and EIA
  (`"thousand barrels per day"`) fit.
- `metadata.indicator_catalog.indicator_id` is `String(100)`; derived ids are
  built by `gold.derived_*_indicator_id`.
- `gold.gold_analytical` PK is `(id, timestamp)`; Gold is delete-and-reinsert
  per indicator id, and the derived ids must therefore be stable across runs.
- `record_metadata` is the Python attribute for the physical `metadata` column.
- Domain vocabulary in use: `gdp`, `inflation`, `trade`, `welfare`, `energy`,
  `fx`, `gold`, `unclassified`. New mappings must use these values.

## Proposed Approach

Work bottom-up and keep the World Bank path behaviourally unchanged:

1. **Repair the two latent defects first** (double-prefixed derived ids; the
   daily test seed helper) and add a one-off Alembic data migration to delete
   any legacy `TGJU.TGJU.%` Gold rows. Everything else reuses `gold.py`.
2. **Generalise the runner instead of forking it.** Introduce a structural
   `FetchResult` protocol and a frozen `SourceSpec` (source name/type,
   frequency, derived prefix, default derivation, per-indicator overrides,
   forecast support). `run_pipeline()` becomes source-agnostic;
   `run_world_bank_pipeline()` remains as a wrapper so existing tests and the
   `python -m src.connectors.world_bank` CLI keep working.
3. **Handle forecasts explicitly.** IMF projections are future-dated by design.
   Add an opt-in `allow_future` path through `prepare_silver_frame`,
   `bronze_to_silver`, and `validate_data_quality` (default `False`, so World
   Bank/TGJU are unaffected), count forecast rows in the transformation log,
   and tag each forecast observation with `observation_type` =
   `actual`/`estimate`/`forecast` derived from the WEO vintage year.
4. **Make `.YOY` frequency-correct.** Replace the lag-1 `pct_change` with a
   prior-year, timestamp-aligned comparison: for each row, look up the value
   exactly one year earlier; publish a rate only when that period exists (no
   interpolation, no cross-gap fabrication). Annual behaviour is unchanged.
5. **Add per-source parsers** next to their connectors (mirroring the TGJU
   scraper/parser split) so payload parsing is unit-testable from fixtures with
   no network. Bronze envelopes follow `{"rows": [...flattened observations...],
   "meta": {...}, "raw_response": ...}` so `extract_rows()` works uniformly and
   the untouched response is still retained.
6. **IMF** fetches the full indicator payload, filters to `IRN`, and stores the
   full response for audit. Rate indicators (`NGDP_RPCH`, `PCPIPCH`, `LUR`,
   `BCA_NGDPD`) get **no** derived series; level indicators (`NGDPD`,
   `NGDPDPC`) get YoY.
7. **EIA** fetches monthly crude production with facets, paging, and sorting,
   and derives YoY (lag 1 year) on monthly levels. Missing/invalid key raises an
   actionable error and aborts the run once, rather than failing per indicator.
8. **OPEC** is gated (see Context). If reached: parse the daily basket page,
   store daily Silver, and publish month-end Gold levels through
   `src/etl/frequency.py`; no derived metrics until `ret1d` history exists.
9. **Validate with fixtures, not live APIs.** Integration tests assert the
   Bronze → Silver → Gold roundtrip against Docker; live tests are marked
   `@pytest.mark.live` and gated by `RUN_LIVE_API_TESTS=1`.

## Task Metadata

**Type:** New Capability (+ small Bug Fix and Refactor)
**Complexity:** High
**Affected Areas:** `src/connectors/` (3 new sources + parser modules),
`src/etl/` (pipeline runner, silver, gold, frequency), `src/utils/` (periods,
config, validation), `alembic/versions/` (data cleanup), `tests/`, `docs/`
**Dependencies:** existing `requests`, `pandas`, `Playwright`, SQLAlchemy,
Alembic. No new third-party packages are required.

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `src/connectors/world_bank.py` — reference connector: config dataclass,
  injected session/retry/rate-limiter, `fetch_series()` result object,
  `discover()`, `main()` (read `:119-167`, `:297-620`, `:593`).
- `src/etl/pipeline.py` — runner to generalise: `IndicatorOutcome`/`PipelineSummary`,
  `upsert_indicator_catalog`, `update_catalog_availability`, `_collect_one`,
  `_persist_indicator`, `run_world_bank_pipeline`, `run_cli` (read all).
- `src/etl/silver.py` — the parser seam (`bronze_to_silver:270`,
  `prepare_silver_frame:121`, `_default_parser:89`) and the cleaning counters.
- `src/etl/gold.py` — derived-id helpers (`:83`, `:97`, `:111`),
  `_growth_records` (`:208`), `_daily_return_records` (`:296`),
  `silver_to_gold` (`:492`), `_replace_gold_rows` (`:479`).
- `src/etl/bronze.py` — `wrap_envelope:43`, `extract_rows:70`, `write_bronze:95`.
- `src/utils/validation.py` — `validate_date_range:47` (future-date error),
  `validate_data_quality:147`.
- `src/utils/config.py` — `APIConfig` (`:101-120`); add `opec_base_url` here.
- `src/utils/retry.py` — `RetryPolicy` / `RateLimiter` injection contract.
- `src/database/schema.py` — `IndicatorCatalog:167`, `SilverCleaned:75`,
  `GoldAnalytical:121`; confirm column widths/JSONB before adding ids.
- `tests/conftest.py` — `FakeSession`, `FakeHTTPSession`, `FakeResponse`,
  `load_world_bank_fixture`; extend with IMF/EIA/OPEC loaders.
- `tests/unit/connectors/test_world_bank.py` — connector unit-test idiom.
- `tests/integration/test_world_bank_pipeline.py` — integration roundtrip idiom.
- `docs/phase-2/data_dictionary.md` — the "observed, not advertised" coverage
  format every new indicator must follow.

### Data / ML References

- `src/chain_linking/splice.py` — frequency-aware overlap (`monthly` → 12);
  pass the true frequency so chain-linking stays correct.
- `src/etl/lineage.py` — `transformation()` context manager; every new layer
  write must be wrapped and counted.
- `docs/plans/phase-2-world-bank-connector.md` — plan format and the
  Bronze/Silver/Gold conventions this plan extends.
- `docs/plans/phase-3-tgju-scraper.md` — scraper + parser split and the
  Playwright testing approach to reuse for OPEC.

### External Documentation

- IMF DataMapper API v1 — `https://www.imf.org/external/datamapper/api/v1`
  (verify against the live payloads in Context; there is no filtering, so the
  client owns country/year selection).
- IMF WEO indicator codes — `https://www.imf.org/external/datamapper/datasets/WEO`
  (confirm `NGDP_RPCH`, `PCPIPCH`, `NGDPD` labels/units before seeding).
- EIA Open Data API v2 browser — `https://www.eia.gov/opendata/browser/international`
  (confirm product/activity facet ids and the TBPD unit).
- EIA registration — `https://www.eia.gov/opendata/register.php` (API key).
- OPEC basket price — `https://www.opec.org/opec_web/en/data_graphs/40.htm`
  (Cloudflare-protected; inspect with a real browser before writing selectors).

### Patterns to Follow

**Naming:** files snake_case; classes PascalCase; constants UPPER_SNAKE;
private helpers leading underscore. Indicator ids: source codes are stored raw
where already globally unique (World Bank), otherwise namespaced (TGJU). For
Phase 4 use **`IMF.NGDPD`**, **`EIA.IRN.CRUDE_PRODUCTION`**, **`OPEC.BASKET`**
and derive the prefix from the same namespace so ids never double-prefix.

**Structure:** connector (`connect`/`discover`/`fetch`/`validate`/`fetch_series`)
+ separate pure `*_parser.py`; pipeline persistence stays in `src/etl/`;
`main()` delegates to `src/etl/pipeline.run_cli` via a local import.

**Config:** frozen-ish dataclass with defaults from `get_config()`; no hardcoded
URLs, timeouts, page sizes, or country codes in logic.

**Testing:** fixtures captured from real payloads; fake HTTP session + no-op
sleeps for unit tests; `FakeSession` for ETL; `@pytest.mark.integration` against
Docker; `@pytest.mark.live` behind `RUN_LIVE_API_TESTS=1`; parsers tested
without network.

**Data:** preserve the raw response; skip-and-count nulls; flag (never drop)
outliers; upsert Silver on `(indicator_id, timestamp)`; delete-and-reinsert Gold
per indicator; log every transformation through `lineage.transformation`.

---

## IMPLEMENTATION PLAN

### Phase 4.1: Prerequisite repairs (do first)

Fix the two defects that block the daily-metrics suite and would produce wrong
derived ids for every namespaced source, plus the data cleanup that the naming
fix requires.

### Phase 4.2: Shared foundations

`src/utils/periods.py`, `src/etl/frequency.py`, forecast-aware validation, and
the frequency-aware YoY change in `gold.py`.

### Phase 4.3: Generic runner

`FetchResult` protocol + `SourceSpec` + `run_pipeline()`; World Bank/TGJU
behaviour preserved.

### Phase 4.4: Connectors

IMF (parser → connector → CLI), then EIA (parser → connector → CLI), then the
gated OPEC track.

### Phase 4.5: Validation & documentation

Fixtures, unit/integration tests, observed coverage in the data dictionary,
phase-4 reports, and README/AGENTS/`.env.example` corrections.

---

## STEP-BY-STEP TASKS

Execute in order; later tasks assume earlier ones.

### Task 1: FIX derived-indicator id double prefix

- **IMPLEMENT:** Make `derived_growth_indicator_id`,
  `derived_ret1d_indicator_id`, and `derived_ma30_indicator_id`
  (`src/etl/gold.py:83,97,111`) idempotent about the namespace: if
  `indicator_id.startswith(f"{prefix}.")` return `f"{indicator_id}.{suffix}"`,
  otherwise keep the current `f"{prefix}.{indicator_id}.{suffix}"` behaviour.
  Add a short helper `_namespaced(indicator_id, prefix, suffix)` used by all
  three.
- **PATTERN:** Existing WB expectations must not move:
  `derived_growth_indicator_id("NY.GDP.MKTP.CD") == "WB.NY.GDP.MKTP.CD.YOY"`.
- **DEPENDENCIES:** None.
- **GOTCHA:** The TGJU docstrings already promise `TGJU.USD.FREE.RET1D`; the
  implementation returns `TGJU.TGJU.USD.FREE.RET1D`. Fix the code to match the
  documented id, not the reverse. `TEST.PRICE` + prefix `TEST` in the tests also
  becomes `TEST.PRICE.RET1D` — confirm that is the intended assertion.
- **VALIDATE:** `poetry run python -c "from src.etl.gold import derived_ret1d_indicator_id; print(derived_ret1d_indicator_id('TGJU.USD.FREE','TGJU'))"`
  prints `TGJU.USD.FREE.RET1D`.

### Task 2: CREATE one-off migration deleting legacy double-prefixed Gold rows

- **IMPLEMENT:** `alembic/versions/<ts>_normalise_tgju_derived_ids.py` executing
  `DELETE FROM gold.gold_analytical WHERE indicator_id LIKE 'TGJU.TGJU.%'`.
  `downgrade()` is a documented no-op (the rows are regenerated on the next
  TGJU run).
- **PATTERN:** Data-migration style already used in
  `alembic/versions/20260819_1236_silver_unique_constraint.py` (docstring
  explains intent); generate with `alembic revision -m "normalise tgju derived ids"`
  **without** `--autogenerate` (no schema change).
- **DEPENDENCIES:** Task 1.
- **GOTCHA:** A schema-only `autogenerate` would produce an empty migration, and
  `alembic check` must stay clean afterward. Do not touch
  `TIMESCALE_MANAGED_INDEXES`.
- **VALIDATE:** `poetry run alembic upgrade head && poetry run alembic check`.

### Task 3: FIX the daily-metrics test seed helper

- **IMPLEMENT:** In `tests/unit/etl/test_gold.py`, change `seed_daily_silver()`
  from `session.add(row)` to `session.seed(SilverCleaned, rows)` (matching
  `seed_silver()`), and ensure `catalog_entry_daily()` also seeds through the
  FakeSession API.
- **PATTERN:** `seed_silver()` at `tests/unit/etl/test_gold.py:70-88`.
- **DEPENDENCIES:** Tasks 1–2 (namespacing assertions depend on them).
- **GOTCHA:** `FakeSession.query(...)` only returns seeded rows; `session.add`
  is not enough. Do not change production code to accommodate the test harness.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_gold.py -q -o addopts=""`
  → **40 passed** (was 28 passed / 10 failed).

### Task 4: CREATE `src/utils/periods.py`

- **IMPLEMENT:** Pure helpers: `annual_period_end(year) -> datetime` (Dec 31,
  UTC), `month_period_end(year, month) -> datetime` (last calendar day, UTC),
  `parse_period(value, frequency) -> datetime`, and
  `year_earlier(timestamp) -> datetime` (exact prior-year period using
  `pd.DateOffset(years=1)`).
- **PATTERN:** `world_bank._parse_annual_timestamp`
  (`src/connectors/world_bank.py:207`) is the reference implementation; move
  the logic here and have World Bank call the shared helper (behaviour
  identical).
- **DEPENDENCIES:** None.
- **GOTCHA:** Use `calendar.monthrange` or `pd.Period(...).end_time` for
  month-end; never hardcode 28–31. Keep everything `timezone=True` UTC. A
  quarterly period end is a month end (Mar/Jun/Sep/Dec) and needs no separate
  function for this phase.
- **VALIDATE:** `poetry run pytest tests/unit/utils/test_periods.py -q`;
  `poetry run mypy src/utils/periods.py`.

### Task 5: UPDATE forecast-aware validation

- **IMPLEMENT:** Add `allow_future: bool = False` and an optional `now: datetime
  | None = None` to `validate_date_range` (`src/utils/validation.py:47`) and
  thread it through `validate_data_quality` (`:147`). When
  `allow_future=True`, future timestamps are reported as an informational
  warning (or omitted) instead of an error. Default keeps every existing
  behaviour.
- **PATTERN:** Existing optional `min_date`/`max_date` parameters.
- **DEPENDENCIES:** None.
- **GOTCHA:** Do not simply delete the future check — it protects World Bank and
  TGJU from clock bugs. Existing tests in `tests/unit/utils/test_validation.py`
  must pass unchanged.
- **VALIDATE:** `poetry run pytest tests/unit/utils/test_validation.py -q`.

### Task 6: UPDATE Silver for intentional future periods

- **IMPLEMENT:** Add `allow_future: bool = False` to `prepare_silver_frame`
  (`src/etl/silver.py:121`) and `bronze_to_silver` (`:270`). Add
  `forecast_records: int = 0` to `SilverPreparation` and include it in
  `counters()`. When `allow_future` is true, count rows with
  `timestamp > utc_now()` as `forecast_records` and do not treat them as
  failed/skipped. Pass `allow_future` into `validate_data_quality`.
- **PATTERN:** `SilverPreparation` counters already surface
  null/duplicate/future/outlier counts into `TransformationLog`.
- **DEPENDENCIES:** Task 5.
- **GOTCHA:** `future_records` currently means "rows the parser dropped". Keep
  that meaning for non-forecast sources; when `allow_future` is true the parser
  does not drop them, so `forecast_records` is the honest counter. The Silver
  `metadata` should record `observation_type` from the parsed row.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_silver.py -q`.

### Task 7: UPDATE Gold with a genuine prior-year YoY

- **IMPLEMENT:** In `_growth_records` (`src/etl/gold.py:208`) replace
  `linked[VALUE_COLUMN].pct_change(fill_method=None)` with a prior-year-aligned
  comparison: build a value lookup keyed by timestamp, and for each row look up
  `year_earlier(timestamp)` (Task 4). Publish
  `(value / prior_value - 1) * 100` only when the exact prior-year period
  exists; otherwise `NaN` (skipped). Do the same on
  `original_value` for the `spans_base_year_break` logic.
- **PATTERN:** Keep the rest of `_growth_records` intact (attribution to the
  later period's `silver_id`, `is_chain_linked` from either period, confidence
  scoring).
- **DEPENDENCIES:** Task 4.
- **GOTCHA:** Annual series must produce byte-identical results to today
  (`tests/unit/etl/test_gold.py::test_silver_to_gold_derives_a_year_over_year_series`
  and adjacent tests). Monthly gaps must yield no rate, not a fake one. Do not
  interpolate (AGENTS.md).
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_gold.py -q -o addopts=""`
  → all pass, including new monthly/quarterly cases.

### Task 8: CREATE `src/etl/frequency.py`

- **IMPLEMENT:** `to_month_end(frame, *, value_column="value",
  timestamp_column="timestamp") -> pd.DataFrame` that groups daily rows by
  calendar month and keeps the **last observation in the month**, stamped at
  month end (AGENTS.md: end-of-month for price data). Return the same column
  contract as Silver (`timestamp`, `value`). Expose
  `aggregate_to_monthly(frame, method="month_end")` with only `month_end`
  implemented, so future methods (mean for volumes) slot in.
- **PATTERN:** `src/chain_linking/splice.normalise_series` (`:129`) for
  sort/dedupe/columns conventions.
- **DEPENDENCIES:** Task 4 (`month_period_end`).
- **GOTCHA:** Do not forward-fill missing days. If a month has no observation,
  it produces no row (later reported as a gap). Keep timestamps tz-aware UTC.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_frequency.py -q`;
  `poetry run mypy src/etl/frequency.py`.

### Task 9: REFACTOR `src/etl/pipeline.py` to a generic runner

- **IMPLEMENT:**
  - Add a runtime-checkable `FetchResult` protocol with `indicator_id: str`,
    `frame: pd.DataFrame`, `raw_envelope: Any`, `request_url: str | None`,
    `http_status_code: int | None`, and
    `collection_metadata() -> dict[str, Any]`.
  - Add frozen `IndicatorDerivation(derivation_strategy: str | None, include_growth: bool)`
    and `SourceSpec(source_name, source_type, frequency, derived_prefix,
    default_derivation, overrides: Mapping[str, IndicatorDerivation] = {},
    supports_forecasts: bool = False)`.
  - Add `run_pipeline(connector, spec, indicators=None, dry_run=False) -> PipelineSummary`,
    moving the body of `run_world_bank_pipeline` (`:320`) and generalising
    `_collect_one`/`_persist_indicator` (`:282`) to the protocol + spec.
    `_persist_indicator` must pass `spec.frequency`, `spec.source_type`,
    `spec.supports_forecasts`, and the per-indicator derivation into
    `bronze_to_silver` / `silver_to_gold`.
  - Keep `run_world_bank_pipeline(...)` as a thin wrapper that builds the World
    Bank `SourceSpec` and calls `run_pipeline`, preserving its signature and
    return type. Keep `run_cli(..., spec=...)` generic.
- **PATTERN:** Existing `run_world_bank_pipeline`/`_collect_one` structure; keep
  "one session per indicator", `INDICATOR_ERRORS` containment, and
  `_ensure_database`.
- **DEPENDENCIES:** Task 6, Task 7.
- **GOTCHA:** This is the highest-risk change. `PipelineSummary.source_name`
  defaults to `SOURCE_NAME` today — pass `spec.source_name`. Do not change the
  World Bank CLI output format or `IndicatorOutcome` fields. Type the protocol
  with `Protocol` from `typing`, and satisfy mypy strict (no `Any` leakage
  beyond `raw_envelope`).
- **VALIDATE:** `poetry run pytest tests/unit -q -o addopts=""` and
  `poetry run mypy src/etl/pipeline.py`; then
  `poetry run python -m src.connectors.world_bank --dry-run` still works.

### Task 10: CREATE IMF parser and connector

- **IMPLEMENT:**
  - `src/connectors/imf_parser.py`: `parse_indicator_metadata(payload)`,
    `flatten_values(values, indicator_id, country="IRN")` (returns
    `{period, value}` rows for one country, skipping the empty-string key and
    non-mapping values), and `imf_parser(rows, indicator_id, unit, now)` →
    DataFrame with Silver columns using `periods.annual_period_end`. The IMF
    parser ignores `now` (forecasts are kept).
  - `src/connectors/imf.py`: `IMFConfig(base_url from APIConfig.imf_url,
    country="IRN", timeout>=30, indicators=IMF_INDICATORS)`,
    `ImfFetchResult` with `raw_envelope` (`{"rows", "meta", "raw_response"}`),
    `ImfConnector(DataConnector)` with injected session/retry/rate-limiter,
    `discover()` reading `/indicators`, `connect()` probing `/countries`,
    `fetch_series()` fetching `/api/v1/<code>` and filtering to IRN, and
    `main()` delegating to `run_cli` with the IMF `SourceSpec`.
  - Constants: `IMF_INDICATORS` registry with per-code domain/unit/derivation:
    `NGDP_RPCH`→gdp/no-derived, `PCPIPCH`→inflation/no-derived,
    `NGDPD`→gdp/yoy, `NGDPDPC`→gdp/yoy, `LUR`→welfare/no-derived,
    `BCA_NGDPD`→trade/no-derived.
- **PATTERN:** `src/connectors/world_bank.py` end to end.
- **DEPENDENCIES:** Tasks 4, 9.
- **GOTCHA:** The `/<code>/IRN` path does **not** filter; fetch `/api/v1/<code>`
  and select IRN yourself, but store the full `raw_response` for audit. Parse
  the vintage year from `source` (`"World Economic Outlook (April 2026)"`) and
  set `observation_type` = `actual`/`estimate`/`forecast` relative to it. A
  missing `values[code]` or missing IRN is a `DataRetrievalError`, not an empty
  series. Annual timestamps remain Dec 31, so 2027–2031 are future-dated —
  `supports_forecasts=True` is mandatory.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_imf.py -q`;
  `poetry run python -m src.connectors.imf --dry-run` prints per-indicator
  counts including forecast rows.

### Task 11: CREATE EIA parser and connector

- **IMPLEMENT:**
  - `src/connectors/eia_parser.py`: `eia_parser(rows, indicator_id, unit, now)`
    mapping `period` (`YYYY-MM`) → `periods.month_period_end`, coercing the
    string `value` to float (blank/`null` → None, non-numeric → `ParsingError`),
    and surfacing `unitName`/`dataFlagDescription` in metadata.
  - `src/connectors/eia.py`: `EiaConfig(api_key from APIConfig.eia_api_key,
    base_url, country="IRN", products/activity facets, page_length, timeout)`,
    `EiaFetchResult`, `EiaConnector` with `fetch_series()` paging
    `length`/`offset` and sorting `period` ascending, `discover()` from a
    committed product registry, `validate()`, and `main()`.
  - Indicator registry: `EIA.IRN.CRUDE_PRODUCTION` →
    `productId=55, activityId=1` (crude + NGPL), and
    `EIA.IRN.TOTAL_LIQUIDS` → `productId=53, activityId=1`; domain `energy`,
    frequency `monthly`, unit `thousand barrels per day`.
- **PATTERN:** `world_bank.py` connector shape; `RetryPolicy` must not retry
  403 auth errors.
- **DEPENDENCIES:** Tasks 4, 9.
- **GOTCHA:** Treat the `.env.example` placeholder
  (`your_eia_api_key_here`), empty string, and `None` as "key not configured"
  and raise an actionable `PlatformConnectionError` from `connect()` so the run
  aborts once instead of failing every indicator. `response.total` is a string;
  stop paging when the collected count reaches it. Unknown facets return
  HTTP 200 with `total: "0"` — that is an empty series, not an error, but a
  missing key is.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_eia.py -q`;
  `EIA_API_KEY=<real key> poetry run python -m src.connectors.eia --dry-run`
  shows ≈29 monthly crude rows.

### Task 12: UPDATE config and `.env.example`

- **IMPLEMENT:** Add `opec_base_url` to `APIConfig`
  (`src/utils/config.py:101`) defaulting to
  `https://www.opec.org/opec_web` with alias `OPEC_BASE_URL`; add the matching
  line to `.env.example` (and an OPEC section note). Confirm the EIA/IMF vars
  are documented as required/optional respectively.
- **PATTERN:** Existing `tgju_base_url` entry and `.env.example` API block.
- **DEPENDENCIES:** None.
- **GOTCHA:** `APIConfig` uses `extra="ignore"` and aliases; follow the same
  `Field(default=..., alias=...)` form.
- **VALIDATE:** `poetry run pytest tests/unit/utils/test_config.py -q`.

### Task 13: OPEC track — gated

- **IMPLEMENT:** Only if the decision gate passes.
  - `src/connectors/opec_parser.py`: pure HTML/JSON parser for the basket price
    table, returning `{date, value}` rows; Persian/Arabic digits are not
    expected here, but reuse `normalise_digits` if needed.
  - `src/connectors/opec_scraper.py`: `OpecScraper(DataConnector)` using
    synchronous Playwright (`headless=True`), `page.set_default_timeout(30_000)`,
    user-agent rotation, Bronze envelope `{"rows": [{"html": ..., "url": ...,
    "scraped_at": ...}]}` per AGENTS.md; indicator id `OPEC.BASKET`.
  - Gold path: publish the daily levels, then month-end monthly levels via
    `src/etl/frequency.py` (either pre-resample before `silver_to_gold` or add a
    `target_frequency`/`aggregation` option — pick one and document it).
- **PATTERN:** `src/connectors/tgju_scraper.py` + `tgju_parser.py`, and
  `docs/plans/phase-3-tgju-scraper.md` Tasks 4–6.
- **DEPENDENCIES:** Tasks 4, 8, 9.
- **GOTCHA:** Probes on 2026-09-12 show Cloudflare returns an HTML challenge for
  both the `.xlsx` and ASB URLs; a headless browser may still be challenged.
  Timebox live access to one session. Capture a fixture, ship parser tests, and
  if access fails, leave the connector inactive (do not add it to a DAG) and
  record the limitation in `docs/phase-4/VALIDATION.md`. Never commit live HTML
  with cookies/tokens.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_opec.py -q` (parser
  + scraper mocked with fixture HTML). Live check only via
  `RUN_LIVE_API_TESTS=1 poetry run pytest -m live`.

### Task 14: CREATE fixtures

- **IMPLEMENT:** `tests/fixtures/imf/` (`indicators.json`,
  `NGDP_RPCH_normal.json`, `PCPIPCH_normal.json`, `NGDPD_normal.json`,
  `missing_indicator.json`, `countries_normal.json`),
  `tests/fixtures/eia/` (`crude_production_page1.json`,
  `crude_production_page2.json`, `empty_facets.json`,
  `missing_key_error.json`), and `tests/fixtures/opec/` (`basket_prices.html`,
  plus a challenge page under a clearly named file for the blocked-path test).
  Extend `tests/conftest.py` with `load_imf_fixture`, `load_eia_fixture`,
  `load_opec_fixture`, and fake-session routers.
- **PATTERN:** `tests/fixtures/world_bank/` + `load_world_bank_fixture`
  (`tests/conftest.py`); fixtures are captured, never hand-fabricated.
- **DEPENDENCIES:** Tasks 10–11 (fixtures can be captured during those tasks).
- **GOTCHA:** Keep each fixture small — trim IMF payloads to IRN plus a couple
  of countries and a handful of years; do not commit a full 121 KB payload per
  indicator if unnecessary, but keep at least one untrimmed-shape fixture so
  the empty-string-key quirk is covered.
- **VALIDATE:** unit suites load every fixture with no network.

### Task 15: CREATE unit test suites

- **IMPLEMENT:** `tests/unit/connectors/test_imf.py`,
  `test_eia.py`, `test_opec.py`, `tests/unit/connectors/test_imf_parser.py`,
  `test_eia_parser.py`, `test_opec_parser.py`, `tests/unit/utils/test_periods.py`,
  `tests/unit/etl/test_frequency.py`, plus additions to `test_gold.py`
  (monthly/quarterly YoY), `test_silver.py` (forecast retention), and
  `test_pipeline.py` (generic runner with a fake connector).
- **PATTERN:** `tests/unit/connectors/test_world_bank.py` (fake HTTP session,
  no-op retries) and the `FakeSession` ETL idiom.
- **DEPENDENCIES:** Tasks 1–11.
- **GOTCHA:** Assert the exact observed quirks: IMF ignores `/IRN` and
  `periods`; the empty-string key is skipped; EIA `value`/`total` are strings;
  EIA 403 error codes; a missing EIA key raises once; annual WB YoY unchanged.
- **VALIDATE:** `poetry run pytest tests/unit -q`.

### Task 16: CREATE integration tests

- **IMPLEMENT:** `tests/integration/test_imf_pipeline.py`,
  `test_eia_pipeline.py` (and `test_opec_pipeline.py` if Task 13 lands),
  `@pytest.mark.integration`, running the connector against a fake HTTP session
  plus the real Docker Postgres so Bronze → Silver → Gold is exercised, with
  cleanup afterward. Assert IMF forecast rows survive to Gold and EIA monthly
  YoY is lag-1-year.
- **PATTERN:** `tests/integration/test_world_bank_pipeline.py`.
- **DEPENDENCIES:** Tasks 10–15.
- **GOTCHA:** `make test-integration` disables the coverage gate; use the same
  `reader`/`count` helpers as the World Bank integration test. Ensure the
  forecast rows do not trip the future-date validation path.
- **VALIDATE:** `make db-up && poetry run alembic upgrade head && make test-integration`.

### Task 17: UPDATE documentation

- **IMPLEMENT:**
  - `docs/phase-2/data_dictionary.md` (per AGENTS.md): add an IMF section, an
    EIA section, and an OPEC section (if landed) with **observed** coverage
    from a real run, forecast horizon called out, and base-year `None` noted.
  - `docs/phase-4/IMPLEMENTATION.md`, `docs/phase-4/VALIDATION.md`,
    `docs/phase-4/README.md` mirroring the phase-3/phase-7 report structure and
    recording commands + outcomes.
  - `README.md`: data-source table (IMF/EIA/OPEC status), roadmap Phase 4
    checkboxes, quick-start commands for the new CLIs, and fix the stale
    "23 failing" test-status line (`README.md:308`).
  - `AGENTS.md`: Phase 4 status, new connector/parser files, `source_type`
    usage, forecast-handling convention, and the periodic-helper location.
- **PATTERN:** `docs/phase-3/IMPLEMENTATION.md` and `docs/phase-3/VALIDATION.md`.
- **DEPENDENCIES:** Tasks 10–16 (coverage numbers come from a real run).
- **GOTCHA:** Document discrepancies honestly (AGENTS.md currently says either
  Phase 4 or Phase 7 is next). Do not claim OPEC coverage if the gate failed.
- **VALIDATE:** README commands match `Makefile`; every `docs/` link resolves.

---

## TESTING & VALIDATION

### Unit Tests

- IMF: metadata parsing, IRN filtering, empty-string-key skip, missing
  indicator/country error, vintage/forecast tagging, annual period end,
  pagination-free single request, retry/backoff on 5xx, no retry on 4xx.
- EIA: string-value coercion, blank value → null, invalid value → `ParsingError`,
  `YYYY-MM` → month-end, pagination assembly, `total` string handling, empty
  facets, missing/invalid/placeholder key, 403 not retried, ascending sort.
- OPEC (gated): digit normalisation, table parsing from fixture HTML, missing
  selector → `ParsingError`, mocked Playwright fetch, challenge-page detection.
- Shared: `periods` month-end leap years; `frequency.to_month_end` picks the last
  observation and emits no row for an empty month; `_growth_records` monthly
  lag-1-year, quarterly lag-1-year, annual unchanged, gappy month yields no rate.
- Runner: `run_pipeline` with a fake connector writes Bronze/Silver/Gold through
  one session per indicator and contains per-indicator failures.
- Regression: all existing World Bank, TGJU, utils, and dashboard tests unchanged.

### Integration Tests

- IMF roundtrip: fake HTTP → Bronze (`rows`/`meta`/`raw_response`) → Silver
  (forecast rows retained, `observation_type` recorded) → Gold (levels, YoY for
  level indicators only) and idempotency on re-run.
- EIA roundtrip: monthly crude levels + prior-year YoY in Gold; re-run corrects
  revised values via Silver upsert without duplicating.
- Cross-source sanity: IMF `NGDP_RPCH` and World Bank `NY.GDP.MKTP.KD.ZG`
  overlap for 2000–2024 and should be directionally consistent; assert the
  overlap exists and record the mean absolute difference as an observation (do
  not fail on magnitude — different methodologies).
- OPEC (if landed): daily Silver → month-end Gold across a multi-month fixture.

### Data Validation

- No null/blank observation is stored; skipped counts appear in
  `TransformationLog.record_metadata`.
- Silver upsert keeps one row per `(indicator_id, timestamp)` across re-runs.
- IMF forecast rows are present in Gold with `observation_type` in
  `{estimate, forecast}`; historical rows are `actual`.
- `indicator_catalog.availability_end` for IMF reflects the forecast horizon
  and the metadata records `forecast_through` so the horizon is not mistaken
  for observed history.
- Units fit `String(50)`; derived ids are unique and stable.

### ML Validation

Not applicable this phase — no models or forecasting are built. The only
temporal-correctness obligations are (a) forecasts are labelled as such and
never mixed into historical evaluation, and (b) no interpolation/fill-forward
introduces synthetic precision.

### Edge Cases

- IMF payload contains the empty-string key / `null` value; IRN absent for an
  indicator; forecast years overlap the current year (estimate vs forecast).
- IMF WEO vintage changes (April → October) and a forecast year is revised.
- EIA key missing, placeholder, invalid, or rate-limited (`DEMO_KEY`).
- EIA empty facets (`total: "0"`) vs a genuinely errored request.
- Monthly and quarterly series with a missing prior-year period.
- OPEC returns a Cloudflare challenge instead of data.
- Re-running any pipeline does not create duplicate Silver/Gold rows.
- Bronze `raw_response` size stays acceptable for one IMF indicator (~120 KB).

---

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
make format
make lint
make typecheck
```

### Level 2: Unit Tests

```bash
poetry run pytest tests/unit/etl/test_gold.py tests/unit/utils/test_periods.py \
  tests/unit/etl/test_frequency.py tests/unit/connectors/test_imf.py \
  tests/unit/connectors/test_eia.py -q
make test
```

### Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run alembic upgrade head
poetry run alembic check
make test-integration
make test-all
```

### Level 4: Feature-Specific Validation

```bash
# Dry runs (no writes) — connectivity + parsing only
poetry run python -m src.connectors.world_bank --dry-run   # regression
poetry run python -m src.connectors.imf --dry-run          # forecasts visible
EIA_API_KEY=<real key> poetry run python -m src.connectors.eia --dry-run

# Full runs
poetry run python -m src.connectors.imf
EIA_API_KEY=<real key> poetry run python -m src.connectors.eia

# Live smoke (manual, opt-in)
RUN_LIVE_API_TESTS=1 poetry run pytest -m live
```

### Level 5: Manual Validation

- Query Gold for `IMF.NGDPD` and confirm 1980→2031 with the last five years
  flagged as forecasts:

```sql
SELECT timestamp, value, record_metadata->>'observation_type' AS obs_type
FROM gold.gold_analytical
WHERE indicator_id = 'IMF.NGDPD'
ORDER BY timestamp DESC
LIMIT 10;
```

- Query EIA monthly crude and its derived YoY:

```sql
SELECT indicator_id, timestamp, value
FROM gold.gold_analytical
WHERE indicator_id IN ('EIA.IRN.CRUDE_PRODUCTION', 'EIA.IRN.CRUDE_PRODUCTION.YOY')
ORDER BY indicator_id, timestamp DESC
LIMIT 20;
```

- Open the dashboard (`make dashboard`) and confirm IMF inflation appears on the
  Inflation page, IMF GDP series on GDP & Economy, and EIA crude on Trade,
  Welfare & Energy — no dashboard code change should be required.
- Compare IMF real GDP growth with World Bank `NY.GDP.MKTP.KD.ZG` over the
  common years; record the observation in the phase-4 validation report.

---

## ACCEPTANCE CRITERIA

- [ ] `derived_ret1d_indicator_id("TGJU.USD.FREE", "TGJU") == "TGJU.USD.FREE.RET1D"`;
      World Bank derived ids unchanged; legacy `TGJU.TGJU.%` rows removed by migration
- [ ] `tests/unit/etl/test_gold.py` passes fully (no daily-metrics failures)
- [ ] `run_pipeline(connector, spec)` supports IMF/EIA without copying the World
      Bank runner; `run_world_bank_pipeline` retains its signature and behaviour
- [ ] IMF connector implements all four `DataConnector` methods, fetches IRN
      history **and** WEO forecasts, and tags `actual`/`estimate`/`forecast`
- [ ] EIA connector requires a real API key, pages results, and loads monthly
      Iran crude oil production with the observed TBPD unit
- [ ] Monthly and quarterly `.YOY` series compare against the exact prior-year
      period; annual results unchanged; no interpolation
- [ ] Optional OPEC connector parses fixture HTML and either loads month-end
      basket prices from live access **or** is documented as blocked with no
      false coverage claim
- [ ] `metadata.indicator_catalog` is seeded idempotently for every new indicator
- [ ] `TransformationLog` rows exist for every Bronze→Silver and Silver→Gold run,
      including forecast counts and failures
- [ ] Re-running any new connector produces no duplicate Silver/Gold rows
- [ ] `python -m src.connectors.imf` and `python -m src.connectors.eia` run end
      to end; dry runs need no database
- [ ] Unit tests pass with no network; integration tests pass against Docker;
      live tests are skipped unless `RUN_LIVE_API_TESTS=1`
- [ ] `make check` green; coverage ≥80% overall
- [ ] Data dictionary records observed coverage for every loaded indicator
- [ ] `docs/phase-4/` reports and README/AGENTS/`.env.example` match reality

---

## RISKS & TRADE-OFFS

| Risk | Impact | Mitigation |
|------|--------|------------|
| **OPEC is behind Cloudflare** (verified: challenge HTML, 403 on ASB) | OPEC basket cannot be ingested headlessly | Timeboxed Playwright attempt; ship parser + fixtures regardless; defer live extraction to Phase 5 if blocked and say so explicitly |
| **IMF forecasts are future-dated** and the platform currently drops future periods and errors on them | The headline IMF deliverable (forecasts) would be silently discarded | Opt-in `allow_future` through parser → Silver → validation; explicit `forecast_records` counter; integration test asserting forecasts reach Gold |
| **Generic-runner refactor touches the validated World Bank path** | Regressing Phase 2/3 is the biggest Phase 4 risk | Keep `run_world_bank_pipeline` as a wrapper; run the full unit + integration suites after Task 9 before adding connectors |
| **Derived-id rename orphans existing Gold rows** | Stale `TGJU.TGJU.%` series visible in the dashboard | One-off data migration (Task 2); Gold delete-and-reinsert regenerates correct ids |
| **IMF payload has no server-side filtering** | Each indicator downloads ~120 KB of all-country data | Filter to IRN client-side; store `raw_response` for audit; only ~6 indicators |
| **EIA requires a personal API key** | CI/live tests need a secret; `DEMO_KEY` is shared and rate-limited | Fixtures for unit/integration; `.env` + `EIA_API_KEY` for live; fail fast with an actionable message |
| **Monthly `.YOY` semantics change** | Mis-labelled growth would be a silent data-quality bug | Timestamp-aligned prior-year comparison + explicit monthly/quarterly tests; no interpolation |
| **Unit/coverage gate is global** | A large new surface can fail the gate even when tested | Write tests alongside each module; check coverage after each task |
| **Existing stale docs** (README test counts, AGENTS next-phase) | Misleads the next agent | Task 17 corrects every claim touched by this phase |

### Trade-offs Accepted

1. **Generic runner via a `Protocol` rather than a new base class.** Minimal
   disruption to the validated World Bank path; connectors stay independent.
2. **Store IMF's full multi-country payload as `raw_response`.** Costs ~120 KB
   per indicator but preserves re-parsing and auditability (AGENTS.md).
3. **Forecasts share the Silver/Gold tables with a metadata label.** No schema
   change; consumers must filter `observation_type` when they want history only.
4. **Namespaced indicator ids (`IMF.…`, `EIA.…`, `OPEC.…`).** Slightly longer
   ids, but collision-free and consistent with TGJU; derived ids stay clean via
   the Task 1 fix.
5. **No Airflow DAGs for the new sources this phase.** Monthly cadence is low
   value until the connectors are validated and OPEC access is settled.

### Open Decisions

- **OPEC go/no-go** (Task 13 gate) — resolved during implementation, recorded
  in `docs/phase-4/VALIDATION.md`.
- **OPEC monthly aggregation placement** — pre-resample before `silver_to_gold`
  vs a `target_frequency` option on the Gold transformer. Prefer pre-resample
  (keeps Gold single-responsibility) unless a second monthly-source need appears.
- **IMF forecast horizon and catalog availability.** Confirm whether
  `availability_end` should include the forecast horizon or historical actuals
  only; the plan assumes include-with-`forecast_through`-metadata.
- **EIA `productId=55` vs `53`** as the canonical "crude production" series —
  verify against the EIA browser and PRD wording before seeding the catalog.
- **Whether to also add `NGDPDPC`/`LUR`/`BCA_NGDPD` or keep Phase 4 to the
  PRD's inflation + GDP growth + forecasts MVP.** The plan defaults to the
  six-indicator registry but it can be trimmed without design change.

---

## NOTES

### Discrepancies found during planning

1. **Derived-id bug:** `src/etl/gold.py:97,111` produce
   `TGJU.TGJU.USD.FREE.RET1D`/`.MA30`, while their own docstrings and
   `tests/unit/etl/test_gold.py:793-794` expect `TGJU.USD.FREE.RET1D`/`.MA30`.
   Task 1 resolves it toward the documented id.
2. **Daily-metrics tests fail for a second reason:** `seed_daily_silver` uses
   `session.add` instead of `session.seed`, so `load_silver_series` sees zero
   rows. Task 3 fixes the harness; the README's claim of "10 gold daily-metrics
   tests pending implementation" is inaccurate — the production code exists.
3. **README test status is stale:** 13 Airflow DAG tests now pass (verified);
   `README.md:308` still lists them as failing. Task 17 corrects it.
4. **IMF DataMapper has no server-side filtering** (country path and `periods`
   ignored) and an invalid indicator returns HTTP 200 with a countries payload.
   Both must be handled explicitly or the connector will silently mislead.
5. **OPEC static downloads are Cloudflare-protected**, contradicting the PRD's
   "parse OPEC XML/CSV" assumption. The plan treats OPEC as gated rather than
   pretending the CSV path works.

### Key Design Decisions

1. **Bronze envelopes are always `{"rows": [...], "meta": {...}}`** (plus
   `raw_response` where useful) so `extract_rows()` works uniformly and parsers
   are pure functions over a documented row list. This extends the Phase 2
   World Bank convention rather than inventing a new one.
2. **Parsers live beside their connector as pure modules**, following the TGJU
   scraper/parser split; no parser touches the database or network.
3. **Forecasts are first-class rows, not filtered out.** They carry
   `observation_type` and live in the same tables; temporal-correctness is the
   consumer's responsibility and is documented.
4. **`.YOY` is a prior-year comparison at every supported frequency**, computed
   by exact timestamp alignment, never positional lag or interpolation.
5. **One session per indicator** (existing contract) is preserved by the
   generic runner; a bad indicator still cannot roll back another's work.
6. **Rate indicators are not re-derived.** `NGDP_RPCH`, `PCPIPCH`, `LUR`, and
   `BCA_NGDPD` are already percentages; publishing a YoY of them would be
   meaningless. Only level indicators get derived series.

### Deferred to Later Phases

- Real multi-base-year chain-linking validation (Phase 5, with SCI/CBI).
- Airflow DAGs for IMF/EIA/OPEC monthly cadence.
- Dashboard forecast styling (a distinct visual treatment for
  `observation_type` in `{estimate, forecast}`).
- Any forecasting/ML layer on top of the new series — only after the data is
  validated and leakage rules are designed.

### Success Metrics

After Phase 4 completion:

- [ ] IMF inflation and GDP growth (history + 5-year forecasts) are queryable
      from Gold and visible on the existing dashboard domain pages
- [ ] Iran monthly crude oil production is loaded from EIA with prior-year YoY
- [ ] A new source requires only a connector + parser + `SourceSpec` — no
      changes to `run_pipeline` or the ETL layers
- [ ] IMF real GDP growth and World Bank GDP growth overlap coherently over the
      common years (documented comparison)
- [ ] `make check` and `make test-all` green; the daily-metrics suite that was
      failing now passes

---

## Confidence Assessment

**Confidence: 8/10**

**High confidence because:**

- All three external API contracts were probed live on 2026-09-12 and their
  quirks (IMF ignored filters + empty-string key + future forecasts; EIA string
  values + auth error codes + paging; OPEC Cloudflare block) are documented
  rather than assumed.
- The World Bank connector, ETL layers, parser seam, lineage, retry/rate-limiter,
  and test harnesses are implemented, validated, and directly reusable.
- Every storage/validation constraint that could bite (NOT NULL `value`, dict
  `raw_data`, composite Gold PK, future-date validation, coverage gate) has an
  explicit mitigation and a test.
- The two latent defects blocking the daily-metrics suite were reproduced and
  root-caused during planning, so the prerequisite work is well bounded.

**Remaining uncertainty:**

- **OPEC live access is unproven** and may not be solvable headlessly this phase;
  the plan deliberately makes it gated rather than critical-path.
- **The generic-runner refactor carries regression risk** on the validated
  World Bank/TGJU paths; it is sequenced first, behind the full existing suite.
- **IMF WEO vintage/forecast semantics** (which year counts as estimate vs
  projection) are a convention this plan proposes, not one the API states.
- **EIA canonical facet choice** (`productId` 55 vs 53) and the real coverage
  per indicator will only be confirmed by a real keyed run.
- **Monthly `.YOY` changes shared Gold behaviour**; the annual path is asserted
  unchanged, but any consumer assuming lag-1 semantics for monthly data must be
  re-checked (none exists today).

**Recommendation:** Proceed. Do Tasks 1–9 first and re-run the existing unit and
integration suites before writing any new connector — that de-risks the runner
refactor and unblocks the already-built daily derivation. Then deliver IMF and
EIA, and treat OPEC as a timeboxed stretch with an explicit documented outcome.

**Confidence in the implementation plan: 8/10.**
