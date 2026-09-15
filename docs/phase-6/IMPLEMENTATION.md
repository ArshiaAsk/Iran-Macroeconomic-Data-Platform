# Phase 6 Implementation Notes

Task-scoped notes for the Phase 6 plan
(`docs/plans/phase-6-market-survey-connectors.md`). See
`docs/phase-6/VALIDATION.md` for the reconnaissance/decision-gate record and the
per-task validation results.

---

## Task 2 — Optional extras and configuration

Phase 6 is the first phase whose upstream sources are **packages** rather than
HTTP endpoints, so the dependency question came before any code: both packages
are optional, and neither may reach the default install.

### `[tool.poetry.extras]`

```toml
[tool.poetry.extras]
airflow = ["apache-airflow"]
tsetmc  = ["finpy-tse"]
hbsir   = ["hbsir"]
```

with the dependencies themselves marked optional:

```toml
finpy-tse  = {version = "^1.2", optional = true}
hbsir      = {version = "0.6.6", optional = true}
```

**Why optional.** The unit suite must run — and the 80% coverage gate must
pass — on a plain `poetry install`, with no network and no package-backed
transport. Every Phase 6 test injects a fake client/loader, so the extras are
only needed for a real run.

**Pinning.** `hbsir` is pinned exactly (`0.6.6`) because the parser's column
contract (`Year/ID/Income`, `Year/ID/Weight`) comes from its cleaned tables and
the package is under active development. `finpy-tse` uses a caret range: it is
stable and unmaintained, and reads the version at runtime through
`importlib.metadata` (it has **no** `__version__` attribute).

### `APIConfig` additions

| Field | Env alias | Default | Note |
|-------|-----------|---------|------|
| `tsetmc_base_url` | `TSETMC_BASE_URL` | `http://cdn.tsetmc.com/api` | The cdn the package itself talks to |
| `tsetmc_timeout` | `TSETMC_TIMEOUT` | `30` | validated ≥ `MIN_TIMEOUT_SECONDS` (10) |
| `hbsir_data_dir` | `HBSIR_DATA_DIR` | `Data` | `hbsir` downloads its cleaned Parquet here |
| `hbsir_download_timeout` | `HBSIR_DOWNLOAD_TIMEOUT` | `60` | validated positive |

`.env.example` gained a Phase 6 block carrying the
`poetry install --extras "tsetmc hbsir"` instruction and the pinned versions.

### Validation

```text
poetry lock                     → PASS
poetry install                  → PASS (no Phase 6 package pulled)
poetry run python -c "import importlib.util as u; print(u.find_spec('finpy_tse'), u.find_spec('hbsir'))"
                                → PASS (None None — extras absent, as designed)
poetry run pytest tests/unit -q → PASS (837 passed, 1 skipped)
```

---

## Task 3 — Gold month-end derived-series path (`src/etl/gold.py`)

TSETMC is the platform's first **daily** source, and its headline use case —
TEDPIX against monthly CPI and FX — needs a monthly series. Rather than
teaching Gold about TSETMC, the path is **source-agnostic and opt-in**.

### Opt-in flag

`IndicatorDerivation` gained one field with a default that preserves every
existing source's behaviour exactly (`src/etl/pipeline.py:136`):

```python
include_monthly: bool = False
```

It is plumbed through `run_pipeline` → `silver_to_gold(...)` → the derivations
helper alongside `include_growth`.

### Derived id and provenance

```python
DERIVED_MONTH_END_SUFFIX = "ME"
DERIVED_MONTH_END_METHOD = "month_end_from_daily"

derived_month_end_indicator_id("TSETMC.TEDPIX", "TSETMC")  # "TSETMC.TEDPIX.ME"
```

The `.ME` row is republished into the same Gold hypertable with
`record_metadata.derivation = "month_end_from_daily"` and the source indicator
id, so a consumer can always tell a derived month-end point from an observed
one.

### Month-end semantics — no forward-fill

`src/etl/frequency.py::to_month_end` takes the **last observation in each
month** and nothing else:

- A month with no session produces **no** `.ME` row (asserted in
  `tests/integration/test_tsetmc_pipeline.py::test_gold_month_end_creates_no_month_without_a_session`).
- No interpolation, no carry-forward, no synthetic month-end timestamp.

