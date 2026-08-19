# Task: Phase 2 — World Bank Connector, ETL Pipeline & Chain-Linking

## Task Description

Build the first end-to-end data path through the platform: a World Bank API v2
connector that lands raw JSON in Bronze, a reusable Bronze → Silver → Gold
transformation pipeline with full lineage tracking, and the automated
chain-linking algorithm that reconciles base-year changes before data reaches
Gold.

**Why:** Phase 1 delivered the schema and the `DataConnector` protocol but not a
single row of real data. Phase 2 proves the medallion architecture works against
a live source, establishes the connector and ETL patterns that all eight
remaining sources will mirror, and delivers the chain-linking capability that is
the platform's core differentiator.

**Timeline:** Week 3-4

**PRD mapping:** Phase 2 = PRD §7 Task 4 (World Bank API Connector), Task 5
(Bronze → Silver → Gold pipeline), Task 6 (automated chain-linking).

## Scope

### In Scope

- [ ] `WorldBankConnector` implementing the `DataConnector` protocol, with a
      `WorldBankConfig` dataclass for per-connector settings
- [ ] Shared retry/backoff utility (`src/utils/retry.py`) usable by every future
      connector
- [ ] Bronze writer: raw API envelope persisted immutably + `DataCollectionLog`
      audit row
- [ ] Silver transformer: parse, validate, deduplicate, flag outliers, reject
      nulls, write `TransformationLog`
- [ ] Gold transformer: chain-linked series, derived growth rates, domain
      tagging, `TransformationLog`
- [ ] Chain-linking module (`src/chain_linking/splice.py`): break detection,
      splice method, confidence scoring, `ChainLinkingLog`
- [ ] `IndicatorCatalog` seeding from `discover()`
- [ ] Alembic migration adding the Silver uniqueness constraint
- [ ] `python -m src.connectors.world_bank` CLI entry point for manual runs
- [ ] `docs/data_dictionary.md` — first version, covering the World Bank
      indicator set
- [ ] Unit tests with captured API fixtures; integration tests for the full
      layer roundtrip; synthetic-data tests for chain-linking

### Out of Scope

- [ ] TGJU scraper and Playwright infrastructure (PRD Phase 3 — see
      **Discrepancy** in Notes)
- [ ] Airflow orchestration and scheduled DAGs (Phase 3)
- [ ] IMF, EIA, OPEC connectors (Phase 4)
- [ ] CBI TSD and SCI scrapers, Persian/Jalali date conversion (Phase 5)
- [ ] Streamlit dashboard and Plotly visualisations (Phase 7)
- [ ] CI/CD, backup automation, performance tuning (Phase 8)
- [ ] Forecasting / ML models (out of platform scope for now)
- [ ] Frequency conversion utilities (daily → monthly) — not needed until a
      sub-annual source lands in Phase 3

## Context

**Current State (verified 2026-08-18):** Phase 1 is complete and validated. The
repository contains the 4-layer schema (7 tables), a live TimescaleDB hypertable
on `gold.gold_analytical`, the `DataConnector` ABC, validation/logging/config
utilities, and 53 passing tests at 95.30% combined coverage. `src/etl/`,
`src/chain_linking/`, and `src/connectors/world_bank.py` do **not** exist yet —
`src/etl/` and `src/chain_linking/` are empty packages.

**Data flow this phase must realise:**

```text
World Bank API v2  (annual, IRN, 1960→present)
        ↓  WorldBankConnector.fetch()
bronze.bronze_raw          raw JSON envelope, immutable
        ↓  src/etl/silver.py
silver.silver_cleaned      one row per (indicator_id, timestamp), validated
        ↓  src/chain_linking/splice.py + src/etl/gold.py
gold.gold_analytical       chain-linked, growth rates, domain-tagged
```

**Storage constraints that shape the design** (from `src/database/schema.py`):

- `BronzeRaw.raw_data` is `Mapped[dict[str, Any]]` — the World Bank response is a
  **JSON array**, so it must be wrapped before insert.
- `SilverCleaned.value` is `Mapped[float]`, **NOT NULL** — null observations
  cannot be stored and must be skipped-and-counted.
- `SilverCleaned.bronze_id` and `GoldAnalytical.silver_id` are NOT NULL FKs —
  every derived row needs a real parent, including computed growth rates.
- `GoldAnalytical` has a composite PK `(id, timestamp)` (TimescaleDB requires
  the partitioning column in every unique index).
- `record_metadata` is the Python attribute; the physical column is `metadata`.

**Verified API behaviour (probed live on 2026-08-18):**

| Property | Observed |
|----------|----------|
| Response shape | JSON array `[meta, rows]` |
| `meta` keys | `page`, `pages`, `per_page`, `total`, `sourceid`, `lastupdated` (e.g. `"2026-07-13"`) |
| Row shape | `{indicator:{id,value}, country:{id,value}, countryiso3code, date:"2020", value:450269020578.621, unit:"", obs_status:"", decimal:0}` |
| Row ordering | **Newest first** (descending by date) |
| `date` field | Year as a **string** for annual indicators |
| `value` field | Nullable — gaps are `null`, not omitted rows |
| `unit` field | Always empty string in practice; real units come from the indicator endpoint |
| Default paging | `per_page=50`; `FP.CPI.TOTL.ZG` 1960:2026 → `total: 66, pages: 2` |
| Large paging | `per_page=20000` returns all 66 rows in one page |
| Invalid indicator | **HTTP 200** with `[{"message":[{"id":"120","key":"Invalid value","value":"The provided parameter value is not valid"}]}]` |
| Latency | One probe timed out at 25s; a 45s retry succeeded — set timeout ≥30s and lean on backoff |

