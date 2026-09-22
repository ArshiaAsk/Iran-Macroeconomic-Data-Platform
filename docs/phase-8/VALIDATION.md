# Phase 8 Validation Report — Production Readiness

**Status:** Phase 8 **complete through Wave G**, pending owner acceptance of the
two open owner decisions (branch protection, LICENSE). The fresh-clone
acceptance walkthrough (Task 21) passed on a genuinely fresh clone, and this
record (Task 22) separates **verified in this run** from **not automated in this
run**.

**Plan:** [phase-8-production-readiness.md](../plans/phase-8-production-readiness.md)
· **Wave 0 evidence:** [wave-0-spike.md](wave-0-spike.md)
· **Benchmark baseline:** [benchmarks.json](benchmarks.json)
· **Operations:** [../operations/runbook.md](../operations/runbook.md),
[../operations/troubleshooting.md](../operations/troubleshooting.md),
[../operations/ci.md](../operations/ci.md)

This record mirrors the `docs/phase-7.2/VALIDATION.md` convention: the sections
below are the "verified" record, and the explicit *Not automated in this run*
list is at the end. The **before** column is the Wave 0 baseline
([wave-0-spike.md](wave-0-spike.md) §2–3); the **after** column is the measured
final state at HEAD `544f7be`.

---

## Validated environment

| Component | Version | Evidence |
|---|---|---|
| Date | 2026-09-22 (UTC) | `date -u` |
| Branch | `development` (25 ahead of `origin/development`, unpushed) | `git status -sb` |
| Phase 8 base (pre-change) | `92eff6f` (tag `phase-7.2-complete`) | `git log` |
| Final HEAD | `544f7be` | `git log` |
| Python | 3.12.3 | `poetry run python --version` |
| Poetry | 2.4.1 | `poetry --version` |
| ruff | 0.1.15 | `poetry run ruff --version` |
| mypy | 1.20.2 | `poetry run mypy --version` |
| pytest | 7.4.4 | `poetry run pytest --version` |
| Database image | `timescale/timescaledb:2.28.3-pg15` | `docker compose ps` |
| Running digest | `sha256:6343bdc87ca132c6b53acb26113a6bad1821d188fa39975a745f32ddd9757634` | `docker inspect --format '{{index .RepoDigests 0}}'` |
| TimescaleDB / PostgreSQL | **2.28.3** / **15.18** | `SELECT extversion …`; `SHOW server_version` |
| Local database host port | **5433** (the `.env` override; a system PostgreSQL holds 5432) | `docker compose ps` |

---

## Before / after — Wave 0 baseline vs final measured state

The plan's original assumed numbers are **not** used here; the "before" column is
the Wave 0 baseline and the "after" column is the actual final run.

| Metric | Wave 0 (pre-change `92eff6f`) | Final (`544f7be`) | Delta |
|---|---|---|---|
| Unit suite (`pytest -m "not integration"`) | **1473 passed, 3 skipped, 136 deselected** | **1514 passed, 3 skipped, 136 deselected** | **+41 passed** |
| Integration suite (`pytest -m integration`, live DB) | 132 passed, 4 skipped (136 selected) | 132 passed, 4 skipped (see §Integration) | unchanged |
| Coverage (`--cov=src --cov=dashboard`) | 90% (6806 stmts, 658 missed) | **90.33%** (6806 stmts, 658 missed) | +0.33 pt |
| `mypy src dashboard` | 0 errors / 68 files | **0 errors / 68 files** | unchanged |
| `ruff check .` | clean | clean | unchanged |
| `ruff format --check .` | 165 files | **170 files** | +5 files |
| Tracked files | — | 650 | — |

The unit delta (+41) is the new Phase 8 test suites: `tests/unit/scripts/`
(the health classifier and the benchmark helpers). Coverage's *statement* total
is unchanged because the new CLIs live under `scripts/`, which the coverage set
(`src/` + `dashboard/`) does not measure — the ratio moves only slightly.

Per-package coverage (Wave 0 measurement, unchanged source set): `src/` 89%
(4433/478), `dashboard/` 92% (2373/180); pytest-cov aggregates both into the one
90.33% ratio the 80% gate enforces.

---

## Gate results

### Level 1 — Static / style

```text
poetry run ruff check .              → PASS (clean)
poetry run ruff format --check .     → PASS (170 files already formatted)
poetry run mypy src dashboard        → PASS (0 errors, 68 source files)
```

### Level 2 — Unit tests (coverage gate)

```text
poetry run pytest -m "not integration"  → PASS: 1514 passed, 3 skipped, 136 deselected
                                           coverage 90.33% ≥ 80% gate
poetry run pytest tests/unit/scripts -q --no-cov → PASS
```