This matches the platform-wide rule that market holidays and missing survey
years are gaps, never filled.

### Validation

```text
poetry run pytest tests/unit/etl/test_gold.py tests/unit/etl/test_frequency.py -q → PASS
poetry run pytest tests/unit/etl/test_phase6_registration.py -q                   → PASS (13)
```

Both `test_default_derivation_keeps_month_end_off` and
`test_existing_sources_do_not_opt_into_month_end` guard the other five sources.

---

## Task 4 — TSETMC connector (`src/connectors/tsetmc.py`, `tsetmc_parser.py`)

### Split: pure parser, injected transport

Two modules, mirroring the TGJU/SCI shape:

| Module | Responsibility |
|--------|----------------|
| `tsetmc_parser.py` | **Pure.** `SESSION_DATE_FIELD = "dEven"`, `parse_session_date(value)`, `tsetmc_parser(...)` — raw `indexB2` records → a tidy daily frame. No I/O, no package import. |
| `tsetmc.py` | Everything else: config, indicators, the injectable client, `build_spec()`, the CLI. |

### Injectable transport

```python
class TsetmcClient(Protocol):
    def fetch_index_history(self, ins_code: str) -> TsetmcIndexPayload: ...

class FinpyTseClient:   # imports finpy_tse lazily, inside the call
    ...
```

The Protocol is the package analogue of the `http_session` injection used by
the World Bank / IMF / EIA / TGJU connectors: tests pass a fake client built
from the captured fixtures, so the suite never imports `finpy_tse`.

**Why the connector reads the raw `indexB2` endpoint rather than the package's
DataFrame:** `Get_CWI_History` returns a processed frame and discards the raw
envelope, so the raw JSON is fetched (same `insCode`, same cdn) for Bronze
reproducibility. The package version is still recorded, and
`TsetmcFetchResult.collection_metadata()` carries:

```json
{
  "indicator_id": "TSETMC.TEDPIX",
  "package": "finpy-tse",
  "package_version": "1.2.10",
  "ins_code": "32097828799138957",
  "rows_returned": 4283,
  "rows_usable": 4283,
  "envelope_convention": "raw_data = {rows, meta}"
}
```

`package_version` comes from `importlib.metadata.version("finpy-tse")` — the
distribution has no `__version__` attribute (Task 1 finding).

### Indicator registry — TEDPIX only

```python
TSETMC_INDICATORS = {
    "TSETMC.TEDPIX": TsetmcIndicator(
        indicator_id="TSETMC.TEDPIX",
        name="Tehran Stock Exchange total index (TEDPIX)",
        domain="market",
        ins_code="32097828799138957",
    ),
}
DEFAULT_INDICATORS = tuple(TSETMC_INDICATORS)
```

`DEFAULT_UNIT = "index points"`. Trading value, market P/E, and market cap are
**absent by decision** — see the deviation log in VALIDATION.md and the
evidence in `tests/fixtures/tsetmc/SOURCES.md`. No placeholder id was created.

### `build_spec()`

```python
frequency="daily"
IndicatorDerivation(derivation_strategy="daily",
                    include_growth=True,      # RET1D
                    include_monthly=True)     # .ME
parser=tsetmc_parser
```

`MA30` comes from the standard daily derivation set. The spec is handed to the
generic `run_pipeline`/`run_cli` unchanged — the connector adds **no runner
logic**.

### Session timestamps

`dEven` is a Gregorian `yyyymmdd` integer. It is normalized to a UTC session
timestamp (the Tehran session close), so the daily series is strictly
monotonic and comparable with the other sources' period ends. Holidays and
Thu/Fri are simply absent — the two-week fixture window
(`tedpix_window_1404-06.csv`) contains **9** real rows.

### Missing-extra behaviour

One actionable error, not a silent empty collection:

```text
ConnectionError: finpy-tse is not installed. Install it with `poetry install -E tsetmc`
```

### CLI

`python -m src.connectors.tsetmc [--indicators ID ...] [--dry-run] [--start] [--end] [--log-level]`.
`--start/--end` are accepted for parity with the other connectors but **ignored**
— the package returns full history and offers no server-side window.

### Files changed (this task)

