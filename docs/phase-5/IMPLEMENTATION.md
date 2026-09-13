# Phase 5 Implementation Notes

Task-scoped notes for the Phase 5 plan
(`docs/plans/phase-5-cbi-sci-scrapers.md`). See `docs/phase-5/VALIDATION.md`
for the reconnaissance/decision-gate record.

---

## Task 2 — Parsing dependencies (`pdfplumber`, `xlrd`)

Added to `[tool.poetry.dependencies]` and locked in `poetry.lock`:

### `pdfplumber = "^0.11"` (resolved 0.11.10)

**Why:** SCI publishes part of the required series as PDF, not Excel. Task 1
captured two genuine PDFs — the monthly CPI report
(`tests/fixtures/sci/cpi_report_1405-05_base1400.pdf`, 554 KB) and the annual
labour-force report (`unemployment_report_1404.pdf`, 1.02 MB) — and the plan's
SCI parser must handle PDF tables. PDF parsing is therefore **confirmed**, so
this stays a runtime dependency (not dev-only). It pulls `pdfminer.six`
(20260107) and `pypdfium2`, both recorded in the lock file. Persian RTL PDFs
extract with reversed visual order, which the parser (Task 4) must normalise —
not a dependency concern.

### `xlrd = "^2.0"` (resolved 2.0.2)

**Why:** Task 1 captured a genuine legacy `.xls` workbook —
`tests/fixtures/sci/unemployment_spring_1405.xls`
(`application/vnd.ms-excel`, BIFF) — plus similar `.xls` files on the SCI labour
and agricultural price pages. `openpyxl` cannot read BIFF, so `xlrd` is
required.

**Gotcha honoured:** `xlrd >= 2.0` reads **only** `.xls`, never `.xlsx`.
`openpyxl` remains the reader for the `.xlsx` publications (national/urban/
rural/decile/base-1395 CPI, unemployment annual); `xlrd` is used solely for the
legacy `.xls` path.

### Validation

```text
poetry lock                                             → PASS (lock file written)
poetry install                                          → PASS (4 installs, 0 updates, 0 removals)
poetry run python -c "import pdfplumber, pandas; print('ok')" → PASS (ok)
```

Smoke-tested against the real Task 1 fixtures:

```text
xlrd.open_workbook(unemployment_spring_1405.xls)   → 10 sheets, first "فهرست جداول"
pdfplumber.open(cpi_report_1405-05_base1400.pdf)   → 11 pages, page 1 text + 1 table extracted
```

---

## Task 5 — SCI scraper/connector (`src/connectors/sci_scraper.py`)

The connector downloads SCI's publications as **files** and stores one Bronze
row per file (`{"rows": [parsed...], "meta": {raw_file_base64, sha256, …}}`),
delegating all layout handling to `src/connectors/sci_parser.py` (Task 4).
It follows the TGJU connector shape: injected `Browser`/HTTP session,
`RetryPolicy`, and `RateLimiter`; `discover()`; `fetch_series()`; a
`run_sci_pipeline()`/`main()` CLI with `--dry-run` and `--indicators`.

Registry (real Task 1 URLs, base years explicit in the file):

| Publication | Series id | Base | Frequency |
|---|---|---|---|
| `cpi_national` | `SCI.CPI.NATIONAL.B2021` | 1400 = 2021 | monthly |
| `cpi_urban` | `SCI.CPI.URBAN.B2021` | 1400 = 2021 | monthly |
| `cpi_rural` | `SCI.CPI.RURAL.B2021` | 1400 = 2021 | monthly |
| `cpi_base1395` | `SCI.CPI.URBAN.B2016` | 1395 = 2016 | monthly |
| `cpi_decile` | `SCI.CPI.DECILE.B2021.D1…D10` | 1400 = 2021 | monthly |
| `unemployment_spring_1405` | `SCI.UNEMPLOYMENT.QUARTERLY` | — | quarterly |

