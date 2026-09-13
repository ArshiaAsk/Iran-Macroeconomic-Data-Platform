# Task: Phase 5 — CBI TSD & SCI Domestic Scrapers (Monetary, CPI, Unemployment) with Real Multi-Base-Year Chain-Linking

## Task Description

Build the platform's first **complex domestic source** integrations and its first
**real multi-base-year chain-linking** on live data:

1. A **Statistical Center of Iran (SCI, `amar.org.ir`) scraper** that collects
   headline and decile-level **CPI** (monthly index, multiple base years 2011 /
   2016 / 2021) and **unemployment** (quarterly, percent) from Excel / PDF / HTML
   publications, landing raw files in Bronze.
2. A **Central Bank of Iran (CBI TSD, `tsd.cbi.ir`) scraper** that collects
   **monetary aggregates** (`M0` monetary base, `M2` liquidity, money multiplier)
   and the **Tehran housing price index** from the legacy TSD system (Excel /
   web tables), landing raw files in Bronze.
3. The **platform change that makes (1) possible**: teach `src/etl/gold.py` to
   chain-link **overlapping published base-year segments** via the existing
   (currently unused outside unit tests) `chain_link(metadata={"segments": ...})`
   path, and store every segment's original and linked values with an audit row
   in `metadata.chain_linking_log`.

**Why:** Every prior phase ingested sources that are either clean APIs or
single-value, single-base-year scrapes. Phase 5 is where the platform's headline
promise — *automated chain-linking of base-year discontinuities* — is proven on
the real case it was designed for: SCI's CPI, published as separate series on
2011, 2016, and 2021 bases with overlapping periods and no official linked
history. It is also the first **file-based** (Excel/PDF) ingestion and the first
source whose availability is genuinely uncertain.

**PRD mapping:** Phase 5 = PRD §10 Task 12 (CBI TSD scraper for monetary
aggregates) and Task 13 (SCI scraper for CPI and unemployment). Timeline:
Week 5–6. Also exercises AGENTS.md rules for scrapers (parser/scraper split,
Persian handling, Playwright, 1–2 req/sec, raw HTML/Excel in Bronze) and for
chain-linking (12-month overlap, ±1% growth preservation, confidence score,
audit trail, reversibility).

## Scope

### In Scope

- [ ] **Reconnaissance + decision gate** (first task, may adjust everything
      downstream): capture real SCI/CBI pages, Excel/PDF files and HTML as
      fixtures; decide which sources proceed and record evidence either way
- [ ] **Shared Persian helpers**: extract `normalise_digits`, `parse_price`,
      `jalali_to_gregorian`, and a Jalali month-name map from `tgju_parser.py`
      into `src/utils/persian.py` (AGENTS.md: shared utilities live in
      `src/utils/`), with `tgju_parser.py` importing them (behaviour-preserving)
- [ ] **SCI parser** (`src/connectors/sci_parser.py`): pure functions turning
      SCI Excel sheets, PDF tables, and HTML tables into tidy frames, tagged
      with the publication's `base_year`
- [ ] **SCI scraper/connector** (`src/connectors/sci_scraper.py`): discovery +
      file download + Bronze raw-file persistence + Silver upsert for CPI
      (headline + deciles) and unemployment, registered via a
      `SCI_INDICATOR_REGISTRY`
- [ ] **CBI parser + scraper** (`src/connectors/cbi_parser.py`,
      `cbi_scraper.py`): monetary aggregates and housing index — **gated** by
      Task 1; not implemented if the F5 bot-defense gate is closed
- [ ] **Gold multi-segment chain-linking**: extend `silver_to_gold` to accept
      `segment_indicator_ids`, load each base-year segment from Silver, and pass
      them to the existing `chain_link(metadata={"segments": [...]})` overlap
      path; publish one canonical, linked series per indicator
- [ ] **Segment storage model**: each published base-year series is stored in
      Silver under its own indicator id (e.g. `SCI.CPI.HEADLINE.B2016`) so the
      `uq_silver_indicator_timestamp` constraint is respected, with
      `record_metadata.base_year` recorded; canonical linked id is
      `SCI.CPI.HEADLINE`
- [ ] **Bronze file envelope**: base64 raw bytes + `sha256` / `content_type` /
      `filename` / `byte_length` metadata, alongside parsed `rows`, with a
      configurable size guard
- [ ] **Config**: SCI/CBI base URLs, file-size guard, per-source timeouts and
      rate limits in `src/utils/config.py` + `.env.example`
- [ ] **CLI + runner** for each source: `python -m src.connectors.sci_scraper`
      and (if gated open) `python -m src.connectors.cbi_scraper`, with
      `--dry-run` touching no database (mirror TGJU)
- [ ] **Airflow DAGs**: weekly SCI check (and CBI if enabled), mirroring
      `airflow/dags/tgju_daily.py`
- [ ] **Unit tests** (parser fixtures for Excel/PDF/HTML, Persian helpers,
      multi-segment linking, growth preservation) and **integration tests**
      (Bronze → Silver → Gold roundtrip with three overlapping base-year
      segments, idempotent re-run, chain-linking audit row)
- [ ] **Live tests** gated behind `RUN_LIVE_API_TESTS=1` + `@pytest.mark.live()`
- [ ] Docs: `docs/phase-5/README.md`, `IMPLEMENTATION.md`, `VALIDATION.md`;
      `docs/phase-2/data_dictionary.md` extended with observed SCI/CBI coverage;
      README/AGENTS/.env.example updates

### Out of Scope

- [ ] TSETMC / HBSIR package connectors (Phase 6)
- [ ] New dashboard pages — CPI/monetary indicators appear automatically on the
      existing Inflation / Monetary domain pages via
      `metadata.indicator_catalog.domain`
- [ ] CI/CD, backup automation, performance tuning (Phase 8)
- [ ] Forecasting / nowcasting / any ML model — this phase is collection,
      cleaning, and chain-linking only
- [ ] Intraday or real-time capture; SCI/CBI publish monthly/quarterly with
      multi-month lags
- [ ] Object storage / S3-style raw-file store — raw files live as base64 in
      Bronze JSONB for MVP (see risks)
- [ ] Retrofitting chain-linking into already-published World Bank / IMF / EIA /
      TGJU Gold rows — those sources carry no base-year breaks
- [ ] A complete historical sweep of every SCI publication back to inception;
      the MVP targets the published multi-base-year CPI window and is
      registry-extensible

## Context

### Current state (verified 2026-09-13)

- Phases 1, 2, 3, 4, and 7 are complete and committed on `development`; working
  tree clean, in sync with `origin/development`. Latest commit `7764abf`.
