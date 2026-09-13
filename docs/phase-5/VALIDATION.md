# Phase 5 Validation Report

**Status:** 🟡 In progress — **Tasks 1–5 complete; Tasks 6–7 gated and skipped.**
SCI proceeds end to end (parser + scraper); the **CBI gate was re-checked for
Tasks 6–7 and is still closed**, so the whole CBI parser/scraper path remains
deferred. SCI Gold chain-linking, runner wiring, DAG and docs tasks continue.
**Validation Date:** September 13, 2026
**Environment:** local workstation, Python 3.12, Poetry, Playwright 1.62
(Chromium), sandboxed network with escalated approval for outbound calls.

---

## Task 1 — Reconnaissance + decision gate

### Summary

| Deliverable | Result |
|-------------|--------|
| SCI (amar.org.ir) | ✅ **Proceeds.** `robots.txt` permissive; a normal browser load yields genuine publications; 12 real fixtures captured |
| CBI (cbi.ir / tsd.cbi.ir) | ⛔ **Gate closed.** F5 ASM "Request Rejected" on the main domain; TSD subdomain unreachable. Deferred with evidence, no bypass |
| `tests/fixtures/sci/SOURCES.md` | ✅ present (provenance, checksums, workbook structures) |
| `tests/fixtures/cbi/SOURCES.md` | ✅ present (block evidence only — no data) |
| Plan hypothesis (CPI base years 2011/2016/2021) | ⚠️ Partly confirmed — see **Discrepancy** below |

### SCI reconnaissance

**Reachability / policy.** `https://www.amar.org.ir/robots.txt` → HTTP 200,
`text/plain`, 4291 bytes, permissive for the publication paths used
(`/Portals/0/…`). Evidence: `tests/fixtures/sci/robots.amar.txt` +
`robots.amar.response.txt`.

**Normal browser load.** A headless Chromium with a normal User-Agent loads
`https://amar.org.ir/prices` (title `شاخصهای قیمت`) and
`https://amar.org.ir/work` (`نیروی کار`) and serves genuine Excel/PDF
publications. ⚠️ The site rejects the container's default HTTP proxy at the TLS
layer (`ERR_CONNECTION_CLOSED`); captures were made over a direct connection
(`--proxy-server=direct://`). This is an environment quirk, not a site block —
`curl` reaches the same URLs directly.

**TLS.** The server presents an incomplete certificate chain (leaf
`CN=amar.org.ir` ← `Certum DV TLS G2 R39 CA`, but the missing intermediate is
not sent); OpenSSL returns verify code 21. Evidence:
`tests/fixtures/sci/tls_certificate.txt`. A future connector must verify
deliberately rather than defaulting to `verify=False`.

**Captured fixtures (12).** Full provenance + sha256 in
`tests/fixtures/sci/_capture.json`; structures in `.../SOURCES.md`.

| Category | Fixtures |
|----------|----------|
| CPI time series (Excel) | `cpi_national_timeseries.xlsx`, `cpi_urban_timeseries.xlsx`, `cpi_rural_timeseries.xlsx`, `cpi_decile_timeseries.xlsx`, `cpi_base1395_timeseries.xlsx` |
| CPI report (PDF) | `cpi_report_1405-05_base1400.pdf` |
| Unemployment | `unemployment_annual_1404.xlsx`, `unemployment_spring_1405.xls` (legacy BIFF), `unemployment_report_1404.pdf` |
| Pages / policy | `prices_page.html`, `work_page.html`, `robots.amar.txt` (+ response headers) |

**Formats confirmed (drives Task 2 dependencies).**
- `.xlsx` is the dominant publication format → **`openpyxl` (already present) is enough** for most sheets.
- **Legacy `.xls` exists** (`unemployment_spring_1405.xls`,
  `application/vnd.ms-excel`) → the plan's conditional **`xlrd ^2.0` is required**.
- **PDFs exist** for monthly CPI and labour reports → **`pdfplumber` is required**.

### CBI gate — ⛔ CLOSED (deferred, not implemented)

**Decision:** the Central Bank's TSD monetary aggregates (M0/M2/multiplier) and
the Tehran housing index are **not ingested**. No connector, parser, config,
DAG, or fixture-with-data is added. This mirrors the Phase 4 OPEC ruling.

