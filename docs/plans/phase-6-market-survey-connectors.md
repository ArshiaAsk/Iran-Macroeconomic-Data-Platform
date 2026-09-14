# Task: Phase 6 — Market & Survey Connectors (TSETMC Stock Market + HBSIR Household Survey)

## Task Description

Add the platform's first **Python-package-backed** data sources, completing the
"Market & Survey Data" phase of the PRD:

1. A **Tehran Stock Exchange (TSETMC)** connector that wraps the `finpy-tse`
   package (or `TseClient`) to collect **daily** capital-market indicators —
   **TEDPIX index**, **retail trading value**, and the **market P/E ratio**
   (plus market capitalization if the package exposes it historically) — and
   publishes a **month-end downsampled** series so market data can be aligned
   with monthly CPI/FX in cross-domain analysis.
2. A **Household Budget Survey (HBSIR)** connector that wraps the `hbsir`
   package (Iran Open Data) to derive **annual inequality and welfare
   indicators** — **Gini coefficient**, **poverty rate**, and **income decile
   shares** — from survey microdata, stored once per survey year aligned to the
   Iranian survey year end.

**Why:** Phases 1–5 and 7 delivered API connectors, HTML/file scrapers, real
chain-linking, and a dashboard. Phase 6 is the remaining PRD data phase and the
first time the platform consumes a **Python library as the transport** rather
than HTTP directly. It also adds the first **capital-market** domain (equity
returns and valuation, distinct from FX/gold/inflation) and the first
**microdata-derived** indicators (Gini/poverty computed by the platform, not
published as a ready series). These unlock the PRD demos: TEDPIX plotted against
monthly CPI/FX, and income-inequality trends over 10+ years.

**PRD mapping:** Phase 6 = PRD §11 Task 14 (TSETMC connector) and Task 15
(HBSIR connector). Timeline: Week 6–7. PRD §14.1 also lists "Daily scraping
successfully running for TGJU and TSETMC sources" as a functional acceptance
criterion.

## Scope

### In Scope

- [ ] **Reconnaissance + dependency gate** (first task, may reshape everything
      downstream): confirm `finpy-tse` and `hbsir` are installable and usable in
      this environment, pin versions, verify licenses/maintenance, confirm the
      exported client/data APIs, and capture fixtures. Record evidence either way
      and defer a source that cannot be made to work (OPEC/CBI precedent).
- [ ] **Optional Poetry extras** for the two packages (`tsetmc`, `hbsir`),
      mirroring the existing optional `airflow` extra, so the default install and
      test suite do not require either package.
- [ ] **Lazy, injectable client loading** in each connector: import the package
      only inside the connector, accept an injected client/loader object for
      tests (the package analogue of `http_session` injection), and raise one
      actionable error when the extra is not installed.
- [ ] **TSETMC connector + parser-by-convention** (`src/connectors/tsetmc.py`):
      discover TEDPIX / trading value / market P/E, fetch daily history, tag
      market holidays and missing sessions as absent (never forward-filled), and
      return a `FetchResult` with the package payload in Bronze.
- [ ] **TSETMC daily derived metrics**: publish `RET1D` and `MA30` through the
      existing `derivation_strategy="daily"` path in `src/etl/gold.py`.
- [ ] **Month-end downsample**: add a source-agnostic derived-series path in
      Gold that republishes a daily series at month-end using the existing
      `src/etl/frequency.py::to_month_end`, so `TSETMC.TEDPIX` can be compared
      with monthly CPI/FX at exact timestamps.
- [ ] **HBSIR parser** (`src/connectors/hbsir_parser.py`): pure functions that
      turn survey extracts into tidy annual frames — Gini, poverty rate, and
      decile shares — with weighting/temporal assumptions documented.
- [ ] **HBSIR connector** (`src/connectors/hbsir.py`): discover the survey years
      available locally/via the package, load each year's required columns, run
      the parser, and persist annual Silver observations.
- [ ] **Per-source `build_spec()` + CLI** for both connectors
      (`python -m src.connectors.tsetmc`, `python -m src.connectors.hbsir`) with
      `--dry-run` touching no database (mirror IMF/EIA/SCI).
- [ ] **Config**: TSETMC/HBSIR base URLs, local data directory, timeouts, and
      package-version capture in `src/utils/config.py` + `.env.example`.
- [ ] **Airflow DAG** `airflow/dags/tsetmc_daily.py` at 23:00 Asia/Tehran
      (AGENTS.md schedules TGJU/TSETMC daily at 11 PM Iran time); HBSIR is annual
      and runs on demand (decision recorded in NOTES).
- [ ] **Unit tests** (parser math with fixtures, client-injection, missing-extra
      error, holiday gaps, monthly downsample) and **integration tests**
      (Bronze → Silver → Gold roundtrip, idempotent re-run, daily + month-end
      series, annual alignment).
