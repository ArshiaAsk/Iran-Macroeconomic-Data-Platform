# Phase 6 Validation Report

Phase 6 — Market & Survey Connectors (TSETMC + HBSIR).
Plan: [phase-6-market-survey-connectors.md](../plans/phase-6-market-survey-connectors.md).

**Scope note.** Tasks 1–9 were implemented and committed on 2026-09-14/15 and
their results are recorded here from the committed suites (`672187d` for Tasks
1–8, `5231ee6` for Task 9). Task 11 (the full end-to-end validation pass —
`make check`, the whole integration suite, and a real live run for each source)
runs *after* this documentation task; the sections it will fill are marked
**[Task 11]** and must not be read as passing today. Nothing below claims a
result that was not actually produced by the command shown.

---

## Task 1 — Reconnaissance / dependency gate

**Verdict: both sources OPEN**, with a **scope narrowing for TSETMC** (TEDPIX
only). Recorded in full in [README.md](README.md#approved-decisions-2026-09-13);
the evidence is reproduced here.

| Deliverable | Result |
|-------------|--------|
| `finpy-tse` install + import | ✅ **1.2.10**, pure-python wheel, imports on CPython 3.12 |
| `hbsir` install + import | ✅ **0.6.6** (+ `bssir==0.6.8`), pure-python, `Requires-Python >=3.10` |
| Smallest real read, TSETMC | ✅ `Get_CWI_History(ignore_date=True, just_adj_close=True)` → **4,283 sessions**, 1387-09-14 (2008-12-04) → 1405-06-22 (2026-09-13) |
| Smallest real read, HBSIR | ✅ `hbsir.load_table("Weight", 1400)` → **37,988 rows**; `Total_Income` loads for 1369…1403 |
| `tests/fixtures/tsetmc/` + `SOURCES.md` + `_capture.json` | ✅ present (3 captured files, sha256 recorded) |
| `tests/fixtures/hbsir/` + `SOURCES.md` + `_manifest.json` | ✅ present (3 captured files + derived metrics) |

### TSETMC — ✅ OPEN, with a scope change

**Installability / compatibility**

- License **BSD 3-clause**; last release **2024-04-24**; no PyPI project URL.
- **No `__version__` attribute** — the version must be read with
  `importlib.metadata.version("finpy-tse")`; the connector does exactly this.
- Maintenance is stalled (~2.4 years) but the endpoints are stable (verified
  live).

**Probes**

| Probe | Result |
|-------|--------|
| `finpy_tse.Get_CWI_History(ignore_date=True, just_adj_close=True)` | ✅ 4,283 rows, one per trading day |
| Raw `cdn.tsetmc.com/api/Index/GetIndexB2History/32097828799138957` | ✅ HTTP 200, `indexB2` list of `{insCode, dEven, xNivInuClMresIbs, xNivInuPbMresIbs, xNivInuPhMresIbs}` |
| Two-week window (`1404-06-01`…`1404-06-15`) | ✅ **9 rows** — Thu/Fri and holidays are **absent, not filled** |
| `Get_MarketWatch(save_excel=False)` | ✅ 1,544 symbols — a **current-day snapshot**, per-symbol `Value`/`Market Cap`/`EPS`, **no market P/E column** |
| `MarketData/GetMarketOverview/{1,2,3}`, `MarketWatchInit.aspx` | ✅ reachable, **current-day** aggregates only (`marketActivityQTotTran`, `marketValue`) — no history, **no P/E** |

**Findings that changed Task 4**

1. **TEDPIX = `Get_CWI_History`** ("شاخص کل"), `insCode 32097828799138957`.
   The index close is returned in a column **mislabelled `"Adj Close"`**; there
   is no adjusted/unadjusted choice for the index level itself. The connector
   records `insCode` + package version in Bronze metadata and treats level jumps
   as data, not a splice.
2. **Market P/E is not available** in the package or in any probed cdn endpoint.
3. **Historical aggregate trading value is not available** — only current-day
   snapshots, so there is no backfill path for a "retail trading value" series.
4. **Market cap** is likewise current-day only.

**Verdict.** OPEN for the **TEDPIX level series** (daily + month-end), which
delivers the headline demo (TEDPIX vs monthly CPI/FX). Trading value, market
P/E, and market cap move to **DEFER** — no current-day reconstruction.

### HBSIR — ✅ OPEN

**Installability / compatibility**

- License **MIT** (both packages), GitHub `Iran-Open-Data/HBSIR`, actively
  maintained (releases through 2025-12). `hbsir.__version__` is present.

**Probes**

| Probe | Result |
|-------|--------|
| `hbsir.load_table("Weight", 1400)` | ✅ 37,988 rows (`Year, ID, Weight`) — auto-downloaded cleaned Parquet from the Arvan S3 mirror |
| `hbsir.load_table("Total_Income", years=[…])` | ✅ loads for **1369…1403** (35 Jalali years; probed 1369/1385/1390/1395/1400/1403) |
| `hbsir.load_table("Total_Expenditure", 1400)` | ✅ 37,988 rows (`Gross_Expenditure`, `Net_Expenditure`) |

**Findings that shaped Task 5**

1. `hbsir` is a **loader + metadata package, not an HTTP client**: after the
   first download it works fully offline from `Data/HBSIR/4_cleaned/`. The
   connector therefore injects a loader (the package analogue of
   `http_session`).
2. **Weights are essential and available**; the parser must require them.
3. The package provides weighted quantile/decile helpers but **no Gini and no
   poverty line** — consistent with the plan's "derive in-platform".
4. No official خط فقر exists in the package, so the poverty line must be
   **explicit and relative** (default `50% × weighted median`).
5. Survey years are **Jalali**; the true Iranian year-end (Esfand 29/30) must be
   computed, and the Jalali year retained in metadata.

**Real computation behind the recorded trend** (household-weighted, no
equivalence scaling):

| Jalali year | Gini | Poverty % (`50% × weighted median`) | Weighted households |
|-------------|------|--------------------------------------|---------------------|
| 1390 | 0.3494 | 15.85 | 21.16 M |
| 1395 | 0.3767 | 16.26 | 24.85 M |
| 1400 | 0.3704 | 16.42 | 26.69 M |
| 1403 | 0.3451 | 14.58 | 28.20 M |

(1400 decile shares, %: 1.88 / 3.86 / 5.21 / 6.38 / 7.58 / 8.92 / 10.54 /
12.60 / 15.81 / 27.22 — sum ≈ 100.0.) Committed as
`tests/fixtures/hbsir/metrics_trend.json`, which the unit suite asserts against.

### Environment limitations

Network is sandboxed in this project's environment; installs and live reads in
Task 1 required escalated approval. The gate evidence above was gathered under
that approval, in a scratch venv (`/tmp/p6recon`, Python 3.12.3). HBSIR's
downloads (~tens of MB per year) landed in the scratch venv's `Data/`, not in
the repo. **The optional packages are not installed in the project venv** — the
default install and the unit suite stay package-free, exactly as the plan
requires.

---

## Task 2 — Optional extras and configuration

| Gate | Result |
|------|--------|
| `[tool.poetry.extras]` | ✅ `airflow`, **`tsetmc = ["finpy-tse"]`**, **`hbsir = ["hbsir"]`** |
| Optional dependency pins | ✅ `finpy-tse` / `hbsir = "0.6.6"` marked `optional = true` |
| `APIConfig` fields | ✅ `tsetmc_base_url` (default `http://cdn.tsetmc.com/api`), `tsetmc_timeout` (30), `hbsir_data_dir` (`Data`), `hbsir_download_timeout` (60) — all with positive-value validators |
| `.env.example` | ✅ Phase 6 block added with the `poetry install --extras "tsetmc hbsir"` instruction and the pinned versions |
| Package-free unit suite | ✅ **verified today**: `poetry run python -c "importlib.util.find_spec(...)"` → `finpy_tse False`, `hbsir False`, and 837 unit tests pass anyway |

---

## Task 3 — Gold month-end derived-series path

Source-agnostic and opt-in: `IndicatorDerivation.include_monthly: bool = False`
(`src/etl/pipeline.py:136`), plumbed through `silver_to_gold(...)` and the
derived-ids helper (`src/etl/gold.py`), producing
`derived_month_end_indicator_id(indicator_id, prefix)` → `<ID>.ME` with
`record_metadata.derivation = "month_end_from_daily"`.

| Gate | Result |
|------|--------|
| `poetry run pytest tests/unit/etl/test_gold.py tests/unit/etl/test_frequency.py -q` | ✅ PASS (regression guard for the most data-sensitive module) |
| Month-end = last observation per month, **no forward-fill** | ✅ asserted in `tests/unit/etl/test_frequency.py` and `tests/integration/test_tsetmc_pipeline.py::test_gold_month_end_creates_no_month_without_a_session` |
| Existing sources unaffected | ✅ `tests/unit/etl/test_phase6_registration.py::test_default_derivation_keeps_month_end_off` and `::test_existing_sources_do_not_opt_into_month_end`, plus the full pre-existing Gold suite |

---

## Task 4 — TSETMC connector

`src/connectors/tsetmc.py` + `src/connectors/tsetmc_parser.py`.

| Gate | Result |
|------|--------|
| `poetry run pytest tests/unit/connectors/test_tsetmc.py tests/unit/connectors/test_tsetmc_parser.py -q` | ✅ PASS — 42 + 15 tests |
| Registry scope | ✅ `TSETMC_INDICATORS` contains **`TSETMC.TEDPIX` only** (domain `market`, unit `index points`, `insCode 32097828799138957`) |
| Missing-extra behaviour | ✅ **reproduced today**: `poetry run python -m src.connectors.tsetmc --dry-run` → one actionable `ConnectionError` (`… Install it with \`poetry install -E tsetmc\` …`), pipeline aborted cleanly |
| Holidays stay absent | ✅ asserted by the fixture window (9 rows for two weeks) and by the integration suite |

---

## Task 5 — HBSIR parser and connector

`src/connectors/hbsir_parser.py` + `src/connectors/hbsir.py`.

| Gate | Result |
|------|--------|
| `poetry run pytest tests/unit/connectors/test_hbsir_parser.py tests/unit/connectors/test_hbsir.py -q` | ✅ PASS — 46 + 36 tests |
| Registry scope | ✅ `HBSIR.GINI`, `HBSIR.POVERTY.RATE`, `HBSIR.INCOME.DECILE.D1…D10` (domain `welfare`; Gini unit `index (0-1)`, the rest `percent`) |
| Weights mandatory | ✅ `ParsingError` on missing/mismatched/non-finite/negative/all-zero weights — asserted in the parser suite |
| Relative poverty documented | ✅ `POVERTY_LINE_RULE = "50% of weighted median household income"` written to `record_metadata` and the Bronze manifest; integration test `test_bronze_poverty_row_carries_the_relative_methodology` |
| Jalali → Iranian year-end | ✅ `src/utils/persian.iranian_year_end` (Esfand 29/30); Jalali year retained in metadata; integration test `test_silver_is_annual_and_aligned_to_the_gregorian_year_end` |
| Growth opt-out | ✅ rate/share indicators opt out of `YOY` (`test_hbsir_spec_opts_every_indicator_out_of_growth`) |
| Missing-extra behaviour | ✅ **reproduced today**: `poetry run python -m src.connectors.hbsir --dry-run` → actionable `ConnectionError` (`… \`poetry install -E hbsir\` …`) |

---

## Task 6 — Runner and catalog wiring

| Gate | Result |
|------|--------|
| Both specs accepted unchanged | ✅ `test_tsetmc_pipeline_accepts_its_spec_unchanged`, `test_hbsir_pipeline_accepts_its_spec_unchanged` |
| Catalog registration | ✅ `test_tsetmc_discovery_registers_only_tedpix_in_the_market_domain` (1 indicator), `test_hbsir_discovery_registers_the_twelve_welfare_indicators` (12) |
| No fabricated availability | ✅ `test_discovered_availability_is_left_unset_for_both_sources`; the real run fills the range (integration: `test_catalog_records_the_observed_daily_coverage`, `test_catalog_records_the_annual_welfare_coverage`) |
| Deferred ids absent everywhere | ✅ `test_deferred_tsetmc_indicators_are_not_registered` + `tests/integration/test_tsetmc_pipeline.py::test_deferred_indicators_are_absent_everywhere` |
| `poetry run pytest tests/unit/etl/test_pipeline.py -q` | ✅ PASS (existing pipeline suite unaffected) |

---

## Task 7 — TSETMC daily Airflow DAG

`airflow/dags/tsetmc_daily.py`: `schedule="0 23 * * *"` Asia/Tehran,
`catchup=False`, `max_active_runs=1`, `retries: 3`, failure callback escalating
after exhausted retries.

| Gate | Result |
|------|--------|
| `poetry run pytest tests/unit/airflow/test_dag_import.py -q` | ✅ PASS (extended to import `tsetmc_daily`) |
| Parses without a DB or the optional package | ✅ the package import lives inside the task callable, matching `tgju_daily.py` |

---

## Task 8 — Fixtures and unit tests

160 Phase 6 unit tests across six files, **no network and no optional package**:

| File | Tests | What it covers |
|------|------:|----------------|
| `tests/unit/connectors/test_tsetmc.py` | 42 | client injection, holiday gaps, units, validation, missing-extra error |
| `tests/unit/connectors/test_tsetmc_parser.py` | 15 | `dEven` → UTC session timestamp, malformed records |
| `tests/unit/connectors/test_hbsir.py` | 36 | loader injection, annual alignment, growth opt-out |
| `tests/unit/connectors/test_hbsir_parser.py` | 46 | known Gini/poverty/decile cases; weights required; decile sums |
| `tests/unit/connectors/test_phase6_fixtures.py` | 8 | fixture provenance/checksums, recorded trend reproduction |
| `tests/unit/etl/test_phase6_registration.py` | 13 | registry, spec derivations, catalog mapping, month-end opt-in |
| **Total** | **160** | |

Fixtures: `tests/fixtures/tsetmc/` (`tedpix_cwi_raw.json` 772,388 bytes /
`sha256 6d833ce8…`, `tedpix_window_1404-06.csv`, `marketwatch_columns.json`) and
`tests/fixtures/hbsir/` (`income_expenditure_weight_1400_sample.csv`,
`metrics_trend.json`, `_manifest.json`).

| Gate | Result |
|------|--------|
| `poetry run pytest tests/unit -q` | ✅ **837 passed, 1 skipped** (the pre-existing gated live test) |
| Coverage | ✅ **89%** (`--cov-fail-under=0` view; the `make check` gate is 80%) |

---

## Task 9 — Integration tests

`tests/integration/test_tsetmc_pipeline.py` (14 tests) and
`tests/integration/test_hbsir_pipeline.py` (15 tests) run the **real
Bronze → Silver → Gold pipeline** against live PostgreSQL + TimescaleDB, with
the upstream sources replaced by fake transports over the committed fixtures.

| Assertion area | TSETMC | HBSIR |
|----------------|--------|-------|
| Bronze stores the raw payload / one derived envelope per indicator | ✅ | ✅ |
| Bronze never stores household rows (HBSIR) | — | ✅ |
| Package name + version in Bronze metadata; **no secrets** | ✅ | ✅ |
| Silver daily + monotonic; non-sessions never filled | ✅ | ✅ annual year-end alignment |
| Gold levels + `RET1D` + `MA30` + `.ME`, values recomputed in SQL | ✅ | ✅ levels only (12 series) |
| Gold rows live in the Timescale hypertable | ✅ | ✅ |
| Catalog coverage filled from the run | ✅ | ✅ |
| Deferred indicators absent everywhere | ✅ | — |
| Idempotent re-run (Silver upsert, Gold republish) | ✅ | ✅ |

| Gate | Result |
|------|--------|
| `poetry run pytest tests/integration/test_tsetmc_pipeline.py tests/integration/test_hbsir_pipeline.py -m integration -q --cov-fail-under=0` | ✅ **29 passed in 19.24s** (reproduced 2026-09-15) |

Deferred-indicator absence is checked by id at the catalog level. Note that
after a full integration run the shared dev database is left holding the
suites' 70-session TSETMC window; Task 11's live run is what populates the real
coverage.

---

## Task 10 — Documentation and project status

| Gate | Result |
|------|--------|
| `rg -n "TSETMC\|HBSIR" docs/phase-2/data_dictionary.md docs/phase-6/` | ✅ PASS — see the command record below |
| `docs/phase-6/{README,IMPLEMENTATION,VALIDATION}.md` | ✅ created/refreshed |
| Data dictionary sections | ✅ `# TSETMC Indicators (Phase 6)` and `# HBSIR Indicators (Phase 6)` appended |
| Root `README.md` | ✅ source table rows, Phase 6 roadmap, status line |
| `AGENTS.md` | ✅ connector tree, lifecycle stage, Key Files, On-Demand Context |

### Stale-status correction

`docs/phase-6/README.md` still said *"Task 2 (optional extras + config) in
progress. Task 3+ not started"* although Tasks 1–8 were committed in `672187d`
and Task 9 in `5231ee6`. Task 10 brought the status line in line with the
committed state; the gate decisions themselves were carried over unchanged and
the long-form gate narrative moved to this file.

---

## Deviations from the plan (recorded, not silent)

1. **TSETMC indicator scope narrowed to TEDPIX.** The plan assumed TEDPIX +
   trading value + market P/E. Task 1 evidence shows only TEDPIX is
   package-supported; trading value, market P/E, **and market cap** are
   deferred. Approved at the gate; no indicator was invented to fill the gap,
   and the integration suite asserts the deferred ids are absent everywhere.
2. **TSETMC Bronze stores the raw `indexB2` payload *and* the normalized
   frame.** The plan said "the package payload"; the package returns a processed
   DataFrame and discards the raw envelope, so the connector captures the raw
   JSON itself (retrievable via the same `insCode`) for reproducibility.
3. **HBSIR Bronze stores a derived annual extract + manifest, not microdata.**
   The plan allowed this; the implementation makes it explicit
   (`microdata_persisted: false`, SHA-256 of the income/weight extract, source
   table names, survey years, household counts).
4. **No new project dependencies beyond the plan.** Both packages are optional
   extras pinned to the Task 1 versions, so the default install and the unit
   suite stay package-free.
5. **`--start`/`--end` on the TSETMC CLI are accepted for parity but ignored** —
   the package returns full history and offers no server-side window.

## Discrepancies vs the plan

- **The plan's acceptance criterion "ingests daily TEDPIX, trading value, and
  market P/E" cannot be met** and is superseded by the approved gate decision
  (TEDPIX only). It is recorded as a deviation rather than silently failing.
- **The plan's data-dictionary expectation of database-observed coverage** is
  satisfied for the shape of the series (real captured sessions, real survey
  years and metrics) but the *pipeline* coverage is from fixture replay, not a
  live production run, because the optional packages are deliberately not
  installed in the project venv. Task 11 is where the live numbers land.
- **No `@pytest.mark.live` test exists for either Phase 6 source**, although the
  plan's Level-4 validation lists one. The fixture-replay suites cover the same
  contract offline; the gated live test is open work.

---

## Final validation record — **[Task 11]**

Task 10 does **not** run `make check` or the full integration suite (Task 11
owns that pass). What *was* executed while documenting is recorded honestly
below.

```text
# Reproduced 2026-09-15, Task 10 (working tree at the time of writing)
poetry run pytest tests/unit -q --no-cov            → 837 passed, 1 skipped in 22.33s
poetry run pytest tests/unit -q --cov-fail-under=0  → 837 passed, 1 skipped, 89% coverage
poetry run pytest tests/integration/test_tsetmc_pipeline.py \
                   tests/integration/test_hbsir_pipeline.py \
                   -m integration -q --cov-fail-under=0
                                                     → 29 passed in 19.24s
poetry run alembic check                             → No new upgrade operations detected.
poetry run python -m src.connectors.tsetmc --dry-run → ConnectionError (missing extra), pipeline aborted
poetry run python -m src.connectors.hbsir  --dry-run → ConnectionError (missing extra), pipeline aborted
poetry run python -c "importlib.util.find_spec('finpy_tse'/'hbsir')" → False / False (extras absent)
poetry run pytest tests/unit/connectors/test_tsetmc.py -m live -q --no-cov
                                                     → 44 deselected, 0 selected (no live test exists)
```

**[Task 11] still to run and record here:**

- `make check` (ruff format + ruff check + mypy + pytest) at the 80% gate.
- `poetry run pytest tests/integration -m integration -q --cov-fail-under=0`
  (the full suite, not just Phase 6).
- A **real live TSETMC run** (`poetry install -E tsetmc` + `python -m
  src.connectors.tsetmc`) and an **HBSIR run** from the documented local extract
  (`poetry install -E hbsir` + `python -m src.connectors.hbsir`), with the
  resulting Gold coverage written into
  `docs/phase-2/data_dictionary.md` and the commands/results copied here.

## Acceptance-criteria status

| Criterion | Status |
|-----------|--------|
| Documented reconnaissance decision per package (open or evidenced deferral) | ✅ both OPEN; TSETMC scope narrowed with evidence |
| `python -m src.connectors.tsetmc` ingests TEDPIX + `RET1D`/`MA30`/`.ME` | ✅ implemented; **live run pending [Task 11]** (extras not installed here) |
| ~~ingests trading value and market P/E~~ | ⛔ **deferred by gate decision** (no historical source) |
| `python -m src.connectors.hbsir` ingests Gini + poverty + 10 deciles | ✅ implemented; **live run pending [Task 11]** |
| Catalog rows with correct domain/frequency/units and observed availability | ✅ asserted in unit + integration suites; live availability pending [Task 11] |
| Gregorian storage with Jalali year in metadata; TSETMC UTC period-ends | ✅ |
| Holidays / missing survey years stay gaps, never filled | ✅ |
| Optional extras keep the default install and unit suite package-free | ✅ verified today |
| `make check` at the 80% gate; integration green; `alembic check` clean | ️ partial: unit 89%, Phase 6 integration 29 passed, `alembic check` clean — **full `make check` is [Task 11]** |
| `docs/phase-6/` exists; data dictionary / README / AGENTS updated | ✅ (this task) |
| No regressions in the World Bank / IMF / EIA / TGJU / SCI suites | ✅ unit suite green with Phase 6 added; **full integration sweep is [Task 11]** |

## Remaining work

1. **[Task 11]** the full end-to-end pass listed above (live runs + `make check`
   + the whole integration suite).
2. **Gated live tests** (`@pytest.mark.live` + `RUN_LIVE_API_TESTS=1`) for both
   sources — the plan's Level-4 command currently selects 0 tests.
3. **Trading value / market P/E / market cap** remain deferred. Lifting the
   deferral needs either forward accumulation of `MarketOverview` snapshots or a
   full per-symbol snapshot derivation — both outside "wrap the package" and
   both requiring a review decision.
4. **Official Iranian poverty line** (calorie-based) — a methodology decision,
   not an implementation gap; the relative measure is the documented default.