**Chain-linking reality check:** World Bank WDI constant-price series are already
rebased by the Bank to a single reference year (`NY.GDP.MKTP.KD` is "constant
2015 US$"), so a single WB series contains **no internal base-year break**. This
is expected and does not invalidate Task 6 — the PRD itself specifies
chain-linking be proven with **unit tests using synthetic data**. Real
multi-base-year series arrive with SCI/CBI in Phase 5. The algorithm is built and
validated now so it is ready when that data lands; the Gold writer records
`is_chain_linked=False` and `chain_linking_confidence=None` for series with no
detected break.

## Proposed Approach

Follow the PRD task order, building bottom-up so each layer is testable before
the next depends on it:

1. **Retry utility first** — a decorator/helper every connector will use, unit
   tested with a fake clock so no test sleeps.
2. **Connector second** — `fetch()` returns a DataFrame; Bronze persistence is a
   separate concern so the connector stays unit-testable with captured fixtures
   and zero network access.
3. **ETL layers third** — one module per hop (`bronze.py`, `silver.py`,
   `gold.py`) plus a shared `lineage.py` that writes `TransformationLog`
   uniformly. Layer writers take a session so they compose inside one
   transaction.
4. **Chain-linking fourth** — pure functions over DataFrames, no database
   coupling; the Gold transformer calls it and persists the audit row.
5. **Wire-up last** — the module CLI runs discover → fetch → Bronze → Silver →
   Gold for the full indicator set, and the integration test asserts the row
   counts and FK chain end to end.

Reuse Phase 1 primitives rather than reinventing: `validate_data_quality()` for
Silver gating, `detect_outliers_iqr()` for flagging, `log_with_context()` for
structured logs, the existing exception hierarchy for failures.

## Task Metadata

**Type:** New Capability (connector + pipeline + algorithm)
**Complexity:** High
**Affected Areas:** Connectors, ETL, Chain-linking, Database (one migration), Docs, Tests
**Dependencies:** Phase 1 complete (schema, hypertable, `DataConnector`, config, validation utils)

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

| File | Why |
|------|-----|
| `AGENTS.md` | Authoritative conventions — connector patterns, `record_metadata`, `utc_now()`, chain-linking rules |
| `PRD.md` §7 Tasks 4-6, §16 | The requirements this plan implements |
| `src/connectors/base.py` | The exact ABC signatures to satisfy (`connect`/`discover`/`fetch`/`validate`) and `IndicatorMetadata` fields |
| `src/database/schema.py` | Every column, nullability, FK, and default the ETL must honour |
| `src/database/connection.py` | `get_db()`, `get_session()` context manager semantics (commit/rollback/close) |
| `src/utils/validation.py` | `ValidationResult`, `validate_data_quality()`, `detect_outliers_iqr()` signatures |
| `src/utils/exceptions.py` | Which exception to raise where |
| `src/utils/config.py` | `APIConfig.world_bank_url`, `CollectionConfig.retry_max`/`timeout` |
| `src/utils/logging.py` | `get_logger()`, `log_with_context()` usage |
| `tests/conftest.py` | Existing fixtures to reuse (`sample_timeseries`, `test_config`) |
| `tests/unit/connectors/test_base.py` | The connector unit-test pattern to mirror |
| `tests/integration/test_database.py` | The integration-test pattern: `pytestmark`, test-DB fixture, skip-when-unreachable, always-rollback session |
| `alembic/env.py` | `MANAGED_SCHEMAS`, `TIMESCALE_MANAGED_INDEXES`, autogenerate filters |
| `docs/phase-1/VALIDATION.md` | The validated environment baseline and the command sequence to re-run |

### Data References

- **Indicator set for this phase** (all annual, country `IRN`):

  | Indicator | Meaning | Domain |
  |-----------|---------|--------|
  | `NY.GDP.MKTP.CD` | GDP, current US$ | `gdp` |
  | `NY.GDP.MKTP.KD` | GDP, constant 2015 US$ | `gdp` |
  | `NY.GDP.MKTP.KN` | GDP, constant LCU | `gdp` |
  | `NY.GDP.MKTP.KD.ZG` | GDP growth, annual % | `gdp` |
  | `NY.GDP.PCAP.KD` | GDP per capita, constant 2015 US$ | `gdp` |
  | `FP.CPI.TOTL.ZG` | Inflation, consumer prices, annual % | `inflation` |
  | `NE.EXP.GNFS.CD` | Exports of goods and services, current US$ | `trade` |
  | `NE.IMP.GNFS.CD` | Imports of goods and services, current US$ | `trade` |
  | `NE.RSB.GNFS.CD` | External balance on goods and services | `trade` |
  | `SP.POP.TOTL` | Total population | `welfare` |
  | `SP.POP.GROW` | Population growth, annual % | `welfare` |
  | `EG.USE.PCAP.KG.OE` | Energy use per capita (best-effort; may be discontinued) | `energy` |

- **Expected volume:** ~12 indicators × ~66 years ≈ 800 Silver rows, plus derived
  growth-rate series in Gold. Small — correctness matters here, not throughput.
- **Known gaps:** Iranian series have sanctions-era holes; several indicators
  stop before the present. Gaps must be **flagged, never interpolated** at
  Silver.
- **Captured fixtures:** save real responses to
  `tests/fixtures/world_bank/{indicator}_{scenario}.json` so unit tests never
  touch the network.

### External Documentation

- World Bank Indicators API v2 — https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
- Paging and format parameters — https://datahelpdesk.worldbank.org/knowledgebase/articles/898581
- WDI metadata (units, source notes) — https://databank.worldbank.org/source/world-development-indicators
- Chain-linking methodology (OECD) — https://www.oecd.org/sdd/na/chainlinking.htm
- TimescaleDB hypertable inserts — https://docs.timescale.com/use-timescale/latest/hypertables/

### Patterns to Follow

| Pattern | Source |
|---------|--------|
| Connector subclass + context manager | `src/connectors/base.py`, `tests/unit/connectors/test_base.py` |
| Timezone-aware timestamps via `utc_now()` | `src/database/schema.py` |
| Session-per-unit-of-work with rollback on error | `src/database/connection.py::get_session` |
| Structured logging with context dict | `src/utils/logging.py::log_with_context` |
| Validation returning `ValidationResult`, not raising | `src/utils/validation.py` |
| Integration test that self-provisions a `_test` database and skips cleanly | `tests/integration/test_database.py` |
| Config as Pydantic settings with aliases + `populate_by_name=True` | `src/utils/config.py` |

---

## IMPLEMENTATION PLAN

### Phase 2.1: Foundation (shared utilities + migration)

Retry/backoff helper, the Silver uniqueness migration, and the indicator
registry constants. Nothing downstream can be built safely without these.

### Phase 2.2: Core Change (connector + ETL layers)

`WorldBankConnector` and the three ETL modules with lineage logging. This is the
bulk of the phase and the part all future connectors will copy.

### Phase 2.3: Integration (chain-linking + Gold wiring + CLI)

Chain-linking module, its integration into the Gold transformer, catalog
seeding, and the runnable pipeline entry point.

### Phase 2.4: Validation (tests, docs, end-to-end proof)

Unit + integration + synthetic tests, data dictionary, and the full validation
command sequence.

---

## STEP-BY-STEP TASKS

### Task 1: REMOVE `alembic/versions/20260818_1337_initial_schema.py`

- **IMPLEMENT:** Delete the stray no-op migration (revision `a8b6302444ef`,
  `down_revision = "9a0d7ad75b18"`, both `upgrade()` and `downgrade()` are
  `pass`). It is an untracked autogenerate artefact with no content.
- **PATTERN:** Real migrations look like
  `alembic/versions/20260817_1456_initial_schema.py`.
- **DEPENDENCIES:** None.
- **GOTCHA:** Must happen **before** Task 2, otherwise the new migration chains
  off a no-op revision and the history carries a permanent dead link. Confirm
  the file is untracked (`git status`) and that no database has it applied
  (`alembic current`) before deleting.
- **VALIDATE:** `poetry run alembic history` shows a single head at
  `9a0d7ad75b18`; `poetry run alembic check` reports no drift.

### Task 2: CREATE `alembic/versions/<ts>_silver_unique_constraint.py`

- **IMPLEMENT:** Add a unique constraint
  `uq_silver_indicator_timestamp` on `silver.silver_cleaned (indicator_id,
  timestamp)` so the Silver layer can enforce AGENTS.md's "reject duplicate
  `(indicator_id, timestamp)`" rule at the database level, and so upserts have a
  conflict target.
- **PATTERN:** Generate with
  `poetry run alembic revision --autogenerate -m "Silver unique constraint"`
  after adding a `UniqueConstraint` to `SilverCleaned.__table_args__` in
  `src/database/schema.py`.
- **DEPENDENCIES:** Task 1.
- **GOTCHA:** `__table_args__` on `SilverCleaned` is a tuple ending in the
  `{"schema": "silver"}` dict — the new constraint goes **before** that dict.
  Do **not** add a unique constraint to `GoldAnalytical`: TimescaleDB requires
  the partitioning column in every unique index, so any Gold uniqueness must
  include `timestamp`.
- **VALIDATE:** `poetry run alembic upgrade head` succeeds;
  `poetry run alembic check` clean; `poetry run alembic downgrade -1 &&
  poetry run alembic upgrade head` roundtrips.

### Task 3: CREATE `src/utils/retry.py`

- **IMPLEMENT:** `retry_with_backoff` decorator (and/or a `RetryPolicy` helper):
  exponential backoff with jitter, max attempts from
  `CollectionConfig.retry_max`, base delay configurable, plus a
  `RateLimiter`-style minimum spacing between requests.
- **PATTERN:** Read config via `get_config().collection`; log every retry with
  `log_with_context(logger, "WARNING", "retrying", attempt=…, delay=…, url=…)`.
- **DEPENDENCIES:** `src/utils/config.py`, `src/utils/logging.py`,
  `src/utils/exceptions.py`.
- **GOTCHA:** Retry `requests.Timeout`, `requests.ConnectionError`, HTTP 5xx and
  429 — but **never** 4xx other than 429 (a bad indicator code will never
  succeed). Use `time.monotonic()` for elapsed time, not `time.time()`. Raise
  `DataRetrievalError` (from `src/utils/exceptions.py`) when attempts are
  exhausted, chaining the original with `raise … from exc`. Inject the sleep
  function so unit tests can pass a no-op and run instantly. Note that
  `src/utils/exceptions.py` shadows the builtin `ConnectionError` — import the
  `requests` exception under an alias to avoid ambiguity.
- **VALIDATE:** `poetry run pytest tests/unit/utils/test_retry.py -v`;
  `poetry run mypy src/utils/retry.py`.

### Task 4: CREATE `src/connectors/world_bank.py`

- **IMPLEMENT:** `WorldBankConfig` dataclass (base URL from
  `APIConfig.world_bank_url`, `country="IRN"`, `per_page=20000`,
  `timeout` ≥ 30s, `date_range=(1960, current_year)`) and
  `WorldBankConnector(DataConnector)`:
  - `connect()` — probe a cheap endpoint, return `bool`, set up a
    `requests.Session`.
  - `discover()` — call `/indicator/{id}` per configured indicator, return
    `list[IndicatorMetadata]` (name, description from `sourceNote`, unit,
    `frequency="annual"`, domain, `source_name="world_bank"`, source URL,
    availability start/end).
  - `fetch(indicator_id, start_date, end_date)` — paginated GET, return a
    DataFrame with columns `timestamp`, `value`, `indicator_id`, `unit`,
    `obs_status`, and carry the raw envelope for the Bronze writer.
  - `validate(data)` — delegate to `validate_data_quality()`.
  - `disconnect()` — close the session.
  - `__main__` guard delegating to the pipeline runner (Task 10).
- **PATTERN:** Mirror the ABC exactly as in `src/connectors/base.py`; decorate
  HTTP calls with the Task 3 retry helper.
- **DEPENDENCIES:** Tasks 3; `src/connectors/base.py`, `src/utils/*`.
- **GOTCHA:**
  - The API returns **HTTP 200 with an error payload** for an invalid indicator:
    `raise_for_status()` is not sufficient. Detect a top-level `message` key and
    raise `DataRetrievalError`.
  - Rows arrive **newest-first**; sort ascending by timestamp before returning.
  - `date` is a **year string** for annual data — convert to
    `datetime(year, 12, 31, tzinfo=UTC)` (period end, timezone-aware).
  - Observation `unit` is always `""`; take the real unit from the indicator
    endpoint, not the data rows.
  - `value` may be `null` — keep nulls in the DataFrame so `validate()` can
    measure `null_percentage`; they are dropped at Silver, not here.
  - Drop observations whose period end is in the future, or
    `validate_date_range()` will report future dates as an error.
  - `fetch()` must not write to the database — Bronze persistence is Task 5.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_world_bank.py -v`;
  `poetry run mypy src/connectors/world_bank.py`.

### Task 5: CREATE `src/etl/bronze.py`

- **IMPLEMENT:** `write_bronze(session, source_name, source_type, raw_envelope,
  request_url, http_status_code, record_metadata) -> UUID` — insert one
  `BronzeRaw` row and one `DataCollectionLog` row; return the Bronze id.
- **PATTERN:** Take an existing `Session` so the caller controls the
  transaction; use `session.flush()` to obtain the generated UUID without
  committing.
- **DEPENDENCIES:** `src/database/schema.py`, `src/database/connection.py`.
- **GOTCHA:** `BronzeRaw.raw_data` is typed `Mapped[dict[str, Any]]` but the API
  returns a **list** — wrap it as `{"meta": envelope[0], "rows": envelope[1]}`
  and record the wrapping convention in the data dictionary so re-parsing works.
  Never mutate or re-write a Bronze row: it is immutable by contract.
  `collection_timestamp` defaults via `utc_now` at INSERT — do not set it by
  hand.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_bronze.py -v`.

### Task 6: CREATE `src/etl/lineage.py`

- **IMPLEMENT:** `record_transformation(session, source_layer, target_layer,
  transformation_type, records_processed, records_failed, status,
  error_message=None, record_metadata=None)` writing one `TransformationLog`
  row; plus a context manager that captures start/end and marks `failed` on
  exception.
- **PATTERN:** Same session-in signature as Task 5; statuses limited to
  `success` / `partial` / `failed`.
- **DEPENDENCIES:** `src/database/schema.py`.
- **GOTCHA:** The audit row must be written even when the transformation fails —
  on failure the caller rolls back data changes but the log needs its own
  session/commit boundary. Decide and document that boundary explicitly rather
  than losing failure records to the rollback.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_lineage.py -v`.

### Task 7: CREATE `src/etl/silver.py`

- **IMPLEMENT:** `bronze_to_silver(session, bronze_id, indicator_id,
  source_name) -> TransformResult`:
  1. Load the Bronze row, parse `rows` into a DataFrame.
  2. Drop null-valued observations, counting them as `records_failed`.
  3. Reject duplicate `(indicator_id, timestamp)` pairs.
  4. Run `validate_data_quality()`; set `validation_status` per row.
  5. Flag outliers via `detect_outliers_iqr()` — set `is_outlier=True`, **do not
     drop**.
  6. Insert `SilverCleaned` rows with `bronze_id` set.
  7. Write the `TransformationLog` row via Task 6.
- **PATTERN:** Reuse `src/utils/validation.py` rather than writing new checks.
- **DEPENDENCIES:** Tasks 5, 6.
- **GOTCHA:** `SilverCleaned.value` is NOT NULL — nulls **must** be skipped, and
  the count surfaced in the transformation log so gaps stay visible.
  `validation_status` and `is_outlier` are `mapped_column(default=…)`, i.e.
  INSERT-time defaults — reading them on an unflushed instance yields `None`.
  Re-running the pipeline must be idempotent: use an upsert against
  `uq_silver_indicator_timestamp` (Task 2) or check-then-skip, and state which.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_silver.py -v`.

### Task 8: CREATE `src/chain_linking/splice.py`

- **IMPLEMENT:**
  - `detect_base_year_breaks(df) -> list[BaseYearBreak]` — identify
    discontinuities where a series changes base year (level jump without a
    corresponding growth-rate jump, or explicit metadata).
  - `splice_series(old, new, overlap) -> pd.DataFrame` — rescale the older
    segment onto the newer base using the overlap-period ratio, preserving
    growth rates.
  - `calculate_confidence(overlap_months, growth_variance) -> float` — score
    from overlap length and growth-rate variance.
  - `chain_link(df, metadata) -> ChainLinkResult` — orchestrates the above and
    returns linked values plus the fields `ChainLinkingLog` needs
    (`base_year_from`, `base_year_to`, `linking_method`, `records_linked`,
    `avg_confidence_score`, `overlap_period_months`, `growth_rate_variance`).
- **PATTERN:** Pure functions over DataFrames — **no database access** in this
  module, so it is trivially unit-testable with synthetic fixtures.
- **DEPENDENCIES:** `src/utils/exceptions.py` (`ChainLinkingError`).
- **GOTCHA:** AGENTS.md requires ≥12 months of overlap; for **annual** series 12
  months is a single data point, which cannot support a variance estimate.
  Define `MIN_OVERLAP_PERIODS = 3` years for annual frequency and document the
  frequency-dependent minimum. Growth rates must be preserved within **±1%** —
  assert this inside `splice_series` and raise `ChainLinkingError` on violation.
  Never overwrite the original observation: Gold keeps `original_value` beside
  the linked `value`. Guard against division by zero and sign changes in the
  overlap ratio.
- **VALIDATE:** `poetry run pytest tests/unit/chain_linking/test_splice.py -v`;
  `poetry run mypy src/chain_linking/splice.py`.

### Task 9: CREATE `src/etl/gold.py`

- **IMPLEMENT:** `silver_to_gold(session, indicator_id) -> TransformResult`:
  1. Load the Silver series for the indicator.
  2. Run `chain_link()`; set `value`, `original_value`, `is_chain_linked`,
     `chain_linking_confidence`.
  3. Compute derived series (year-over-year growth) as additional Gold rows.
  4. Tag `domain` from the indicator registry.
  5. Insert `GoldAnalytical` rows with `silver_id` set.
  6. Write `ChainLinkingLog` (when a break was detected) and
     `TransformationLog`.
- **PATTERN:** Same session-in signature as the other ETL modules.
- **DEPENDENCIES:** Tasks 7, 8, 6.
- **GOTCHA:** `GoldAnalytical.silver_id` is NOT NULL — a derived growth-rate row
  must still reference a real Silver parent; use the row the value was computed
  **at** (the later of the two periods) and record the derivation in
  `record_metadata`. Give derived rows distinct ids, e.g.
  `WB.NY.GDP.MKTP.KD.YOY`, so they never collide with source indicators. The PK
  is `(id, timestamp)`; inserts must supply a timestamp. When no break is
  detected, write `is_chain_linked=False` and leave
  `chain_linking_confidence=None` — do not fabricate a confidence of 1.0.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_gold.py -v`.

### Task 10: CREATE `src/etl/pipeline.py` + CLI wiring

- **IMPLEMENT:** `run_world_bank_pipeline(indicators=None, dry_run=False)` —
  connect, `discover()` → seed/refresh `IndicatorCatalog`, then per indicator:
  fetch → Bronze → Silver → Gold, aggregating a summary. Wire
  `python -m src.connectors.world_bank` to it with `argparse`
  (`--indicators`, `--dry-run`, `--log-level`).
- **PATTERN:** One `get_session()` block per indicator so a single failure does
  not abort the whole run; log a per-indicator summary with
  `log_with_context()`.
- **DEPENDENCIES:** Tasks 4-9.
- **GOTCHA:** `IndicatorCatalog.indicator_id` is the primary key — seeding must
  upsert, not blind-insert, or a second run raises a unique violation. Continue
  past a failed indicator (log and count it) rather than raising, but exit
  non-zero if any indicator failed so callers and future Airflow tasks can
  detect it.
- **VALIDATE:** `poetry run python -m src.connectors.world_bank --dry-run`.

### Task 11: CREATE `tests/fixtures/world_bank/*.json`

- **IMPLEMENT:** Capture real responses: a normal series, a series with null
  gaps, a two-page paginated response, the invalid-indicator error payload, and
  an indicator-metadata response.
- **PATTERN:** Verbatim API JSON, one file per scenario; loaded by a
  `conftest.py` fixture helper.
- **DEPENDENCIES:** Task 4 (to know which calls matter).
- **GOTCHA:** Capture the **raw** envelope including `meta` — the Bronze writer
  stores it, so fixtures must exercise the wrapping. Do not hand-edit values
  into unrealistic shapes; if a scenario cannot be captured live, generate it and
  label it synthetic in a comment sidecar.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_world_bank.py -v`
  passes with **no** network access.

### Task 12: CREATE unit test suites

- **IMPLEMENT:** `tests/unit/utils/test_retry.py`,
  `tests/unit/connectors/test_world_bank.py`, `tests/unit/etl/test_bronze.py`,
  `test_silver.py`, `test_gold.py`, `test_lineage.py`,
  `tests/unit/chain_linking/test_splice.py`.
- **PATTERN:** Mirror `tests/unit/connectors/test_base.py`; mock all HTTP via
  the captured fixtures; add `__init__.py`-free package dirs matching the
  existing layout.
- **DEPENDENCIES:** Tasks 3-11.
- **GOTCHA:** The 80% coverage gate is global — new modules with thin tests will
  drag the whole project under the threshold. `tests/**` has ruff per-file
  ignores for `ARG` and `PLR2004`, so fixture arguments and magic numbers are
  fine in tests but **not** in `src/`. Pass a no-op sleep into the retry helper
  so the suite stays fast.
- **VALIDATE:** `make test` — all pass, coverage ≥80%.

### Task 13: CREATE `tests/integration/test_world_bank_pipeline.py`

- **IMPLEMENT:** Full Bronze → Silver → Gold roundtrip against the live test
  database using **fixture** data (not live API calls): assert row counts per
  layer, FK integrity, that Gold rows land in the hypertable, that
  `TransformationLog` rows exist for both hops, and that a re-run is idempotent.
  Add a separate `@pytest.mark.live` test that hits the real API and is skipped
  by default.
- **PATTERN:** Copy the harness from `tests/integration/test_database.py` —
  module-level `pytestmark = pytest.mark.integration`, self-provisioned
  `{name}_test` database, `pytest.skip()` when PostgreSQL is unreachable,
  function-scoped session that always rolls back.
- **DEPENDENCIES:** Tasks 10, 11.
- **GOTCHA:** The test database needs the Task 2 migration applied, so the
  fixture must run `create_all_tables()` **after** the schema change (or run
  Alembic). Rolled-back sessions mean assertions must happen inside the same
  transaction. Keep the `live` test out of `make test-all`.
- **VALIDATE:** `make test-integration`.

### Task 14: CREATE `docs/data_dictionary.md`

- **IMPLEMENT:** Per-indicator table (id, name, unit, frequency, domain,
  coverage years, source URL, known gaps, base-year note), the Bronze
  `raw_data` wrapping convention, the derived-indicator naming scheme, and the
  chain-linking confidence interpretation.
- **PATTERN:** Match the tone and table style of `docs/phase-1/VALIDATION.md`.
- **DEPENDENCIES:** Task 10 (real coverage numbers come from an actual run).
- **GOTCHA:** Record **observed** coverage from the run, not what the World Bank
  claims. Note `lastupdated` from the API `meta` so staleness is auditable.
- **VALIDATE:** Every indicator the pipeline loads has a row; no placeholders.

### Task 15: UPDATE `README.md`, `AGENTS.md`, `docs/phase-1/VALIDATION.md`

- **IMPLEMENT:** Flip the data-sources table so **World Bank** is accurately
  marked implemented and the rest reflect real phases; update the roadmap; add
  the connector-implementation pattern reference to `AGENTS.md` if the built
  pattern differs from what is documented; correct the "Next Steps (Phase 2)"
  list in `VALIDATION.md` so TGJU is attributed to Phase 3.
- **PATTERN:** Existing document structure — edit in place, no restructuring.
- **DEPENDENCIES:** Tasks 4-14.
- **GOTCHA:** `README.md` **already** claims the World Bank connector is
  "✓ Implemented" and lists `world_bank.py`, `imf.py`, `tgju_scraper.py`,
  `cbi_scraper.py` in the project structure. Those claims are currently false;
  this task is what makes the first one true and must correct the rest.
- **VALIDATE:** Documentation matches observed reality — re-read after the run.

---

## TESTING & VALIDATION

### Unit Tests

- **Retry:** succeeds first try; retries then succeeds; exhausts and raises
  `DataRetrievalError`; does **not** retry 404; does retry 429 and 503; backoff
  grows; jitter stays within bounds.
- **Connector:** parses a normal fixture; handles null values; follows
  pagination across two pages; raises `DataRetrievalError` on the HTTP-200 error
  payload; sorts ascending; converts year strings to `datetime(y,12,31,UTC)`;
  drops future periods; `discover()` maps metadata fields; context manager
  closes the session; cannot be instantiated abstractly (mirrors
  `test_base.py`).
- **Bronze:** wraps the list envelope into a dict; returns a UUID; writes a
  `DataCollectionLog` row.
- **Silver:** skips nulls and counts them; rejects duplicates; flags outliers
  without dropping; sets `bronze_id`; writes a `TransformationLog`.
- **Gold:** sets `original_value` and `value`; growth rows get correct ids and a
  non-null `silver_id`; `is_chain_linked=False` with `confidence=None` when no
  break; domain tagging.
- **Lineage:** success/partial/failed statuses; failure still records a row.

### Integration Tests

- Full pipeline from fixture JSON through all three layers with correct counts.
- FK chain: every Silver row resolves to a Bronze row; every Gold row to a
  Silver row.
- Gold rows are queryable through the hypertable.
- Re-running the pipeline does not duplicate Silver rows.
- `TransformationLog` and `ChainLinkingLog` rows written as expected.
- `@pytest.mark.live`: real API fetch for one indicator returns ≥50 annual
  observations.

### Data Validation

- Silver: no nulls in `value`; no duplicate `(indicator_id, timestamp)`; all
  timestamps timezone-aware; no future periods.
- Gold: chain-linked growth rates match Silver growth rates within **±1%**;
  `original_value` always preserved; confidence in `[0, 1]` or `NULL`.
- Cross-layer: Silver row count = Bronze observation count − nulls − duplicates.
- Coverage: ≥50 years for at least `NY.GDP.MKTP.CD` and `SP.POP.TOTL`
  (the PRD's "50+ years in Gold" deliverable).

### Chain-Linking Validation (synthetic)

Per PRD Task 6, correctness is proven on synthetic series where the answer is
known:

- Two segments with a known scale factor → splice recovers it exactly.
- Growth rates identical before and after linking (within ±1%).
- Confidence rises with longer overlap and falls with higher variance.
- Insufficient overlap (<`MIN_OVERLAP_PERIODS`) → `ChainLinkingError`.
- No break present → passthrough, `is_chain_linked=False`.
- Three-segment chain links transitively in the right order.

### Edge Cases

- Indicator returns zero observations for Iran.
- Indicator discontinued mid-series (`EG.USE.PCAP.KG.OE`).
- All-null series.
- Network timeout on page 2 of a paginated fetch.
- API returns a `message` payload mid-run.
- Duplicate `(indicator_id, timestamp)` across two Bronze rows from re-runs.
- Zero or sign-flipping values in the chain-linking overlap window.
- Database unavailable (integration tests skip, pipeline errors cleanly).

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

Expect: all unit tests pass, coverage ≥80% (Phase 1 baseline was 40 tests /
86.68%).

### Level 3: Integration Tests

```bash
make db-up
poetry run alembic upgrade head
make test-integration
make test-all
```

Expect: pipeline integration tests pass; `make test-all` passes with coverage
≥80%.

### Level 4: Migration & Schema Checks

```bash
poetry run alembic history
poetry run alembic check
poetry run alembic downgrade -1 && poetry run alembic upgrade head
make db-check
```

Expect: single head, no drift, clean roundtrip, TimescaleDB extension present.

### Level 5: Manual End-to-End

```bash
poetry run python -m src.connectors.world_bank --dry-run
poetry run python -m src.connectors.world_bank
```

Then verify the layers:

```bash
docker compose exec postgres psql -U iran_macro -d iran_macro_db \
  -c "SELECT source_name, count(*) FROM bronze.bronze_raw GROUP BY 1;" \
  -c "SELECT indicator_id, count(*), min(timestamp), max(timestamp)
      FROM silver.silver_cleaned GROUP BY 1 ORDER BY 1;" \
  -c "SELECT indicator_id, count(*), bool_or(is_chain_linked)
      FROM gold.gold_analytical GROUP BY 1 ORDER BY 1;" \
  -c "SELECT source_layer, target_layer, status, sum(records_processed)
      FROM metadata.transformation_log GROUP BY 1,2,3;"
```

Live-API check (manual, before declaring the phase done):

```bash
poetry run pytest tests/integration/ -m live -v
```

---

## ACCEPTANCE CRITERIA

- [ ] `WorldBankConnector` implements all four `DataConnector` abstract methods
- [ ] Retry/backoff utility exists, is config-driven, and is reused by the
      connector
- [ ] Raw API envelopes persisted immutably in `bronze.bronze_raw` with
      `DataCollectionLog` audit rows
- [ ] `silver.silver_cleaned` populated with validated, deduplicated,
      outlier-flagged rows, each linked to its Bronze parent
- [ ] `gold.gold_analytical` populated with chain-linked values, preserved
      `original_value`, derived growth rates, and domain tags
- [ ] Chain-linking module implements break detection, splice, and confidence
      scoring, with `ChainLinkingLog` rows written when a break is linked
- [ ] Growth rates preserved within ±1% through chain-linking (asserted in
      tests)
- [ ] `IndicatorCatalog` seeded from `discover()`, idempotently
- [ ] `TransformationLog` written for every Bronze→Silver and Silver→Gold run,
      including failures
- [ ] ≥50 years of continuous GDP data queryable from Gold (PRD §16 validation)
- [ ] `python -m src.connectors.world_bank` runs the full pipeline end to end
- [ ] Silver uniqueness migration applied; `alembic check` clean; roundtrip
      verified
- [ ] Unit tests pass with no network access; integration tests pass against
      Docker
- [ ] `make check` passes all gates; coverage ≥80%
- [ ] `docs/data_dictionary.md` documents every loaded indicator
- [ ] `README.md` data-source table and roadmap match observed reality

---

## RISKS & TRADE-OFFS

| Risk | Impact | Mitigation |
|------|--------|------------|
| **World Bank API latency/instability** — one probe timed out at 25s | Pipeline runs fail intermittently | Timeout ≥30s, retry with backoff, per-indicator isolation so one failure does not abort the run |
| **No real base-year break in WDI data** — constant-price series are pre-rebased | Chain-linking cannot be validated on real data this phase | Prove correctness on synthetic fixtures (as the PRD specifies); real multi-base series arrive with SCI/CBI in Phase 5; keep the module database-free so it is reusable unchanged |
| **`SilverCleaned.value` is NOT NULL** | Genuine data gaps cannot be represented as rows | Skip nulls, count them in `TransformationLog`, and document the convention; revisit making `value` nullable if analysts need explicit gap rows |
| **Silver had no unique constraint** | Re-runs silently duplicate observations | Add `uq_silver_indicator_timestamp` (Task 2) and make the writer idempotent |
| **Derived Gold rows need a non-null `silver_id`** | Growth-rate rows have no single natural parent | Attribute to the later period's Silver row and record the derivation in `record_metadata` |
| **Global 80% coverage gate** | A large new surface area can fail the gate even if new code is tested | Write tests alongside each module, not at the end; check coverage after each task |
| **README already claims the connector exists** | Docs are currently misleading | Task 15 corrects every false claim, not just the World Bank row |
| **Stray no-op migration on disk** | A new migration would chain off a dead revision | Delete it first (Task 1) and confirm a single head |

### Trade-offs Accepted

1. **`fetch()` returns a DataFrame and does not write Bronze.** Keeps the
   connector unit-testable without a database, at the cost of the caller having
   to pass the raw envelope through to the Bronze writer.
2. **Chain-linking is pure/database-free.** More plumbing in `gold.py`, but the
   algorithm is testable in isolation and reusable by every future source.
3. **One session per indicator, not one per run.** Weaker global atomicity, far
   better partial-failure behaviour for a 12-indicator batch.
4. **`per_page=20000` single-request fetches.** Pagination is still implemented
   and tested (via fixtures), but normal runs make one call per indicator.
5. **Docs updated at the end (Task 15).** Coverage numbers must come from a real
   run, so documentation cannot be written first.

### Open Decisions

- **Domain taxonomy for population and energy.** The PRD's domains are
  gdp/inflation/trade/monetary/energy/welfare. This plan assigns population →
  `welfare` and energy-use → `energy`. Confirm before seeding the catalog, since
  the dashboard will group by it.
- **`TransformationLog` transaction boundary on failure** — a separate session
  guarantees failures are recorded but breaks strict atomicity with the data
  write. Decide during Task 6.
- **Upsert vs check-then-skip for Silver idempotency.** Upsert is cleaner;
  check-then-skip is more auditable. Pick one and apply it consistently.
- **Whether `EG.USE.PCAP.KG.OE` stays in the set** if it proves discontinued for
  Iran — drop it or keep it as a documented sparse series.

---

## NOTES

### Discrepancy: what Phase 2 contains

`docs/phase-1/VALIDATION.md` ("Next Steps") and
`docs/phase-1/IMPLEMENTATION_REPORT.md` both list the **TGJU scraper** under
Phase 2. `PRD.md` §7 places TGJU in **Phase 3** and defines Phase 2 as Tasks
4-6 (World Bank connector, ETL pipeline, chain-linking).

This plan follows the **PRD**, because `docs/plans/phase-1-foundation.md` maps
1:1 to PRD Phase 1 Tasks 1-3 and `AGENTS.md` instructs "Follow PRD task order".
Task 15 corrects the Phase-1 documents so the phase boundary is unambiguous.

Also note: `README.md` currently marks the World Bank connector
"✓ Implemented" and lists four connector files in its project structure. None
of those files exist today. Completing this plan makes the World Bank claim
true; Task 15 corrects the remainder.

### Key Design Decisions

1. **Bronze stores the wrapped envelope.** `{"meta": …, "rows": […]}` — required
   because `raw_data` is typed as a dict while the API returns a list. The
   `meta.lastupdated` value is worth keeping for staleness auditing.
2. **Annual timestamps are period-end.** `datetime(year, 12, 31, tzinfo=UTC)`.
   Consistent, sortable, and compatible with future monthly/daily sources.
3. **Derived indicators are namespaced.** `WB.NY.GDP.MKTP.KD.YOY` — never
   collides with a source indicator id.
4. **Nulls are recorded, not imputed.** AGENTS.md forbids silently filling gaps;
   the counts live in `TransformationLog`.
5. **Outliers are flagged, not dropped.** Iranian macro series legitimately
   contain extreme values (hyperinflation, sanctions shocks).
6. **Minimum overlap is frequency-dependent.** AGENTS.md's "12 months" is one
   observation for annual data; annual series need ≥3 periods for a meaningful
   variance estimate.

### Deferred to Later Phases

- Frequency conversion (daily → monthly end-of-month, upsample forward-fill
  only) — needed first by TGJU in Phase 3.
- Persian/Jalali date conversion — Phase 5 (CBI/SCI).
- Airflow DAGs wrapping the pipeline runner — Phase 3.
- Real multi-base-year chain-linking validation — Phase 5, when SCI/CBI series
  with actual base-year changes arrive.
- Query-performance work on the hypertable — Phase 7/8.

### Success Metrics

After Phase 2 completion:

- [ ] `poetry run python -m src.connectors.world_bank` loads all configured
      indicators end to end without manual intervention
- [ ] A single SQL query returns a continuous ≥50-year GDP series from Gold
- [ ] The connector pattern is concrete enough that Phase 3's TGJU scraper can
      copy it without redesign
- [ ] `make check` and `make test-all` both green

---

## Confidence Assessment

**Confidence: 8/10**

**High confidence because:**

- The API contract was verified empirically against the live endpoint on
  2026-08-18 (envelope shape, paging, ordering, null handling, the HTTP-200
  error payload), not recalled from memory
- Phase 1's schema, connector ABC, validation utilities, and test harnesses are
  validated and directly reusable
- Every storage constraint that could bite (NOT NULL `value`, dict-typed
  `raw_data`, composite Gold PK, NOT NULL FKs, INSERT-time defaults) has been
  identified up front and has an explicit mitigation
- The scope maps cleanly onto three PRD tasks with a documented resolution of
  the Phase 2 boundary conflict

**Remaining uncertainty:**

- **Chain-linking cannot be validated on real data this phase** — WDI
  constant-price series carry no internal base-year break, so correctness rests
  on synthetic fixtures. The algorithm's real-world behaviour is unproven until
  Phase 5.
- **Iranian data coverage is unknown per indicator** until a real run; some
  series may be too sparse to be useful, and `EG.USE.PCAP.KG.OE` may be
  discontinued entirely.
- **API reliability** — the observed timeout suggests runs may need several
  attempts.
- **`TransformationLog` failure-path transaction boundary** is a genuine design
  decision left open, and getting it wrong loses failure records.

**Recommendation:** Proceed. Start with Task 1 (delete the stray migration) and
Task 2 (Silver uniqueness) since everything downstream assumes them, then build
bottom-up. Revisit the chain-linking confidence thresholds after the first real
multi-base-year source lands in Phase 5.