- The connector/scraper pattern is established twice: the API reference is
  `src/connectors/world_bank.py` driven by `SourceSpec` +
  `run_pipeline` (`src/etl/pipeline.py:468`); the scraper reference is
  `src/connectors/tgju_scraper.py` + `tgju_parser.py` with its own
  `run_tgju_pipeline`.
- `src/connectors/base.py` defines `DataConnector` and `IndicatorMetadata`
  (including `has_base_year_changes` and `base_years`).
- **The chain-linking algorithm already implements overlap splicing but the
  platform never exercises it.** `chain_link` (`src/chain_linking/splice.py:507`)
  gives `metadata["segments"]` precedence over `base_years`; when segments are
  supplied it calls `_chain_link_segments` (`splice.py:578`), the rigorous
  **overlap** method that satisfies AGENTS.md's 12-month-overlap and ±1%
  growth-preservation rules. However, `silver_to_gold` (`src/etl/gold.py:554`)
  only ever passes `metadata={"base_years": resolved_base_years}` from the
  catalog (`gold.py:592-596`). No source produces `segments`, so that path is
  currently covered by unit tests only.
- `detect_base_year_breaks` deliberately defaults `statistical_fallback=False`:
  a level jump alone cannot distinguish a rebase from an economic shock. This is
  the platform's contract and Phase 5 must supply **real overlapping segments**,
  not guess breaks.
- `bronze_to_silver` (`src/etl/silver.py:289`) already exposes the `parser`
  seam and `allow_future`; Silver upserts on
  `uq_silver_indicator_timestamp`.
- `src/etl/frequency.py` (`to_month_end`, `aggregate_to_monthly`) exists and is
  tested but currently unused — daily→monthly only, so it is **not** required
  for CPI (already monthly).
- `src/utils/periods.py` provides `month_period_end`, `annual_period_end`,
  `parse_period`, `year_earlier`; `gold.py` uses `year_earlier` so monthly CPI
  YoY is exact across leap years.
- `src/utils/config.py` has `APIConfig` (World Bank / IMF / EIA / TGJU) and
  `CollectionConfig` (`scraper_min_request_interval`, `scraper_page_timeout`);
  there is **no CBI or SCI setting**.
- `openpyxl ^3.1.0` is already a dependency (dashboard exports use it);
  **`pdfplumber` and `xlrd` are NOT declared**. SCI/CBI publish `.xlsx`, legacy
  `.xls`, and PDFs.
- `IndicatorCatalog` already has `has_base_year_changes` and `base_years`
  (`src/database/schema.py`), and `ChainLinkingLog` has `base_year_from`,
  `base_year_to`, `linking_method`, `records_linked`, `avg_confidence_score`,
  `overlap_period_months`, `growth_rate_variance` — **no migration is expected**
  for this phase.
- `tests/integration/test_tgju_pipeline.py:91` provides `FakePage` /
  `FakeBrowser` for mocked-playwright integration tests — mirror this.
- No CI workflows exist (`.github/workflows` absent); quality gates are local
  `make` targets.

### Data flow this phase must realise

```text
SCI (amar.org.ir)                              CBI (tsd.cbi.ir)   [gated]
  Excel / PDF / HTML publications                Excel / web tables
        ↓  SciScraper.fetch_series(segment)             ↓  CbiScraper.fetch_series()
        ↓  sci_parser (pure)                            ↓  cbi_parser (pure)
bronze.bronze_raw   {"rows":[...], "meta":{base_year, sha256, content_type,
                     filename, byte_length, raw_file_base64}}
        ↓  src/etl/silver.py (parser seam)
silver.silver_cleaned    SCI.CPI.HEADLINE.B2011 / .B2016 / .B2021  (+ deciles,
                         unemployment; CBI M0/M2/multiplier/housing)
        ↓  src/etl/gold.py  silver_to_gold(..., segment_indicator_ids=[...])
        ↓  chain_link(metadata={"segments": [...newest base last...]}, frequency="monthly")
gold.gold_analytical     SCI.CPI.HEADLINE (linked levels + original_value +
                         is_chain_linked + confidence) and .YOY derived series;
                         metadata.chain_linking_log audit row
```

### Verified source reconnaissance (probed 2026-09-13)

These are the **only** live facts this plan rests on; everything else about
selectors and file formats is a hypothesis to be confirmed in Task 1.

| Target | Result |
|--------|--------|
| `https://tsd.cbi.ir/` (https and http) | **No response** — repeated `curl` connection timeouts (HTTP `000`) from this environment, across several attempts |
| `https://www.cbi.ir/` | HTTP **200** but the body contains F5 BIG-IP ASM bot-defense markers (`TSPD`, `bobcmn` challenge script); `https://www.cbi.ir/robots.txt` returns the **challenge page**, not a policy |
| `https://www.amar.org.ir/robots.txt` | HTTP **200**, permissive for data paths; `Disallow` only for `/admin/`, `/App_*/`, `/bin/`, `/images/`, `/Resources/…`, `/activity-feed/`, etc. — the statistics/portal content we need is not disallowed |
| `https://www.amar.org.ir/` | HTTP **301** → `http://amar.org.ir/english`; bare `/english` and `/Portals/0` also 301. Server is a DNN/ASP.NET portal (ASP.NET robots template); TLS chain is non-standard and `curl` needs `-k` or a proper CA bundle |
| `www.amar.org.ir` content | CSP references `rpt.sci.org.ir:4040` and the site serves HTML/Excel/PDF rather than an API — consistent with the research doc's "Excel / PDF / `pdfplumber`" assessment |

**Interpretation.** SCI is likely scraperable under its own `robots.txt`.
CBI's main domain is protected by an F5 bot-defense challenge and its TSD
subdomain did not answer at all — this is the same *class* of problem that got
OPEC deferred in Phase 4. The plan therefore makes CBI an explicit **gated
deliverable** with the same "record evidence, do not bypass" rule from
AGENTS.md/Phase 4, while SCI is the committed deliverable.

### Chain-linking facts that shape the design

- `_chain_link_segments(segments, frequency)` expects segments **ordered oldest
  base first, newest base last**, and links each older segment onto the newest
  combined series by **ratio over the overlap**. `frequency="monthly"` requires
  `min_overlap_periods("monthly") == 12` observations and treats each period as
  1 month (`months_per_period("monthly") == 1`).
- `splice_series` asserts growth preservation within `GROWTH_TOLERANCE` (±1%)
  during overlap and raises `ChainLinkingError` on distortion.
- The linked frame carries `original_value`, `scale_factor`, and
  `is_chain_linked`; Gold already writes these plus `chain_linking_confidence`
  and the `ChainLinkingLog` row.
- **Critical constraint:** `uq_silver_indicator_timestamp` is
  `(indicator_id, timestamp)`. Overlapping base-year publications share
  timestamps, so they cannot share an indicator id. Segments must be stored
  under distinct segment ids; the canonical linked series is produced in Gold.