`make check` (the local convenience target — `format lint typecheck test`) is
green; note it runs `ruff format .` **in place**, so CI uses
`ruff format --check .` instead (D9).

### Level 3 — Integration tests

Run against the live TimescaleDB 2.28.3 / PostgreSQL 15.18 database:

```text
poetry run pytest -m integration -q --no-cov → PASS: 132 passed, 4 skipped
```

The 4 skips are the `RUN_LIVE_API_TESTS`-gated live-network tests
(`test_{imf,sci,tgju,world_bank}_pipeline.py`) — expected, not a silent green.

### Level 4 — Feature-specific validation

Covered by the sections below (image pin, health check, backup/restore,
benchmarks, fresh clone).

---

## Pinned database image (D11)

```text
timescale/timescaledb:2.28.3-pg15
resolved digest: sha256:6343bdc87ca132c6b53acb26113a6bad1821d188fa39975a745f32ddd9757634
```

- `docker-compose.yml` (`services.postgres.image`) — local development.
- `.github/workflows/ci.yml` (`jobs.integration.services.postgres.image`) — CI.
- `grep -rn "latest-pg15" docker-compose.yml .github/` → **no floating tags**.
- The pinned tag resolves to the digest of the running image (verified in Wave 0
  by pulling the tag and comparing digests — **not** `docker manifest inspect`,
  which is geo-blocked here; see [wave-0-spike.md](wave-0-spike.md) §5).
- Pinning the Compose tag was a no-op for the existing `postgres_data` volume:
  the live database still reports TimescaleDB 2.28.3 / PG 15.18 and 20,074 Gold
  rows after the switch.

---

## CI (GitHub Actions)

The workflow [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) defines
three jobs; check names and local equivalents are in
[ci.md](../operations/ci.md):

| Job | Check name | Runs |
|---|---|---|
| `static` | `Static gates (ruff, mypy)` | `ruff check`, `ruff format --check`, `mypy src dashboard` (Python 3.12) |
| `unit` | `Unit tests (Python 3.11)` / `Unit tests (Python 3.12)` | the unit suite; the 80% coverage gate runs on the 3.12 leg only |
| `integration` | `Integration tests (pinned TimescaleDB)` | the 132 DB-backed tests against the pinned service; **fails if any test skips** |

**Not run on GitHub in this environment.** `gh workflow list` and `gh run list`
are empty: the workflow is committed on `development`, which is 25 commits ahead
of `origin/development` and **not pushed**, so GitHub Actions has never seen it.
There are therefore **no CI run IDs or job results to record**. The three jobs
were reproduced locally (the static and unit jobs by `make check`; the
integration job by the `pytest -m integration` run above), and the workflow
syntax is a single valid file, but a real green run requires a push — an owner
action. Pushing was deliberately not performed (it is a shared-state change and
was not requested).

---

## Monitoring — `scripts/health_check.py`

Read-only. It reuses `DashboardRepository.source_freshness` /
`coverage_summary` and the dashboard's `expected_periods` primitive, so the CLI
and the UI cannot disagree. Measured against the live database:

```text
STATUS    SOURCE         LAST OBSERVED        MISSED  DETAIL
stale     eia            2026-05-31T00:00:00+00:00 3       success
ok        hbsir          2025-03-20T00:00:00+00:00 0       success
ok        imf            2031-12-31T00:00:00+00:00 0       success
stale     sci            2026-07-31T00:00:00+00:00 1       success
stale     tgju           2026-09-11T00:00:00+00:00 10      success
stale     tsetmc         2026-09-16T00:00:00+00:00 2       success
ok        world_bank     2025-12-31T00:00:00+00:00 0       success
totals: 7 sources, 3 ok, 4 warning, 0 failed
```

Exit code **1** (degraded: 4 stale warnings, no failures). `stale` is a warning,
not a failure — a domestic source may legitimately lag its publication cadence.
The classifier is unit-tested in `tests/unit/scripts/` with synthetic frames
(fresh / stale / failed / no-data / trading-session / unsupported-frequency), no
network and no database.

---

## Backup / restore roundtrip

`pg_dump -Fc` (33 MB) followed by `scripts/restore_db.sh` into a scratch
database. The script enforces the documented TimescaleDB order — extension →
`timescaledb_pre_restore()` → `pg_restore` → `timescaledb_post_restore()` — and
never passes `-j`.

```text
Backup written: backups/iran_macro_db_20260922T140416Z.bak
  PostgreSQL 15.18 / TimescaleDB 2.28.3 (pg_dump 15.18)

Row counts in 'iran_macro_restore_test':
bronze.bronze_raw=100
silver.silver_cleaned=8446
gold.gold_analytical=20074
metadata.indicator_catalog=54
metadata.data_collection_log=100
Hypertables in 'iran_macro_restore_test':
gold.gold_analytical
```