- `src/connectors/tsetmc_parser.py` (new)
- `src/connectors/tsetmc.py` (new)
- `tests/unit/connectors/test_tsetmc_parser.py`, `test_tsetmc.py` (new)

### Validation

```text
poetry run pytest tests/unit/connectors/test_tsetmc.py tests/unit/connectors/test_tsetmc_parser.py -q → PASS (42 + 15)
poetry run python -m src.connectors.tsetmc --dry-run → ConnectionError (missing extra), aborted cleanly
```

---

## Task 5 — HBSIR parser and connector (`src/connectors/hbsir_parser.py`, `hbsir.py`)

### Split: pure weighted statistics, injected loader

| Module | Responsibility |
|--------|----------------|
| `hbsir_parser.py` | **Pure statistics.** No pandas-I/O, no package import. Every function takes values + weights. |
| `hbsir.py` | Config, indicators, `HbsirLoader` Protocol, `HbsirPackageLoader`, Bronze manifest, `build_spec()`, CLI. |

### Indicator registry — 12 series

| Id | Unit | Derivation |
|----|------|-----------|
| `HBSIR.GINI` | `index (0-1)` | weighted Gini of household income |
| `HBSIR.POVERTY.RATE` | `percent` | share below the relative line |
| `HBSIR.INCOME.DECILE.D1` … `.D10` | `percent` | income share of each weighted decile |

`DECILE_COUNT = 10`, `DECILE_INDICATOR_PREFIX = "HBSIR.INCOME.DECILE.D"`. All
twelve are domain `welfare`, frequency `annual`.

### Weighted statistics — weights are mandatory

The parser raises `ParsingError` on **missing, mismatched, non-finite,
negative, or all-zero** weights. There is no unweighted fallback: an unweighted
Gini over 37,988 sampled households is not a population statistic, and
`hbsir` supplies the sampling weights (`Weight`), so silently degrading would
publish a wrong number under a right-looking id.

Definitions, all household-weighted over `Total_Income` (`Income`), unit of
analysis = household, **no equivalence scaling**:

- **Weighted median** — the first income at which cumulative weight reaches 50%
  (**no interpolation** between observations).
- **Gini** — Lorenz/Brown: `1 − Σ pi (Li−1 + Li)`.
- **Deciles** — cumulative-weight position, ten equal-weight groups;
  `DECILE_SHARE_TOLERANCE_PCT = 0.5` guards the sum to 100.
- **Relative poverty rate** — share of weighted households below
  `k × weighted median`, `DEFAULT_POVERTY_LINE_K = 0.5`, rule string
  `POVERTY_LINE_RULE = "50% of weighted median household income"`.

That rule string is written into **each observation's `record_metadata`** and
into the Bronze manifest, because the measure must never be read as the
official Iranian (خط فقر) line. `hbsir` ships no official line, and the
calorie-requirement path is a separate methodology decision.

### Column contract

`YEAR_COLUMN = "Year"`, `ID_COLUMN = "ID"`, `INCOME_COLUMN = "Income"`,
`WEIGHT_COLUMN = "Weight"` — matching the package's cleaned tables
(`Total_Income`, `Weight`). `Total_Expenditure` is the documented alternative
basis but is not part of the MVP.

### Temporal alignment — Jalali year, real year-end

Survey years are Jalali. Silver stores the **Gregorian Iranian year-end**
computed by `src/utils/persian.iranian_year_end` (Esfand 29 or 30, leap-aware —
never a hardcoded `12-29`), and the Jalali year is retained in
`record_metadata` alongside the weighted-household count and the source tables.

### Growth opt-out

Gini and shares are rates. A year-over-year growth of a Gini coefficient is
meaningless, so every HBSIR indicator opts out of `YOY`:

```python
IndicatorDerivation(derivation_strategy="annual", include_growth=False)
```

`include_monthly` is likewise off — the series is already annual.

### No microdata in Bronze

Bronze stores **derived annual observations plus a manifest**, never household
rows:

```json
{
  "source_tables": ["Total_Income", "Weight"],
  "survey_years_jalali": [1400],
  "extract_checksum_sha256": "…",
  "poverty_line_rule": "50% of weighted median household income",
  "microdata_persisted": false
}
```

The SHA-256 covers the income/weight extract, so the computation is reproducible
without redistributing the survey. An integration test asserts no household row
ever lands in Bronze.