- [ ] **Live tests** gated behind `RUN_LIVE_API_TESTS=1` + `@pytest.mark.live()`
      for TSETMC; HBSIR live tests only if the package works offline from a
      documented local extract.
- [ ] Docs: `docs/phase-6/{README,IMPLEMENTATION,VALIDATION}.md`, data-dictionary
      sections for both sources, and README/AGENTS updates.

### Out of Scope

- [ ] Individual-equity / symbol-level universes and intraday data (TEDPIX-era
      index + market aggregates only, per the PRD).
- [ ] A new dashboard page for capital markets; new indicators will surface via
      the existing Data Catalog and Comparison/Correlation pages (an optional
      small FX/Gold-page addition is noted but not required).
- [ ] Forecasting, nowcasting, or any forward-dated survey data (temporal
      leakage is prohibited; HBSIR is historical only).
- [ ] Reconstructing HBSIR microdata from scratch or redistributing raw
      microdata; only derived aggregates plus a manifest are persisted.
- [ ] Chain-linking for either source (neither publishes overlapping base-year
      segments; TEDPIX rebasing is out of scope).
- [ ] Any change to existing World Bank / IMF / EIA / TGJU / SCI behavior.
- [ ] Cloud deployment, CI/CD, or Phase 8 production-readiness work.

## Context

### Current state (observed)

- The platform runs a **generic Bronze → Silver → Gold runner**
  (`src/etl/pipeline.py`): a connector exposes `connect()`, `discover()`, and a
  richer `fetch_series(indicator_id) -> FetchResult`; a `SourceSpec` supplies
  source name/type, frequency, derived-series namespace, per-indicator
  derivation overrides, forecast support, and the Bronze-row parser.
  `run_cli(...)` wires a connector + spec to the CLI.
- Connectors follow a proven shape: inject transport, `RetryPolicy`, and
  `RateLimiter` (`src/connectors/world_bank.py` is the reference; `eia.py` shows
  an optional API-key `is_configured()` guard and a frozen indicator registry;
  `imf.py:460` shows `build_spec()` and `main()`).
- `src/etl/gold.py` already supports two derivation strategies via
  `silver_to_gold(..., derivation_strategy=...)`: `"yoy"` (annual/quarterly/
  monthly) and `"daily"` (publishes `RET1D` and `MA30`, lines ~763–786, with
  helpers `_daily_return_records` / `_daily_ma30`).
- `src/etl/frequency.py::to_month_end` performs daily → month-end aggregation
  (last observation per calendar month, no fill). It is not yet wired into Gold.
- `src/utils/periods.py` provides `annual_period_end(year)` and
  `month_period_end(year, month)`; `src/utils/persian.py` provides Persian
  digit/price and Jalali→Gregorian helpers. `src/utils/persian.py` already
  covers the Jalali conversion HBSIR survey years need.
- The catalog (`metadata.indicator_catalog`) records indicator id, name, unit,
  frequency, domain, source, availability, base years, and `is_active`; the
  dashboard reads Gold only. New domains (`market`, `welfare` already exists)
  are plain strings, so no schema change is required.
- `tests/conftest.py` provides fixture loaders per source and fake sessions;
  `tests/unit/airflow/test_dag_import.py` imports each DAG by name.
- **Neither `finpy-tse` nor `hbsir` is currently a dependency** (`pyproject.toml`
  / `poetry.lock` contain no match). `apache-airflow` is the only optional extra
  today.

### Assumptions to verify in Task 1

- `finpy-tse` exposes a client class with historical index/valuation access, or
  `TseClient`/`tsetmc` equivalent does; daily history is retrievable without a
  browser and without authentication.
- `hbsir` can load a documented local survey dataset and exposes (or allows
  computation over) income/expenditure columns with sampling weights; it is
  installable on Python 3.11/3.12 and actively maintained.
- Both are redistributable/usable for research under their licenses.

## Proposed Approach

Treat each package as the **transport**, exactly as `requests.Session` is the
transport for HTTP connectors:

1. **Reconnaissance gate (Task 1).** Before writing code, install the packages in
   the environment (or a scratch venv), inspect the public API, run a tiny real
   fetch, and commit fixtures. If a package is missing, broken on this Python
   version, unlicensed for use, or requires a browser/credentials, record the
   evidence and defer that source (as OPEC and CBI were deferred). Build the
   other source regardless.

2. **Dependency isolation.** Add `finpy-tse` and `hbsir` as optional Poetry
   extras so `poetry install` and the default test suite stay light. Connectors
   import lazily and expose `is_available()` / an actionable `ConnectionError`,
   mirroring `src/connectors/eia.py::is_configured`.

3. **Inject the client.** Each connector's `__init__` accepts `config`,
   `client`/`loader` (injected in tests), `retry_policy`, and `rate_limiter`.
   Tests pass a `FakeTsetmcClient` / `FakeHbsirLoader`; no package, no network,
   no wall-clock cost in the unit suite.

