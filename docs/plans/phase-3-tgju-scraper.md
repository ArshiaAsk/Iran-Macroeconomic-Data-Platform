# Task: Phase 3 — TGJU Web Scraper, Daily FX/Gold Pipeline & Airflow Orchestration

## Task Description

Build the platform's first **web-scraping** data path and its first **scheduled**
data path: a Playwright-based TGJU scraper that lands raw HTML in Bronze, a
Persian-aware parser that produces daily FX and gold-price observations, a
Bronze → Silver → Gold pipeline adapted for daily price series (daily returns +
30-day moving averages), and an Apache Airflow deployment that runs the daily
collection automatically at 23:00 Iran time with backfill and failure alerting.

**Why:** Phase 2 proved the medallion architecture against a clean JSON API
(World Bank). Phase 3 proves it against the *hard* case the platform exists for:
a domestic source with **no API**, **JavaScript-rendered** content, **Persian
digits and Jalali dates**, **daily frequency**, and **no scheduler**. It
establishes the scraper, Persian-handling, daily-frequency, and orchestration
patterns that every remaining domestic source (CBI, SCI, TSETMC, HBSIR) will
mirror.

**Timeline:** Week 3-4

**PRD mapping:** Phase 3 = PRD §8 Task 7 (Playwright scraper foundation), Task 8
(TGJU parser + daily FX/gold Silver/Gold), Task 9 (Airflow orchestration &
scheduling).

## Scope

### In Scope

- [ ] `TgjuScraper` implementing the `DataConnector` protocol (Playwright
      transport), with a `TgjuConfig` dataclass for per-connector settings
- [ ] `tgju_parser.py` — **pure** parsing module: HTML → tidy DataFrame, Persian
      digit normalisation, Jalali → Gregorian date conversion (no I/O)
- [ ] User-agent rotation (`fake-useragent`) and request throttling
      (exponential backoff + jitter, 1-2 req/sec) reusing `src/utils/retry.py`
- [ ] Raw HTML persisted immutably in Bronze (`source_type="scraper"`) +
      `DataCollectionLog` audit row
- [ ] Scraper health monitoring: success rate + response-time tracking recorded
      in the collection log / metadata
- [ ] Silver transformer path for TGJU: parse via injected parser, price
      reasonableness checks, outlier flagging, null/duplicate handling,
      `TransformationLog`
- [ ] Gold transformer path for **daily price series**: passthrough chain-link,
      derived **daily returns** and **30-day moving average** series, domain
      tagging
- [ ] Behavior-preserving **generalisation** of `src/etl/silver.py` and
      `src/etl/gold.py` so the World Bank path is untouched but a second source
      can reuse the cleaning/validation/upsert core
- [ ] `IndicatorCatalog` seeding from `discover()` for the TGJU instruments
- [ ] `run_tgju_pipeline()` runner + `python -m src.connectors.tgju_scraper` CLI
- [ ] Apache Airflow (LocalExecutor) deployment: daily DAG at 23:00 Asia/Tehran,
      backfill DAG, failure alerting, run via `make` targets
- [ ] New dependencies: `jdatetime`, `beautifulsoup4`, `lxml`
- [ ] Unit tests (parser with HTML fixtures, Persian conversion, mocked
      Playwright scraper, retry/UA rotation); integration tests (full
      Bronze → Silver → Gold roundtrip); DAG import/structure test
- [ ] `docs/phase-2/data_dictionary.md` extended with the TGJU instruments and
      observed coverage from a real run

### Out of Scope

- [ ] CBI TSD and SCI scrapers (Phase 5) — though they will copy this pattern
- [ ] Real multi-base-year chain-linking validation (Phase 5 — SCI CPI)
- [ ] IMF, EIA, OPEC connectors (Phase 4)
- [ ] TSETMC / HBSIR package connectors (Phase 6)
- [ ] Streamlit dashboard and Plotly visualisations (Phase 7)
- [ ] CI/CD, backup automation, cloud/production Airflow (Phase 8)
- [ ] Intraday / real-time price capture — daily end-of-day snapshot only
- [ ] Full TGJU historical backfill of every instrument to inception — the
      backfill DAG is built and proven on a bounded range; a complete historical
      sweep is an operational follow-up

## Context

**Current State (verified 2026-09-08):** Phases 1 and 2 are complete and
validated — 4-layer schema, TimescaleDB hypertable on `gold.gold_analytical`,
`DataConnector` ABC, the World Bank connector, the full Bronze → Silver → Gold
pipeline, chain-linking, and 253 passing tests. For Phase 3 the following are
verified:

- `src/connectors/tgju_scraper.py` and `tgju_parser.py` do **not** exist yet.
- `airflow/dags/` and `airflow/config/` exist but are **empty**.
- `pyproject.toml` already declares `playwright ^1.40.0`, `fake-useragent
  ^1.4.0`, and `apache-airflow ^3.3.0` (optional, extra `airflow`);
  `pytest-asyncio ^0.21.0` is a dev dependency. **`jdatetime`,
  `beautifulsoup4`, and `lxml` are NOT declared** — Phase 3 must add them.
- `src/utils/config.py` has **no** scraper/TGJU settings. `CollectionConfig`
  exposes `retry_max`, `timeout`, `user_agent_rotation`; `APIConfig` has no TGJU
  URL.
- `src/etl/silver.py` imports `rows_to_frame` from `world_bank` and its
  `prepare_silver_frame` is World-Bank-shaped; `src/etl/gold.py` hardcodes
  year-over-year growth and the `"WB."` derived-id prefix. Both must be
  generalised **without changing the World Bank result**.
- `mypy` overrides already list `playwright.*` under `ignore_missing_imports`;
  `jdatetime` and `bs4` will need adding there (no bundled stubs).

**Data flow this phase must realise:**

```text
TGJU website  (daily, JS-rendered, Persian digits + Jalali dates)
        ↓  TgjuScraper.fetch()  (Playwright, UA rotation, throttling)
bronze.bronze_raw          {"html": …} envelope, source_type="scraper", immutable
        ↓  src/connectors/tgju_parser.py  (pure: HTML → tidy frame)
        ↓  src/etl/silver.py  (injected parser)
silver.silver_cleaned      one row per (indicator_id, timestamp), validated
        ↓  src/etl/gold.py  (daily-metrics strategy)
gold.gold_analytical       prices + daily returns + 30-day MA, domain-tagged
        ↑
   Airflow DAG (LocalExecutor) triggers run_tgju_pipeline() nightly @ 23:00 IRST
```

**Storage constraints that shape the design** (from `src/database/schema.py`,
re-confirmed):