## Proposed Approach

Reuse the proven patterns rather than inventing new architecture:

1. **Reconnaissance first, gated.** Task 1 captures real fixtures and decides
   which sources proceed. It is a checkpoint: if SCI's publication format is
   different from every hypothesis, Tasks 4–5 change; if CBI's F5 challenge
   cannot be satisfied by ordinary browser navigation (as opposed to a bypass),
   CBI is recorded as blocked and deferred exactly like OPEC.
2. **Pure parsers, thin scrapers.** `sci_parser.py` / `cbi_parser.py` contain
   all format-specific logic (Excel sheet layout, PDF table extraction, HTML
   tables, Persian digits, Jalali dates) and carry the bulk of test coverage;
   `sci_scraper.py` / `cbi_scraper.py` handle navigation, download, rate
   limiting, and Bronze persistence. This mirrors TGJU and AGENTS.md.
3. **Shared Persian utilities.** Extract the reusable digit/price/Jalali logic
   from `tgju_parser.py` into `src/utils/persian.py` and have `tgju_parser`
   import it, so SCI/CBI do not copy it. This is a behaviour-preserving refactor
   guarded by the existing TGJU parser tests.
4. **Segment ids in Silver, canonical id in Gold.** Each published base-year
   series (`…B2011`, `…B2016`, `…B2021`) is a distinct Silver indicator so the
   unique constraint is respected and the raw publication is preserved
   ("reversibility"). The canonical `SCI.CPI.HEADLINE` is produced by Gold from
   the segments.
5. **Exercise the existing overlap algorithm.** Extend `silver_to_gold` with an
   optional `segment_indicator_ids` parameter; when supplied, load each segment
   from Silver and call
   `chain_link(frame=…, metadata={"segments": [oldest, …, newest]}, frequency=…)`.
   No new chain-linking algorithm is written; the tested `_chain_link_segments`
   path is finally used in production.
6. **Raw files as base64 + checksum.** Bronze stores parsed `rows` plus the raw
   file as base64 with `sha256`/`content_type`/`filename`/`byte_length` under
   `meta`, behind a configurable size guard. This keeps AGENTS.md's
   "re-parse without re-scraping" promise without introducing object storage.
7. **Orchestration holds no logic.** DAGs import and call the connector's
   runner, exactly like `tgju_daily`.

## Task Metadata

**Type:** New Capability + Data Pipeline Change
**Complexity:** High
**Affected Areas:** `src/connectors/` (new parsers/scrapers), `src/utils/persian.py` (new), `src/etl/gold.py` (segment linking), `src/etl/bronze.py` (file envelope if needed), `src/utils/config.py`, `airflow/dags/`, `tests/{unit,integration,fixtures}/`, `docs/`
**Dependencies:** existing `playwright`, `beautifulsoup4`, `lxml`, `pandas`, `openpyxl`, `jdatetime`; **new**: `pdfplumber` (PDF tables) and `xlrd` (legacy `.xls`) — add to `pyproject.toml` only if Task 1 confirms the formats

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `src/connectors/tgju_scraper.py` — the scraper template: injected `Browser` + `RetryPolicy` + `RateLimiter`, `Config` dataclass, `FetchResult.collection_metadata()`, `discover()`, `fetch_series()`, `run_*_pipeline`, `main()` CLI, context-manager cleanup
- `src/connectors/tgju_parser.py` — pure-parser template, Persian digit normalisation, `jalali_to_gregorian`, timestamp idempotency, `ParsingError` usage
- `src/connectors/base.py` — `DataConnector` protocol and `IndicatorMetadata` (including `has_base_year_changes`, `base_years`)
- `src/connectors/world_bank.py` — API-reference config/`fetch_series`/`build_spec` pattern
- `src/etl/gold.py` — `silver_to_gold` (`:554`), `_level_records`, `_growth_records`, `_write_chain_linking_log` (`:495`), `_replace_gold_rows` (`:541`), derived-id helpers
- `src/chain_linking/splice.py` — `chain_link` (`:507`), `_chain_link_segments` (`:578`), `calculate_confidence`, `min_overlap_periods`, `months_per_period`, growth-preservation assert
- `src/etl/silver.py` — `bronze_to_silver` (`:289`, `parser`/`allow_future` seam), `load_silver_series` (`:390`), `write_silver`
- `src/etl/bronze.py` — `wrap_envelope` (`:43`), `extract_rows` (`:70`), `write_bronze` (`:95`)
- `src/etl/pipeline.py` — `SourceSpec`/`SeriesConnector`/`FetchResult`, `run_pipeline` (`:468`), `run_cli` (`:585`), `upsert_indicator_catalog` (`:275`), `update_catalog_availability` (`:330`)
- `src/utils/config.py` — `AppConfig` / `APIConfig` / `CollectionConfig` pattern
- `src/utils/retry.py` — `RetryPolicy` / `RateLimiter`
- `src/utils/periods.py` — `month_period_end`, `year_earlier`
- `src/database/schema.py` — `IndicatorCatalog` (`base_years`, `has_base_year_changes`), `SilverCleaned` unique constraint, `ChainLinkingLog`
- `tests/integration/test_tgju_pipeline.py` — `FakePage`/`FakeBrowser`, Bronze→Silver→Gold roundtrip, idempotent re-run
- `tests/unit/connectors/test_tgju_parser.py` — fixture-driven parser test style
- `tests/unit/chain_linking/test_splice.py` — how multi-segment linking and growth preservation are proven
- `airflow/dags/tgju_daily.py` — DAG template (schedule, timezone, task calling the runner)
- `docs/plans/phase-3-tgju-scraper.md` — conventions this plan mirrors

### Data / ML References

- `docs/research/init-research.md` §3 (SCI/CBI coverage and limitations) and §4 (access table: SCI Excel/PDF + `pdfplumber`, CBI TSD Excel/web table)
- `docs/phase-2/data_dictionary.md` — the observed-coverage format new SCI/CBI entries must follow
- `docs/phase-4/VALIDATION.md` — the OPEC "blocked, not implemented" precedent and evidence format for the CBI gate
- `PRD.md` §10 Tasks 12–13 — the authoritative indicator list and demos this phase must satisfy

### External Documentation

- `https://www.amar.org.ir/robots.txt` — re-check at implementation time; capture a snapshot as evidence
- `https://tsd.cbi.ir` — verify reachability from the target network before any work; capture evidence
- `https://pypi.org/project/pdfplumber/` — `extract_tables()` API for PDF tables
- `https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html` — `sheet_name`/`engine` handling for `.xlsx` vs `.xls`
- `https://playwright.dev/python/docs/api/class-download` — `expect_download()` for file downloads