The CPI PDF report and the labour-force PDF expose no extractable tables, and
the annual unemployment cross-tab has no clean rate row (Task 4 finding), so
they are **not** registered. Gold chain-linking of the `B2016`/`B2021` segments
into a canonical id is a later runner-wiring step (this task stops at Silver).

### Config added (Task 5 dependency)

`APIConfig.sci_base_url` / `cbi_tsd_url` / `sci_ca_bundle` and
`CollectionConfig.scraper_download_timeout` / `scraper_max_download_bytes`
(mirrored into `.env.example`). CBI remains gated.

### TLS: deliberate verification of a broken chain

`https://www.amar.org.ir` serves an **incomplete chain** — the leaf is issued by
`Certum DV TLS G2 R39 CA`, but the server advertises older intermediates, so
OpenSSL/Python report *unable to verify the first certificate*. Per the Task 1
recommendation we **pin the missing chain** instead of disabling verification:
`src/connectors/certs/certum_dv_tls_g2_r39_ca.pem` contains the
`Certum DV TLS G2 R39 CA` intermediate (fetched from the leaf's AIA) plus the
self-signed `Certum Trusted Root CA`. `SciScraper` passes it as `verify=` on
every request; `SCI_CA_BUNDLE` overrides the path. No `verify=False` anywhere.

### Validation

```text
poetry run python -m src.connectors.sci_scraper --dry-run → PASS (6/6 publications)
  SCI.CPI.NATIONAL.B2021      185 rows
  SCI.CPI.URBAN.B2021         293 rows
  SCI.CPI.RURAL.B2021         429 rows
  SCI.CPI.URBAN.B2016         251 rows
  SCI.CPI.DECILE.B2021       1250 rows / 10 series
  SCI.UNEMPLOYMENT.QUARTERLY    1 row (9.1%, spring 1405)
```

Live download sha256 values matched the Task 1 `_capture.json` records exactly.

---

## Task 6 — CBI parser (GATED: not implemented)

The plan's Task 6 (`src/connectors/cbi_parser.py`) is conditional on the Task 1
gate being open. The gate was re-probed on 2026-09-13 (plain HTTP + a normal
headless Chromium) and is **still closed**: `www.cbi.ir` returns an F5 TSPD
JavaScript challenge for every path (including `robots.txt`), and `tsd.cbi.ir`
does not resolve. Per the task's own gotcha and the AGENTS.md/OPEC precedent, the
file was **not created** and no CBI fixture-with-data was added.

Fresh evidence: `tests/fixtures/cbi/task6_cbi_home_browser.html`,
`task6_cbi_robots_browser.html`, `task6_cbi_home_curl.html`,
`task6_cbi_robots_curl.txt`, `_gate_task6.json`; full record in
`docs/phase-5/VALIDATION.md` (Task 6 section).

### Validation

```text
poetry run pytest tests/unit/connectors/test_cbi_parser.py → SKIPPED (gated; file intentionally absent)
poetry run ruff check src tests                           → PASS
poetry run mypy src                                       → PASS
poetry run pytest -m "not integration"                    → PASS (see final report)
```

---

## Task 7 — CBI scraper (GATED: not implemented)

Task 7 (`src/connectors/cbi_scraper.py`) is conditional on the same Task 1 gate
as Task 6 and depends on it. It targets `config.cbi_tsd_url` (`tsd.cbi.ir`),
which was re-probed on 2026-09-13 and does not answer on either `http` or
`https` (curl exit 28, HTTP `000`, 20 s timeout). The `www.cbi.ir` F5 TSPD
challenge from the Task 6 re-check still stands.

Per the plan's bot-defense rule and the AGENTS.md/OPEC precedent, **no
`CbiConfig`, `CBI_INDICATOR_REGISTRY`, `CbiScraper`, runner, or CLI was
created**, and no request was retried into a bypass.

Fresh evidence: `tests/fixtures/cbi/_gate_task7.json`; full record in
`docs/phase-5/VALIDATION.md` (Task 7 section).

### Validation

```text
poetry run python -m src.connectors.cbi_scraper --dry-run → NOT RUN (gated; module intentionally absent)
poetry run ruff check src tests                          → PASS
poetry run mypy src                                      → PASS
poetry run pytest -m "not integration"                   → PASS (see final report)
```

---

## Task 8 — SCI Gold multi-segment chain-linking + runner/catalog wiring

**Plan dependency surfaced during implementation.** The plan lists
`silver_to_gold(segment_indicator_ids=...)` as an existing dependency ("Tasks 5
and 5b (gold extension)"), but the extension half — "5b" — was **not** built
during Task 5, which stopped at Silver. Task 8 therefore implements both parts
in one change: the Gold multi-segment extension and the runner/catalog wiring.
This is the one interpretation deviation in this task.

### Part 5b — `src/etl/gold.py` multi-segment linking

`silver_to_gold()` gained `segment_indicator_ids: Sequence[str] | None = None`.
When supplied, the canonical `indicator_id` is **not** read from its own Silver
rows; instead each `B<year>` segment is loaded from Silver, ordered oldest base
first, and spliced into one series under the canonical id:

- `BaseYearSegment` dataclass (`indicator_id`, `series`, `base_year`).
- `base_year_from_indicator_id()` reads the Gregorian base from a
  `…B<year>` suffix; `_segment_base_year()` prefers `record_metadata.base_year`
  and falls back to the id.
- `order_base_year_segments()` sorts ascending; when any base year is unknown it
  **keeps the supplied order and warns** rather than guessing the splice
  direction.
- `load_base_year_segments()` loads and orders them.
- `_merge_segment_series()` derives the per-timestamp Silver-id map from all
  segments so every Gold row keeps a real `silver_id`.
- Empty/missing segments raise `ChainLinkingError` (never a silent passthrough).
- `processed` is the sum of segment rows; the details dict adds `segments`.

The single-series path is untouched.

**Silver metadata propagation (supporting 5b).** Segment ordering needs the
base year on the Silver rows, so `src/etl/silver.py::_silver_records` now merges
a parser-provided `record_metadata` mapping into the persisted row metadata
before `obs_status`/`observation_type`, and the SCI parser adapter in
`src/connectors/sci_scraper.py` emits a `record_metadata` column when the parser
produced one. `parse_publication()` also forwards `sheet`/`row_label` from
`parser_options`.

### Part B — runner + catalog wiring (`src/connectors/sci_scraper.py`)

- `SciCanonicalIndicator` + `SCI_CANONICAL_INDICATORS` registry names the
  canonical series and the published segments that feed them
  (`SCI.CPI.NATIONAL`, `SCI.CPI.URBAN`, `SCI.CPI.RURAL`).
- `discover()` now emits the canonicals **first, active** (`is_active=True`),
  then every publication member with `is_active = member_id not in segment_ids`
  — base-year `…B<year>` segments are seeded **inactive** so the dashboard shows
  the linked series, not the raw segments.
- Canonical CPI entries carry `has_base_year_changes` and `base_years`
  (existing catalog columns; **no migration**).
- `_persist_publication_sci()` records the persisted series ids on the outcome
  (new `IndicatorOutcome.series_ids` field in `src/etl/pipeline.py`).
- `run_sci_pipeline()` accumulates those ids across every publication and, only
  after the whole batch is persisted, calls `_publish_gold_sci()` once. This is
  the "do not chain-link before all segments exist" gotcha: a canonical whose
  Silver segments are incomplete is reported as failed instead of spliced.
- `_publish_gold_sci()` calls
  `silver_to_gold(..., segment_indicator_ids=[...])` for each canonical, then
  publishes every non-segment series (deciles, unemployment) through the plain
  single-series path. `_update_catalog_range()` refreshes each catalog row's
  `availability_start/end` from the **Gold** rows actually published.
- `IndicatorMetadata.is_active` (`src/connectors/base.py`) and
  `_catalog_values()` (`src/etl/pipeline.py`) carry the flag into the
  `indicator_catalog` upsert (PK = `indicator_id`, so re-seeding is an upsert).

### Deviation — real base years and the 1395 sheet

- SCI publishes only **two** CPI bases (1395=2016, 1400=2021), not the plan's
  assumed `[2011, 2016, 2021]`. Only the urban series has two published
  segments; national/rural carry a single segment and publish as passthrough.
  The canonical `base_years` are therefore `(2016, 2021)` / `(2021,)`.
- `cpi_base1395` now parses the tidy **`جدول 3`** sheet (491 rows,
  1361-01 → 1401-01, earliest `1982-03-31`). The wide `جدول 1` only starts at
  1381 — the same first period as the 1400-base workbooks — so it offered no
  older history and spliced to `records_linked=0`. This **changes the Task 1
  documented coverage** for the 1395 segment (1361–1401 observed, not
  1381–1401), which is recorded in `VALIDATION.md`.

### Files changed (this task)

```text
src/etl/gold.py                  BaseYearSegment + segment linking path
src/etl/silver.py                parser record_metadata propagation; scoped-rows parse
src/etl/pipeline.py              IndicatorOutcome.series_ids; is_active in catalog
src/connectors/base.py           IndicatorMetadata.is_active
src/connectors/sci_scraper.py    canonical registry, discover(), Gold wiring
tests/unit/etl/test_gold.py      +9 multi-segment cases
tests/unit/etl/test_silver.py    +metadata propagation, scoped-rows cases
tests/unit/connectors/test_sci_scraper.py  +canonical/segment/Gold-wiring cases
tests/integration/test_sci_pipeline.py     NEW fixture-driven DB roundtrip
```

### Validation

```text
poetry run pytest -m "not integration" -q            → PASS (590 passed, 86.33% coverage)
poetry run pytest tests/integration/test_sci_pipeline.py -q
                                                     → PASS (13 passed, 1 live-skipped, 88.80% coverage)
poetry run ruff check src tests                      → PASS
poetry run ruff format --check src tests             → PASS
poetry run mypy src                                  → PASS
```

The DB integration suite surfaced a multi-series accounting defect: a SCI
*file* is one Bronze row but may carry several series (the deciles), and
`bronze_to_silver`'s generic future-period delta counted each series' sibling
rows as skipped (10 × 1125 = 11250 false "failed"). `bronze_to_silver()` now
takes an optional `rows` subset and the SCI runner passes the per-series slice,
so `metadata.transformation_log` is accurate (now 0). `src/etl/silver.py` and
`tests/unit/etl/test_silver.py` carry that fix. See `VALIDATION.md` (Task 8).

---

## Task 9 — Weekly SCI Airflow DAG (`airflow/dags/sci_weekly.py`)

Added `sci_weekly`, mirroring `tgju_daily.py`: one `PythonOperator` whose
callable imports `run_sci_pipeline` **inside the function** and calls it with
`dry_run=False`, logs the run, and raises `AirflowException` when any
publication failed so Airflow retries and fires the callback. All pipeline logic
stays in `src/connectors/sci_scraper.py`.

- **Schedule:** `0 3 * * 5` — Fridays 03:00 `Asia/Tehran`. SCI publishes
  monthly, so a weekly check is enough; Friday is the Iranian weekend and 03:00
  is low traffic, satisfying the plan's "low-traffic Tehran time".
- **Retries:** 3 attempts, 5-minute delay, exponential backoff, 30-minute cap —
  the same policy as `tgju_daily`.
- **`on_failure_callback`:** logs `ERROR` per failure and escalates to
  `CRITICAL` once retries are exhausted (alerting integration is still a TODO,
  copied from the TGJU DAG).
- **`catchup=False`, `max_active_runs=1`.**
- **Tags:** `sci`, `scraper`, `weekly`, `cpi`, `unemployment`.

**CBI:** the plan's "(+ cbi if open)" is not implemented — the Task 1/6/7 gate
is closed, so no `cbi_weekly` DAG exists.

**Make target:** none added — TGJU has no DAG-specific `make` target to mirror
(the Makefile only has generic `airflow-*` targets).

### Files changed (this task)

```text
airflow/dags/sci_weekly.py                 NEW weekly SCI DAG
tests/unit/airflow/test_dag_import.py      +10 SCI DAG structure/lazy-import tests
```

### Validation

```text
poetry run pytest tests/unit/airflow/test_dag_import.py -q --no-cov
                                                     → PASS (23 passed; 10 new)
poetry run pytest -m "not integration" -q            → PASS (600 passed, 86.33% coverage)
DagBag('airflow/dags') with an unreachable metadata DB
                                                     → dag_ids include sci_weekly, 0 import errors
poetry run ruff check src tests airflow              → PASS
poetry run ruff format --check src tests airflow     → PASS
poetry run mypy src                                  → PASS
```

The DagBag check runs Airflow's own parser with
`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` pointed at a closed port, demonstrating
the plan's gotcha: DAG parsing opens no database connection.

---

## Task 10 — Documentation (data dictionary, README, AGENTS, phase-5)

Documentation-only task. No source code changed.

- **`docs/phase-2/data_dictionary.md`** — added **`# SCI Indicators (Phase 5)`**
  (provenance, canonical + segment coverage tables, chain-linking section,
  Bronze `{rows, meta}` convention, Silver/Gold rules, known limitations, and
  reproduction commands) and **`# CBI Indicators (Phase 5 — GATED)`**. Every
  coverage figure was read from the database after the live run below, per the
  plan's gotcha.
- **`docs/phase-5/README.md`** — NEW, mirroring `docs/phase-4/README.md`
  (quick links, components, sources, tests, quick start, limitations).
- **`README.md`** — data-source table rows for SCI (✅ implemented) and CBI
  (⛔ deferred); the testing status line (690 tests: 600 unit / 90 integration,
  86 pass + 4 live-skipped); the `docs/` tree; the Phase 5 roadmap section
  (marked complete); and the project-status line.
- **`AGENTS.md`** — connector structure tree now lists
  `sci_scraper.py`/`sci_parser.py` (and `tgju_parser.py`); the lifecycle stage,
  docs tree, Key Files table, and on-demand-context table were brought in line.

### Live run behind the observed numbers

```text
poetry run python -m src.connectors.sci_scraper
→ 6/6 publications, 2,649 Silver rows, 4,639 Gold rows
  SCI.CPI.URBAN         533 levels / 521 YoY   (240 chain-linked)
  SCI.CPI.NATIONAL      185 levels / 173 YoY
  SCI.CPI.RURAL         429 levels / 417 YoY
  SCI.CPI.DECILE.*      125 levels / 113 YoY each (10 series)
  SCI.UNEMPLOYMENT.QUARTERLY  1 level (9.1%, spring 1405)
```

### Finding — `ChainLinkingLog` base years (documented, not fixed)

The observed row for `SCI.CPI.URBAN` records `base_year_from = 2023` and
`base_year_to = 2002` — the splice's overlap-boundary years, produced by
`_splice_once()` from `old.iloc[-1].year` / `new.iloc[0].year` — rather than the
nominal 2016→2021 bases. The catalog `base_years` and the `B2016`/`B2021`
segment ids carry the correct bases. Fixing this is a `src/chain_linking/`
change and therefore **out of scope for a documentation task**; it is flagged in
the data dictionary and `VALIDATION.md` for a follow-up.

### Validation

```text
rg -n "SCI|CBI" docs/phase-2/data_dictionary.md docs/phase-5/   → PASS (see VALIDATION.md)
```

---

## Tasks 11–14 — Remaining tests and final validation

### Task 11 — unit tests / fixtures

- **NEW `tests/unit/utils/test_persian.py`** — 48 direct tests for
  `src/utils/persian.py`: digit normalisation (Persian, Arabic-Indic, mixed,
  all three separators), `parse_price` happy/error paths, `parse_jalali_ymd`
  (slash/dash/dot/space separators, Persian + ASCII digits, time component, UTC
  override, leap year 1403/12/30, non-leap 1404/12/30, invalid month, partial
  input), and `jalali_to_gregorian` (weekday + month name, all 12 month names,
  time, error paths). `src/utils/persian.py` coverage went **35% → 100%**.
- Already present from earlier tasks: `tests/unit/connectors/test_sci_parser.py`,
  `test_sci_scraper.py`, and the multi-segment cases in
  `tests/unit/etl/test_gold.py`.
- Added `"tests/unit/utils/test_persian.py"` to the `pyproject.toml`
  `per-file-ignores` for `RUF001`–`RUF003`, matching the existing Persian
  test-data convention.
- `tests/fixtures/sci/*` and `tests/fixtures/cbi/*` were already committed
  (Task 1).

### Task 12 — integration test

`tests/integration/test_sci_pipeline.py` already existed from Task 8 and passes
against PostgreSQL: 13 passed, 1 live-skipped. No changes needed.

### Task 13 — gated live tests

Added `tests/unit/connectors/test_sci_scraper.py::test_live_sci_fetch_parses_a_real_publication`,
behind `@pytest.mark.live()` + `RUN_LIVE_API_TESTS=1`, downloading the single
smallest publication (labour-force `.xls`, ~370 KB) and asserting parseability
and provenance (never fixed values). The docstring records the rate-limit
posture (1–2 req/sec via `RateLimiter`, permissive `robots.txt`) and the closed
CBI gate. Verified once with `RUN_LIVE_API_TESTS=1`: **1 passed**.

### Task 14 — end-to-end validation

```text
make check                                             → PASS (648 passed, 1 skipped, 86.83% coverage)
poetry run pytest tests/integration -m integration -q --cov-fail-under=0
                                                       → PASS (86 passed, 4 live-skipped)
poetry run alembic check                               → No new upgrade operations detected
poetry run python -m src.connectors.sci_scraper        → 6/6 publications, 2,649 Silver / 4,639 Gold
RUN_LIVE_API_TESTS=1 pytest -m live                    → live SCI fetch + live TGJU/WB/IMF (gated)
poetry run ruff check src tests airflow                → PASS
poetry run ruff format --check src tests airflow       → PASS
poetry run mypy src                                    → PASS
```

### Acceptance-criteria status

| Criterion | Status |
|-----------|--------|
| Task 1 fixtures + `SOURCES.md`; CBI gate decided with evidence | ✅ / ✅ (gate closed, evidence committed) |
| SCI CPI (headline + deciles) and unemployment ingest Bronze → Silver → Gold | ✅ |
| Three base-year CPI segments (2011/2016/2021) chain-link, ≥12 mo overlap, ±1% growth | ⚠️ **Source publishes only 2016 + 2021** (no 1390/2011). Urban links 2016→2021 (251-mo overlap, confidence 0.9985); national/rural are single-base passthroughs. Documented deviation from Task 1 reconnaissance. |
| `chain_linking_log` records method/overlap/variance/confidence; `original_value` + `is_chain_linked` on Gold; Bronze keeps sha256 | ✅ (see the base-year labelling note below) |
| Distinct Silver segment ids; no `(indicator_id, timestamp)` collision | ✅ |
| Silver upsert + Gold refresh idempotent on re-run | ✅ |
| CBI implemented behind gate or deferred with evidence (no bypass) | ✅ deferred with evidence |
| Parser/scraper separation, Persian handling, injected transport, 1–2 req/sec, `robots.txt` | ✅ |
| Unit + integration suites pass; `make check` green; ≥80% coverage | ✅ (86.83%) |
| `alembic check` reports no drift | ✅ |
| Data dictionary + README/AGENTS/docs updated | ✅ |
| No regressions in World Bank / IMF / EIA / TGJU suites | ✅ |

**Known non-blocking defect (documented, not fixed):**
`metadata.chain_linking_log.base_year_from`/`base_year_to` store the splice's
break-bracketing years (2023/2002) rather than the nominal 2016/2021 bases; the
catalog `base_years` and `B2016`/`B2021` segment ids are correct. The acceptance
criterion only requires method/overlap/variance/confidence, all of which are
recorded correctly. The fix belongs in `src/chain_linking/` and is listed as a
follow-up.