- `BronzeRaw.raw_data` is `Mapped[dict[str, Any]]` (JSONB). HTML is a string, so
  it must be wrapped as a dict — `{"html": "<…>", "scraped_at": …, "url": …}`.
  `wrap_envelope()` passes dicts through unchanged, so no envelope-list handling
  is needed for the scraper.
- `bronze.extract_rows()` reads a `"rows"` key and is **World-Bank-specific** —
  it must **not** be used for TGJU. The TGJU parser reads `raw_data["html"]`.
- `SilverCleaned.value` is `Mapped[float]`, **NOT NULL** — a missing price is
  skipped-and-counted, never stored as null.
- `SilverCleaned` uniqueness is `uq_silver_indicator_timestamp` on
  `(indicator_id, timestamp)` — the Silver upsert already keys on this; daily
  data must resolve to **one row per instrument per trading day**.
- `GoldAnalytical` has a composite PK `(id, timestamp)`; derived rows need a
  non-null `silver_id`. Daily frequency means far more rows than annual — the
  hypertable handles it, but derived-series ids must be namespaced per source.
- `record_metadata` is the Python attribute; the physical column is `metadata`.
- All timestamps are timezone-aware via `utc_now()`; the parser must emit
  tz-aware UTC timestamps.

**Unverified externals that gate the work (biggest unknowns):** TGJU's exact
URLs, DOM structure, CSS selectors, digit encoding, and date presentation are
**not verified in this plan** — they must be captured live during Task 2 and
frozen as fixtures. `robots.txt` and terms must be checked before scraping
(AGENTS.md: "Only scrape publicly available data; respect robots.txt"). All
selector-level detail below is a **starting hypothesis**, not a contract.

## Proposed Approach

Bottom-up, mirroring the Phase 2 ordering so each layer is testable before the
next depends on it, and touching the validated World Bank path only through
behavior-preserving seams:

1. **Dependencies + config first** — add `jdatetime`/`bs4`/`lxml`, a `TgjuConfig`
   dataclass, and TGJU settings, so nothing downstream hardcodes values.
2. **Reconnaissance + fixtures** — inspect the live site once, capture real HTML,
   and freeze it as fixtures so *all* parser/scraper unit tests run offline.
3. **Parser second (pure)** — `tgju_parser.py` turns HTML into a tidy frame,
   normalises Persian digits, and converts Jalali dates. No Playwright, no DB —
   the highest-value, most-testable unit.
4. **Scraper third** — `TgjuScraper` wraps Playwright behind the `DataConnector`
   protocol, injecting transport/retry/rate-limiter exactly like the World Bank
   connector so tests mock Playwright and never open a browser.
5. **ETL generalisation fourth** — add a `parser`/`derivations` seam to
   `silver.py`/`gold.py` with defaults that preserve the World Bank behaviour;
   add the daily-metrics (returns + MA) strategy.
6. **Pipeline + CLI fifth** — `run_tgju_pipeline()` and the module entry point,
   mirroring `src/etl/pipeline.py`.
7. **Airflow last** — a thin DAG that imports and calls the pipeline runner;
   orchestration holds no business logic.

Reuse Phase 1/2 primitives rather than reinventing: `write_bronze()` (with
`source_type="scraper"`), `write_silver()`/`_silver_records()`,
`validate_data_quality()`, `detect_outliers_iqr()`, `RetryPolicy`/`RateLimiter`,
`chain_link()` (passthrough for daily data), `log_with_context()`, and the
existing exception hierarchy.

## Task Metadata

**Type:** New Capability (scraper connector + Persian handling + daily pipeline + orchestration)
**Complexity:** High
**Affected Areas:** Connectors, ETL (generalisation), Config, Orchestration (Airflow), Dependencies, Docs, Tests
**Dependencies:** Phases 1-2 complete (schema, hypertable, `DataConnector`, ETL, chain-linking, retry utils, config, validation)

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

| File | Why |
|------|-----|
| `AGENTS.md` | Authoritative conventions — scraper rules (§Scraping Constraints, §Scraper Tests, §When Debugging Scrapers), `record_metadata`, `utc_now()`, Persian calendar rule, parser/scraper separation, `text()` for raw SQL |
| `PRD.md` §8 Tasks 7-9, §18.1 | The requirements this plan implements + tech-stack note (Playwright/BeautifulSoup/requests) |
| `docs/plans/phase-2-world-bank-connector.md` | The plan format to mirror and the ETL contract this phase extends |
| `src/connectors/base.py` | The ABC signatures to satisfy (`connect`/`discover`/`fetch`/`validate`) and `IndicatorMetadata` fields |
| `src/connectors/world_bank.py` | **Reference implementation** — constructor injection, config dataclass, `fetch_series()` → result object, `RetryPolicy`/`RateLimiter` usage, `main()`/CLI delegation |
| `src/etl/bronze.py` | `write_bronze()` signature, `SOURCE_TYPE_SCRAPER`, `wrap_envelope()` dict passthrough (why HTML must be wrapped) |
| `src/etl/silver.py` | `prepare_silver_frame`/`bronze_to_silver` (the World-Bank coupling to generalise), `write_silver`/`_silver_records` (reusable core), `load_silver_series` |
| `src/etl/gold.py` | `silver_to_gold`, `_level_records`, `_growth_records` (YOY + `"WB."` prefix to generalise), `_replace_gold_rows` (delete-and-reinsert idempotency) |
| `src/etl/lineage.py` | `transformation()` context manager, `TransformResult`, `resolve_status`, failure-out-of-band boundary |
| `src/etl/pipeline.py` | The runner pattern to copy — one session per unit, contained failures, catalog upsert, CLI wiring |
| `src/chain_linking/splice.py` | `chain_link()` passthrough behaviour + `MIN_OVERLAP_PERIODS_BY_FREQUENCY` (already has `daily: 12`) |
| `src/database/schema.py` | Every column, nullability, FK, default the TGJU rows must honour |
| `src/utils/config.py` | Where/how to add `TgjuConfig` + settings; `CollectionConfig` fields already present |
| `src/utils/retry.py` | `RetryPolicy` (retryable set is requests-specific — see GOTCHA), `RateLimiter` |
| `src/utils/validation.py` | `ValidationResult`, `validate_data_quality()`, `detect_outliers_iqr()` |
| `src/utils/exceptions.py` | `ParsingError`, `DataRetrievalError`, `ConnectionError`, `ValidationError` |
| `tests/conftest.py` | `FakeSession`, `FakeQuery`, `compiled_sql`, fixture-loading pattern to mirror for TGJU HTML fixtures |
| `tests/unit/connectors/test_world_bank.py` | The connector unit-test pattern (build connector with injected fakes + no-op sleeps) |
| `tests/integration/test_world_bank_pipeline.py` | Integration harness — self-provisioned test DB, skip-when-unreachable, always-rollback session |
| `docker-compose.yml`, `Makefile`, `ENVIRONMENT.md` | Where Airflow/Playwright setup and `make` targets slot in; Airflow env-var conventions |