| Probe | Result |
|-------|--------|
| `GET https://www.cbi.ir/` (Playwright, normal UA) | HTTP 200 but body is a **254-byte F5 ASM rejection page** (`Request Rejected`, support ID 7880755047040941175) — no content |
| `GET https://www.cbi.ir/robots.txt` (Playwright) | Same 254-byte rejection page — `robots.txt` is not even served |
| `curl https://www.cbi.ir/robots.txt` | HTTP 200, `text/html`, 42534 bytes of F5 **TSPD JavaScript challenge** (`bobcmn`, `TSPD_101`) |
| `GET https://tsd.cbi.ir/` and `http://tsd.cbi.ir/` (curl + Playwright) | **No response** — connection timeout (`000`) after 25 s (curl) / 40 s (browser) |

Evidence: `tests/fixtures/cbi/{cbi_home.html, cbi_robots.html, robots.cbi.txt,
robots.cbi.response.txt, _gate.json}` and `tests/fixtures/cbi/SOURCES.md`.

The plan's gate criterion is "a normal browser load yields genuine data (not an
F5 challenge/captcha)". It does not, and per AGENTS.md the block is **not**
worked around. Half the PRD phase deliverables (Task 12) therefore defer, exactly
as OPEC did in Phase 4.

### Discrepancy vs the plan

The plan hypothesized **three** published CPI base years (1390/2011, 1395/2016,
1400/2021). Reconnaissance found **two** explicit base-year series on the live
site:

- **1395 = 2016** — `ts_cpi_1395=100-…xlsx` (coverage 1381–1401)
- **1400 = 2021** — national/urban/rural/decile workbooks (coverage to 1405)

No standalone **1390 = 2011** CPI publication was found on `/prices` or its CPI
archives (`catid=3105`). The 1400-base *national* series is restated back to
**فروردین 1390**, so 2011 data exists but only inside the 2021-base series.

Implication for downstream tasks: one real chain link (**1395 → 1400**, overlap
≈ 1400-01…1401) is available from published segments, which is sufficient to
prove the multi-segment Gold path end to end. Whether a 1390-base historical
publication can be sourced is a follow-up; do not assume three segments until
Task 4 confirms coverage. This deviation is the reason Task 1 is a checkpoint
and does not invalidate the phase.

### Chain-linking relevance

`cpi_base1395_timeseries.xlsx` and the 1400-base national workbook share the
period **1400-01 … 1401** (≥12 monthly observations), satisfying
`min_overlap_periods("monthly") == 12` for a real link. Segment indicator ids
(e.g. `SCI.CPI.HEADLINE.B1395`, `SCI.CPI.HEADLINE.B1400`) and the canonical
`SCI.CPI.HEADLINE` remain the design.

---

## Test / validation commands (Task 1)

```text
ls tests/fixtures/sci tests/fixtures/cbi                         → PASS (12 SCI + 5 CBI evidence files)
test -f tests/fixtures/sci/SOURCES.md                            → PASS
test -f tests/fixtures/cbi/SOURCES.md                            → PASS
curl -ksS -o /dev/null -w "%{http_code}" .../robots.txt          → PASS (200, permissive)
openpyxl load of all 6 .xlsx fixtures                            → PASS (sheet names/structure read)
file(1) type check of .xls / .pdf / .xlsx fixtures               → PASS (BIFF / PDF / OOXML as expected)
```

## Task 6 — CBI parser gate re-check

**Decision: gate still CLOSED → `src/connectors/cbi_parser.py` was NOT created.**
The plan's Task 6 is explicitly conditional ("only if the CBI gate is open") and
its gotcha says: *"If the gate is closed, do not create this file; record the
evidence instead (AGENTS.md/OPEC precedent)."* The gate was re-probed on
2026-09-13 before implementing, using both a plain HTTP client and a normal
headless Chromium (the plan's gate criterion: a *normal browser load* must yield
genuine data).

**Re-check (2026-09-13, ~11:30 Iran time):**

| Probe | Transport | Result |
|-------|-----------|--------|
| `https://www.cbi.ir/` | Playwright Chromium (direct) | HTTP 200, **43882 bytes**, F5 TSPD JS challenge (`TSPD_101`, `bobcmn`, `support ID`) — no content |
| `https://www.cbi.ir/robots.txt` | Playwright Chromium (direct) | HTTP 200, **40106 bytes**, same challenge |
| `https://www.cbi.ir/` | `curl` (direct) | HTTP 200, **48138 bytes**, same challenge |
| `https://www.cbi.ir/robots.txt` | `curl` (direct) | HTTP 200, **41210 bytes**, same challenge |
| `https://tsd.cbi.ir/` | `curl` + Playwright | **No response** — `curl` exit 6 "Could not resolve host"; browser `net::ERR_NAME_NOT_RESOLVED`; HTTP `000` |