4. **TSETMC**: daily levels in Gold with the existing `"daily"` strategy
   (`RET1D`, `MA30`). Add a small, source-agnostic **month-end derived series**
   (`...<id>.ME`) in `gold.py` that reuses `frequency.to_month_end`, gated by a
   new opt-in field on `IndicatorDerivation` so no existing source changes
   behavior. Market holidays simply produce no row for that session.

5. **HBSIR**: annual levels in Gold with the existing `"yoy"` strategy where a
   growth rate is meaningful (Gini/poverty/decile *shares* are already
   rates/shares, so they opt out of derived growth via `IndicatorDerivation(
   include_growth=False)`, exactly as IMF rate indicators do). Survey years are
   aligned to the Iranian year end and converted to Gregorian via
   `annual_period_end` + `persian.jalali_to_gregorian`.

6. **Bronze**: persist the raw package payload as `{rows: [...], meta: {...}}`
   with package name/version and retrieval timestamp. For HBSIR, persist the
   annual *input extract* used for the computation plus a checksum/manifest, not
   the full microdata (size + redistribution constraint; see NOTES).

7. **Dashboard**: no new page. New indicators appear in Data Catalog and can be
   correlated with existing monthly series; the month-end series makes a
   TEDPIX-vs-CPI correlation produce non-zero join counts.

## Task Metadata

**Type:** New Capability (2 connectors) + Data Pipeline Change (month-end Gold
   derived series)
**Complexity:** High — two unverified third-party packages, a microdata
   computation (Gini/poverty), and a source-agnostic Gold change; plus a
   dependency/network reconnaissance gate.
**Affected Areas:** `src/connectors/` (new `tsetmc.py`, `hbsir.py`,
   `hbsir_parser.py`; possibly a `tsetmc_parser.py`), `src/etl/gold.py`,
   `src/etl/pipeline.py` (derivation plumbing only), `src/utils/config.py`,
   `pyproject.toml`, `.env.example`, `airflow/dags/`, `tests/`, `docs/`.
**Dependencies:** `finpy-tse` (or equivalent), `hbsir`, pandas, existing
   `SourceSpec`/`run_pipeline`, `RetryPolicy`/`RateLimiter`, `to_month_end`,
   `periods`/`persian` helpers.

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `src/connectors/world_bank.py` — reference connector: injected session/retry/rate-limiter, `FetchResult`, `build_spec` wrapper, `__main__` CLI.
- `src/connectors/eia.py` — frozen indicator registry (`EiaIndicator`), `is_configured()` error path, credential scrubbing, paging; closest analog for a "source might not be configured" guard.
- `src/connectors/imf.py` — `build_spec()` (`imf.py:460`), per-indicator `overrides` (rate indicators opt out of growth), `main()` CLI.
- `src/connectors/sci_scraper.py` — multi-series fetch + catalog handling + custom Gold publish path; relevant if TSETMC emits several series per fetch.
- `src/connectors/base.py` — `DataConnector` ABC and `IndicatorMetadata` (note `is_active` default).
- `src/etl/pipeline.py` — `IndicatorDerivation` (~line 129), `SourceSpec` (~137), `_persist_indicator` (~381), `run_pipeline` (~471), `run_cli` (~588). Read `_derivation_for` to see how per-indicator strategy is resolved.
- `src/etl/gold.py` — `silver_to_gold` (~674), `derivation_strategy` switch (~763–786), `_daily_return_records`, `_daily_ma30`, `_namespaced`, and `derived_indicator_id` naming.
- `src/etl/frequency.py` — `to_month_end` (reuse verbatim for the downsample; do not re-implement).
- `src/etl/bronze.py` — `write_bronze` signature and the `{rows: [...]}` envelope convention.
- `src/etl/silver.py` — `bronze_to_silver` (~295, `parser` + `allow_future`), `load_silver_series` (~401).
- `src/utils/periods.py` — `annual_period_end` (~31), `month_period_end` (~51).
- `src/utils/persian.py` — Persian digit/price helpers and Jalali→Gregorian conversion for survey years.
- `src/utils/config.py` — `APIConfig` (add `tsetmc_*` / `hbsir_*` fields) and `get_config()` caching.
- `src/database/schema.py` — `BronzeRaw`, `SilverCleaned`, `GoldAnalytical`, `IndicatorCatalog`; confirm no schema change is needed.
- `airflow/dags/tgju_daily.py` — DAG template (schedule, retries, failure callback, logging).
- `.env.example` — where new config + optional-extra notes belong.

### Data / ML References

- `src/etl/frequency.py` — daily→month-end contract (last obs, no fill) that the TEDPIX monthly series must honor.
- `src/etl/gold.py` — derived-series naming/provenance rules (`original_value`, `is_chain_linked`, derived ids never collide with source ids).
- `docs/phase-2/data_dictionary.md` — section format to mirror for `# TSETMC Indicators (Phase 6)` and `# HBSIR Indicators (Phase 6)`.
- `docs/phase-4/VALIDATION.md` / `docs/phase-5/VALIDATION.md` — how a gate/deferral is recorded.
- PRD §11 Tasks 14–15 (`PRD.md:552`–`589`) — exact indicator and demo expectations.