### Data References

- **TGJU instrument set for this phase** (daily; codes are proposed and must be
  finalised against the live site in Task 2):

  | Proposed indicator_id | Meaning | Domain | Source (unverified) |
  |-----------------------|---------|--------|---------------------|
  | `TGJU.USD.FREE` | USD free-market exchange rate (IRR) | `fx` | TGJU USD page |
  | `TGJU.GOLD.EMAMI` | Emami gold coin price (IRR) | `gold` | TGJU coin page |
  | `TGJU.GOLD.18K` | 18-karat gold price per gram (IRR) | `gold` | TGJU gold page |
  | `TGJU.COIN.PREMIUM` | Coin premium (coin price − melt value) | `gold` | scraped if published, else derived — see GOTCHA |

- **Frequency:** daily. Expected volume grows ~365 rows/instrument/year, unlike
  the ~66 rows/indicator of World Bank — correctness and idempotency of the
  **one-row-per-day** rule matter more than throughput.
- **Derived Gold series (PRD Task 8):** daily return (`pct_change × 100`, unit
  `%`) and 30-day moving average (unit = source unit). Namespaced
  `TGJU.<id>.RET1D` and `TGJU.<id>.MA30`.
- **Persian specifics:** Persian digits `۰۱۲۳۴۵۶۷۸۹` (U+06F0–U+06F9) and
  Arabic-Indic `٠١٢٣٤٥٦٧٨٩` (U+0660–U+0669); thousands separators may be ASCII
  `,`, Arabic comma `،` (U+060C), or Persian thousands separator `٬` (U+066C);
  dates shown in Jalali (e.g. `۱۴۰۳/۰۶/۱۸`).
- **Captured fixtures:** save real HTML to `tests/fixtures/tgju/<page>_<scenario>.html`
  (normal snapshot, a missing-instrument page, a Persian-digit edge case) so unit
  tests never touch the network.

### External Documentation

- Playwright for Python (sync API, `goto`, `wait_for_selector`, `content()`) —
  https://playwright.dev/python/docs/intro
- `fake-useragent` — https://pypi.org/project/fake-useragent/
- `jdatetime` (Jalali ↔ Gregorian) — https://pypi.org/project/jdatetime/
- BeautifulSoup 4 — https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Apache Airflow 3.x (DAGs, timezones, LocalExecutor, `db migrate`) —
  https://airflow.apache.org/docs/apache-airflow/stable/
- Airflow time zones (Asia/Tehran scheduling) —
  https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/timezone.html

### Patterns to Follow

| Pattern | Source |
|---------|--------|
| Connector subclass + injected transport/retry/rate-limiter + context manager | `src/connectors/world_bank.py`, `AGENTS.md §Connector Protocol` |
| `fetch()` returns a frame and writes nothing; a `fetch_*()` result object carries the raw payload for Bronze | `world_bank.WorldBankFetchResult` |
| Config as a dataclass with defaults from `get_config()` | `world_bank.WorldBankConfig` |
| Bronze write with `source_type="scraper"`; dict envelope | `src/etl/bronze.py` |
| Silver cleaning core (null/dup/outlier + upsert) | `src/etl/silver.py::prepare_silver_frame`/`write_silver` |
| Gold delete-and-reinsert idempotency + derived-series namespacing | `src/etl/gold.py` |
| Pipeline runner: one session per instrument, contained failure, CLI | `src/etl/pipeline.py` |
| Pure-function parser, DB-free, fixture-tested | `src/chain_linking/splice.py` (purity), `world_bank.rows_to_frame` (parsing) |
| Integration test that self-provisions a `_test` DB and skips cleanly | `tests/integration/test_world_bank_pipeline.py` |
| Offline transport fake + no-op sleeps in unit tests | `tests/conftest.py`, `tests/unit/connectors/test_world_bank.py` |

---

## IMPLEMENTATION PLAN

### Phase 3.1: Foundation (dependencies, config, reconnaissance)

Add `jdatetime`/`beautifulsoup4`/`lxml`, the `TgjuConfig` dataclass and settings,
Playwright browser install wiring, and the one-time live reconnaissance that
produces the HTML fixtures every later test depends on.

### Phase 3.2: Core Change (parser + scraper + ETL generalisation)

The pure `tgju_parser.py`, the `TgjuScraper` connector, and the
behavior-preserving generalisation of `silver.py`/`gold.py` plus the daily-metrics
Gold strategy. This is the bulk of the phase and the part CBI/SCI will copy.

### Phase 3.3: Integration (pipeline runner + CLI + Airflow)

`run_tgju_pipeline()`, the module CLI, and the Airflow LocalExecutor deployment
(daily DAG, backfill DAG, alerting, `make` targets).

### Phase 3.4: Validation (tests, docs, end-to-end proof)

Parser/scraper/ETL unit tests, the full integration roundtrip, the DAG import
test, data-dictionary updates, and the full validation command sequence.

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `pyproject.toml` — add Phase 3 dependencies

- **ACTION:** Add runtime deps and mypy overrides.
- **IMPLEMENT:** Add `jdatetime`, `beautifulsoup4`, `lxml` to
  `[tool.poetry.dependencies]`; add `jdatetime.*` and `bs4.*` to the
  `[[tool.mypy.overrides]]` `ignore_missing_imports` module list (alongside the
  existing `playwright.*`). Keep `apache-airflow` as the optional `airflow`
  extra.
- **PATTERN:** Match the existing dependency pins and the mypy override block.
- **DEPENDENCIES:** None.
- **GOTCHA:** `python = ">=3.11,<3.13"` is constrained by Airflow — do not widen
  it. Run `poetry lock` after editing or `poetry install` will refuse. `lxml`
  is BeautifulSoup's parser backend (`BeautifulSoup(html, "lxml")`); without it
  the parser silently falls back to the slower stdlib parser and selectors can
  differ.
- **VALIDATE:** `poetry lock && poetry install`;
  `poetry run python -c "import jdatetime, bs4, lxml"`.

### Task 2: CREATE `tests/fixtures/tgju/*.html` — live reconnaissance

- **ACTION:** Capture real TGJU HTML once and freeze it.
- **IMPLEMENT:** Check `robots.txt`/terms first. Then, from a real browser or a
  one-off Playwright script, save the raw HTML of each target page to
  `tests/fixtures/tgju/<page>_normal.html`, plus at least one
  `<page>_missing.html` (instrument absent) and note the exact selectors, digit
  encoding, and Jalali date format observed. Record the source URLs and capture
  date in a short `tests/fixtures/tgju/SOURCES.md` sidecar.