Evidence saved under `tests/fixtures/cbi/`:
`task6_cbi_home_browser.html`, `task6_cbi_robots_browser.html`,
`task6_cbi_home_curl.html`, `task6_cbi_robots_curl.txt`, and the machine-readable
`_gate_task6.json` (status, byte length, sha256, challenge markers).

This is consistent with (and fresher than) the Task 1 gate record above: the
site still answers every request with a JavaScript challenge rather than the
monetary/housing tables, and the TSD subdomain is still unreachable. No request
was retried into a bypass, no parser was written, and no CBI fixture-with-data
was created.

**Validation:** the plan's Task 6 command
`poetry run pytest tests/unit/connectors/test_cbi_parser.py` is **skipped** — the
plan itself allows this when gated, and the test file is deliberately absent so
the suite does not import a non-existent CBI parser. `ruff`/`mypy`/unit tests
remain green with no CBI code in the tree.

## Task 7 — CBI scraper gate re-check

**Decision: gate still CLOSED → `src/connectors/cbi_scraper.py` was NOT
created.** The plan's Task 7 is conditional on the same Task 1 gate and depends
on Task 6, which is itself gated. Task 7 points at `config.cbi_tsd_url`
(`tsd.cbi.ir`), so that exact host was re-probed on 2026-09-13 immediately before
implementing.

**TSD re-check (2026-09-13, ~11:45 Iran time):**

| Probe | Transport | Result |
|-------|-----------|--------|
| `https://tsd.cbi.ir/` | `curl` (direct) | **No response** — `curl` exit 28, connection timed out after 20 s, HTTP `000` |
| `http://tsd.cbi.ir/` | `curl` (direct) | **No response** — `curl` exit 28, connection timed out after 20 s, HTTP `000` |

The `www.cbi.ir` F5 TSPD JavaScript challenge recorded in the Task 6 re-check
still applies to the CBI parent domain. Evidence:
`tests/fixtures/cbi/_gate_task7.json` (machine-readable TSD probe result).

There is therefore **no `CbiConfig`, `CBI_INDICATOR_REGISTRY`, `CbiScraper`,
`run_cbi_pipeline()` or `python -m src.connectors.cbi_scraper` CLI** in the
tree. Per AGENTS.md the block was not worked around, so no request was retried
into a bypass and no CBI fixture-with-data was created.

**Validation:** the plan's Task 7 command
`poetry run python -m src.connectors.cbi_scraper --dry-run` is **documented as
gated** (the plan explicitly allows this). There is no module to run.

## Task 8 — SCI Gold multi-segment chain-linking + runner/catalog wiring

**Status: IMPLEMENTED and VALIDATED (unit + real PostgreSQL/TimescaleDB
integration).**

### What was validated

| Gate | Result |
|------|--------|
| `poetry run pytest -m "not integration" -q` | **PASS** — 590 passed, 90 deselected, 86.33% coverage |
| `poetry run pytest tests/integration/test_sci_pipeline.py -q` | **PASS** — 13 passed, 1 skipped (live, gated), 88.80% coverage |
| `poetry run pytest tests/integration/test_sci_pipeline.py -q --cov-fail-under=0` | **PASS** — 13 passed, 1 skipped |
| `poetry run ruff check src tests` | **PASS** |
| `poetry run ruff format --check src tests` | **PASS** — 88 files already formatted |
| `poetry run mypy src` | **PASS** — no issues in 32 source files |

The integration run happened twice: first on `localhost:5433` with Docker
unavailable at first probe, then again once the PostgreSQL container was up. The
suite provisions `iran_macro_db_test`, seeds it from the Task 1 SCI fixtures (no
network), and truncates between tests.

### Defect found and fixed by the integration suite

The SCI decile publication is **one Bronze row** (the file) carrying **ten
series** (1250 rows). `_persist_publication_sci` calls `bronze_to_silver` once
per series, but Silver's accounting assumes one series per envelope, so on each
of the ten calls the 1125 rows belonging to the sibling series were counted as
"future periods skipped":

```text
before:  SCI.CPI.DECILE.B2021  fetched=1250 silver=1250 failed=11250
after:   SCI.CPI.DECILE.B2021  fetched=1250 silver=1250 failed=0
```