### Patterns to Follow

**Naming:** `src/connectors/sci_scraper.py` + `sci_parser.py` (scraper/parser split per AGENTS.md); ids `SCI.CPI.HEADLINE`, `SCI.CPI.HEADLINE.B2016`, `SCI.UNEMPLOYMENT.RATE`, `CBI.M0`, `CBI.M2`, `CBI.MONEY.MULTIPLIER`, `CBI.HOUSING.TEHRAN`

**Structure:** one connector per file; registry dict `path → (indicator_id, name, domain, base_year)`; config as a frozen-ish dataclass with `get_config()` defaults; `fetch_series()` returns a result object carrying `frame`, `raw_envelope`, `request_url`, `http_status_code`, and `collection_metadata()`

**Testing:** parser fixtures under `tests/fixtures/{sci,cbi}/`; mock the browser with `FakePage`/`FakeBrowser`; integration tests use fixtures, never live scraping; live tests behind `RUN_LIVE_API_TESTS=1` + `@pytest.mark.live()`

**Data/ML:** never fill nulls; upsert Silver on `(indicator_id, timestamp)`; Gold deletes-and-reinserts per indicator; chain-link only from explicit base years or overlapping segments; store `original_value` always and `is_chain_linked` per row; keep Persian source dates in `record_metadata`

**Security/politeness:** 1–2 req/sec via `RateLimiter`, honest `User-Agent`, respect `robots.txt`, never bypass an access-control challenge, never log full raw files

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

Reconnaissance and the source gate come first; then dependencies, shared Persian
helpers, config, and the multi-segment Gold capability (which is independent of
either scraper and can be built and tested against synthetic segments).

### Phase 2: Core Change

SCI parser, SCI scraper/connector, then the (gated) CBI parser/scraper.

### Phase 3: Integration

Runner + CLI, catalog seeding (canonical active, segments inactive), Airflow
DAG, data-dictionary and docs updates.

### Phase 4: Validation

Unit + integration + gated live tests, full roundtrip and chain-linking
validation, then the Phase 5 validation report.

---

## STEP-BY-STEP TASKS

Execute tasks in dependency order. **Task 1 is a checkpoint** — do not start
Tasks 4–8 until its fixtures exist; do not implement CBI (Tasks 6–7) unless the
gate criteria in Task 1 are met.

### RECONNOISSANCE + CAPTURE FIXTURES (sci, cbi)

- **IMPLEMENT:** Using a real browser (Playwright, `headless=False` for manual
  inspection if needed), locate the current SCI CPI / unemployment publication
  pages and the CBI TSD monetary/housing pages. Save real `.xlsx` / `.xls` /
  `.pdf` / HTML files under `tests/fixtures/sci/` and `tests/fixtures/cbi/`.
  Record in `tests/fixtures/sci/SOURCES.md` / `.../cbi/SOURCES.md`: exact URL,
  retrieval date, HTTP status, content-type, byte length, sha256, and the file's
  internal structure (sheet names, header rows, units, base year, Jalali vs
  Gregorian labels). Re-fetch `robots.txt` and save the response as evidence.
  **Decision gate:** SCI proceeds if `robots.txt` permits the path and a normal
  browser load yields a genuine publication. CBI proceeds only if a normal
  browser load yields genuine data (not an F5 challenge/captcha); otherwise write
  the evidence into `docs/phase-5/VALIDATION.md`, leave CBI unimplemented, and
  continue with SCI.
- **PATTERN:** `tests/fixtures/tgju/SOURCES.md`, `docs/phase-4/VALIDATION.md` (OPEC gate evidence format)
- **DEPENDENCIES:** local Playwright Chromium (`poetry run playwright install chromium`); outbound network
- **GOTCHA:** Do **not** build a workaround for a bot-defense challenge. Passing a
  challenge by scripting around it is a bypass (same ruling as OPEC). A normal
  browser session rendering the site is acceptable; a captcha/JS challenge is a
  stop signal. SCI uses a non-standard TLS chain — verify the certificate
  deliberately rather than defaulting to `verify=False`.
- **VALIDATE:** `ls tests/fixtures/sci tests/fixtures/cbi` and
  `test -f tests/fixtures/sci/SOURCES.md`; re-run `curl -ksS -o /dev/null -w "%{http_code}" https://www.amar.org.ir/robots.txt`

### ADD pdfplumber, xlrd dependencies

- **IMPLEMENT:** Add `pdfplumber = "^0.11"` and, only if Task 1 captures a legacy
  `.xls` file, `xlrd = "^2.0"` to `[tool.poetry.dependencies]`; run
  `poetry lock`; add a short note in `docs/phase-5/IMPLEMENTATION.md` explaining
  why each is needed.
- **PATTERN:** `pyproject.toml` existing dependency block; `openpyxl` already
  present for `.xlsx`
- **DEPENDENCIES:** Task 1 findings
- **GOTCHA:** `xlrd>=2.0` no longer reads `.xlsx` (only `.xls`); do not replace
  `openpyxl`. `pdfplumber` pulls `pdfminer.six`; keep it a runtime dependency
  only if PDF parsing is confirmed.
- **VALIDATE:** `poetry run python -c "import pdfplumber, pandas; print('ok')"`

### CREATE src/utils/persian.py

- **IMPLEMENT:** Move `PERSIAN_DIGITS`, `ARABIC_INDIC_DIGITS`, `PERSIAN_TO_ASCII`,
  `ARABIC_INDIC_TO_ASCII`, `normalise_digits`, `parse_price`,
  `jalali_to_gregorian`, and the Persian month-name map from
  `src/connectors/tgju_parser.py` into a new pure module `src/utils/persian.py`.
  Add a `parse_jalali_ymd` helper for the `YYYY/MM/DD` Jalali strings SCI files
  commonly use (Jalali year `1405` etc.). Update `tgju_parser.py` to import and
  re-export these names so `test_tgju_parser.py` passes unchanged.
- **PATTERN:** `tgju_parser.py` function bodies verbatim; `src/utils/periods.py` for module style
- **DEPENDENCIES:** none
- **GOTCHA:** Keep `ParsingError` from `src.utils.exceptions` (not `ValueError`).
  This is a behaviour-preserving move — do not change regexes or timezone
  handling. Persian month names contain `RUF001`-class characters; add the new
  file to the appropriate ruff `per-file-ignores` only if needed, mirroring the
  existing `tgju_parser.py` entry.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_tgju_parser.py -q --no-cov`

### UPDATE src/utils/config.py + .env.example

- **IMPLEMENT:** Add to `APIConfig`: `sci_base_url`
  (`https://www.amar.org.ir`, alias `SCI_BASE_URL`) and `cbi_tsd_url`
  (`https://tsd.cbi.ir`, alias `CBI_TSD_URL`). Add to `CollectionConfig`:
  `scraper_max_download_bytes` (alias `SCRAPER_MAX_DOWNLOAD_BYTES`, default
  e.g. `10_000_000`) and `scraper_download_timeout` (alias
  `SCRAPER_DOWNLOAD_TIMEOUT`, default 60) with validators mirroring the existing
  ones. Mirror every new variable into `.env.example` with comments (and note
  that CBI is gated).