- **PATTERN:** Verbatim payloads, one file per scenario — mirrors
  `tests/fixtures/world_bank/*.json`.
- **DEPENDENCIES:** Task 1 (Playwright browser installed).
- **GOTCHA:** This is the single largest source of risk in the phase — every
  parser test is written against these fixtures, so they must be **real**, not
  hand-authored. Do not commit anything beyond publicly served markup. If a
  value is JS-rendered, capture *after* `wait_for_selector`, not the initial
  document. Respect rate limits even during capture.
- **VALIDATE:** Files exist and open; selectors identified in `SOURCES.md` locate
  every target price by hand before any parser code is written.

### Task 3: UPDATE `src/utils/config.py` — TGJU / scraper settings

- **ACTION:** Add TGJU configuration without breaking existing config.
- **IMPLEMENT:** Add `tgju_base_url` to `APIConfig` (alias `TGJU_BASE_URL`,
  sensible default). Add scraper throttle/health knobs — either extend
  `CollectionConfig` (e.g. `scraper_min_request_interval`, default `1.0`;
  `scraper_page_timeout`, default `30`) or introduce a small `ScraperConfig`
  sub-config wired into `AppConfig`. The per-connector `TgjuConfig` dataclass
  (Task 5) reads these via `get_config()`.
- **PATTERN:** Copy an existing `BaseSettings` sub-config exactly (aliases,
  `populate_by_name=True`, `extra="ignore"`), and wire it into `AppConfig` with
  `Field(default_factory=…)` like `collection`/`api`.
- **DEPENDENCIES:** None (can precede Task 2).
- **GOTCHA:** `get_config()` is `lru_cache`d — tests that depend on env overrides
  must construct config objects directly rather than expecting a re-read. Keep
  the 1-2 req/sec rule (`AGENTS.md`) as the default interval (≥0.5s). Do not put
  secrets here — TGJU needs none.
- **VALIDATE:** `poetry run python -c "from src.utils.config import get_config;
  print(get_config().api.tgju_base_url)"`; `poetry run mypy src/utils/config.py`.

### Task 4: CREATE `src/connectors/tgju_parser.py` — pure parsing module

- **ACTION:** Turn raw HTML into a tidy, validated-shape DataFrame with no I/O.
- **IMPLEMENT:**
  - `normalise_digits(text) -> str` — map Persian (U+06F0–U+06F9) and
    Arabic-Indic (U+0660–U+0669) digits to ASCII; strip `,`/`،`/`٬`/whitespace.
  - `parse_price(text) -> float` — normalise then parse to float; raise
    `ParsingError` on non-numeric.
  - `jalali_to_gregorian(date_text, *, tz="Asia/Tehran") -> datetime` — parse a
    Jalali date via `jdatetime`, return a tz-aware **UTC** datetime; keep the raw
    Persian string for the caller to store in `record_metadata`.
  - `parse_tgju_html(html, indicator_id, *, now=None) -> pd.DataFrame` — locate
    the instrument by the selectors frozen in Task 2 and return columns
    `timestamp, value, indicator_id, unit, obs_status` (the same frame shape the
    Silver core expects).
- **PATTERN:** Pure functions over strings/HTML — mirrors the purity of
  `chain_linking/splice.py` and the frame shape of `world_bank.rows_to_frame`
  (`FRAME_COLUMNS`).
- **DEPENDENCIES:** Tasks 1, 2.
- **GOTCHA:** Store **Gregorian** in the frame, original Persian/Jalali string in
  metadata (AGENTS.md). A daily homepage snapshot with no explicit date is
  stamped with the **trading day in Asia/Tehran** (not naive `utcnow`, which ruff
  DTZ rejects) — derive it from `now` so tests are deterministic. Emit tz-aware
  UTC timestamps. Do not fabricate a `unit`; set it explicitly per instrument
  (IRR). Raise `ParsingError` when a required selector is missing rather than
  returning an empty frame silently — a scrape that parsed nothing must be
  visible.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_tgju_parser.py -v`;
  `poetry run mypy src/connectors/tgju_parser.py`.

### Task 5: CREATE `src/connectors/tgju_scraper.py` — `TgjuScraper` connector

- **ACTION:** Implement the `DataConnector` protocol over Playwright.
- **IMPLEMENT:** `TgjuConfig` dataclass (base URL, per-instrument paths,
  timeout, throttle interval, UA-rotation flag — defaults from `get_config()`)
  and `TgjuScraper(DataConnector)`:
  - `__init__(self, config=None, browser=None, retry_policy=None,
    rate_limiter=None)` — inject the Playwright driver/page factory and
    retry/rate-limiter, exactly like the World Bank constructor injects
    `http_session`; track `_owns_browser`.
  - `connect()` — launch a headless Chromium (or verify the injected driver);
    return `bool`.
  - `discover()` — return `list[IndicatorMetadata]` for the TGJU instruments
    (name, unit=IRR, `frequency="daily"`, domain, `source_name="tgju"`, source
    URL); leave availability `None` (the pipeline fills it).
  - `fetch(indicator_id, start_date, end_date) -> pd.DataFrame` — navigate, wait
    for the selector, read `content()`, delegate to `tgju_parser`.
  - `fetch_page(indicator_id) -> TgjuFetchResult` — richer method carrying
    `frame`, `raw_html`, `request_url`, `http_status_code`, `response_time_ms`,
    `user_agent`, and a `collection_metadata()` dict for Bronze/health.
  - `validate(data)` — delegate to `validate_data_quality()`.
  - `disconnect()` — close the browser only if `_owns_browser`; context-manager
    support.
  - `main()` — delegate to the pipeline `run_cli` (local import to avoid a
    cycle), mirroring `world_bank.main()`.
- **PATTERN:** Copy `src/connectors/world_bank.py` structure verbatim, swapping
  the `requests.Session` transport for a Playwright page and JSON parsing for the
  Task 4 parser. Rotate the UA per request with `fake-useragent` when
  `user_agent_rotation` is set; throttle via the injected `RateLimiter`
  (`wait()`); wrap navigation in retry/backoff.
- **DEPENDENCIES:** Tasks 3, 4.
- **GOTCHA:**
  - **`RetryPolicy.run()`'s retryable set is requests-specific** (Timeout /
    ConnectionError / HTTP 429/5xx). Playwright raises `PlaywrightTimeoutError`.
    Either (recommended) generalise `RetryPolicy` to accept an optional
    retryable-exception predicate (default preserves today's behaviour), or wrap
    navigation in a small loop using `RetryPolicy.delay_for(attempt)` and catch
    `PlaywrightTimeoutError` → raise `DataRetrievalError` on exhaustion. Pick one
    and state it.
  - `fetch()` must **not** write to the database — Bronze persistence is the
    pipeline's job (mirrors the World Bank split).
  - Prefer Playwright's **sync** API: `DataConnector.fetch` is synchronous and
    Airflow tasks run synchronously, so the sync API avoids event-loop-in-worker
    problems. (`pytest-asyncio` is present but the parser — the part worth
    testing hardest — needs no browser at all.)
  - Set a realistic UA and a bounded navigation timeout; never retry a
    genuinely-absent instrument forever.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_tgju_scraper.py -v`
  (Playwright fully mocked); `poetry run mypy src/connectors/tgju_scraper.py`.