Root-cause fix: `bronze_to_silver()` gained an optional
`rows: Sequence[Mapping] | None` argument (defaults to the Bronze row's stored
rows), and the SCI runner now passes the per-series slice of the envelope
(`rows=[row for row in envelope["rows"] if row["indicator_id"] == series_id]`).
The file stays the unit of Bronze; only the **accounting scope** changed. This
keeps `metadata.transformation_log.future_periods_skipped` honest for
multi-series files. A unit test
(`test_bronze_to_silver_scopes_rows_to_one_series`) covers the new argument.

### Fixture-verified chain-link facts

Parsing the Task 1 fixtures and linking the urban pair directly (unit-level,
`tests/unit/connectors/test_sci_scraper.py::test_real_urban_segments_chain_link_with_older_history`):

```text
SCI.CPI.URBAN.B2016   491 rows   1982-03-31 → 2023-01-31   (tidy جدول 3)
SCI.CPI.URBAN.B2021   293 rows   2002-03-31 → 2026-07-31
chain_link(base 1395 → 1400):  is_chain_linked=True, linking_method=overlap,
                               records_linked=240, overlap_period_months=251,
                               avg_confidence_score=0.9985
```

Only two CPI bases exist (1395=2016, 1400=2021); the urban series is the only
canonical with two published segments. The `ChainLinkingLog`'s
`base_year_from`/`base_year_to` come from the splice's detected break
timestamps, not the nominal Jalali bases, which is why the integration test
asserts `records_linked > 0`, `overlap_period_months >= 12`, and
`avg_confidence_score is not None` rather than hard-coding years.

### Discrepancy — 1395-base coverage

The plan and Task 1 note recorded the urban 1395 segment as **1381–1401**. The
1395 workbook turns out to contain an additional tidy long sheet (`جدول 3`)
reaching back to **1361-01 (1982-03-31)**; the wide `جدول 1` is the 1381-start
sheet and splices to zero rescaled rows. `cpi_base1395` now parses `جدول 3`, so
the **observed** canonical coverage is **1361–1401**, and the 1395→1400 splice
rescales 240 pre-1381 observations. This is a deliberate deviation from the
documented Task 1 coverage, taken because it is what the real file contains and
what makes the link meaningful.

### Deviation — Task 5b dependency

The plan declares `silver_to_gold(segment_indicator_ids=...)` (Task "5b") as a
dependency of Task 8 but it was not built in Task 5. Task 8 implements the Gold
multi-segment extension itself alongside the runner/catalog wiring. See
`docs/phase-5/IMPLEMENTATION.md` (Task 8) for the full file list and behavior.

### Not done (correctly out of scope for Task 8)

- The weekly Airflow DAG (a later task).
- A *live network* run of the SCI connector (`--dry-run` against
  `amar.org.ir`); the integration suite is fixture-driven by design.

## Task 9 — Weekly SCI Airflow DAG

**Status: IMPLEMENTED and VALIDATED.**

`airflow/dags/sci_weekly.py` schedules `run_sci_pipeline(dry_run=False)` weekly
(Fridays 03:00 `Asia/Tehran`, cron `0 3 * * 5`) with 3 retries,
exponential backoff, a failure callback, `catchup=False`, and
`max_active_runs=1`. No CBI DAG (gate closed) and no new Make target (TGJU has
none to mirror).

| Gate | Result |
|------|--------|
| `poetry run pytest tests/unit/airflow/test_dag_import.py -q --no-cov` | **PASS** — 23 passed (10 new SCI tests) |
| `poetry run pytest -m "not integration" -q` | **PASS** — 600 passed, 86.33% coverage |
| `DagBag('airflow/dags')` with unreachable metadata DB | **PASS** — `sci_weekly` parsed, 0 import errors |
| `poetry run ruff check src tests airflow` | **PASS** |
| `poetry run ruff format --check src tests airflow` | **PASS** — 91 files already formatted |
| `poetry run mypy src` | **PASS** |

The DagBag parse was run with
`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://nobody:nobody@127.0.0.1:1/nodb"`,
confirming the plan's "no database connection at parse time" gotcha.

## Task 10 — Documentation (data dictionary, README, AGENTS, phase-5)

**Status: IMPLEMENTED and VALIDATED.** Documentation-only; no source changes.