- **PATTERN:** `CollectionConfig.scraper_page_timeout` + its validator
  (`src/utils/config.py`), `.env.example` comment blocks
- **DEPENDENCIES:** none
- **GOTCHA:** `BaseSettings` with `populate_by_name=True`; keep aliases
  uppercase and defaults config-driven — no hardcoded URLs in connector logic.
- **VALIDATE:** `poetry run pytest tests/unit/utils/test_config.py -q --no-cov`

### UPDATE src/etl/gold.py — multi-segment chain-linking

- **IMPLEMENT:** Add an optional `segment_indicator_ids: Sequence[str] | None`
  parameter to `silver_to_gold`. When supplied (and non-empty):
  1. load each segment with `load_silver_series(session, segment_id)`;
  2. order oldest base first by each segment's `record_metadata.base_year`
     (fall back to segment order and warn if absent);
  3. skip/raise if any segment is empty (`ChainLinkingError` with a clear
     message);
  4. call `chain_link(frame=<newest>, metadata={"segments": [...]}, frequency=<frequency>)`
     so the existing `_chain_link_segments` path runs;
  5. publish levels + derived YoY under the canonical `indicator_id` and write
     the `ChainLinkingLog` row as today.
  Keep the current single-series behaviour when `segment_indicator_ids` is
  omitted. Add a small helper `load_base_year_segments(session, ids)` for
  testability.
- **PATTERN:** `silver_to_gold` (`src/etl/gold.py:554`) and its existing
  `chain_link(metadata={"base_years": ...})` call (`:592-596`);
  `_chain_link_segments` contract (`src/chain_linking/splice.py:578`)
- **DEPENDENCIES:** none (can be built before the scrapers)
- **GOTCHA:** `_chain_link_segments` raises `ChainLinkingError` when a pair lacks
  `min_overlap_periods(frequency)` — with `monthly` that is **12 overlapping
  months**. Segment ordering is load-bearing (oldest first). The derived YoY
  helper already uses `year_earlier`, so no change there. Do not fabricate
  confidence for unlinked data.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_gold.py tests/unit/chain_linking/test_splice.py -q --no-cov`

### CREATE src/connectors/sci_parser.py

- **IMPLEMENT:** Pure functions (no I/O, no browser):
  - `parse_cpi_excel(path_or_bytes, base_year, ...)` → tidy frame
    (`timestamp`, `value`, `indicator_id`, `unit`, `obs_status`, plus
    `base_year`), handling sheet selection, header offset, Persian digits,
    Jalali `YYYY/MM` labels → `month_period_end`, and unit normalization
    (`index` vs `percent`).
  - `parse_cpi_pdf(path_or_bytes, base_year, ...)` using `pdfplumber.extract_tables()`.
  - `parse_cpi_html(html, base_year, ...)` using BeautifulSoup for table pages.
  - `parse_unemployment_excel/pdf(...)` for quarterly headcount rates.
  - `detect_base_year(text_or_filename)` → `int | None`, and
    `split_segments(...)` if a single workbook carries multiple base years.
  All raise `ParsingError` (never bare `ValueError`) and set `obs_status="A"`.
  Set `record_metadata`/frame fields for `base_year` and the original Persian
  period label.
- **PATTERN:** `src/connectors/tgju_parser.py` (pure, fixture-tested, `ParsingError`),
  `src/utils/periods.month_period_end`, `src/utils/persian.py` (Task 3)
- **DEPENDENCIES:** Task 1 fixtures; `pdfplumber`/`openpyxl`/`xlrd` (Task 2)
- **GOTCHA:** Persian digits and Jalali dates are the top parsing risk; never
  guess base years from values (`statistical_fallback` is off by policy). SCI
  splices CPI on the **index** and reports inflation as derived YoY — do not
  chain-link percentages. Preserve the original Jalali label in metadata.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_sci_parser.py -q --no-cov`

### CREATE src/connectors/sci_scraper.py

- **IMPLEMENT:** `SciConfig` dataclass (base URL, registry, page timeout,
  download timeout, max bytes, UA, headless); `SCI_INDICATOR_REGISTRY` mapping
  publication → `(indicator_id, name, domain, frequency, base_year)`;
  `SciFetchResult` with `frame`, `raw_envelope` (base64 file + `sha256` +
  `content_type` + `filename` + `byte_length` + parsed `rows`),
  `request_url`, `http_status_code`, and `collection_metadata()`;
  `SciScraper(DataConnector)` with injected `Browser`/`RetryPolicy`/`RateLimiter`,
  `discover()`, `fetch_series(indicator_id)` (download via
  `page.expect_download()` or `requests` for direct file links),
  `validate()`, `disconnect()` owning only what it created; `run_sci_pipeline()`
  and `main()` CLI with `--dry-run` and `--indicators`, mirroring
  `run_tgju_pipeline`.
- **PATTERN:** `src/connectors/tgju_scraper.py` (whole file);
  `Playwright expect_download` docs
- **DEPENDENCIES:** Tasks 1–5; `src/etl/bronze.write_bronze`,
  `src/etl/silver.bronze_to_silver(parser=...)`,
  `src/etl/gold.silver_to_gold(segment_indicator_ids=...)`
- **GOTCHA:** The unit of Bronze for a file source is the **file**, not a value:
  wrap as `{"rows": [...parsed...], "meta": {...}}` and keep `raw_file_base64`
  inside `meta` under the size guard. Do not use `extract_rows()` for the raw
  file (it expects a `rows` list). Segment ids must be distinct
  (`…B2011`/`…B2016`/`…B2021`); the canonical id is created only by Gold.
  `RateLimiter.wait()` before every request; cite `robots.txt` in the docstring.
- **VALIDATE:** `poetry run python -m src.connectors.sci_scraper --dry-run`

### CREATE src/connectors/cbi_parser.py — ONLY IF CBI GATE OPEN

- **IMPLEMENT:** Pure functions parsing TSD Excel/web-table monetary aggregates
  (`M0`, `M2`, multiplier) and the Tehran housing index; Persian/Jalali handling
  via `src/utils/persian.py`; `ParsingError` on malformed tables.
