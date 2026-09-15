# Phase 6: Market & Survey Connectors (TSETMC + HBSIR)

**Status:** ✅ Complete — both packages opened at the Task 1 gate and implemented
end to end; **TSETMC narrowed to TEDPIX** (trading value, market P/E, and market
cap deferred with evidence).
**Completed:** September 15, 2026
**Gate approved:** September 13, 2026
**Plan:** [phase-6-market-survey-connectors.md](../plans/phase-6-market-survey-connectors.md)

---

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| **[IMPLEMENTATION.md](IMPLEMENTATION.md)** | Task-by-task architecture notes, deviations | Developers |
| **[VALIDATION.md](VALIDATION.md)** | Task 1 gate evidence, per-task validation, final record | QA, Maintainers |
| **[data_dictionary.md](../phase-2/data_dictionary.md#tsetmc-indicators-phase-6)** | Observed TSETMC/HBSIR coverage (Phase 6 sections) | Analysts |
| **[tsetmc/_capture.json](../../tests/fixtures/tsetmc/_capture.json)** | Machine-readable TSETMC capture provenance | QA |
| **[hbsir/_manifest.json](../../tests/fixtures/hbsir/_manifest.json)** | Machine-readable HBSIR capture provenance | QA |

---

## What Was Built

### Components

- ✅ **Optional extras + config** (`pyproject.toml`, `src/utils/config.py`) —
  `tsetmc = ["finpy-tse"]` and `hbsir = ["hbsir"]` extras plus
  `TSETMC_BASE_URL`/`TSETMC_TIMEOUT`/`HBSIR_DATA_DIR`/`HBSIR_DOWNLOAD_TIMEOUT`
  in `APIConfig` and `.env.example`. The default install and the unit suite
  stay package-free.
- ✅ **Gold month-end derived path** (`src/etl/gold.py`) — opt-in
  `IndicatorDerivation(include_monthly=True)` republishes a daily series at
  month-end as `<derived_id>.ME` via `src/etl/frequency.py::to_month_end`
  (last session of the month, **no forward-fill**). Defaults off; no existing
  source changed.
- ✅ **TSETMC parser** (`src/connectors/tsetmc_parser.py`) — pure `indexB2`
  record → tidy daily frame; `dEven` → UTC session timestamp, holidays absent.
- ✅ **TSETMC connector** (`src/connectors/tsetmc.py`) — injectable
  `TsetmcClient` (`FinpyTseClient` wraps the raw cdn endpoint), indicator
  registry, `build_spec()` (frequency `daily`, `include_monthly=True`), CLI.
- ✅ **HBSIR parser** (`src/connectors/hbsir_parser.py`) — pure weighted
  `gini`, `poverty_rate`, `income_decile_shares`; **weights mandatory**
  (`ParsingError` otherwise); no microdata persisted.
- ✅ **HBSIR connector** (`src/connectors/hbsir.py`) — injectable `HbsirLoader`
  (`HbsirPackageLoader` wraps `hbsir.load_table`), 12-indicator registry,
  Bronze manifest + SHA-256 extract checksum instead of raw microdata.
- ✅ **Runner/catalog wiring** — both `build_spec()` outputs run through
  `run_pipeline`/`run_cli` unchanged; catalog domains `market` / `welfare`,
  frequencies `daily` / `annual`; availability filled from the real run.
- ✅ **Daily DAG** (`airflow/dags/tsetmc_daily.py`) — 23:00 `Asia/Tehran`,
  `catchup=False`, `max_active_runs=1`, retries + failure callback, lazy import
  so the DAG parses without the optional package.
-  **TSETMC trading value / market P/E / market cap** — deferred: no
  historical source in `finpy-tse` or the probed cdn endpoints (evidence in
  [VALIDATION.md](VALIDATION.md#task-1--reconnaissance--dependency-gate)).

### Sources

| Source | Frequency | Indicators | Coverage (observed) |
|--------|-----------|-----------:|---------------------|
| TSETMC (TEDPIX) | Daily | 1 + `RET1D`, `MA30`, `.ME` | 2008-12-04 → 2026-09-13; **4,283 real sessions** in the captured payload (70 replayed in the integration suite) |
| HBSIR (survey) | Annual | 12 (Gini + relative poverty + 10 deciles) | Jalali 1369–1403 (35 survey years); Gini observed 1390=0.349, 1395=0.377, 1400=0.370, 1403=0.345 |

Both sources register catalog rows with **no fabricated availability**: the real
run fills `availability_start/end`, and `discover()` leaves them `None`.

### Tests

- **Unit:** 837 passed + 1 gated live-skipped, **89% coverage**, including 160
  Phase 6 tests (TSETMC 42, TSETMC parser 15, HBSIR connector 36, HBSIR parser
  46, fixtures 8, registration 13).
- **Integration:** 29 passed in the two Phase 6 suites (TSETMC 14 + HBSIR 15)
  against live PostgreSQL + TimescaleDB, with no network and no optional
  package: the connectors are injected with fake transports over the committed
  fixtures.
- **Quality gates:** `ruff check` / `ruff format --check` clean, `mypy src`
  clean, `alembic check` → *No new upgrade operations detected* (no Phase 6
  migration needed).

---

## Quick Start

### Prerequisites

```bash
poetry install --extras "tsetmc hbsir"   # optional packages; the base install omits them
make db-up
poetry run alembic upgrade head
```

HBSIR data lands in `Data/HBSIR/4_cleaned/` (config `HBSIR_DATA_DIR`) on first
use and works offline afterwards.

### Run the pipeline

```bash
# Fetch + parse + validate, write nothing
poetry run python -m src.connectors.tsetmc --dry-run
poetry run python -m src.connectors.hbsir --dry-run

# Full Bronze → Silver → Gold
poetry run python -m src.connectors.tsetmc            # TEDPIX + RET1D + MA30 + .ME
poetry run python -m src.connectors.hbsir             # Gini + relative poverty + deciles

# One series
poetry run python -m src.connectors.tsetmc --indicators TSETMC.TEDPIX --dry-run
```

Both CLIs accept `--log-level`; `--start/--end` are accepted for parity but
ignored (the package returns full history). Without the extras installed the
CLI **fails loudly** with the actionable
`poetry install -E tsetmc` / `poetry install -E hbsir` message rather than
silently collecting nothing.

### Schedule it

```bash
make airflow-up            # loads airflow/dags/tsetmc_daily.py
poetry run airflow dags trigger tsetmc_daily
```

### Run the tests

```bash
poetry run pytest tests/unit -q
poetry run pytest tests/integration/test_tsetmc_pipeline.py tests/integration/test_hbsir_pipeline.py \
  -m integration -q --cov-fail-under=0
```

---

## Approved decisions (2026-09-13)

Task 1 is approved with the following scope decisions, which are binding for
Tasks 2+:

### TSETMC
- **OPEN: `TSETMC.TEDPIX` only** — daily level series from `Get_CWI_History`
  (`insCode 32097828799138957`).
- Include the daily derivations **`RET1D`** and **`MA30`**, plus the month-end
  **`.ME`** series.
- **DEFER `Trading Value` and `Market P/E`.** `finpy-tse` provides no reliable
  *historical* version of either; they must **not** be invented or reconstructed
  from current-day snapshots.
- **DEFER market capitalization** — no reliable historical source was found.

### HBSIR
- **OPEN: weighted Gini** and **weighted income decile shares**.
- **Poverty rate is OPEN only as an explicitly documented *relative* measure**:
  `50% × weighted median income` (household-weighted, configurable via
  `poverty_line_k`). It must **not** be described as the official Iranian
  poverty line; the rule (`50% of weighted median household income`) is written
  into each observation's metadata and the Bronze manifest.
- **Weights are mandatory** — fail loudly (`ParsingError`) if unavailable.
- **Preserve the Jalali survey year** in metadata and convert the timestamp to
  the correct **Gregorian Iranian year-end** (Esfand 29/30, leap-aware), never a
  hardcoded `12-29`.

---

## Gate summary

| Source | Package | Verdict | One-line reason |
|--------|---------|---------|-----------------|
| **TSETMC** | `finpy-tse==1.2.10` | ✅ **OPEN** (TEDPIX only) | Live daily TEDPIX history 2008-12-04 → today, no auth; the package exposes **no market P/E and no historical aggregate trading value** |
| **HBSIR** | `hbsir==0.6.6` (+`bssir==0.6.8`) | ✅ **OPEN** | Real microdata loads offline after auto-download; income/expenditure/weights present; 1369–1403 coverage |

Both packages install and import cleanly on Python 3.12 and are pure-python
(`py3-none-any`) with permissive licenses (BSD-3 / MIT). **No source was
deferred to a hand-rolled scraper** in Phase 6. Full probe evidence, per-task
validation, and the final record are in [VALIDATION.md](VALIDATION.md).

---

## Notes and limitations

- **TSETMC ships one index, not three.** The plan assumed TEDPIX + trading value
  + market P/E; reconnaissance found only TEDPIX is package-supported, so the
  MVP narrows to it. The gap is recorded, not silently dropped — see
  [VALIDATION.md](VALIDATION.md#deviations-from-the-plan-recorded-not-silent).
- **Market holidays and missing survey years are gaps.** No forward-fill
  anywhere: a two-week TSETMC window returns only the 9 real sessions, and the
  integration suite asserts a month with no session produces **no** `.ME` row.
- **HBSIR's measures are rates/shares, so the source opts out of `YOY`** — a
  growth series on a Gini or a share would be meaningless. `include_monthly` is
  off for HBSIR too.
- **No microdata is persisted.** Bronze keeps the derived annual observations
  plus a manifest (source tables, survey years, household counts, SHA-256 of the
  income/weight extract) so the computation is reproducible without
  redistributing the survey.
- **The official Iranian (خط فقر) poverty line is not modelled.** The calorie
  requirements / official-line path is a follow-up decision, not assumed here.
- **No `@pytest.mark.live` test exists for either source.** The live path is
  evidenced by the Task 1 capture plus the fixture-replay suites; a gated live
  test remains open work, recorded in
  [VALIDATION.md](VALIDATION.md#remaining-work).
- **This README was rewritten in Task 10.** Until then it carried the Task 1
  gate record and a stale "Task 2 in progress, Task 3+ not started" status line
  while Tasks 1–9 were already committed. The gate decisions are unchanged in
  substance; the full narrative now lives in
  [VALIDATION.md](VALIDATION.md#task-1--reconnaissance--dependency-gate).