All five row counts match the live database exactly and the hypertable survived
the restore (not just the rows). The scratch database was dropped afterwards;
the live database is unchanged (20,074 Gold rows). `backups/` is gitignored.

---

## Performance benchmarks and the committed baseline

`scripts/benchmark_queries.py` runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` on
the dashboard's hot queries. **Index usage is the only hard gate**; timings are
reported and compared, never gated (D7).

**First run — the committed baseline** (`docs/phase-8/benchmarks.json`, commit
`1dc4f8d`, 2026-09-22T13:13:46Z):

| Query | exec ms | plan ms | rows | index |
|---|---|---|---|---|
| `load_series` | 298.980 | 268.814 | 13,882 | yes |
| `coverage_summary` | 414.564 | 155.245 | 82 | yes |
| `source_freshness` | 0.164 | 0.512 | 7 | yes |
| `catalog_read` | 0.111 | 0.375 | 50 | yes |

**Wave G re-run** at `544f7be` (same environment: Python 3.12.3, PG 15.18,
TimescaleDB 2.28.3, identical row counts):

| Query | exec ms | index | delta vs baseline |
|---|---|---|---|
| `load_series` | 240.609 | yes | −58.371 ms (−19.5%) |
| `coverage_summary` | 349.252 | yes | −65.312 ms (−15.8%) |
| `source_freshness` | 0.156 | yes | −0.008 ms (−4.9%) |
| `catalog_read` | 0.114 | yes | +0.003 ms (+2.7%) |

Result: **`OK: index usage intact, no timing regression`**. All four hot queries
use an index; none exceeds the <1 s query budget. A normal run does **not**
modify the tracked baseline (verified: `git status --short` clean after the
re-run).

---

## Fresh-clone acceptance walkthrough (Task 21)

**Method.** A genuinely fresh environment, not a re-run in the warm working tree:
a fresh `git clone` of the committed HEAD `544f7be` into `/tmp/phase8-freshclone2`
(clean tree), a **fresh Poetry virtualenv**, and an **isolated Compose project**
with its own volume, publishing host port **5434** (5432 is held by a system
PostgreSQL, 5433 by the live container). Only the documented README quickstart
was followed. The live `postgres_data` volume was never touched.

**Timing (PRD §14.4 target: < 1 hour).**

| Step | Time |
|---|---|
| `git clone` | ~1 s |
| `poetry install` (warm Poetry cache) | 11 s |
| `cp .env.example .env` | instant |
| `make db-up` (fresh volume) | 5 s |
| `poetry run alembic upgrade head` | 3 s |
| `make check` | 191.58 s |
| `make dashboard` → HTTP 200 / `_stcore/health` `ok` | ~2 s |
| **Total (clone → running dashboard)** | **≈ 4 min 29 s** |

**Result: PASS.** `make check` in the fresh clone reported **1514 passed, 3
skipped, 136 deselected**, coverage **90.33%** — identical to the warm tree. The
dashboard served HTTP 200 and a `ok` health probe.

### Defects found and fixed (Task 21)

The walkthrough's whole purpose is to catch local-state dependencies. It found
one **blocking** reproducibility defect and several documentation errors:

1. **Untracked CSV test fixtures (blocking).** `.gitignore:111` ignores `*.csv`
   globally, and the "captured source fixtures … must be committed" exception
   block un-ignored only `*.xlsx` / `*.xls` — **not `*.csv`**. The two CSV
   fixtures required by committed tests were therefore never committed:
   - `tests/fixtures/hbsir/income_expenditure_weight_1400_sample.csv`
   - `tests/fixtures/tsetmc/tedpix_window_1404-06.csv`

   On a fresh clone `make check` failed with **9 failed, 1505 passed, 3 skipped**
   (`test_hbsir_parser.py` ×6, `test_phase6_fixtures.py` ×3); the fixtures
   existed only in the warm working tree. **Fixed** by adding
   `!tests/fixtures/**/*.csv` to `.gitignore` and committing both fixtures.
   Verified: with the fixtures present the 54 tests in those two files pass, and
   the full fresh-clone `make check` is green (1514 passed).
2. **`.env.example` password mismatch.** The template shipped
   `DATABASE_PASSWORD=your_secure_password_here`, but Compose creates the role
   with `iran_macro_pass`, so the documented `alembic upgrade head` failed with
   `FATAL: password authentication failed for user "iran_macro"`. **Fixed** by
   aligning the template (and `DATABASE_URL` / the Airflow connection string).
3. **README clone URL** was the `yourusername/iran-macro-platform` placeholder.
   **Fixed** to the real repository URL.
4. **Headless `poetry install`** fails with `SecretServiceNotAvailableException`
   (Poetry's keyring cannot reach a D-Bus secret service). Documented:
   `POETRY_KEYRING_ENABLED=false poetry install …`.
5. **Hardcoded `container_name`** in `docker-compose.yml` prevents a second stack
   / clone from starting on the same daemon (name conflict). Documented as a
   limitation (the walkthrough renamed the live container to free the name, then
   restored it).

Corrections 2–5 are folded into `README.md`, `.env.example` and
`docs/operations/troubleshooting.md` (scenarios 15–17).

---

## Acceptance criteria (PRD §13 Task 19/20, §14.4)

| Criterion | Result |
|---|---|
| CI runs on push/PR with static, unit (3.11+3.12), integration jobs | **Workflow committed**; not yet run on GitHub (branch unpushed) — owner action |
| Integration job uses a real TimescaleDB service and fails on skips | **Workflow implements it**; locally reproduced (132 passed, 4 expected live skips) |
| No floating `latest` tag; compose and CI pin the same version | **PASS** — both `2.28.3-pg15`, digest `sha256:6343bdc8…` |
| `make check` typechecks `src/` and `dashboard/` | **PASS** — `mypy src dashboard`, 0 errors / 68 files |
| Coverage over `src/` + `dashboard/` meets the 80% gate | **PASS** — 90.33% aggregated |
| `poetry.lock` committed; CI installs from it | **PASS** — tracked (219 packages) |
| `health_check.py` reports health/freshness and exits non-zero on failed/stale | **PASS** — exit 1 with 4 stale warnings; unit-tested |
| Backup/restore exist, documented, and a tested roundtrip restores all four schemas + hypertable | **PASS** — row counts + `gold.gold_analytical` hypertable verified |
| Benchmarks cover hot queries, report against <1 s, gate on index usage | **PASS** — 4 queries, all index-backed, all <1 s |
| Each benchmark run persisted to `benchmarks.json`; later runs report deltas | **PASS** — baseline at `1dc4f8d`; Wave G delta table above |
| Architecture doc, runbook, troubleshooting (10+ scenarios) | **PASS** — `docs/architecture.md`, `docs/operations/runbook.md`, `docs/operations/troubleshooting.md` (17 scenarios) |
| New developer can set up and run in <1 hour | **PASS** — ≈ 4 min 29 s from clone to dashboard |
| No ETL/schema/migration/presentation behaviour changed | **PASS** — Phase 8 touches tooling/CI/docs only; no `src/`/`alembic/`/`airflow/` logic change |
| `VALIDATION.md` separates verified from not-automated | **this document** |
| No regressions: unit + integration suites pass | **PASS** — 1514 passed / 132 passed |

---

## Not automated in this run

Recorded as open, **not** as verified:

- **A real GitHub Actions run.** The workflow has not executed on GitHub — the
  branch is unpushed. The jobs were reproduced locally; a green remote run and
  its run IDs require a push (owner action).
- **Branch protection / required checks on `main`.** A repository setting, not a
  file; only the owner can enable it ([ci.md](../operations/ci.md)).
- **The pinned image as a GitHub Actions `services:` container.** Verified as an
  image and as a local Compose service; the runner path is proven only by a
  remote CI run.
- **Live-network connectors and the 4 `RUN_LIVE_API_TESTS` integration tests.**
  Gated off by default; not exercised here.
- **The benchmark against a future baseline.** Timings are environment-dependent
  and reported, never gated (D7); only index usage is enforced.
- **A LICENSE.** Still "to be determined" (`README.md`); no `LICENSE` is tracked
  — an owner decision.
- **Phase 7.x deferred items** (cache TTL/manual refresh, Phase 7.1 Tasks 27–28,
  accepted dashboard deviations) and the Phase 7.2 data-correctness items D1/D2
  — unchanged, out of Phase 8 scope (D8).

---

## Open owner items

| Item | Why it is open | Action |
|---|---|---|
| Enable branch protection / required checks | Repository setting | See [ci.md](../operations/ci.md) §Required checks |
| Push the branch and confirm a green CI run | Shared-state action, not performed here | `git push` then `gh run watch` |
| Choose a LICENSE | Owner decision | `README.md` License section |

## Closing checks

- `git status --short` → clean (only intended files committed; `backups/` and
  `htmlcov/` are gitignored).
- No file under `src/`, `alembic/` or `airflow/` changed by Phase 8's Wave G.
- No merge or push is part of this change set.