### Missing-extra behaviour

```text
ConnectionError: hbsir is not installed. Install it with `poetry install -E hbsir`
```

### Files changed (this task)

- `src/connectors/hbsir_parser.py` (new)
- `src/connectors/hbsir.py` (new)
- `tests/unit/connectors/test_hbsir_parser.py`, `test_hbsir.py` (new)

### Validation

```text
poetry run pytest tests/unit/connectors/test_hbsir_parser.py tests/unit/connectors/test_hbsir.py -q → PASS (46 + 36)
poetry run python -m src.connectors.hbsir --dry-run → ConnectionError (missing extra)
```

---

## Task 6 — Runner and catalog wiring

No runner code was written: both connectors produce a `SourceSpec` and hand it
to the existing `run_pipeline` / `run_cli`.

| Source | Domain | Frequency | Indicators |
|--------|--------|-----------|-----------:|
| `tsetmc` | `market` | `daily` | 1 (+ `RET1D`, `MA30`, `.ME`) |
| `hbsir` | `welfare` | `annual` | 12 |

**No fabricated availability.** `discover()` registers the catalog row and
leaves `availability_start`/`availability_end` unset; only a real run writes the
observed range. This is asserted in
`test_discovered_availability_is_left_unset_for_both_sources` and, from the
other side, in the integration tests that check the range the run actually
produced.

### Files changed (this task)

- `src/connectors/tsetmc.py`, `src/connectors/hbsir.py` (registration + catalog
  mapping of the two specs)
- `tests/unit/etl/test_phase6_registration.py` (new, 13 tests)

### Validation

```text
poetry run pytest tests/unit/etl/test_phase6_registration.py tests/unit/etl/test_pipeline.py -q → PASS
```

---

## Task 7 — TSETMC daily Airflow DAG (`airflow/dags/tsetmc_daily.py`)

```python
dag_id="tsetmc_daily"
schedule="0 23 * * *"        # 23:00 Asia/Tehran, after the session settles
catchup=False
max_active_runs=1
default_args={"retries": 3}
on_failure_callback=_on_failure_callback
```

Follows `tgju_daily.py`. The optional package is imported **inside** the task
callable, so the DAG parses without the extra installed and without a database
connection — the property `tests/unit/airflow/test_dag_import.py` asserts.

### Files changed (this task)

- `airflow/dags/tsetmc_daily.py` (new)
- `tests/unit/airflow/test_dag_import.py` (extended)

### Validation

```text
poetry run pytest tests/unit/airflow/test_dag_import.py -q → PASS
```

---

## Task 8 — Fixtures and unit tests

Tests are written against **captured real payloads**, not invented ones:

| Fixture | Size | Provenance |
|---------|------|-----------|
| `tests/fixtures/tsetmc/tedpix_cwi_raw.json` | 772,388 B | raw `indexB2` for `insCode 32097828799138957` (`sha256 6d833ce8…`) |
| `tests/fixtures/tsetmc/tedpix_window_1404-06.csv` | 206 B | `Get_CWI_History(start='1404-06-01', end='1404-06-15')` — 9 sessions (`sha256 89544dab…`) |
| `tests/fixtures/tsetmc/marketwatch_columns.json` | 2,933 B | `Get_MarketWatch` column inventory — the **P/E-absence evidence** (`sha256 df8002b1…`) |
| `tests/fixtures/hbsir/income_expenditure_weight_1400_sample.csv` | 200 real 1400 rows | `Year, ID, Income, Gross_Expenditure, Net_Expenditure, Weight` |
| `tests/fixtures/hbsir/metrics_trend.json` | 4 survey years | computed Gini / relative poverty / decile shares + source column lists |
| `tests/fixtures/hbsir/_manifest.json` | — | package versions, mirror URL, source Parquet names/sizes/sha256 |

Each directory has a `SOURCES.md` describing the package, the probes, and the
findings, and a machine-readable provenance file (`_capture.json` /
`_manifest.json`). `tests/unit/connectors/test_phase6_fixtures.py` asserts the
checksums, so a fixture cannot be silently edited.

160 Phase 6 unit tests: TSETMC connector 42, TSETMC parser 15, HBSIR connector
36, HBSIR parser 46, fixtures 8, registration 13.