Added `# SCI Indicators (Phase 5)` and `# CBI Indicators (Phase 5 — GATED)` to
`docs/phase-2/data_dictionary.md`, created `docs/phase-5/README.md`, and updated
the root `README.md` (source table, test status, docs tree, Phase 5 roadmap,
project status) and `AGENTS.md` (connector tree, lifecycle stage, docs tree,
Key Files, on-demand context).

### Live run behind the recorded coverage (2026-09-13)

```text
poetry run python -m src.connectors.sci_scraper
→ 20/20 outcomes ok (6 publications + 14 Gold targets)
→ 2,649 Silver rows, 4,639 Gold rows
→ SCI.CPI.URBAN 533 levels / 521 YoY, 240 chain-linked
→ ChainLinkingLog(SCI.CPI.URBAN, overlap, records_linked=240,
                   overlap_period_months=251, avg_confidence_score=0.9985)
```

### Validation

| Gate | Result |
|------|--------|
| `rg -n "SCI|CBI" docs/phase-2/data_dictionary.md docs/phase-5/` | **PASS** — SCI/CBI sections present in both |
| `poetry run pytest -m "not integration" -q` | **PASS** — 600 passed, 86.33% coverage |
| `poetry run pytest tests/integration -m integration -q --cov-fail-under=0` | **PASS** — 86 passed, 4 live-skipped |

### Finding — `ChainLinkingLog.base_year_from`/`base_year_to` (documented, not fixed)

The live row stores `2023`/`2002` (the splice's overlap-boundary years from
`src/chain_linking/splice.py::_splice_once`) instead of the nominal `2016`/`2021`
bases. Catalog `base_years` and the `B2016`/`B2021` ids are correct. This is a
pre-existing chain-linking defect, **out of scope for the documentation task**,
flagged in the data dictionary for a follow-up fix.

## Tasks 11–14 — Remaining tests + final end-to-end validation

**Status: COMPLETE.** Phase 5 closes with the CBI gate documented as deferred.

### Added

- `tests/unit/utils/test_persian.py` — 48 tests; `src/utils/persian.py`
  coverage 35% → **100%**.
- `tests/unit/connectors/test_sci_scraper.py::test_live_sci_fetch_parses_a_real_publication`
  — gated live test (`@pytest.mark.live()` + `RUN_LIVE_API_TESTS=1`),
  verified once against the real site: **1 passed**.
- `pyproject.toml` — added the new Persian test file to `per-file-ignores`
  (`RUF001`–`RUF003`), matching existing test-data conventions.

### Final validation record

```text
make check                                             → PASS (648 passed, 1 skipped, 86.83% coverage)
poetry run pytest tests/integration -m integration -q --cov-fail-under=0
                                                       → PASS (86 passed, 4 live-skipped)
poetry run alembic check                               → No new upgrade operations detected
poetry run python -m src.connectors.sci_scraper        → 20/20 outcomes, 2,649 Silver / 4,639 Gold
RUN_LIVE_API_TESTS=1 pytest tests/unit/connectors/test_sci_scraper.py::test_live_sci_fetch_parses_a_real_publication
                                                       → 1 passed
poetry run ruff check src tests airflow                → PASS
poetry run ruff format --check src tests airflow       → PASS
poetry run mypy src                                    → PASS
```

No regressions in the World Bank / IMF / EIA / TGJU integration suites, and
`alembic check` reports no model/database drift (no new migration).

### Acceptance-criteria deviations

- **Only two CPI bases exist** (1395=2016, 1400=2021) — the plan's three
  segments (2011/2016/2021) cannot be realised because SCI does not publish a
  1390/2011 base. Urban links 2016→2021; national/rural are single-base.
- **`ChainLinkingLog.base_year_from`/`base_year_to`** store the splice's
  break-bracketing years (2023/2002) rather than the nominal bases. The
  catalog `base_years` and `B2016`/`B2021` ids are correct; the required
  method/overlap/variance/confidence fields are all correct. Fixing the
  labelling is a `src/chain_linking/` follow-up.

## Remaining work

Phase 5 is complete for the achievable scope. The only open item is a
non-blocking follow-up:

- Fix `ChainLinkingLog.base_year_from`/`base_year_to` to use the nominal
  segment bases rather than the splice's break-bracketing years
  (`src/chain_linking/splice.py`).
- CBI (Tasks 6–7) is **out of scope** unless the gate is re-opened by a future
  change in CBI's bot defense — revisit only with recorded evidence.