### Task 6: UPDATE `src/etl/silver.py` — generalise the parse seam

- **ACTION:** Let a second source reuse the Silver cleaning core.
- **IMPLEMENT:** Add a `parser` parameter to `bronze_to_silver` (and the
  underlying `prepare_silver_frame`) — a callable `(raw_data, indicator_id, unit,
  now) -> pd.DataFrame` — defaulting to the current World-Bank behaviour
  (`extract_rows` + `rows_to_frame`). TGJU passes a parser that reads
  `raw_data["html"]` and calls `tgju_parser.parse_tgju_html`. Everything after
  the frame is produced (null-drop, dedup, outlier flag, `write_silver` upsert,
  `TransformationLog`) is unchanged and shared.
- **PATTERN:** Keep the default argument bound to the World-Bank parser so the
  existing call sites and results are byte-for-byte identical.
- **DEPENDENCIES:** Task 4.
- **GOTCHA:** The World Bank path must stay **green with no test changes** —
  prove it by running the existing Silver tests unchanged. `SilverCleaned.value`
  is NOT NULL, so the TGJU parser producing a null price is skipped-and-counted,
  same as WB. Avoid a new import cycle: the default parser already lives via
  `world_bank`; TGJU's parser is injected by the caller, so `silver.py` must not
  import `tgju_scraper`.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_silver.py -v` (existing,
  unchanged) + new TGJU cases; `poetry run mypy src/etl/silver.py`.

### Task 7: UPDATE `src/etl/gold.py` — daily-metrics derivation strategy

- **ACTION:** Add daily returns + 30-day MA without disturbing the WB YOY path.
- **IMPLEMENT:** Generalise the derived-series step so `silver_to_gold` accepts a
  derivation **strategy** (or add a sibling `silver_to_gold_daily`). Provide a
  daily strategy that emits two derived series from the linked levels:
  `TGJU.<id>.RET1D` (`value.pct_change() × 100`, unit `%`) and `TGJU.<id>.MA30`
  (`value.rolling(30).mean()`, unit = source unit). Namespace the derived ids by
  source (`TGJU.…`) instead of the hardcoded `"WB."` prefix. The level-writing,
  chain-link call (passthrough for daily), delete-and-reinsert idempotency, and
  `TransformationLog` are reused.
- **PATTERN:** Mirror `_growth_records` / `derived_growth_indicator_id` but
  parametrise the prefix and the derivation function; keep `_level_records` and
  `_replace_gold_rows` as-is.
- **DEPENDENCIES:** Task 6.
- **GOTCHA:** Every derived Gold row needs a non-null `silver_id` — attribute
  each metric to the **current day's** Silver row (the day the metric is computed
  at), and skip leading rows where the metric is undefined (first return; first
  29 days of the MA) rather than inventing a parent. `chain_link()` on a
  no-base-year daily series must return a clean passthrough
  (`is_chain_linked=False`, `chain_linking_confidence=None`) — do not fabricate
  confidence. Keep the WB YOY output identical (existing Gold tests unchanged).
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_gold.py -v` (existing +
  new daily cases); `poetry run mypy src/etl/gold.py`.

### Task 8: CREATE `src/connectors/tgju_scraper.py` pipeline runner + CLI

- **ACTION:** Wire discover → fetch → Bronze → Silver → Gold for TGJU.
- **IMPLEMENT:** `run_tgju_pipeline(indicators=None, dry_run=False,
  connector=None) -> PipelineSummary` and `run_cli(...)` / `main()`, mirroring
  `src/etl/pipeline.py`. Per instrument: `fetch_page()` → `write_bronze(...,
  source_type="scraper")` → `bronze_to_silver(..., parser=tgju_parser_fn,
  frequency="daily")` → `update_catalog_availability` → `silver_to_gold(...,
  <daily strategy>)`. One session per instrument; contained failures; non-zero
  exit if any failed. Entry point: `python -m src.connectors.tgju_scraper
  [--dry-run] [--indicators] [--log-level]`.
- **PATTERN:** Copy `run_world_bank_pipeline` / `_collect_one` /
  `_persist_indicator` / `upsert_indicator_catalog` structure; reuse
  `INDICATOR_ERRORS`.
- **DEPENDENCIES:** Tasks 5, 6, 7.
- **GOTCHA:** `IndicatorCatalog.indicator_id` is the PK — seed via upsert.
  Re-running the same day must **not** duplicate rows: Silver upserts on
  `(indicator_id, timestamp)` and Gold deletes-and-reinserts, so the trading-day
  timestamp must be stable across runs on the same day. Decide whether the daily
  snapshot timestamp is midnight-Tehran or the observed page date — document it.
  Consider whether to reuse the shared `pipeline.py` (add a source parameter) or
  keep a TGJU-local runner; a local runner is lower-risk for the validated WB
  path — state the choice.
- **VALIDATE:** `poetry run python -m src.connectors.tgju_scraper --dry-run`.

### Task 9: CREATE Airflow deployment — `airflow/dags/tgju_daily.py` (+ backfill)

- **ACTION:** Schedule the pipeline nightly and enable backfill + alerting.
- **IMPLEMENT:**
  - `airflow/dags/tgju_daily.py` — DAG `tgju_daily`, `schedule="0 23 * * *"` with
    `timezone`/pendulum `Asia/Tehran`, `catchup=False`, a single task calling
    `run_tgju_pipeline()`; task-level `retries` + `retry_delay`;
    `on_failure_callback` that logs with context and (per PRD) notifies on
    repeated failures.
  - `airflow/dags/tgju_backfill.py` — parametrised (`start`/`end`) backfill DAG
    calling the historical-fetch path over a bounded date range.
  - Airflow config/env (`airflow/config/` and `.env`): `AIRFLOW_HOME=./airflow`,
    `AIRFLOW__CORE__EXECUTOR=LocalExecutor`,
    `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` pointing at a **separate** `airflow`
    database on the same Postgres instance.
  - `Makefile` targets: `airflow-init` (`airflow db migrate` + admin user),
    `airflow-up` (`airflow standalone` or scheduler+api server), `airflow-down`.