### Validation

```text
poetry run pytest tests/unit -q --no-cov           → 837 passed, 1 skipped
poetry run pytest tests/unit -q --cov-fail-under=0 → 837 passed, 1 skipped, 89%
```

---

## Task 9 — Integration tests

`tests/integration/test_tsetmc_pipeline.py` (14) and
`tests/integration/test_hbsir_pipeline.py` (15) exercise the **real**
Bronze → Silver → Gold path against Docker PostgreSQL + TimescaleDB, with the
upstream source replaced by a fake transport over the committed fixtures — no
network, no optional package.

What they pin down, beyond a smoke test:

- Bronze holds the raw payload / one derived envelope per indicator, with the
  package name and version, and **no secrets**.
- Bronze never holds HBSIR household rows.
- Silver is daily and monotonic for TSETMC; annual and aligned to the Gregorian
  Iranian year-end for HBSIR; missing sessions and years are never filled.
- Gold carries levels plus `RET1D`, `MA30`, and `.ME` (TSETMC) / 12 level series
  (HBSIR), with the derived values **recomputed in SQL** rather than trusted
  from Python.
- Gold rows are in the Timescale hypertable.
- Catalog coverage is written by the run.
- The deferred TSETMC ids are absent everywhere.
- A re-run is idempotent (Silver upsert on `(indicator_id, timestamp)`, Gold
  delete-and-reinsert).

### Validation

```text
poetry run pytest tests/integration/test_tsetmc_pipeline.py tests/integration/test_hbsir_pipeline.py -m integration -q --cov-fail-under=0
    → 29 passed in 19.24s
poetry run alembic check → No new upgrade operations detected.
```

No Phase 6 migration was needed — the Gold hypertable and catalog already
existed from earlier phases.

---

## Task 10 — Documentation (data dictionary, README, AGENTS, phase-6)

- `docs/phase-6/{README,IMPLEMENTATION,VALIDATION}.md` written.
- `docs/phase-2/data_dictionary.md` gained `# TSETMC Indicators (Phase 6)` and
  `# HBSIR Indicators (Phase 6)`, mirroring the SCI section.
- Root `README.md`: the TSETMC/HBSIR source rows, the Phase 6 roadmap boxes, and
  the project status line.
- `AGENTS.md`: the connector tree, the lifecycle stage, the docs tree, the Key
  Files table, and the On-Demand Context rows.

### Stale status corrected

`docs/phase-6/README.md` had carried the Task 1 gate record and a
"Task 2 in progress, Task 3+ not started" status line while Tasks 1–9 were
already committed (`672187d`, `5231ee6`). The gate decisions are unchanged in
substance; the long-form gate narrative moved to VALIDATION.md.

### Observed coverage recorded

The dictionaries' observed numbers come from the Task 1 capture — 4,283 real
TEDPIX sessions (2008-12-04 → 2026-09-13) and HBSIR survey years 1369–1403 with
the computed Gini / poverty / decile trend — plus the fixture-replay integration
results. They are labelled as such: the optional packages are deliberately not
installed in the project venv, so no live end-to-end run backs them yet. That
run is Task 11's job, and the dictionary sections say so.

### Validation

```text
rg -n "TSETMC|HBSIR" docs/phase-2/data_dictionary.md docs/phase-6/ → PASS
```

---

## Deviation log (summary)

Full detail and evidence in
[VALIDATION.md](VALIDATION.md#deviations-from-the-plan-recorded-not-silent).

1. **TSETMC narrowed to TEDPIX** — trading value, market P/E, and market cap
   deferred (no historical source; evidence in
   `tests/fixtures/tsetmc/SOURCES.md` and `marketwatch_columns.json`).
2. **Bronze stores the raw `indexB2` payload** in addition to the normalized
   frame, because the package discards the raw envelope.
3. **HBSIR Bronze stores a derived extract + manifest**, explicitly
   `microdata_persisted: false`.
4. **No dependencies beyond the plan** — both packages are optional extras.
5. **TSETMC `--start/--end` accepted but ignored** (no server-side window in
   the package).
6. **No `@pytest.mark.live` test exists for either source**, although the
   plan's Level-4 validation lists one; recorded as open work, not skipped
   silently.