- **PATTERN:** `sci_parser.py` / `tgju_parser.py`
- **DEPENDENCIES:** Task 1 gate open + fixtures
- **GOTCHA:** If the gate is closed, do **not** create this file; record the
  evidence instead (AGENTS.md/OPEC precedent).
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_cbi_parser.py -q --no-cov`
  (or skip when gated)

### CREATE src/connectors/cbi_scraper.py — ONLY IF CBI GATE OPEN

- **IMPLEMENT:** `CbiConfig`, `CBI_INDICATOR_REGISTRY`, `CbiScraper` and runner
  mirroring `sci_scraper.py`, pointing at `config.cbi_tsd_url`, with the same
  Bronze file envelope and `--dry-run` CLI.
- **PATTERN:** `sci_scraper.py`
- **DEPENDENCIES:** Task 6
- **GOTCHA:** Same bot-defense rule as Task 1; if any request yields a challenge
  page, abort the run with a clear error and record it rather than retrying into
  a bypass.
- **VALIDATE:** `poetry run python -m src.connectors.cbi_scraper --dry-run`
  (or documented as gated)

### CREATE SQL/runner wiring for segments + catalog

- **IMPLEMENT:** In the SCI runner, after each segment's `bronze_to_silver`,
  call the new `silver_to_gold(..., segment_indicator_ids=[...])` for the
  canonical indicator once all segments for that indicator have been persisted.
  Seed the catalog with `discover()` such that canonical indicators are active
  and `B<year>` segment ids are seeded with `is_active=False` (so the dashboard
  shows the linked series, not raw segments). Set
  `has_base_year_changes=True` and `base_years=[2011, 2016, 2021]` on canonical
  CPI entries (the existing catalog columns exist — no migration).
- **PATTERN:** `src/etl/pipeline.upsert_indicator_catalog` (`:275`) and
  `update_catalog_availability` (`:330`);
  `tests/unit/etl/test_gold.py` `derived_*` patterns
- **DEPENDENCIES:** Tasks 5 and 5b (gold extension)
- **GOTCHA:** `IndicatorCatalog.indicator_id` is the primary key, so seeding is
  an upsert; keep `availability_start/end` sourced from observed data. Do not
  chain-link before all segments exist, or the overlap check will fail.
- **VALIDATE:** `poetry run pytest tests/integration/test_sci_pipeline.py -q`

### CREATE airflow/dags/sci_weekly.py (+ cbi if open)

- **IMPLEMENT:** Weekly DAG at a low-traffic Tehran time that calls
  `run_sci_pipeline()` (mirroring `tgju_daily.py`; no logic in the DAG), with
  retries and failure logging. Add a `make` target if TGJU has one.
- **PATTERN:** `airflow/dags/tgju_daily.py`, `tests/unit/airflow/test_dag_import.py`
- **DEPENDENCIES:** Task 8
- **GOTCHA:** AGENTS.md cadence: weekly for SCI/CBI. DAG import must not open a
  database connection at parse time.
- **VALIDATE:** `poetry run pytest tests/unit/airflow/test_dag_import.py -q --no-cov`

### UPDATE docs (data dictionary, README, AGENTS, phase-5)

- **IMPLEMENT:** Add SCI (and CBI, if implemented) sections to
  `docs/phase-2/data_dictionary.md` with **observed** coverage from a real run
  (indicator id, unit, domain, base years, coverage, Silver/Gold counts, known
  gaps). Create `docs/phase-5/README.md`, `IMPLEMENTATION.md`, and
  `VALIDATION.md` (record the CBI gate evidence and the live-run commands and
  results). Update the README roadmap/status line and the AGENTS.md structure
  tree (replace the `cbi_scraper.py, sci_scraper.py — later phases` comment).
- **PATTERN:** `docs/phase-2/data_dictionary.md`, `docs/phase-3/README.md`, `docs/phase-4/VALIDATION.md`
- **DEPENDENCIES:** Tasks 1–9
- **GOTCHA:** Distinguish documented intent from observed results; do not write
  coverage numbers you did not read from the database.
- **VALIDATE:** `rg -n "SCI|CBI" docs/phase-2/data_dictionary.md docs/phase-5/`

### CREATE tests (unit + fixtures)

- **IMPLEMENT:** `tests/unit/connectors/test_sci_parser.py`
  (Excel/PDF/HTML fixtures, Persian digits, Jalali→Gregorian month-end, base-year
  detection, malformed → `ParsingError`), `tests/unit/connectors/test_sci_scraper.py`
  (mocked browser/download, rate limiting, UA, provenance, size guard),
  `tests/unit/connectors/test_cbi_parser.py` (if gated open), and
  `tests/unit/utils/test_persian.py`. Extend
  `tests/unit/etl/test_gold.py` with multi-segment cases
  (`segment_indicator_ids`) including a segment with <12 months overlap →
  `ChainLinkingError`, and growth preservation within ±1%.
- **PATTERN:** `tests/unit/connectors/test_tgju_parser.py`,
  `tests/unit/chain_linking/test_splice.py`, `tests/integration/test_tgju_pipeline.py`
- **DEPENDENCIES:** Tasks 3–8
- **GOTCHA:** No network and no wall-clock sleeps in unit tests — inject fakes.
  Add `tests/fixtures/sci/*` and `tests/fixtures/cbi/*` (not generated).
- **VALIDATE:** `poetry run pytest tests/unit -q --no-cov`

### CREATE tests/integration/test_sci_pipeline.py (+ cbi)

- **IMPLEMENT:** Fixture-driven Bronze → Silver → Gold roundtrip using `FakePage`/
  `FakeBrowser`; three overlapping base-year segments for headline CPI; assert
  the canonical Gold series is continuous, `is_chain_linked` is true only on
  rescaled rows, `original_value` is always populated, YoY is exact and
  preserves growth ±1%, one `ChainLinkingLog` row with the expected
  `base_year_from`/`base_year_to` and `avg_confidence_score`, segment Silver rows
  share no `(indicator_id, timestamp)` collision, and a re-run is idempotent
  (Silver count stable, Gold refresh stable).
- **PATTERN:** `tests/integration/test_tgju_pipeline.py`,
  `tests/integration/test_world_bank_pipeline.py`
- **DEPENDENCIES:** Task 8; running PostgreSQL/TimescaleDB
- **GOTCHA:** Mark `@pytest.mark.integration`; roll back/clean up. Assert
  `original_value` is non-null on every Gold level row.
- **VALIDATE:** `poetry run pytest tests/integration/test_sci_pipeline.py -m integration -q --cov-fail-under=0`

### ADD live tests (gated)

- **IMPLEMENT:** `tests/unit/connectors/test_sci_scraper.py::test_live_*` and
  `test_cbi_scraper.py::test_live_*` behind
  `@pytest.mark.live()` + `RUN_LIVE_API_TESTS=1`, fetching a small bounded
  publication and asserting parseability (not fixed values). Document rate
  limits/quotas and the CBI gate in the test docstring.
- **PATTERN:** existing `@pytest.mark.live` tests in Phase 3/4
- **DEPENDENCIES:** Tasks 5/7
- **GOTCHA:** Must be skipped by default; never rely on live data in CI-less
  local gates.
- **VALIDATE:** `RUN_LIVE_API_TESTS=1 poetry run pytest -m live -q --no-cov`

### VALIDATE end to end + write report

- **IMPLEMENT:** Run a real SCI pipeline against the dev database
  (`poetry run python -m src.connectors.sci_scraper`), then verify in SQL that
  the canonical CPI series is continuous across all three bases and that
  `metadata.chain_linking_log` has the expected rows. Record the numbers and
  commands in `docs/phase-5/VALIDATION.md`, including the CBI gate outcome and
  the EIA-style "not done" honesty where relevant.
- **PATTERN:** `docs/phase-4/VALIDATION.md`, `docs/phase-3/VALIDATION.md`
- **DEPENDENCIES:** Tasks 1–12
- **GOTCHA:** Report only observed results; distinguish fixture-based from live.
- **VALIDATE:** `make check && poetry run pytest tests/integration -m integration -q --cov-fail-under=0`

---

## TESTING & VALIDATION

### Unit Tests

- Persian helpers: Persian + Arabic-Indic digits, separators, `parse_price`,
  Jalali→Gregorian including leap years and timezone conversion, malformed input.
- SCI parser: Excel (`.xlsx`, and `.xls` if captured), PDF via `pdfplumber`, HTML;
  header offsets, sheet selection, Jalali `YYYY/MM` → month-end, base-year
  detection, unit normalization, `ParsingError` on malformed sheets.
- CBI parser (if gated open): monetary aggregate tables, housing index.
- Scraper transport: mocked `FakeBrowser`/download, rate limiter invoked,
  size guard rejects oversized files, provenance metadata (url, sha256,
  content_type, byte_length), `disconnect()` ownership semantics.
- Gold multi-segment: correct oldest-first ordering, linked continuity,
  `original_value` always present, `is_chain_linked` only on rescaled rows,
  growth preserved within ±1%, <12-month overlap raises `ChainLinkingError`,
  missing base-year metadata warns and falls back to supplied order.

### Integration Tests

- Full Bronze → Silver → Gold roundtrip from fixture files.
- Segment Silver rows to not collide on `uq_silver_indicator_timestamp`.
- One canonical Gold series per CPI indicator; `ChainLinkingLog` audit row.
- Idempotent re-run: Bronze appends, Silver upserts (stable count), Gold refreshes.
- Catalog: canonical active with `base_years=[2011, 2016, 2021]`; segments inactive.
- No migration drift: `poetry run alembic check` still passes.

### Data Validation

- No null filling; skipped nulls counted in `records_failed`.
- Outliers flagged (IQR) but not dropped.
- Coverage/freshness recorded from the real run in the data dictionary.
- Original Persian period label retained in `record_metadata`; Gregorian stored.
- Chain-linking: overlap ≥ 12 monthly periods; growth preservation ±1%;
  confidence score populated; `original_value` + linked value both stored
  (reversibility).

### ML Validation

Not applicable — no model training in this phase.

### Edge Cases

- SCI publishes an overlapping-window revision (same timestamp, new value) — the
  Silver upsert must update rather than duplicate.
- A base year with fewer than 12 overlapping months → `ChainLinkingError` and a
  failed (not silently linked) indicator outcome.
- A publication is a `.xls` (not `.xlsx`) → engine selection / `xlrd`.
- A PDF with no extractable tables → `ParsingError`, not an empty success.
- A file exceeds `scraper_max_download_bytes` → rejected with provenance logged.
- SCI/CBI page structure changes → parser regression test with old + new fixture.
- CBI returns a challenge page → abort with a clear error (no bypass).

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
make format
make lint
make typecheck
poetry run mypy src dashboard
```

### Level 2: Unit Tests

```bash
poetry run pytest tests/unit/connectors/test_sci_parser.py tests/unit/connectors/test_sci_scraper.py tests/unit/utils/test_persian.py -q --no-cov
poetry run pytest tests/unit/etl/test_gold.py tests/unit/chain_linking/test_splice.py -q --no-cov
poetry run pytest tests/unit/airflow/test_dag_import.py -q --no-cov
make test
```

### Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run alembic upgrade head
poetry run alembic check
poetry run pytest tests/integration/test_sci_pipeline.py -m integration -v --cov-fail-under=0
poetry run pytest tests/integration -m integration --cov-fail-under=0
```

### Level 4: Feature-Specific Validation

```bash
poetry run python -m src.connectors.sci_scraper --dry-run
poetry run python -m src.connectors.sci_scraper
poetry run python -m src.connectors.cbi_scraper --dry-run   # only if the CBI gate is open
RUN_LIVE_API_TESTS=1 poetry run pytest -m live -q --no-cov
```

Then verify in SQL (or psql) that the canonical CPI series spans all three base
years without a break and that `metadata.chain_linking_log` contains one row per
linking operation with `overlap_period_months >= 12` and a confidence score.

### Level 5: Manual Validation

- Open the existing Inflation domain page in the Streamlit dashboard and confirm
  the linked CPI series and its YoY appear without a dashboard code change.
- Spot-check one linked CPI value against the source publication by hand.

## ACCEPTANCE CRITERIA

* [ ] Task 1 fixtures and `SOURCES.md` committed; SCI proceeds and the CBI gate
      is decided with recorded evidence
* [ ] SCI CPI (headline + at least one decile group) and unemployment ingest
      Bronze → Silver → Gold from real publications
* [ ] Three base-year CPI segments (2011 / 2016 / 2021) chain-link into one
      continuous canonical Gold series with ≥12-month overlap and ±1% growth
      preservation
* [ ] `metadata.chain_linking_log` records every link with method, overlap,
      variance, and confidence; Gold rows carry `original_value` and
      `is_chain_linked`; raw files preserved in Bronze with sha256
* [ ] Each published segment is stored under a distinct Silver indicator id;
      no `(indicator_id, timestamp)` collision
* [ ] Silver upsert and Gold refresh are idempotent on re-run
* [ ] CBI is either implemented behind the gate or explicitly deferred with
      evidence in `docs/phase-5/VALIDATION.md` (no bypass)
* [ ] Parser/scraper separation, Persian handling, injected transport, 1–2 req/sec,
      and `robots.txt` compliance follow AGENTS.md
* [ ] Unit + integration suites pass; `make check` green; coverage ≥80%
* [ ] `poetry run alembic check` reports no drift (no migration expected)
* [ ] Data dictionary records observed coverage; README/AGENTS/docs updated
* [ ] No regressions in World Bank / IMF / EIA / TGJU suites

## RISKS & TRADE-OFFS

- **CBI bot-defense (High).** `www.cbi.ir` serves an F5 `TSPD` challenge and
  `tsd.cbi.ir` did not respond in reconnaissance. Mitigation: Task 1 gate; if a
  normal browser cannot obtain genuine data, defer CBI with evidence exactly as
  OPEC was deferred. Do not build a bypass.
- **SCI publication format is unverified (High).** Sheet layouts, base-year
  labelling, PDF vs Excel availability, and URL structure are hypotheses until
  Task 1. Mitigation: reconnaissance-first checkpoint; parser driven by captured
  fixtures, not assumptions.
- **Multi-base-year storage vs unique constraint (High, design).** Overlapping
  segments share timestamps. Mitigation: distinct `B<year>` segment ids + a
  canonical Gold id; this is the main design decision and must be validated by
  the integration test.
- **Segment ordering / overlap adequacy (Medium).** `_chain_link_segments`
  requires oldest-first and ≥12 monthly overlapping periods. Mitigation: order by
  `record_metadata.base_year` and fail loudly (ChainLinkingError) when overlap is
  insufficient.
- **Raw-file storage in JSONB (Medium).** Base64 inflates size and could bloat
  Bronze. Mitigation: configurable `scraper_max_download_bytes` guard, record
  `sha256`/`byte_length`, and defer object storage to a later phase.
- **New dependencies (Low–Medium).** `pdfplumber`/`xlrd` are new runtime
  dependencies. Mitigation: add only when Task 1 confirms the format; document
  why in `IMPLEMENTATION.md`.
- **Source fragility (Medium).** SCI/CBI pages change without notice.
  Mitigation: pure parser + fixtures, regression tests with old and new samples,
  log truncated HTML/table dumps on parse failure.
- **Redistribution of `tgju_parser` helpers (Low).** Mitigation: behaviour-
  preserving move guarded by the existing TGJU parser suite.

## NOTES

### Alignment with PRD & AGENTS.md

- PRD §10 Tasks 12–13 map 1:1 onto the SCI (Task 13) and CBI (Task 12) work and
  their demos (M0/M2 trends; continuous 20-year CPI after chain-linking;
  inflation by income decile).
- AGENTS.md mandates: parser separate from scraper; raw files/HTML in Bronze;
  Persian → Gregorian for storage with the original in metadata; mock Playwright
  in tests; 1–2 req/sec + `robots.txt`; `record_metadata` (never a `metadata`
  attribute); tz-aware `utc_now()`; chain-linking with 12-month overlap, ±1%
  growth preservation, confidence scoring, and an audit trail; "if a source is
  blocked, do not work around it — record the evidence and defer."

### Key Design Decisions

1. **Segments in Silver, linked series in Gold.** Respects the unique
   constraint, preserves the raw publication for re-parsing/reversibility, and
   keeps chain-linking in the layer that already owns the audit log.
2. **Reuse `_chain_link_segments` unchanged.** The overlap algorithm and its
   growth-preservation assert already satisfy the AGENTS.md rules; only the
   plumbing from Silver to `chain_link(metadata={"segments": ...})` is new.
3. **No schema migration expected.** `base_year` travels in JSONB
   `record_metadata`; the segment identity is in the indicator id; the
   `ChainLinkingLog` columns already exist.
4. **Bronze unit is the file.** The envelope keeps parsed `rows` plus base64 raw
   bytes and a checksum, so a parser fix never needs a re-download.
5. **CBI is gated, SCI is committed.** Mirrors the Phase 4 OPEC ruling and keeps
   the phase deliverable even if CBI is blocked.

### Open Questions (resolve in Task 1)

- Does SCI publish CPI as `.xlsx`, `.xls`, PDF, HTML, or a mix — and is there an
  overlap table for each base pair (2011/2016, 2016/2021) of at least 12 months?
- Are CPI deciles a separate publication or extra columns; how many should the
  MVP include?
- Does CBI TSD return genuine content to a real browser, or a captcha/JS
  challenge? Is `tsd.cbi.ir` reachable from the target network at all?
- Should the canonical linked CPI indicator be `SCI.CPI.HEADLINE` (new) or a
  link from the existing `FP.CPI.TOTL.ZG` (World Bank) — keep the two namespaced
  as separate sources.
- Object storage vs base64 for raw files beyond the MVP size guard.

### Success Metrics

After Phase 5 completion:

- [ ] One SQL query returns a continuous monthly CPI series spanning 2011–2024
      on the 2021 base, with `is_chain_linked` and confidence populated
- [ ] Inflation-by-decile (or at least headline) plots from Gold without any
      dashboard change
- [ ] `metadata.chain_linking_log` provides a complete audit of every base-year
      transition
- [ ] SCI runs on a weekly Airflow schedule; Bronze holds the raw publications
- [ ] CBI is either ingesting or has a recorded, evidence-backed deferral

---

## Confidence Assessment

**Confidence: 6/10**

**High confidence because:**

- The scraper/parser, connector, config, retry, and pipeline patterns are proven
  twice (World Bank, TGJU) and this plan mirrors them rather than inventing a
  new architecture.
- The hardest algorithm — overlap-based multi-segment chain-linking — already
  exists and is unit-tested; the plan only threads real segments into it.
- The storage constraints (unique `(indicator_id, timestamp)`, JSONB
  `record_metadata`, no-migration ChainLinkingLog) were verified on disk, and
  the segment-id + canonical-id design respects them.
- Live reconnaissance was performed: SCI is reachable and `robots.txt`-permissive;
  CBI's F5 challenge and TSD unreachability are documented facts, not guesses.

**Remaining uncertainty (why not higher):**

- **SCI's actual publication formats and base-year overlap windows are
  unverified.** This is the dominant risk and the reason Task 1 is a
  reconnaissance checkpoint. Selector/sheet details in this plan are hypotheses.
- **CBI may be blocked**, in which case half the PRD phase deliverables defer —
  the same situation as OPEC in Phase 4.
- **PDF table extraction** (`pdfplumber`) on Persian RTL government PDFs is
  historically unreliable; if SCI only publishes PDFs for some series, the parser
  risk rises.
- **Multi-segment Gold plumbing** is additive but touches the most
  data-sensitive module; ordering and overlap-length failures must be handled
  explicitly rather than silently.

**Recommendation:** Proceed, but **front-load Task 1** and treat its fixtures as
the contract for Tasks 4–7. Build the Gold multi-segment change early against
synthetic segments (it is source-independent), keep the World Bank/TGJU/IMF/EIA
suites green as the regression guard, and defer CBI without hesitation if the
bot-defense gate cannot be passed by ordinary browser access.