### External Documentation

- `finpy-tse` PyPI / GitHub README — client class names, index-history and valuation methods, supported Python versions, license, last release date (verify in Task 1).
- `hbsir` PyPI / Iran-Open-Data GitHub README — dataset download/loading API, column/schema names, weighting guidance, license, maintenance status (verify in Task 1).
- Tehran Stock Exchange / TSETMC conventions — trading calendar (Iranian week: closed Fri; market holidays), TEDPIX definition and base, market P/E definition (use package-provided values; do not assume).
- Iran Open Data / HBSIR methodology — survey year definition, sampling weights, income vs expenditure deciles, and any published Gini/poverty methodology to match (see NOTES on making the poverty line explicit).

*Only fetch these at Task 1; network is restricted in this environment, so record any access limitations honestly and prefer a locally installed package's docstrings as the source of truth.*

### Patterns to Follow

**Naming:** snake_case modules (`tsetmc.py`, `hbsir_parser.py`); one source per file; indicators namespaced `TSETMC.<SERIES>` / `HBSIR.<SERIES>`, derived ids suffixed `.RET1D`, `.MA30`, `.ME`, `.YOY`.

**Structure:** connector = transport/IO; parser = pure frame logic. TSETMC is index-based, so a separate `tsetmc_parser.py` is optional — put pure row→frame logic there if the package returns objects that need normalization; HBSIR *must* split computation (`hbsir_parser.py`) from data loading (`hbsir.py`), mirroring `sci_scraper.py`/`sci_parser.py`.

**Config:** frozen dataclass `TsetmcConfig` / `HbsirConfig` with defaults from `get_config()`; no hardcoded URLs/paths/timeouts in logic.

**Testing:** fixture-based parser tests; inject fake package clients; mark integration tests `@pytest.mark.integration`; live tests `@pytest.mark.live()` + `RUN_LIVE_API_TESTS=1`.

**Data/ML:** timezone-aware UTC; `record_metadata` attribute for the `metadata` column; Persian/Jalali → Gregorian for storage with the original year retained in metadata; no forward-fill (gaps stay gaps); no future dates.

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation

- Run the reconnaissance gate (Task 1) and write the fixtures + a short evidence
  note in `docs/phase-6/README.md`. This is the contract for the rest.
- Add optional Poetry extras and config fields; add `.env.example` entries.
- Build the source-agnostic Gold month-end path early, against synthetic daily
  frames, so TSETMC can depend on it (it is testable without either package).

### Phase 2: Core Change

- Implement `tsetmc_parser.py` (if needed) and `tsetmc.py`; register indicators,
  add `build_spec()`, CLI, and the daily derivation.
- Implement `hbsir_parser.py` (Gini/poverty/deciles, pure + tested) and
  `hbsir.py`; add `build_spec()` and CLI.

### Phase 3: Integration

- Wire both sources into `run_pipeline`/`run_cli`, the indicator catalog, and the
  month-end derived series.
- Add `airflow/dags/tsetmc_daily.py`; extend `tests/unit/airflow/test_dag_import.py`.
- Update docs, data dictionary, README, and AGENTS lifecycle/status.

### Phase 4: Validation

- Unit + integration suites green at the 80% coverage gate; `ruff`/`mypy` clean;
  `alembic check` shows no drift (no new migration expected); a real live TSETMC
  run recorded in `docs/phase-6/VALIDATION.md`.

---

## STEP-BY-STEP TASKS

Execute tasks in dependency order. Each task ends with a validation command.

### 1. VERIFY external packages and open/close the dependency gate

- **IMPLEMENT:** Inspect `finpy-tse` and `hbsir`: install each in the project
  environment (or a scratch venv), record version + license + last release,
  exercise the smallest real read, and capture the raw output as a fixture under
  `tests/fixtures/tsetmc/` and `tests/fixtures/hbsir/`. Write findings to
  `docs/phase-6/README.md`. If a package is unusable, mark that source deferred
  with evidence and continue with the other.
- **PATTERN:** `docs/phase-5/VALIDATION.md` Task 1 reconnaissance + `tests/fixtures/cbi/_gate.json`.
- **DEPENDENCIES:** network/escalation for installs; Python 3.11/3.12.
- **GOTCHA:** network is restricted here — request escalation for `poetry add`;
  if install fails, that is a gate finding, not a reason to hand-roll a scraper
  (the PRD explicitly names these packages).
- **VALIDATE:** `poetry run python -c "import finpy_tse, hbsir; print(finpy_tse.__version__, hbsir.__version__)"` (adjust module names to the real ones) and a committed fixture per source.

### 2. ADD optional extras and configuration