- **PATTERN:** DAGs are **thin** — import and call the pipeline runner; no
  business logic in the DAG. Reuse structured logging for alerts.
- **DEPENDENCIES:** Task 8.
- **GOTCHA:** Airflow **3.x** is required (2.x pins `sqlalchemy<2.0`, which
  breaks the 2.0 typed ORM — AGENTS.md). Keep Airflow's metadata tables in their
  **own** database/schema so they never collide with `bronze/silver/gold/metadata`.
  A DAG that imports the whole `src` tree can be slow to parse — keep imports
  light and the callable at task runtime. `Asia/Tehran` DST: rely on
  pendulum/Airflow tz handling, not a fixed UTC offset. Given PRD open question
  ("Is Airflow too heavy for local setup?") and the analyst-friendly constraint,
  document a cron/APScheduler fallback but implement Airflow as specified.
- **VALIDATE:** `poetry run pytest tests/unit/airflow/test_dag_import.py -v`
  (DAG imports, no cycles, one `tgju_daily` DAG, valid schedule);
  `airflow dags list` shows `tgju_daily`; manual `airflow dags test tgju_daily`.

### Task 10: CREATE unit test suites

- **ACTION:** Cover parser, scraper, and the ETL generalisations offline.
- **IMPLEMENT:** `tests/unit/connectors/test_tgju_parser.py`,
  `test_tgju_scraper.py`; extend `tests/unit/etl/test_silver.py` and
  `test_gold.py` with TGJU cases; `tests/unit/airflow/test_dag_import.py`. Add a
  `load_tgju_fixture()` helper + fixtures to `tests/conftest.py` mirroring the
  World Bank loader; build a fake Playwright page that returns fixture HTML.
- **PATTERN:** Mirror `tests/unit/connectors/test_world_bank.py`; reuse
  `FakeSession`/`compiled_sql`; inject no-op sleeps into `RetryPolicy`/`RateLimiter`.
- **DEPENDENCIES:** Tasks 4-9.
- **GOTCHA:** The 80% coverage gate is **global** — thin tests on this large new
  surface will drag the whole project under. `tests/**` has ruff ignores for
  `ARG`/`PLR2004`. Never launch a real browser in unit tests — mock Playwright
  entirely. Test Persian conversion with real glyphs from the Task 2 fixtures,
  not transliterations.
- **VALIDATE:** `make test` — all pass, coverage ≥80%.

### Task 11: CREATE `tests/integration/test_tgju_pipeline.py`

- **ACTION:** Prove the full roundtrip against the live test database.
- **IMPLEMENT:** Drive Bronze → Silver → Gold from **fixture HTML** (no live
  scrape): assert one Silver row per instrument per day, FK integrity
  (Silver→Bronze, Gold→Silver), Gold rows land in the hypertable, daily-return /
  MA derived rows exist with correct ids, `TransformationLog` rows for both hops,
  and that a same-day re-run is idempotent (no duplicate Silver rows). Add a
  `@pytest.mark.live` test (skipped unless `RUN_LIVE_API_TESTS=1`) that scrapes
  one real page.
- **PATTERN:** Copy `tests/integration/test_world_bank_pipeline.py` — module
  `pytestmark = pytest.mark.integration`, self-provisioned `_test` DB,
  `pytest.skip()` when Postgres is unreachable, always-rollback session.
- **DEPENDENCIES:** Tasks 8, 2.
- **GOTCHA:** The test DB must have the current schema (all migrations applied).
  Keep the `live` test out of `make test-all`. Assertions must run inside the
  same rolled-back transaction.
- **VALIDATE:** `make test-integration`.

### Task 12: UPDATE `docs/phase-2/data_dictionary.md`, `README.md`, `AGENTS.md`

- **ACTION:** Record what Phase 3 actually delivered.
- **IMPLEMENT:** Add the TGJU instruments (id, meaning, unit, frequency=daily,
  domain, observed coverage, source URL, Bronze HTML-wrapping convention, derived
  `RET1D`/`MA30` naming, Persian/Jalali handling note). Flip the README
  data-sources table so **TGJU** is "Implemented (Phase 3)" and update the
  roadmap; update `AGENTS.md` lifecycle line and, if the built scraper pattern
  differs from what's documented, the connector guidance.
- **PATTERN:** Edit in place; match existing table/tone.
- **DEPENDENCIES:** Tasks 8, 11 (coverage numbers come from a real run).
- **GOTCHA:** Record **observed** coverage from an actual run, not TGJU's claims.
  Consider renaming `docs/phase-2/data_dictionary.md` → `docs/data_dictionary.md`
  (multi-phase) or add a Phase 3 section; do not silently strand TGJU under a
  phase-2 path — state the choice.
- **VALIDATE:** Every loaded TGJU instrument has a row; docs match reality.

---

## TESTING & VALIDATION

### Unit Tests

- **Parser:** normalises Persian and Arabic-Indic digits; strips `,`/`،`/`٬`;
  parses prices to float; `jalali_to_gregorian` returns the correct tz-aware UTC
  datetime; `parse_tgju_html` returns the expected frame from the normal fixture;
  raises `ParsingError` on a missing selector / non-numeric price; missing
  instrument fixture handled.
- **Scraper:** implements the `DataConnector` ABC; `fetch()` returns a frame from
  mocked page HTML; UA rotation applied when configured; `RateLimiter.wait()`
  invoked; retry then success on a simulated `PlaywrightTimeoutError`; exhaustion
  raises `DataRetrievalError`; `disconnect()` closes only an owned browser;
  context manager cleans up; cannot be instantiated abstractly.
- **Silver (generalised):** existing World-Bank cases pass **unchanged**; a TGJU
  parser injection cleans HTML-sourced rows; nulls skipped-and-counted;
  duplicates rejected; outliers flagged not dropped.
- **Gold (generalised):** existing WB YOY cases pass **unchanged**; daily
  strategy emits `RET1D` and `MA30` with correct values, ids, units, and
  non-null `silver_id`; first return / first 29 MA rows skipped;
  `is_chain_linked=False`, `confidence=None` for passthrough.
- **DAG:** `tgju_daily` imports without error, has exactly one DAG, a valid
  `Asia/Tehran` schedule, `catchup=False`, and retries configured.

### Integration Tests

- Full pipeline from fixture HTML through all three layers with correct counts.
- FK chain intact: every Silver row → a Bronze row; every Gold row → a Silver row.
- Gold rows queryable through the hypertable; derived series present.
- Same-day re-run does not duplicate Silver rows (idempotency).
- `TransformationLog` rows written for both hops.
- `@pytest.mark.live`: one real TGJU page scrapes and parses to ≥1 observation.