- **IMPLEMENT:** In `pyproject.toml` add `[tool.poetry.extras]` entries
  `tsetmc = ["finpy-tse"]` and `hbsir = ["hbsir"]` (versions pinned from Task 1);
  add them to the `dev`/optional dependency groups as appropriate so CI without
  the extras still runs. In `src/utils/config.py::APIConfig` add
  `tsetmc_base_url`, `hbsir_data_dir`, and any timeout/limit fields; mirror them
  in `.env.example` with an explanatory comment.
- **PATTERN:** existing `airflow` extra in `pyproject.toml`; `APIConfig` EIA/SCI fields; `.env.example` EIA block.
- **DEPENDENCIES:** Task 1 versions.
- **GOTCHA:** do not make the packages mandatory — the unit suite must not import
  them. Keep `get_config()` cache-safe.
- **VALIDATE:** `poetry run python -c "from src.utils.config import get_config; print(get_config().api.tsetmc_base_url)"`.

### 3. ADD the Gold month-end derived-series path (source-agnostic)

- **IMPLEMENT:** Extend `IndicatorDerivation` with an opt-in
  `include_monthly: bool = False` (or an equivalent documented flag). In
  `src/etl/gold.py`, when enabled, republish the daily linked series at
  month-end as `<derived_id>.ME` using `src/etl/frequency.py::to_month_end`,
  carrying `original_value`, `unit`, `frequency="monthly"`, domain, and a
  `record_metadata.derivation = "month_end_from_daily"`. Name the id with the
  existing `_namespaced` helper so it cannot collide. Ensure the refresh deletes
  the `.ME` rows too.
- **PATTERN:** `gold.py` `_daily_return_records` / `_daily_ma30` (derived-row construction and metadata), and the derived-id helpers.
- **DEPENDENCIES:** none (works on synthetic frames).
- **GOTCHA:** month-end aggregation must not forward-fill; a month with no
  session yields no row. Do not change default behavior for any existing source
  (`include_monthly` defaults False, and `SourceSpec`/`IndicatorDerivation`
  remain backward compatible).
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_gold.py tests/unit/etl/test_frequency.py -q`.

### 4. CREATE the TSETMC connector

- **IMPLEMENT:** `src/connectors/tsetmc.py` with:
  - `TsetmcConfig` (frozen dataclass, defaults from `get_config()`),
  - a `TsetmcFetchResult` carrying `frame`, `raw_envelope`, `request_url`/`source_ref`,
    `package_version`, `collection_metadata()`,
  - a `TsetmcIndicator` registry (TEDPIX, trading value, market P/E, optionally
    market cap) with ids/names/units/domains,
  - `TsetmcConnector(DataConnector)` with injected `client`, `retry_policy`,
    `rate_limiter`; `connect()` verifies the extra is importable and the client
    responds; `discover()` returns `IndicatorMetadata`; `fetch_series()` returns
    the result; `validate()` checks positive index/P-E and non-negative value,
  - `build_spec()` (frequency `daily`, `derivation_strategy="daily"`,
    `include_monthly=True`) and `main()` with `--dry-run`, `--indicators`,
    `--start/--end`.
- **PATTERN:** `src/connectors/eia.py` (registry + config + FetchResult + is-configured guard) and `src/connectors/imf.py` (`build_spec`/`main`).
- **DEPENDENCIES:** Tasks 1–3.
- **GOTCHA:** market holidays/missing sessions must be *absent*, not zero or
  filled; timestamp the observation at the trading day's period end in UTC; never
  emit future-dated rows (Silver's default future-date rejection is the guard).
  Capture the package version in provenance for reproducibility.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_tsetmc.py -q` (added in Task 9) and `poetry run python -m src.connectors.tsetmc --dry-run`.

### 5. CREATE the HBSIR parser and connector

- **IMPLEMENT:** `src/connectors/hbsir_parser.py` with pure, weighted
  computations: `gini(values, weights)`, `poverty_rate(values, weights, line)`,
  `income_decile_shares(values, weights)`, returning tidy annual frames. Then
  `src/connectors/hbsir.py` with `HbsirConfig` (local data dir), an injectable
  `loader`, `HbsirFetchResult`, an indicator registry (`HBSIR.GINI`,
  `HBSIR.POVERTY.RATE`, `HBSIR.INCOME.DECILE.D1..D10`), `discover()`,
  `fetch_series()`, `validate()` (Gini ∈ [0,1], poverty ∈ [0,100], decile shares
  ≈ 100), `build_spec()` (frequency `annual`, rate/share indicators opt out of
  growth via `overrides`), and `main()` with `--dry-run`.
- **PATTERN:** parser/scraper split of `sci_parser.py`/`sci_scraper.py`; IMF `overrides` for rate indicators; `src/utils/persian.py` + `periods.annual_period_end` for the year timestamp.
- **DEPENDENCIES:** Task 1 (package + dataset availability).
- **GOTCHA:** Gini and deciles are only meaningful with sampling weights — the
  parser must require weights and fail loudly (`ParsingError`) if absent. Survey
  years are Jalali; store Gregorian year-end and keep the original Jalali year in
  `record_metadata`. Do not persist the full microdata to Bronze.
- **VALIDATE:** `poetry run pytest tests/unit/connectors/test_hbsir_parser.py tests/unit/connectors/test_hbsir.py -q` and `poetry run python -m src.connectors.hbsir --dry-run`.

### 6. WIRE both sources into the runner and catalog

- **IMPLEMENT:** Confirm `run_pipeline`/`run_cli` accept the two `build_spec()`
  outputs unchanged; if TSETMC emits multiple series per fetch, follow the SCI
  multi-series persistence path. Ensure catalog `domain` values are `market` and
  `welfare`, `frequency` is `daily`/`annual`, and availability is filled from
  observed ranges (not fabricated).
- **PATTERN:** `imf.py::main` → `run_cli`; `sci_scraper.py` catalog handling.
- **DEPENDENCIES:** Tasks 4–5.
- **GOTCHA:** `discover()` must leave `availability_start/end` `None` unless the
  source can report real coverage; the pipeline fills it after storing.
- **VALIDATE:** `poetry run pytest tests/unit/etl/test_pipeline.py -q`.

### 7. ADD the TSETMC Airflow DAG

- **IMPLEMENT:** `airflow/dags/tsetmc_daily.py`, schedule `0 23 * * *` Asia/Tehran,
  `catchup=False`, `max_active_runs=1`, retries with exponential backoff, a
  failure callback, and a callable that runs `run_tsetmc_pipeline(dry_run=False)`
  and raises `AirflowException` on any failed indicator.
- **PATTERN:** `airflow/dags/tgju_daily.py` (copy its structure).
- **DEPENDENCIES:** Task 4.
- **GOTCHA:** DAGs must parse without a DB connection or the optional package
  installed — keep the import inside the task callable (as TGJU does).
- **VALIDATE:** `poetry run pytest tests/unit/airflow/test_dag_import.py -q` (extend it to import `tsetmc_daily`).

### 8. ADD fixtures and unit tests

- **IMPLEMENT:** `tests/fixtures/tsetmc/` and `tests/fixtures/hbsir/` raw
  captures + `SOURCES.md`; `tests/unit/connectors/test_tsetmc.py` (client
  injection, holiday gaps, units, validation, missing-extra error),
  `test_tsetmc_parser.py` if a parser is added, `test_hbsir_parser.py` (known
  Gini/poverty/decile cases, weights required), `test_hbsir.py` (loader
  injection, annual alignment, growth opt-out), and Gold tests for the month-end
  series in `tests/unit/etl/test_gold.py`.
- **PATTERN:** `tests/unit/connectors/test_eia.py`, `test_eia_parser.py`, `test_sci_parser.py`; `tests/conftest.py` fixture loaders.
- **DEPENDENCIES:** Tasks 1, 3–5.
- **GOTCHA:** no unit test may import the real packages or hit the network.
- **VALIDATE:** `poetry run pytest tests/unit -q`.

### 9. ADD integration tests

- **IMPLEMENT:** `tests/integration/test_tsetmc_pipeline.py` and
  `tests/integration/test_hbsir_pipeline.py`: Bronze envelope + package version,
  Silver daily/annual rows, Gold levels + `RET1D`/`MA30` + month-end `.ME` for
  TSETMC, annual Gini/poverty/deciles for HBSIR, database idempotency, and
  catalog coverage.
- **PATTERN:** `tests/integration/test_eia_pipeline.py`, `test_imf_pipeline.py`.
- **DEPENDENCIES:** Tasks 4–6; Docker PostgreSQL.
- **GOTCHA:** integration tests must not require the optional packages — use
  fake clients/builders, exactly as the API pipeline tests use fake sessions.
- **VALIDATE:** `poetry run pytest tests/integration/test_tsetmc_pipeline.py tests/integration/test_hbsir_pipeline.py -m integration -q --cov-fail-under=0`.

### 10. UPDATE documentation and project status

- **IMPLEMENT:** Create `docs/phase-6/{README,IMPLEMENTATION,VALIDATION}.md`; add
  `# TSETMC Indicators (Phase 6)` and `# HBSIR Indicators (Phase 6)` sections to
  `docs/phase-2/data_dictionary.md`; update README's source table, roadmap, and
  status line; update AGENTS.md (connector tree, lifecycle stage, Key Files).
- **PATTERN:** `docs/phase-5/{README,IMPLEMENTATION,VALIDATION}.md`; existing data-dictionary sections.
- **DEPENDENCIES:** all prior tasks.
- **GOTCHA:** record the real gate outcome for each package, including any
  deferral and its evidence.
- **VALIDATE:** `rg -n "TSETMC|HBSIR" docs/phase-2/data_dictionary.md docs/phase-6/`.

### 11. RUN final end-to-end validation