### Data Validation

- Silver: no null `value`; one row per `(indicator_id, timestamp)`; timestamps
  tz-aware; no future dates; prices strictly positive (non-positive → invalid,
  skipped-and-counted).
- Gold: daily return = day-over-day `pct_change × 100`; 30-day MA matches a
  reference rolling mean; `original_value` preserved; confidence in `[0,1]` or
  NULL.
- Persian: digits fully normalised (no residual non-ASCII in numeric fields);
  Jalali date round-trips to the expected Gregorian day; original Persian string
  retained in `record_metadata`.

### Edge Cases

- Instrument selector missing / DOM changed (parser raises, pipeline contains it).
- Page loads but the value is JS-rendered late (wait-for-selector).
- Navigation timeout on one instrument (retry, then contained failure).
- Persian thousands separators and a decimal point in the same number.
- Duplicate scrape on the same trading day (idempotent upsert).
- Non-positive or zero price (reject as invalid).
- Database unavailable (integration skips; pipeline errors cleanly).
- Airflow metadata DB unreachable (DAG parse test still passes; runtime alerts).

---

## VALIDATION COMMANDS

### Level 1: Static Analysis

```bash
make format
make lint
make typecheck
```

Expect: ruff format clean, `ruff check` 0 errors, `mypy --strict` no issues.

### Level 2: Unit Tests

```bash
make test
```

Expect: all unit tests pass (World Bank suite unchanged), coverage ≥80%.

### Level 3: Integration Tests

```bash
make db-up
poetry run alembic upgrade head
make test-integration
make test-all
```

Expect: TGJU pipeline integration tests pass; `make test-all` green, coverage ≥80%.

### Level 4: Dependency & Schema Checks

```bash
poetry lock --check
poetry run alembic check          # no model drift (Phase 3 adds no columns)
make db-check
poetry run playwright install --dry-run chromium
```

Expect: lock in sync, no drift, TimescaleDB present, Chromium available.

### Level 5: Manual End-to-End

```bash
poetry run python -m src.connectors.tgju_scraper --dry-run
poetry run python -m src.connectors.tgju_scraper
```

Then verify the layers:

```bash
docker compose exec postgres psql -U iran_macro -d iran_macro_db \
  -c "SELECT source_name, source_type, count(*) FROM bronze.bronze_raw
      WHERE source_name='tgju' GROUP BY 1,2;" \
  -c "SELECT indicator_id, count(*), min(timestamp), max(timestamp)
      FROM silver.silver_cleaned WHERE source_name='tgju' GROUP BY 1 ORDER BY 1;" \
  -c "SELECT indicator_id, count(*) FROM gold.gold_analytical
      WHERE indicator_id LIKE 'TGJU.%' GROUP BY 1 ORDER BY 1;"
```

Airflow (manual, before declaring the phase done):

```bash
make airflow-init
make airflow-up
airflow dags list | grep tgju
airflow dags test tgju_daily
RUN_LIVE_API_TESTS=1 poetry run pytest tests/integration/ -m live -v
```

---

## ACCEPTANCE CRITERIA

- [ ] `TgjuScraper` implements all four `DataConnector` methods over Playwright,
      with injected transport/retry/rate-limiter (unit-tested with no browser)
- [ ] `tgju_parser.py` is pure (no I/O), normalises Persian/Arabic-Indic digits,
      and converts Jalali → Gregorian, storing the original Persian in metadata
- [ ] User-agent rotation and 1-2 req/sec throttling with backoff are in place
- [ ] Raw HTML persisted immutably in `bronze.bronze_raw` with
      `source_type="scraper"` and a `DataCollectionLog` audit row
- [ ] Scraper health (success rate, response time) recorded in the collection log
- [ ] `silver.silver_cleaned` holds one validated, deduplicated, outlier-flagged
      row per instrument per trading day, each linked to its Bronze parent
- [ ] `gold.gold_analytical` holds prices plus derived `RET1D` and `MA30` series
      with correct ids, units, and non-null `silver_id`
- [ ] `silver.py`/`gold.py` generalised **without changing the World Bank
      result** — the entire existing test suite passes unchanged
- [ ] `IndicatorCatalog` seeded from `discover()`, idempotently
- [ ] `python -m src.connectors.tgju_scraper` runs the full pipeline end to end
- [ ] Airflow `tgju_daily` DAG runs the pipeline at 23:00 Asia/Tehran with
      `catchup=False`, retries, and failure alerting; a backfill DAG exists
- [ ] `jdatetime`, `beautifulsoup4`, `lxml` added; `poetry lock` in sync
- [ ] Unit tests pass with no network/browser; integration tests pass against
      Docker; DAG import test passes
- [ ] `make check` passes all gates; coverage ≥80%
- [ ] Data dictionary documents every loaded TGJU instrument; README/roadmap
      updated

---

## RISKS & TRADE-OFFS

| Risk | Impact | Mitigation |
|------|--------|------------|
| **TGJU DOM/selectors unknown & change without notice** (AGENTS.md names this the top scraper risk) | Parser breaks silently; wrong or empty data | Capture real fixtures first (Task 2); parser **raises** on missing selectors; scraper health tracked; fixtures pin the contract; parser separated from scraper for cheap re-targeting |
| **JS-rendered content** | `content()` before render yields empty prices | `wait_for_selector` before reading; capture fixtures post-render |
| **Persian digits / Jalali dates** | Silent mis-parsing of numbers or dates | Dedicated pure functions tested against real glyphs; store Gregorian + original Persian in metadata |
| **`RetryPolicy` retryable set is requests-specific** | Playwright timeouts not retried | Generalise `RetryPolicy` (behaviour-preserving) or wrap navigation using `delay_for()` and catch `PlaywrightTimeoutError` |
| **Touching validated ETL (`silver.py`/`gold.py`)** | Could regress the Phase 2 World Bank path | Add seams with defaults bound to current behaviour; require the existing suite to pass **unchanged**; new source injects its parser/strategy |
| **Anti-scraping / IP blocking** | Daily runs blocked | UA rotation, ≥0.5s spacing, backoff, partial-failure tolerance; respect robots.txt; do not parallelise aggressively |
| **Airflow weight on a laptop** (PRD open question; 16GB constraint) | Orchestration too heavy / analyst-unfriendly | LocalExecutor + separate metadata DB; document cron/APScheduler fallback; keep DAGs thin |
| **Daily idempotency** | Re-runs duplicate rows | Stable trading-day timestamp + Silver upsert + Gold delete-and-reinsert; assert in integration test |
| **Coin premium may be derived, not scraped** | Wrong provenance | Decide during Task 2: scrape if TGJU publishes it, else compute and mark derived in metadata |
| **Global 80% coverage gate on a large new surface** | Gate fails even with tested code | Write tests alongside each module; parser (pure) carries most coverage cheaply |