- **IMPLEMENT:** Full quality gates plus a real live TSETMC run (if the gate is
  open) and an HBSIR run from the documented local extract; record commands and
  results in `docs/phase-6/VALIDATION.md`.
- **PATTERN:** `docs/phase-5/VALIDATION.md` final validation record.
- **DEPENDENCIES:** all prior tasks.
- **GOTCHA:** if either package is deferred, `docs/phase-6/VALIDATION.md` must
  say so explicitly with evidence and the phase still closes on the other source.
- **VALIDATE:** `make check` and `poetry run pytest tests/integration -m integration -q --cov-fail-under=0`.

---

## TESTING & VALIDATION

### Unit Tests

- TSETMC client injection with a `FakeTsetmcClient`; market-holiday gaps stay
  absent; timestamps are UTC session period-ends; validation rejects
  non-positive index/P-E; missing extra raises one actionable error.
- Gold month-end: last-observation-per-month selection, leap-year February,
  no fill for empty months, `.ME` id naming, and that existing sources are
  unaffected (`include_monthly=False`).
- HBSIR parser: Gini on known distributions (equality = 0, maximal = 1), weights
  affect the result, poverty rate respects an explicit line, decile shares sum
  to ~100, and a `ParsingError` when weights are missing.
- HBSIR connector: loader injection, Jalali survey-year → Gregorian year-end,
  growth opt-out for rate/share indicators.

### Integration Tests

- Bronze envelope carries the package name/version and a checksum; no secrets.
- TSETMC: Bronze → Silver daily → Gold levels + `RET1D`/`MA30` + `.ME`;
  idempotent re-run replaces derived rows; catalog coverage filled.
- HBSIR: Bronze → Silver annual → Gold levels; idempotent re-run.
- No DB schema drift.

### Data Validation

- Range checks (TEDPIX/P-E > 0; trading value ≥ 0; Gini ∈ [0,1];
  poverty ∈ [0,100]); completeness per indicator; no future-dated rows; no
  duplicate `(indicator_id, timestamp)`; frequency preserved (daily stays daily,
  annual stays annual at month-end).

### ML Validation

Not applicable — no models. The relevant correctness properties are
**leakage avoidance** (HBSIR is historical only; no forecast support on either
`SourceSpec`) and **reproducibility** (package version + raw payload in Bronze).

### Edge Cases

- Empty/missing TSETMC sessions and long holiday stretches.
- TEDPIX index rebasing or a package returning adjusted vs unadjusted values
  (record which, don't silently mix).
- `hbsir` returning a survey year with a changed schema or missing weights.
- Very large HBSIR extracts (size guard + manifest instead of raw microdata).
- Python-version incompatibility of either package.

---

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
poetry run ruff check src tests airflow
poetry run ruff format --check src tests airflow
poetry run mypy src
```

### Level 2: Unit Tests

```bash
poetry run pytest tests/unit -q
poetry run pytest tests/unit/connectors/test_tsetmc.py tests/unit/connectors/test_hbsir_parser.py tests/unit/connectors/test_hbsir.py tests/unit/etl/test_gold.py -q
```

### Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run alembic upgrade head
poetry run pytest tests/integration -m integration -q --cov-fail-under=0
poetry run alembic check
```

### Level 4: Feature-Specific Validation

```bash
poetry run python -m src.connectors.tsetmc --dry-run
poetry run python -m src.connectors.tsetmc --indicators TSETMC.TEDPIX --dry-run
poetry run python -m src.connectors.hbsir --dry-run
RUN_LIVE_API_TESTS=1 poetry run pytest tests/unit/connectors/test_tsetmc.py -q -m live
```

### Level 5: Manual Validation

- `make dashboard` and confirm TEDPIX appears in Data Catalog and that a
  TEDPIX-vs-monthly-CPI correlation returns a non-zero join count (or document
  the expected zero if coverage does not overlap).
- Inspect Gold rows for one TSETMC month to confirm `.ME` equals the last daily
  observation of that month.

---

## ACCEPTANCE CRITERIA

* [ ] A documented reconnaissance decision exists for each package (open or
      evidence-backed deferral).
* [ ] `python -m src.connectors.tsetmc` ingests daily TEDPIX, trading value, and
      market P/E into Bronze/Silver/Gold, with `RET1D`/`MA30` and a month-end
      series.
* [ ] `python -m src.connectors.hbsir` ingests annual Gini, poverty rate, and
      income decile shares for 10+ survey years from the documented source.
* [ ] Both sources register catalog rows with correct domain/frequency/units and
      observed availability.
* [ ] Survey years are Gregorian in storage with the original Jalali year in
      metadata; TSETMC timestamps are UTC period-ends.
* [ ] Market holidays and missing survey years appear as gaps, never filled or
      zeroed.
* [ ] Optional extras keep the default install and unit suite package-free.
* [ ] `make check` passes at the 80% coverage gate; integration suites green;
      `alembic check` clean.
* [ ] `docs/phase-6/` exists and the data dictionary / README / AGENTS are
      updated.
* [ ] No regressions in existing World Bank / IMF / EIA / TGJU / SCI suites.

---

## RISKS & TRADE-OFFS

- **Package availability/maintenance is the dominant risk (High).** `finpy-tse`
  and `hbsir` are third-party and unverified here. Mitigation: Task 1 gate,
  optional extras, lazy import, fixture-based tests, and an explicit deferral
  path per source.
- **Microdata computation correctness (Medium).** Gini/poverty depend on
  weights, the income vs expenditure definition, and the poverty line.
  Mitigation: pure, unit-tested functions on known distributions; require
  weights; make the poverty line explicit in config/metadata and document it.
- **Bronze size/redistribution for HBSIR (Medium).** Full microdata may be large
  or non-redistributable. Mitigation: persist the annual input extract + manifest
  and checksum, not raw microdata; respect the license.
- **Gold change blast radius (Medium).** The month-end path touches the most
  data-sensitive module. Mitigation: opt-in flag defaulting off, derived-id
  namespacing, refresh deletes the new ids, and full existing Gold/frequency unit
  suites as the regression guard.
- **TEDPIX adjustments/rebasing (Low–Medium).** Silently mixing adjusted and
  unadjusted values would corrupt the series. Mitigation: record the adjustment
  basis in metadata; treat rebasing as a break to document, not auto-link.
- **Network-restricted environment (Low).** Installs and live fetches may need
  escalation; record failures as gate evidence rather than guessing the API.

## NOTES

### Design Decisions

1. **Packages as transport.** Inject the client/loader so unit tests need
   neither the package nor the network — the same philosophy as
   `http_session`/`RetryPolicy` injection in `world_bank.py`.
2. **Optional extras, not core deps.** Mirrors the `airflow` extra and keeps the
   platform installable and testable without either package.
3. **Month-end upsample lives in Gold, not the connector**, so AGENTS.md's
   "frequency maths live in shared helpers" holds and the change is reusable.
4. **HBSIR derived in-platform.** The PRD calls for Gini/poverty/deciles, which
   the package does not publish as ready series; pure parser functions own that
   math and are independently testable.
5. **No new schema/migration expected.** New domains/frequencies are strings;
   derived series and package provenance travel in existing columns/JSONB.
6. **HBSIR is on-demand, not scheduled.** The data is annual and heavy; a DAG is
   unnecessary. TSETMC follows AGENTS.md's 23:00 daily slot.

### Open Questions (resolve in Task 1)

- Do `finpy-tse`/`hbsir` install on Python 3.11/3.12, and what are their
  licenses and last release dates?
- Does the TSETMC client expose historical TEDPIX/P-E/trading value without
  authentication or a browser, and at what granularity/adjustment basis?
- Does `hbsir` ship data or require the analyst to download it separately; which
  columns/weights does it expose?
- What poverty line methodology should be used (official Iranian line vs a
  documented relative line), and should deciles be income or expenditure?
- Is market capitalization historically available in the package; if not, drop
  it from the MVP.

### Success Metrics

- [ ] One Gold query returns a continuous daily TEDPIX series plus a month-end
      series spanning the available history, with `RET1D`/`MA30` derived rows.
- [ ] A TEDPIX-vs-monthly-CPI correlation produces a non-zero matched-observation
      count.
- [ ] One Gold query returns annual Gini, poverty, and decile shares for 10+
      years, exportable to CSV from the dashboard.
- [ ] TSETMC runs on the daily Airflow schedule; both sources have a recorded
      gate outcome.

---

## Confidence Assessment

**Confidence: 6/10**

**High confidence because:**

- The connector → `SourceSpec` → `run_pipeline` → Gold path is proven by four
  sources; this plan reuses it rather than inventing architecture.
- The transport-injection, optional-extra, and gate/deferral patterns all exist
  in-repo, so the shape of the work is well understood.
- Daily derived metrics already exist; the month-end path is a small, isolated,
  source-agnostic addition on top of an existing helper.
- No schema migration is expected, and the catalog/domain fields are free-form.

**Remaining uncertainty (why not higher):**

- **Both packages are unverified** — availability, APIs, licenses, and data
  access are assumptions until Task 1. This is the dominant risk.
- **HBSIR microdata access and methodology** (weights, poverty line,
  income-vs-expenditure, dataset size) are unresolved and materially affect the
  parser.
- **TSETMC history/adjustment semantics** (rebasing, adjusted vs unadjusted,
  package coverage) need confirmation before the Gold series can be trusted.
- **The Gold month-end change**, while small, touches the most data-sensitive
  module and must not alter existing sources.

**Recommendation:** Proceed, but **front-load Task 1** and treat its fixtures as
the contract. Build the source-agnostic month-end Gold path early against
synthetic data; keep the existing unit/integration suites green as the
regression guard; and defer either package without hesitation if the gate cannot
be passed, recording the evidence as OPEC/CBI did.