### Trade-offs Accepted

1. **Playwright sync API** over async — matches the sync `DataConnector`
   protocol and Airflow's sync tasks; the untestable-without-browser surface is
   kept tiny by pushing logic into the pure parser.
2. **Generalise existing ETL** rather than fork TGJU-specific copies — one
   cleaning/validation core to maintain, at the cost of carefully preserving the
   World Bank behaviour behind default arguments.
3. **Daily end-of-day snapshot** as the MVP; full historical backfill is proven
   on a bounded range but not swept to inception this phase.
4. **TGJU-local pipeline runner** (rather than overloading `src/etl/pipeline.py`)
   to keep the validated World Bank runner untouched — mild duplication for lower
   regression risk.
5. **Airflow as specified**, with a documented lighter-weight fallback, honouring
   the PRD while acknowledging the local-machine constraint.

### Open Decisions

- **Trading-day timestamp semantics** for a homepage snapshot: midnight
  Asia/Tehran vs the page's displayed Jalali date. Affects idempotency and joins.
- **Generalise `RetryPolicy`** (add a retryable predicate) vs a scraper-local
  retry loop. First is cleaner and reused by future scrapers; second is lower
  blast-radius.
- **`silver_to_gold` strategy parameter** vs a separate `silver_to_gold_daily`.
  Parametrising is DRY; a sibling function is safer for the WB path.
- **Airflow metadata store**: separate `airflow` database vs a dedicated schema
  in the same DB. Separate DB is the cleaner isolation.
- **Coin premium**: scraped field vs computed (coin − 8.133g × 18K-equivalent).
- **Data-dictionary location**: keep under `docs/phase-2/` (add a section) vs
  promote to `docs/data_dictionary.md`.
- **Backfill data source**: TGJU per-instrument historical pages (structure
  unverified) vs deferring a full sweep to operations.

---

## NOTES

### Alignment with PRD & AGENTS.md

- PRD §8 Tasks 7-9 map 1:1 onto Phases 3.1-3.3 here; §18.1 lists Playwright +
  BeautifulSoup + requests for scraping (this plan uses Playwright for transport
  and BeautifulSoup/lxml for parsing).
- AGENTS.md mandates: parser file **separate** from scraper file
  (`tgju_scraper.py` + `tgju_parser.py`); store raw HTML in Bronze; Persian →
  Gregorian for storage with the original kept in metadata; mock Playwright in
  tests; 1-2 req/sec + robots.txt; `record_metadata` (never a `metadata`
  attribute); `text()` for raw SQL; tz-aware `utc_now()`.

### Key Design Decisions

1. **HTML lands in Bronze wrapped as a dict** — `{"html": …, "scraped_at": …,
   "url": …}` — because `raw_data` is JSONB; `wrap_envelope()` passes dicts
   through, so no list-envelope handling is needed. `extract_rows()` is **not**
   used for TGJU.
2. **The parser is the load-bearing, pure unit** — all Persian/Jalali/selector
   logic lives there, DB- and browser-free, so it carries the bulk of test
   coverage and is trivially re-targetable when TGJU changes.
3. **ETL is generalised behind defaults** — the World Bank path is the default;
   TGJU injects a parser (Silver) and a daily-metrics strategy (Gold).
4. **Chain-linking is passthrough for daily FX/gold** — no base-year breaks
   exist, so `chain_link()` returns unlinked levels with `is_chain_linked=False`;
   this is expected, not a gap.
5. **Orchestration holds no logic** — the DAG imports and calls
   `run_tgju_pipeline()`, so the pipeline is fully testable and runnable without
   Airflow.

### Deferred to Later Phases

- Multi-base-year chain-linking on real data — Phase 5 (SCI CPI).
- CBI/SCI scrapers (this scraper is their template) — Phase 5.
- Frequency **downsampling** (daily → monthly end-of-month) for cross-source
  analysis — first needed when a monthly source joins TGJU in the dashboard.
- Dashboard visualisation of FX/gold trends — Phase 7.
- Production/containerised Airflow, alerting integrations beyond logs — Phase 8.

### Success Metrics

After Phase 3 completion:

- [ ] `poetry run python -m src.connectors.tgju_scraper` loads all TGJU
      instruments end to end without manual intervention
- [ ] A single SQL query returns a daily FX or gold series with its `RET1D` and
      `MA30` derived series from Gold
- [ ] The `tgju_daily` DAG runs on schedule and lands data Bronze → Gold
- [ ] The scraper/parser pattern is concrete enough that Phase 5's CBI/SCI
      scrapers can copy it without redesign
- [ ] The World Bank suite still passes unchanged; `make check` and
      `make test-all` both green

---

## Confidence Assessment

**Confidence: 6/10**

**High confidence because:**

- The connector, ETL, retry, config, and pipeline patterns are validated in
  Phase 2 and directly reusable; this plan mostly *mirrors* proven code.
- Every storage constraint that could bite (JSONB HTML wrapping, `extract_rows`
  being WB-specific, NOT NULL `value`, composite Gold PK, NOT NULL derived
  `silver_id`, `record_metadata` naming) has been identified with a mitigation.
- The World-Bank-coupling in `silver.py`/`gold.py` is precisely located, and the
  generalisation is behaviour-preserving behind default arguments.
- Dependencies and scaffolding were verified on disk (jdatetime/bs4/lxml absent;
  playwright/fake-useragent/airflow present; empty `airflow/` dirs).

**Remaining uncertainty (why not higher):**

- **TGJU's live structure is unverified in this plan** — URLs, selectors, digit
  encoding, and Jalali presentation must be captured in Task 2 before parser
  code is real. Selector-level detail here is a hypothesis. This is the dominant
  risk and the main reason for a 6.
- **Persian/Jalali handling** is new to the codebase; correctness rests on real
  fixtures, not assumptions.
- **Airflow 3.x local setup** (metadata DB, tz scheduling, standalone vs
  compose) has integration friction and a genuine "too heavy?" open question.
- **Coin premium provenance** (scraped vs derived) and **backfill page
  structure** are unresolved until reconnaissance.

**Recommendation:** Proceed, but **front-load Task 2 (reconnaissance + fixtures)**
before committing to parser selectors — treat its findings as a checkpoint that
may adjust Tasks 4-5. Build bottom-up (deps → config → parser → scraper → ETL
seams → pipeline → Airflow), keeping the World Bank suite green at every step as
the regression guard. Revisit the Airflow-vs-cron decision after Task 9 if local
resource use proves painful.
