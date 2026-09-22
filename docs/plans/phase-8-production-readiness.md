# Task: Phase 8 — Production Readiness (Documentation, CI/CD, Monitoring, Backup, Performance)

## Review outcome

This plan implements `PRD.md` §13 (Task 19 — Comprehensive Documentation; Task 20 —
Testing, Monitoring, and CI/CD) and the Phase 8 deliverables in §16
(comprehensive documentation and runbooks; 80%+ coverage with CI/CD; monitoring
and backup procedures). Task numbers below are **phase-local** (1–22), matching
the Phase 7.1/7.2 plan convention; the PRD mapping is Task 19 → Wave F, Task 20 →
Waves A–E + G.

Every fact marked **verified now** was checked against the working tree, the
installed toolchain, or a real command run during planning, and cites its
evidence.

### Verified in the codebase (evidence for the above)

- **The gate does not typecheck the dashboard.** `Makefile:19` is
  `poetry run mypy src/`. `poetry run mypy src dashboard` **verified now**:
  `Success: no issues found in 68 source files`. `make check`
  (`Makefile:41` = `format lint typecheck test`) therefore passes with an
  unchecked 68-file dashboard.
- **The format gate mutates the tree.** `Makefile:13` is
  `poetry run ruff format .` (in place). `poetry run ruff format --check .`
  **verified now**: `165 files already formatted` — so a non-mutating check
  exists and is currently clean.
- **Coverage measures `src/` only.** `pyproject.toml:165` is `--cov=src` and
  `pyproject.toml:168` is `--cov-fail-under=80`; `dashboard/` is not measured.
- **Widening the coverage gate is safe, and was measured rather than assumed.**
  `poetry run pytest -m "not integration" --cov=src --cov=dashboard
  --cov-fail-under=0` **verified now**: `TOTAL 6806 658 90%`; `src/` alone is
  4433 / 478 = **89%** and `dashboard/` alone is 2373 / 180 = **92%**. pytest-cov
  reports a single ratio over the union of measured statements, so the combined
  figure is 90% — comfortably above the 80% gate. (README's "89.22%" is
  consistent with the `src/`-only figure.)
- **Baseline is green and larger than the README claims.**
  `poetry run pytest -m "not integration" -q --no-cov` **verified now**:
  `1473 passed, 3 skipped, 136 deselected in 81.07s`. `README.md:337` still
  says "1,141 unit tests passing … at 89.22% coverage".
- **`poetry.lock` is git-ignored.** `.gitignore:37`. Only `pyproject.toml` is
  committed, so a CI install is not reproducible from the lock graph.
- **The unit suite requires the `airflow` extra.**
  `tests/unit/airflow/test_dag_import.py` imports the DAG modules directly (no
  `pytest.importorskip`), and those import `airflow`. The optional extras
  (`finpy_tse`, `hbsir`) *do* guard themselves with `pytest.mark.skipif`
  (`tests/unit/connectors/test_tsetmc.py:647`,
  `tests/unit/connectors/test_hbsir.py:530`). **Verified now** in the dev venv:
  `airflow 3.3.1`, `finpy_tse` and `hbsir` importable.
- **Integration tests skip silently without a database.**
  `tests/integration/test_database.py:53` calls `pytest.skip` when PostgreSQL is
  unreachable, so a CI integration job without a service would be **green while
  testing nothing**.
- **Alembic takes its URL from `.env`.** `alembic/env.py:22` sets
  `sqlalchemy.url` from `get_config().database.url`, so CI must set the
  `DATABASE_*` variables rather than rely on a checked-in `.env`.
- **The database service and its healthcheck exist, but the image floats.**
  `docker-compose.yml`: service `postgres`, image
  `timescale/timescaledb:latest-pg15` (a **floating tag**), healthcheck
  `pg_isready -U iran_macro -d iran_macro_db`, named volume `postgres_data`,
  host port `${DATABASE_PORT:-5432}:5432`. **Verified now**: the container is
  running and healthy on host port **5433** (the local `.env` overrides the
  default), reporting **TimescaleDB 2.28.3 on PostgreSQL 15.18**, and the image
  resolves to the digest
  `sha256:6343bdc87ca132c6b53acb26113a6bad1821d188fa39975a745f32ddd9757634`.
  The pinned tag `timescale/timescaledb:2.28.3-pg15` **verified now to exist**
  (`docker manifest inspect`), so a concrete pin is available (D11).
- **The schemas and extension are created by `scripts/init-db.sql`**
  (`CREATE EXTENSION timescaledb` + `bronze`/`silver`/`gold`/`metadata`), and the
  hypertable + compression policy by
  `src/database/connection.py:84-129` (`create_hypertable`,
  `add_compression_policy`).
- **The monitoring data already exists and is already queried.**
  `dashboard/repository.py:296-323` (`source_freshness`, from
  `metadata.data_collection_log`), `dashboard/repository.py:206-240`
  (`coverage_summary`), `dashboard/components/quality.py:281`
  (`expected_periods` — the frequency-aware expectation primitive), and
  `src/etl/lineage.py` (`metadata.transformation_log`).
- **Failure surfacing already has a pattern.** `airflow/dags/tgju_daily.py:53`
  (`_on_failure_callback`) logs structured failure context and escalates at
  exhausted retries; `airflow/dags/tgju_daily.py:42` raises so Airflow marks the
  task failed.
- **The toolchain versions verified now:** Poetry 2.4.1, Python 3.12.3 (only
  3.12 present locally), ruff 0.1.15, mypy 1.20.2, pytest 7.4.4. `gh` CLI is
  installed; `origin` is `https://github.com/ArshiaAsk/Iran-Macroeconomic-Data-Platform.git`.
- **No CI exists.** There is no `.github/` directory and no CI configuration of
  any kind in the tree.
- **Documentation drift confirmed:** `README.md:89` instructs
  `cp .env.template .env` but the tracked file is `.env.example`;
  `README.md:337` carries the stale test count; `README.md:439` still marks
  "Phase 2 … (Current)"; `AGENTS.md:107-117` and `README.md:228-239` list `docs/`
  only through `phase-7.1`.

### Corrected during planning (discovery leads that did not survive verification)

- "The unit suite cannot run without optional extras" is **only half true**: the
  TSETMC/HBSIR tests skip gracefully, but the **Airflow DAG tests do not** — the
  requirement is specifically the `airflow` extra, not "all extras".
- "`make check` is the CI gate" does **not** survive: `make check` runs
  `ruff format .` in place, so using it in CI would mutate the checkout and hide
  formatting drift. CI needs `ruff format --check` (D9).
- "Only the CI service image needs pinning" does **not** survive: the same
  floating `latest-pg15` tag is in `docker-compose.yml`, so pinning CI alone
  would leave local and CI able to diverge. Both are pinned to one version
  (D11). The pinned tag was verified to exist and to match the running
  extension (2.28.3 / PG 15.18).
- "A timing number is a benchmark result" does **not** survive: an unpersisted
  timing cannot be compared to anything, so the benchmark writes a committed
  baseline and reports deltas (D7).
- "Adding `--cov=dashboard` can only raise the combined total" does **not**
  survive: pytest-cov aggregates all `--cov` sources into one
  covered ÷ total ratio, so a second, less-covered source would *lower* it. The
  number was therefore measured before deciding: `dashboard/` is 92%, above
  `src/`'s 89%, giving a combined 90% — the gate can be widened (D3).
- "`dashboard/` coverage is probably below `src/`'s because it was never
  measured" does **not** survive either: the dashboard's 2373 statements are
  92% covered, largely by `tests/unit/dashboard/` (38 test files).
- "`--no-cov` can be combined with `--cov` to produce a coverage report" does
  **not** survive: `--no-cov` disables coverage outright and wins over any
  `--cov` (verified — it emits `CovDisabledWarning` and collects nothing). A
  report-only run must instead clear `addopts` and pass the sources explicitly
  (`-o addopts="" --cov=dashboard --cov-report=term --cov-fail-under=0`).
- The TimescaleDB backup documentation URL previously recorded in the tree no
  longer resolves; the procedure is re-verified against the current mirror and
  PostgreSQL's own `pg_dump`/`pg_restore` pages (see External Documentation).

---

## Task Description

Phases 1–7.2 built a working local platform: a multi-source ETL into
PostgreSQL/TimescaleDB, four Airflow DAGs, and a ten-page Persian/RTL dashboard.
What does **not** exist yet is the operational scaffolding that makes the
platform maintainable and trustworthy by someone other than its author:

- No automated quality gate on commit — every gate is a local `make` target.
- No monitoring of scraper health or data freshness outside the dashboard.
- No backup or restore procedure for the single database that holds all
  bronze/silver/gold data.
- No performance evidence that the dashboard's hot queries meet the PRD's
  stated budgets (<1 s query, <3 s dashboard load), and no baseline to compare
  a future run against.
- A database image pinned to a **floating `latest` tag**, so local and CI can
  silently diverge.
- Documentation that a new developer can follow end-to-end, with a
  troubleshooting guide and an operational runbook.
- A gate that silently under-covers: `make check` does not typecheck
  `dashboard/`, and coverage measures `src/` only.

Phase 8 closes that gap. It is **tooling, CI, operations and documentation** —
it does not add data sources, change ETL behaviour, or touch the dashboard's
presentation.

```text
As an analyst/maintainer of this platform
I want automated gates, health checks, backups and a runbook
So that the platform can be trusted, restored and handed over without the author
```

**Type:** New Capability (operational tooling + CI) with a small Enhancement
component (closing two gate gaps). **Not** a data or ML change.

---

## Scope

### In Scope

- [ ] **CI/CD** — GitHub Actions: static gates, unit tests (Python 3.11 + 3.12),
      integration tests against a **pinned** TimescaleDB service container.
- [ ] **Pinned database image** — replace the floating
      `timescale/timescaledb:latest-pg15` tag with a pinned version in both
      `docker-compose.yml` and the CI service definition (D11).
- [ ] **Quality-gate closure** — widen `make typecheck` to `mypy src dashboard`;
      add a non-mutating `format-check` target; extend the measured coverage set
      to `src/` + `dashboard/` (D3).
- [ ] **Reproducible installs** — commit `poetry.lock`.
- [ ] **Monitoring** — a `scripts/health_check.py` CLI (scraper health + data
      freshness + transformation failures) that exits non-zero, reusing the
      existing repository/quality queries.
- [ ] **Backup & restore** — `pg_dump`/`pg_restore` scripts for the
      TimescaleDB database, Makefile targets, and a **tested** roundtrip.
- [ ] **Performance benchmarks** — a script that runs `EXPLAIN ANALYZE` on the
      dashboard's hot queries, asserts index usage, reports timings against the
      PRD budgets, and **persists each run to a committed
      `docs/phase-8/benchmarks.json` baseline so later runs can be compared and
      regressions highlighted** (D7).
- [ ] **Documentation** — architecture/data-flow document, operational runbook,
      troubleshooting guide (10+ scenarios), and corrections to existing drift.
- [ ] **Acceptance** — a fresh-clone walkthrough and a `docs/phase-8/VALIDATION.md`
      record.

### Out of Scope

- [ ] **Any ETL, connector, schema or Alembic behaviour change.** Phase 8 adds
      no migration and no `src/` logic change beyond what a gate/script needs.
- [ ] **D1 / D2 from Phase 7.2's Deferred Scope** — the TGJU declared-vs-observed
      coverage window and SCI rows with declared coverage but no Gold
      observations. These are data-correctness items requiring live data and a
      new collection run; they remain recorded, not fixed here (D8).
- [ ] **IMF forecast-vs-actual labeling** — an ETL change, carried from 7.1/7.2.
- [ ] **New dashboard pages or presentation changes** — the Phase 7.2 D11
      contract and the `src/`+`alembic/`+`airflow/` boundary for presentation work
      are untouched. The monitoring surface is a script, not a new page (D5).
- [ ] **Cloud/remote deployment, Docker registry publishing, Kubernetes.**
      AGENTS.md's local-only deployment constraint holds; CI tests, it does not
      deploy (D1).
- [ ] **Alerting integrations** (email/Slack/Telegram) — PRD §17.1 post-MVP.
      The health script is exit-code based so a future alerting layer can wrap
      it.
- [ ] **Dark mode, cache-TTL/refresh control, per-page `page_view.py` split** —
      Phase 7.x deferred items, unchanged.
- [ ] **A LICENSE.** `README.md:518` says "To be determined — see LICENSE file"
      and no `LICENSE` is tracked. Choosing a licence is an owner decision, not
      an engineering task; recorded as an open item (NOTES).

---

## Context

### Current state (observed)

| Area | Today |
|---|---|
| CI/CD | None. No `.github/`. All gates are local `make` targets. |
| Static gates | `make format` (mutating), `make lint` (`ruff check`), `make typecheck` (`mypy src/` — **dashboard excluded**). |
| Tests | `make test` = `pytest -m "not integration"` with `--cov=src --cov-fail-under=80`. **Verified now: 1473 passed, 3 skipped, 136 deselected, 81 s.** |
| Integration tests | 136 deselected; skip silently when PostgreSQL is unreachable (`tests/integration/test_database.py:53`). |
| Reproducibility | `poetry.lock` git-ignored (`.gitignore:37`). |
| Monitoring | Dashboard only: `source_freshness()` (`repository.py:296`), `coverage_summary()` (`repository.py:206`), `expected_periods()` (`quality.py:281`), `data_collection_log` / `transformation_log` tables. No CLI, no exit code. |
| Backup | None. One named Docker volume (`postgres_data`) holds everything. |
| Performance | No benchmarks and no persisted baseline. PRD §14.1 states query <1 s and dashboard <3 s; PRD §14.3 states query plans must show index usage. |
| Database image | `docker-compose.yml` uses the floating `timescale/timescaledb:latest-pg15` tag; running 2.28.3 / PG 15.18. No pinned version anywhere. |
| Docs | Rich per-phase `docs/phase-*` records, but no single architecture doc, no runbook, no troubleshooting guide; `README.md` has drifted (`.env.template`, stale counts, stale roadmap). |

### Decisions taken (D1–D11)

| # | Decision | Rationale |
|---|---|---|
| **D1** | **CI is GitHub Actions, tests only.** No deployment, no registry, no cloud services beyond the runner. | The PRD (§13 Task 20) explicitly asks for GitHub Actions. AGENTS.md's "local-only deployment" constraint governs *where the platform runs*, not *where its tests run*; CI does not deploy. |
| **D2** | **Commit `poetry.lock`** (remove `.gitignore:37`). | CI must install a reproducible dependency graph. This **reverses** the Phase 7.2 note that the lock is intentionally not committed; the reversal is required by the new CI deliverable and is recorded here rather than done silently. |
| **D3** | **Keep the 80% threshold; extend the measured set to `src/` + `dashboard/`.** `--cov-fail-under=80` is unchanged; `--cov=dashboard` joins `--cov=src` in `addopts`. If the combined ratio ever falls below 80, scope the gate back to `--cov=src` and report `dashboard` from a separate non-gating run — the threshold is never lowered. | pytest-cov reports one aggregated ratio over all `--cov` sources, so widening the set can lower it — the dashboard cannot be added blind. It was measured first: combined **90%**, `src/` 89%, `dashboard/` 92%, so the gate is safe to widen. The fallback keeps the project's stated criterion (PRD §14.3) intact if that ever changes. |
| **D4** | **Widen `make typecheck` to `mypy src dashboard`.** | `mypy src dashboard` already passes on 68 files **verified now**; `make check` currently under-reports. This is a gate bug, not a feature. |
| **D5** | **Monitoring is a CLI script; the dashboard's freshness view stays the human surface.** | PRD asks for "monitoring scripts" and a "monitoring dashboard". The dashboard already shows per-source freshness; adding a *page* would re-open presentation work under the Phase 7.2 boundary for no gain. A script is cron/Airflow-friendly and testable. |
| **D6** | **Backups are local, `pg_dump -Fc`, gitignored, with `timescaledb_pre_restore()`/`timescaledb_post_restore()` on restore and no `-j`.** | The officially documented TimescaleDB procedure (see External Documentation). `-j` cannot correctly restore the TimescaleDB catalog. Local-only per AGENTS.md — no object storage. |
| **D7** | **Benchmarks persist every run to a committed baseline; index usage is the only hard gate.** `scripts/benchmark_queries.py` writes `docs/phase-8/benchmarks.json` (append/replace per run, keyed by commit) and, on a normal run, compares against the stored baseline and highlights significant regressions (default: execution time >25% slower, or index usage lost). Index usage is the sole non-zero exit condition; timing regressions are reported and summarised, and become fatal only with `--fail-on-regression`. | Wall-clock thresholds are environment-dependent and flaky on shared CI runners, so they cannot gate. But without persistence a timing number is unactionable — a committed baseline makes "slower than last time" a first-class, reviewable signal. |
| **D8** | **D1/D2 (TGJU coverage window, SCI missing Gold) stay out of Phase 8.** | Data-correctness findings needing live data and a new collection run; mixing them into a tooling phase would obscure both. They remain in the Phase 7.2 Deferred Scope list. |
| **D9** | **CI runs `ruff format --check .`, never `make check`.** | `make check` runs `ruff format .` in place (`Makefile:13`), which would mutate the CI checkout and could mask drift. Local `make check` is unchanged. |
| **D10** | **Python matrix = 3.11 and 3.12; static gates run once on 3.12.** | `pyproject.toml:10` allows `>=3.11,<3.13`. A full static run per version costs runner minutes for no additional signal; tests are the version-sensitive part. |
| **D11** | **Pin the TimescaleDB image; no floating tags.** Use `timescale/timescaledb:2.28.3-pg15` (the version the platform is validated against) in **both** `docker-compose.yml` and the CI `services:` block. Record the resolved digest alongside it. | `latest-pg15` silently moves, so local, CI and any future environment can diverge — and a TimescaleDB minor upgrade changes extension behaviour and the dump/restore contract. A floating tag also makes a "works locally, fails in CI" report unfalsifiable. The pinned tag is **verified now to exist**, and matches the running extension (2.28.3 / PG 15.18). |

### Assumptions to verify in Task 1 (Wave 0)

- GitHub Actions minutes/permissions are available for this repository and the
  owner accepts adding `.github/workflows/`.
- The pinned `timescale/timescaledb:2.28.3-pg15` image works as a GitHub Actions
  `services:` container, and pinning it does not break the existing local volume
  (the running container is already 2.28.3, so the pin should be a no-op locally
  — confirm before switching the compose tag).
- The owner accepts pinning `docker-compose.yml` to the same version as CI (D11).
- `pg_dump`/`pg_restore` are present in that image (they ship with the
  PostgreSQL client, which the image includes) and the `iran_macro` role can
  dump the database.
- The 136 integration tests all pass against a fresh database (README claims 128
  pass / 4 live skipped; the count has drifted and must be re-measured). **Task 1
  finding:** `alembic upgrade head` alone **cannot** create a fresh database — no
  migration contains `CREATE SCHEMA`, so it fails with `InvalidSchemaName: schema
  "bronze" does not exist`. The schemas come from `scripts/init-db.sql`, which
  only runs on a container's first init; the CI integration job must apply it
  before migrating (Task 8).
- The owner accepts committing `poetry.lock` (D2).

---

## Proposed Approach

Five concerns, one wave each, ordered so later waves can be verified by earlier
ones:

1. **Close the gate gaps first (Wave A).** Widen typecheck, add `format-check`,
   commit the lock. This makes the CI definition in Wave B trivially correct
   because each command has already been run by hand.
2. **CI (Wave B).** A single workflow, three jobs (static, unit matrix,
   integration). The integration job is the only one that needs a service; it
   must **fail if the tests skip** so a missing database cannot masquerade as a
   pass.
3. **Monitoring (Wave C).** One script that answers "is the platform healthy?"
   from the metadata layer plus Gold freshness, reusing the repository queries
   and the `expected_periods` primitive rather than re-deriving staleness rules.
4. **Backup/restore and benchmarks (Waves D–E).** Local operational scripts,
   following the documented TimescaleDB procedure and the PRD's performance
   budgets. The benchmark run writes a committed baseline so a timing is
   comparable rather than merely recorded.
5. **Documentation and acceptance (Waves F–G).** Write the docs against the
   behaviour the previous waves made observable, then prove the whole thing from
   a fresh clone.

Nothing here changes what the ETL writes. Every script is a **reader** (health,
benchmarks) or an **operator** (backup/restore) of existing state.

### Milestones

| Wave | Delivers | Gate to leave the wave |
|---|---|---|
| 0 | Verification spike + baseline | Baseline recorded in `docs/phase-8/VALIDATION.md`; assumptions resolved |
| A | Gate closure (typecheck, format-check, lock, coverage gate) | `make check` green; `mypy src dashboard` in the gate; combined coverage ≥80% |
| B | GitHub Actions workflow + pinned database image | Workflow green on a PR; integration job fails when the service is absent; no `latest` tag remains in CI or compose |
| C | `scripts/health_check.py` | Script exits 0 on a healthy DB, non-zero on a stale/failed source; unit-tested |
| D | Backup/restore scripts + targets | Roundtrip restore verified into a scratch database |
| E | `scripts/benchmark_queries.py` + committed baseline | Writes `docs/phase-8/benchmarks.json`; asserts index usage; reports deltas vs the previous baseline |
| F | Architecture doc, runbook, troubleshooting, drift fixes | Docs match the tree; no broken links |
| G | Fresh-clone acceptance + validation record | A new developer reaches a running dashboard in <1 hour |

---

## Task Metadata

**Type:** New Capability (CI/CD, monitoring, backup, benchmarks) + Enhancement (gate closure)
**Complexity:** High — five independent concerns, one of which (CI) has never existed in this repo
**Affected Areas:** `.github/`, `Makefile`, `pyproject.toml`, `.gitignore`, `docker-compose.yml`, `scripts/`, `docs/`, `README.md`, `AGENTS.md`
**Dependencies:** GitHub Actions; the pinned `timescale/timescaledb:2.28.3-pg15` service container; `pg_dump`/`pg_restore`; the existing `dashboard.repository` and `dashboard.components.quality` modules; the `airflow` Poetry extra

---

## CONTEXT REFERENCES

### Files to Read Before Implementation

- `Makefile` — every target to widen or add (`typecheck:19`, `format:13`, `check:41`, `test:22`, `db-*:43-64`)
- `pyproject.toml` — pytest/coverage config (`155-196`), mypy strict config (`122-153`), extras (`51-54`)
- `.gitignore` — the lock ignore (`37`) and the backup/artifact patterns (`*.bak`, `*.backup`, `postgres-data/`, `htmlcov/`, `.coverage`)
- `docker-compose.yml` — service name, the **floating** image tag to pin (D11), healthcheck, volume, `${DATABASE_PORT:-5432}` mapping
- `scripts/init-db.sql` — the extension and the four schemas a fresh database needs
- `alembic/env.py:22` — the URL comes from `get_config().database.url`
- `src/utils/config.py` — the `BaseSettings` + alias pattern any new setting must follow
- `src/database/connection.py:84-129` — hypertable + compression policy (what a restore must preserve)
- `src/etl/lineage.py` — `metadata.transformation_log` status semantics (`success`/`partial`/`failed`)
- `dashboard/repository.py:296-323` — `source_freshness()`, the freshness query to reuse
- `dashboard/repository.py:206-240` — `coverage_summary()`, the coverage query to reuse
- `dashboard/components/quality.py:281-357` — `expected_periods` / `expected_observation_count`, the staleness-expectation primitive
- `dashboard/queries.py:16` — `FRESHNESS_CACHE_TTL_SECONDS` (the only TTL; irrelevant to a script but the reference for the 15-minute freshness window)
- `airflow/dags/tgju_daily.py:53-89` — the structured-failure-logging pattern a health script should echo
- `tests/integration/test_database.py:30-95` — the DB fixture and the `pytest.skip`-when-unreachable pattern CI must defeat
- `tests/unit/airflow/test_dag_import.py` — why the `airflow` extra is required for the unit suite
- `tests/unit/connectors/test_tsetmc.py:647`, `tests/unit/connectors/test_hbsir.py:530` — the `skipif` pattern for optional extras
- `tests/unit/dashboard/test_quality.py` — the test style for the expectation primitive the health check and benchmarks lean on
- `docs/phase-8/benchmarks.json` — **to be created** (Task 15); the committed benchmark baseline every later run compares against
- `docs/phase-7.2/VALIDATION.md` — the validation-record style to mirror
- `docs/phase-7.1/README.md` — the runbook style to mirror
- `docs/phase-7.2/README.md` — "How to verify" and "How to add or change a page" sections
- `PRD.md:680-731` — Task 19 and Task 20, the authoritative deliverable list
- `PRD.md:762-767` — §14.4 production-readiness criteria (the acceptance source)
- `PRD.md:736-760` — §14.1–14.3 criteria, including query <1 s and dashboard <3 s
- `AGENTS.md:43-75` — the commands table to extend; `AGENTS.md:656-684` — the constraints

### Data / ML References

- `src/etl/bronze.py`, `src/etl/silver.py`, `src/etl/gold.py` — the pipeline a backup must round-trip intact
- `src/etl/pipeline.py` — per-indicator transaction boundary; the exit-code contract a health check mirrors
- `src/database/schema.py` — the four schemas and their tables (what "the data" means for a backup)
- `docs/phase-2/data_dictionary.md` — indicator/unit/coverage catalog to refresh in Wave F
- `docs/phase-4/VALIDATION.md`, `docs/phase-5/VALIDATION.md`, `docs/phase-6/VALIDATION.md` — the deferred-source evidence the connector limitations index should cite

### External Documentation

- GitHub Actions — workflow syntax: <https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions>
- GitHub Actions — service containers (`services:`, `--health-cmd`): <https://docs.github.com/en/actions/using-containerized-services/about-service-containers>
- `actions/setup-python` — version matrix and caching: <https://github.com/actions/setup-python>
- Poetry — installing with extras and `--no-root` in CI: <https://python-poetry.org/docs/managing-dependencies/#installing-group-dependencies>
- TimescaleDB — logical backup/restore with `pg_dump`/`pg_restore` (the `timescaledb_pre_restore()`/`timescaledb_post_restore()` procedure and the "do not use `-j`" warning): <https://docs.timescaledb.cn/self-hosted/latest/backup-and-restore/logical-backup/>
- PostgreSQL — `pg_dump`: <https://www.postgresql.org/docs/current/app-pgdump.html>; `pg_restore`: <https://www.postgresql.org/docs/current/app-pgrestore.html>
- PostgreSQL — using `EXPLAIN`: <https://www.postgresql.org/docs/current/using-explain.html>
- TimescaleDB — troubleshooting, "versions are mismatched when dumping and restoring": <https://docs.timescaledb.cn/self-hosted/latest/troubleshooting/>

### Patterns to Follow

**Naming:** snake_case modules (`health_check.py`, `benchmark_queries.py`); uppercase constants; `scripts/` holds runnable CLIs (`scripts/dashboard_screenshots.py` is the precedent).

**Structure:** a script is a thin `argparse` CLI over a testable pure function, mirroring `src/etl/pipeline.py` (`run_pipeline` + `run_cli` + `main`) and `scripts/dashboard_screenshots.py`.

**Testing:** pure logic unit-tested with no network and no database (`make test`); anything needing PostgreSQL is marked `@pytest.mark.integration` and skips when unreachable.

**Data/ML:** never interpolate, fill forward or invent values — a health check reports what is stored. Reuse `expected_periods` for staleness rather than re-deriving a calendar rule.

**Config:** no hardcoded host/port/path — read from `src/utils/config.py` (`get_config()`) or an environment variable with a documented default, per AGENTS.md.

**Docs:** mirror `docs/phase-7.2/VALIDATION.md` (separating "verified in this run" from "not automated") and `docs/phase-7.1/README.md` (runbook voice).

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (Wave 0 + Wave A)

Establish the baseline and close the two gate gaps so the CI definition has no
surprises.

- Record the pre-change baseline: unit count, integration count, coverage,
  `mypy`/`ruff` status, wall-clock of `make check`.
- Widen `make typecheck` to `mypy src dashboard`.
- Add a non-mutating `format-check` target.
- Add `dashboard` to the measured coverage set (D3), keeping the 80% threshold.
- Commit `poetry.lock`.

### Phase 2: Core Change (Waves B–E)

Build the four operational capabilities.

- The GitHub Actions workflow: static, unit matrix, integration with a pinned
  TimescaleDB service; and the same pin applied to `docker-compose.yml`.
- `scripts/health_check.py`: scraper health + freshness + transformation
  failures, exit-coded.
- `scripts/backup_db.sh` / `scripts/restore_db.sh` + Makefile targets.
- `scripts/benchmark_queries.py`: `EXPLAIN ANALYZE` on the hot queries, writing
  and comparing against a committed `docs/phase-8/benchmarks.json` baseline.

### Phase 3: Integration (Wave F)

Write the documentation against behaviour the previous phases made observable.

- Architecture and data-flow document.
- Operational runbook.
- Troubleshooting guide (10+ scenarios).
- Drift fixes in `README.md` / `AGENTS.md`.
- Data-dictionary refresh and a connector limitations index.

### Phase 4: Validation (Wave G)

- Fresh-clone acceptance walkthrough (<1 hour).
- `docs/phase-8/VALIDATION.md` separating verified from not-automated.
- Project status update.

---

## STEP-BY-STEP TASKS

Execute tasks in dependency order. Tasks 2–5 are independent of each other but
all precede Task 6.

### 1. VERIFY CI, service container, backup tooling and baseline

- **IMPLEMENT:** Resolve the Wave 0 assumptions and record the pre-change
  baseline. Run and record: `poetry run pytest -m "not integration" -q --no-cov`
  (expect the 1473/3/136 baseline), `poetry run pytest -m integration -q
  --no-cov` against a running database (record the real pass/skip split — README's
  128/4 is stale), `poetry run mypy src dashboard`, `poetry run ruff format
  --check .`, `poetry run ruff check .`. Confirm `pg_dump --version` and
  `pg_restore --version` inside the container
  (`docker compose exec postgres pg_dump --version`). Record the live database
  versions (`SELECT extversion FROM pg_extension WHERE extname='timescaledb';`
  and `SHOW server_version;`) and the resolved image digest
  (`docker inspect --format '{{index .RepoDigests 0}}' <image>`), then confirm
  the pinned tag resolves (`docker manifest inspect
  timescale/timescaledb:2.28.3-pg15`) and that switching `docker-compose.yml` to
  it keeps the existing volume working. Confirm a GitHub Actions
  service container can run the pinned image and that the
  workflow syntax validates (`gh workflow list` after Task 6). Note that a fresh
  service container has the TimescaleDB extension but **not** the
  `bronze`/`silver`/`gold`/`metadata` schemas — `scripts/init-db.sql` only runs on
  a container's first init — so the integration job must apply the schema
  statements before `alembic upgrade head` (see Task 8).
- **PATTERN:** `docs/phase-7.2/wave-0-spike.md` (the Wave 0 capability-probe record).
- **DEPENDENCIES:** Docker running; GitHub repo access.
- **GOTCHA:** The local container publishes host port **5433** (`.env` override),
  while CI will use the default 5432 inside the runner network. Do not record
  local port numbers as CI facts.
- **VALIDATE:** `poetry run pytest -m "not integration" -q --no-cov`

### 2. UPDATE the typecheck target to cover the dashboard (D4)

- **IMPLEMENT:** In `Makefile`, change the `typecheck` recipe from
  `poetry run mypy src/` to `poetry run mypy src dashboard`. Update the
  `AGENTS.md` commands table and the "Notes for AI Agents"/plan NOTES line that
  says the typecheck target covers `src/` only.
- **PATTERN:** `Makefile:18-19`.
- **DEPENDENCIES:** none.
- **GOTCHA:** `make typecheck` is called by `make check`; the change must keep
  `make check` green, and it does **verified now** (`mypy src dashboard` → 68
  files, no issues).
- **VALIDATE:** `make typecheck && make check`

### 3. ADD a non-mutating format-check target (D9)

- **IMPLEMENT:** Add `format-check: ## Check formatting without rewriting files`
  running `poetry run ruff format --check .` to `Makefile`, and add it to the
  `.PHONY` line. Do **not** change the existing `format` target — local
  development keeps the in-place formatter.
- **PATTERN:** `Makefile:12-13`; `.PHONY` at `Makefile:1`.
- **DEPENDENCIES:** none.
- **GOTCHA:** `ruff format --check` exits non-zero on drift; CI must fail on it,
  never auto-fix. Current state is clean **verified now** (165 files).
- **VALIDATE:** `make format-check`

### 4. ADD the dashboard to the coverage gate (D3)

- **IMPLEMENT (measured — proceed):** `pyproject.toml`'s `addopts` already
  carries `--cov=src` and `--cov-fail-under=80`. Add `--cov=dashboard`
  alongside `--cov=src` and leave the threshold unchanged. **This path is
  confirmed by measurement** (Task 1's baseline): with both sources the suite
  reports **90% (6806 statements, 658 missed)** — `src/` alone is 89%
  (4433 / 478) and `dashboard/` alone is 92% (2373 / 180) — so the combined
  ratio clears the 80% gate with a wide margin. Record all three numbers in the
  Wave G validation record.
- **IMPLEMENT (fallback — pre-agreed, only if a later change drops it below
  80%):** Do **not** lower `--cov-fail-under`. Keep the gate scoped to
  `--cov=src` only (as today) and take the dashboard number from a separate,
  non-gating run that clears `addopts` first:
  `poetry run pytest -m "not integration" -o addopts=""
  --cov=dashboard --cov-report=term --cov-fail-under=0`.
  The `-o addopts=""` is required: without it the inherited `--cov=src` would
  make the run report the **combined** ratio rather than `dashboard` alone.
  The 80% threshold is the project's stated criterion (PRD §14.3); it is not a
  knob to turn down.
- **PATTERN:** `pyproject.toml:161-169`.
- **DEPENDENCIES:** Task 1 (the measured baseline).
- **GOTCHA:** pytest-cov **aggregates** every `--cov` source into one ratio
  (covered statements ÷ total statements); it does **not** average the
  per-package percentages. Adding a second source therefore *can* lower the
  combined number — an earlier draft of this plan claimed it "can only raise the
  total", which was wrong. It is safe here only because `dashboard/` measures
  92%, above `src/`'s 89%. Re-measure if the measured source set changes or the
  dashboard's coverage moves materially, and follow the fallback rather than
  relaxing the threshold. Also **verified now**: `--no-cov` disables coverage
  outright and overrides any `--cov` (it emits `CovDisabledWarning` and collects
  nothing), so it is the correct switch for a leg that must not gate — but it
  cannot be paired with `--cov` to produce a report. Use `-o addopts=""` for the
  report-only path instead.
- **VALIDATE:** `poetry run pytest -m "not integration" -q` (expect `TOTAL … 90%` and a green gate)

### 5. COMMIT the Poetry lock file (D2)

- **IMPLEMENT:** Remove the `poetry.lock` line from `.gitignore` (`.gitignore:37`)
  and commit `poetry.lock`. Note the reversal in the plan's NOTES and in the
  commit message.
- **PATTERN:** the existing "Exception:" comment block in `.gitignore` that
  documents why fixtures are tracked.
- **DEPENDENCIES:** Task 1 (confirm the local lock matches the installed set).
- **GOTCHA:** `poetry.lock` was regenerated during Phase 7.2 and no package
  version changed then; re-run `poetry lock` and confirm the resolved version
  list is unchanged before committing, and stop if it proposes upgrades.
- **VALIDATE:** `git check-ignore -v poetry.lock || echo "no longer ignored" && poetry check --lock`

### 6. CREATE the GitHub Actions static job

- **IMPLEMENT:** Create `.github/workflows/ci.yml` with a `static` job on
  `ubuntu-latest`, Python 3.12: checkout, `actions/setup-python` with Poetry
  caching, `poetry install --with dev --extras airflow`, then
  `poetry run ruff check .`, `poetry run ruff format --check .`,
  `poetry run mypy src dashboard`. Trigger on `push` to `main` and on
  `pull_request`.
- **PATTERN:** the local gate order in `Makefile:41`, minus the mutating
  `format`.
- **DEPENDENCIES:** Tasks 2, 3, 5.
- **GOTCHA:** install with the `airflow` extra or the DAG import tests fail
  collection; do **not** run `make check` in CI (D9).
- **VALIDATE:** `gh workflow run ci.yml && gh run watch`

### 7. ADD the unit-test job with a Python matrix (D10)

- **IMPLEMENT:** Add a `unit` job with
  `strategy.matrix.python-version: ["3.11", "3.12"]`, installing with
  `poetry install --with dev --extras airflow`. **The coverage gate runs on the
  3.12 leg only** (decided — see GOTCHA); the 3.11 leg runs the same tests with
  coverage disabled. Two conditional steps make the difference explicit:
  ```yaml
  - name: Unit tests (coverage gate)
    if: matrix.python-version == '3.12'
    run: poetry run pytest -m "not integration"
  - name: Unit tests (no coverage)
    if: matrix.python-version != '3.12'
    run: poetry run pytest -m "not integration" --no-cov
  ```
  `addopts` (`pyproject.toml:161-169`) already supplies
  `--cov=src --cov=dashboard --cov-fail-under=80`, so the gating leg needs no
  extra flags. On the non-gating leg `--no-cov` disables coverage entirely and
  overrides the inherited `--cov-fail-under=80` — **verified now**: a 21-test
  subset run with `--no-cov` and the full `addopts` gate passed with exit 0
  despite near-zero coverage. Both `--no-cov` and `--cov-fail-under` are
  **verified now** to exist in the installed pytest-cov.
- **PATTERN:** `Makefile:21-22` (`test`).
- **DEPENDENCIES:** Task 6 (shared workflow file).
- **GOTCHA:** **Decision (D10): the coverage gate runs only on 3.12.** Coverage
  is a property of the source, not of the interpreter, so a second enforcing leg
  would add runner minutes for no new signal and would fail both legs on the
  same regression. The 3.11 leg still runs every test — it just does not
  re-collect coverage. The TSETMC/HBSIR tests `skipif` on their extras and will
  skip in CI (expected, ~3 skips); the Airflow DAG tests will **fail** without
  the `airflow` extra.
- **VALIDATE:** `gh run view --log`

### 8. PIN the database image and ADD the integration-test job against a TimescaleDB service (D11)

- **IMPLEMENT (pin — do this first):** Replace the floating
  `timescale/timescaledb:latest-pg15` tag with `timescale/timescaledb:2.28.3-pg15`
  in **both** places that define an integration-test database:
  1. `docker-compose.yml` — the `postgres` service `image:`.
  2. `.github/workflows/ci.yml` — the `integration` job's `services.postgres.image`.
  Record the resolved digest (Task 1) as a comment beside each pin, and note the
  pinned extension/server version (2.28.3 / PG 15.18) in `docs/operations/ci.md`.
  Confirm no `latest` tag remains in either file.
- **IMPLEMENT (job):** Add an `integration` job using that pinned image, with the
  env vars `POSTGRES_USER/PASSWORD/DB`, a published port, and a health check
  (`pg_isready`). Steps: checkout, install, set `DATABASE_HOST/PORT/NAME/USER/
  PASSWORD` for the runner, **create the layer schemas and the extension before
  migrating** — apply `scripts/init-db.sql` (or run the equivalent
  `CREATE EXTENSION IF NOT EXISTS timescaledb` + `CREATE SCHEMA IF NOT EXISTS
  bronze/silver/gold/metadata` statements) — then `poetry run alembic upgrade
  head`, then `poetry run pytest -m integration`. Ensure the job **fails** if any
  test skips (e.g. assert the skip count is zero via a `--junitxml` parse or a
  `-p no:cacheprovider` + `-ra` review step), so a missing database cannot pass.
- **PATTERN:** `docker-compose.yml` (image + `pg_isready` healthcheck);
  `alembic/env.py:22` (the URL comes from the env vars).
- **DEPENDENCIES:** Task 6; Task 1's measured integration baseline and resolved
  digest.
- **GOTCHA:** pin the **same** version in compose and CI, or "works locally, fails
  in CI" stays unfalsifiable — that is the whole point of D11. The running
  container is already 2.28.3, so the compose pin should be a no-op for the
  existing `postgres_data` volume; confirm before and after (`SELECT
  extversion …`) rather than assuming. `tests/integration/test_database.py:53`
  skips silently when PostgreSQL is unreachable — the "no silent skips"
  assertion is the whole point of this task. The service container's port is
  internal (5432); do not reuse the local 5433 override.
- **GOTCHA:** A fresh pinned TimescaleDB container has the **extension but not the
  `bronze`/`silver`/`gold`/`metadata` schemas**. `scripts/init-db.sql` is mounted
  via `docker-entrypoint-initdb.d` and only runs on the container's **first**
  initialisation, so a GitHub Actions `services:` container (which starts from a
  fresh, empty volume every run) will not have the schemas. No migration contains
  `CREATE SCHEMA`, so `alembic upgrade head` dies with
  `psycopg2.errors.InvalidSchemaName: schema "bronze" does not exist`. The
  integration job must apply `scripts/init-db.sql` (or the equivalent `CREATE
  SCHEMA` statements) **before** `alembic upgrade head`. The integration tests
  themselves do not depend on alembic — their fixture does `CREATE SCHEMA IF NOT
  EXISTS` + `create_all_tables()` — but the job's explicit migration step does,
  so the ordering is mandatory.
- **VALIDATE:** `grep -rn "latest-pg15" docker-compose.yml .github/ || echo "no floating tags"`; then `gh run watch`; then locally `make db-up && poetry run alembic upgrade head && poetry run pytest -m integration`

### 9. DOCUMENT required checks and branch protection

- **IMPLEMENT:** Add a short `docs/operations/ci.md` (or a README section) naming
  the three jobs as the required checks for `main`, how to run each locally, and
  how to reproduce the integration job without CI. If branch protection is
  desired, record it as an owner action (it is a repository setting, not a file).
- **PATTERN:** `docs/phase-7.2/README.md` "How to verify".
- **DEPENDENCIES:** Tasks 6–8.
- **GOTCHA:** branch protection is a GitHub setting; the plan can specify it but
  only the owner can enable it — mark it clearly rather than assuming it exists.
- **VALIDATE:** `gh api repos/:owner/:repo/branches/main/protection` (after the owner enables it)

### 10. CREATE the health-check script

- **IMPLEMENT:** Create `scripts/health_check.py` with a pure
  `evaluate_health(freshness, coverage, expected) -> HealthReport` function and
  a thin `argparse` CLI (`--json`, `--stale-after-days`, `--fail-on-warning`).
  It reads `metadata.data_collection_log` (latest status per source), applies
  `dashboard.components.quality.expected_periods` against the catalog frequency
  and the last observed Gold timestamp to classify each source
  `ok`/`stale`/`failed`, and exits 0 (healthy), 1 (degraded/warning) or 2
  (failed). Reuse `DashboardRepository.source_freshness` and
  `coverage_summary` rather than writing new SQL.
- **PATTERN:** `src/etl/pipeline.py` (`run_pipeline` + `run_cli` + `main`,
  exit-code contract); `scripts/dashboard_screenshots.py` (CLI shape);
  `dashboard/repository.py:296` and `dashboard/components/quality.py:281`
  (reuse, do not re-derive).
- **DEPENDENCIES:** Task 1.
- **GOTCHA:** read-only — the script must not write to any table. Day-based
  freshness is `Asia/Tehran`-aware (`quality.py:187-200`); period-end
  frequencies key off the UTC calendar date. Do not invent a staleness threshold
  where the catalog frequency already determines one.
- **VALIDATE:** `poetry run python scripts/health_check.py --json`

### 11. ADD health-check tests and a Makefile target

- **IMPLEMENT:** Unit-test `evaluate_health` with synthetic frames covering:
  fresh, stale-beyond-one-period, last-run-failed, no-data-at-all, a
  trading-session source (estimated expectation), and an unsupported frequency
  (no expectation). Add `health: ## Report connector health and data freshness`
  to `Makefile`.
- **PATTERN:** `tests/unit/dashboard/test_quality.py` (the expectation
  primitive's tests); `tests/conftest.py` fake-frame fixtures.
- **DEPENDENCIES:** Task 10.
- **GOTCHA:** no network and no database in the unit tests — feed frames in
  directly.
- **VALIDATE:** `poetry run pytest tests/unit/scripts -q --no-cov`

### 12. CREATE the backup script

- **IMPLEMENT:** Create `scripts/backup_db.sh`: read the connection settings
  from `.env` (or environment), run
  `docker compose exec -T postgres pg_dump -d "$SOURCE" -Fc -f /tmp/<name>.bak`
  then `docker compose cp` the file out to `backups/<name>.bak`, or dump
  directly through the published port with a host `pg_dump` if available.
  Timestamp the filename, refuse to overwrite an existing backup, and print the
  path. Add `backups/` to `.gitignore`.
- **PATTERN:** `Makefile:43-64` (`db-*` targets use `docker compose exec`);
  `scripts/init-db.sql` (script style).
- **DEPENDENCIES:** Task 1 (`pg_dump` present in the image).
- **GOTCHA:** `pg_dump -Fc` is the documented form; record the PostgreSQL and
  TimescaleDB versions alongside the dump (version mismatch breaks restore).
  Do not use `pg_dumpall` — it needs superuser and dumps the whole cluster.
- **VALIDATE:** `bash scripts/backup_db.sh && ls -lh backups/`

### 13. CREATE the restore script

- **IMPLEMENT:** Create `scripts/restore_db.sh` implementing the documented
  procedure against a **scratch** database: `CREATE DATABASE <target>`,
  `CREATE EXTENSION IF NOT EXISTS timescaledb`, `SELECT
  timescaledb_pre_restore();`, `pg_restore -Fc -d <target> <file>`, then
  `SELECT timescaledb_post_restore();`. Refuse to restore over the live
  `iran_macro_db` unless an explicit `--force` is passed.
- **PATTERN:** the same `docker compose exec` pattern as Task 12.
- **DEPENDENCIES:** Task 12.
- **GOTCHA:** **never pass `-j` to `pg_restore`** — it cannot correctly restore
  the TimescaleDB catalog (official warning). The extension must exist on the
  target *before* the restore. Restoring is destructive; the default target must
  be a scratch database.
- **VALIDATE:** `bash scripts/restore_db.sh backups/<name>.bak`

### 14. ADD backup/restore Makefile targets and prove the roundtrip

- **IMPLEMENT:** Add `backup:` and `restore:` targets wrapping the two scripts
  with `BACKUP_FILE=` / `TARGET_DB=` variables. Then actually run the roundtrip:
  back up the live database, restore into a scratch database, and compare row
  counts for `bronze.bronze_raw`, `silver.silver_cleaned`, `gold.gold_analytical`,
  `metadata.indicator_catalog` and `metadata.data_collection_log`.
- **PATTERN:** `Makefile:43-64`.
- **DEPENDENCIES:** Tasks 12–13.
- **GOTCHA:** the hypertable and compression policy must survive the restore —
  verify with
  `SELECT * FROM timescaledb_information.hypertables;` on the restored database,
  not just row counts.
- **VALIDATE:** `make backup && make restore && docker compose exec postgres psql -U iran_macro -d iran_macro_restore_test -c "SELECT count(*) FROM gold.gold_analytical;"`

### 15. CREATE the query benchmark script with a persisted baseline (D7)

- **IMPLEMENT (measure):** Create `scripts/benchmark_queries.py` that runs
  `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` on the dashboard's hot queries —
  `DashboardRepository.load_series` (the ten-page hot path),
  `coverage_summary`, `source_freshness` — plus the Overview's catalog read.
  Parse each plan for a `Seq Scan` on `gold.gold_analytical` /
  `silver.silver_cleaned`. **Index usage is the only hard gate:** exit non-zero
  on an unexpected sequential scan.
- **IMPLEMENT (persist):** Write the run to **`docs/phase-8/benchmarks.json`**
  (committed — it is the baseline, not a build artifact). One record per run,
  keyed by git commit and timestamp, capturing the environment (python,
  PostgreSQL, TimescaleDB, image digest, row counts per table) and, per query:
  `name`, the SQL, `index_used`, `planning_ms`, `execution_ms`, `rows`,
  `shared_hit_blocks`/`shared_read_blocks`. Writing is explicit (`--write`) so a
  normal run never mutates a tracked file.
- **IMPLEMENT (compare):** On a normal run, load the most recent stored run and
  print a delta table — absolute and percentage change in `execution_ms` per
  query, plus any `index_used` transition. Flag a **regression** when execution
  time is >25% slower than the baseline (`--regression-threshold`) or when index
  usage was lost, and print a highlighted summary. Timing regressions do **not**
  change the exit code unless `--fail-on-regression` is passed. If the
  environment differs materially (different PostgreSQL/TimescaleDB version or row
  counts), label the comparison "environment changed" instead of reporting a
  false regression.
- **IMPLEMENT (target):** Add `benchmark: ## Run query benchmarks and compare
  against the stored baseline` to the `Makefile`, and document the
  `--write` baseline-refresh step in the runbook.
- **PATTERN:** `dashboard/repository.py` (the queries to benchmark);
  `scripts/dashboard_screenshots.py` (CLI + report shape).
- **DEPENDENCIES:** Task 1.
- **GOTCHA:** `EXPLAIN ANALYZE` **executes** the query; run it against a
  populated database and keep it strictly read-only. Timing is environment-
  dependent, so it is reported, never gated (D7). Small tables may legitimately
  use a sequential scan — assert index usage only for the queries the PRD names
  (`PRD.md:760`). The baseline must be refreshed with `--write` after an
  intentional change (a new index, a schema change), or every later run reports
  the same stale regression.
- **VALIDATE:** `poetry run python scripts/benchmark_queries.py && poetry run python scripts/benchmark_queries.py --write`

### 16. CREATE the architecture and data-flow document

- **IMPLEMENT:** Create `docs/architecture.md`: the medallion layers and their
  schemas/tables, the connector → pipeline → Gold flow, the four Airflow DAGs
  and their schedules, the dashboard's read path (Gold + catalog, derivedness
  from metadata), and the storage/display timezone policy. Include the Mermaid
  (or ASCII) data-flow diagram the PRD asks for, and link the per-phase records
  instead of duplicating them.
- **PATTERN:** `AGENTS.md:125-173` (the existing flow diagram) and
  `docs/phase-7.1/README.md`.
- **DEPENDENCIES:** none (describes existing behaviour).
- **GOTCHA:** describe **observed** behaviour, not intended — the deferred
  sources (OPEC, CBI, part of TSETMC) must be shown as absent, matching
  `README.md:289-310`.
- **VALIDATE:** manual review against `git ls-files 'src/**'` and
  `airflow/dags/`

### 17. CREATE the operational runbook

- **IMPLEMENT:** Create `docs/operations/runbook.md`: daily/weekly/monthly
  maintenance (the DAG schedules from `airflow/dags/`), how to run a pipeline by
  hand and read its exit code, how to run the health check and interpret its exit
  codes, backup cadence and restore procedure, how to apply a migration, how to
  run the query benchmarks and **refresh the baseline with `--write` after an
  intentional change**, and how to restart the dashboard. Include the DAG
  schedule table (`tgju_daily` 23:00, `tgju_backfill` manual, `sci_weekly`
  Fri 03:00, `tsetmc_daily` 23:00) and the pinned database version.
- **PATTERN:** `docs/phase-7.1/README.md` (runbook voice);
  `AGENTS.md:368-373` (orchestration intent).
- **DEPENDENCIES:** Tasks 10–15 (the commands it documents must exist).
- **GOTCHA:** every command in the runbook must be runnable as written — run each
  one before committing the doc.
- **VALIDATE:** execute each command in the runbook

### 18. CREATE the troubleshooting guide

- **IMPLEMENT:** Create `docs/operations/troubleshooting.md` with **at least ten**
  concrete scenarios (PRD §14.4), each with symptom → diagnosis → fix. Cover at
  minimum: Docker daemon not running / wrong context
  (`DOCKER_CONTEXT=default`), port 5432 occupied (the `DATABASE_PORT` override),
  PostgreSQL unreachable / integration tests skipping, TimescaleDB extension
  missing, `alembic check` drift, a scraper selector break, a Persian-digit or
  Jalali-date parse failure, a source returning no rows, a stale source in the
  health check, restore failing on a missing extension, a dashboard cache
  showing stale data (the 15-minute freshness TTL), and a benchmark reporting a
  regression that is really an environment change (different database version or
  row counts — refresh the baseline with `--write`).
- **PATTERN:** `README.md:385-427` (the existing Troubleshooting section) —
  this guide is the expanded, linked version of it.
- **DEPENDENCIES:** Tasks 10–15.
- **GOTCHA:** only document failures that are reachable in this codebase; cite
  the evidence (a command, a file, a phase record) for each.
- **VALIDATE:** manual review; link check

### 19. FIX documentation drift in README and AGENTS

- **IMPLEMENT:** Correct `README.md:89` (`cp .env.template .env` →
  `cp .env.example .env`), replace the stale test/coverage figures at
  `README.md:337` with the Wave G measured numbers, clear the stale
  "Phase 2 … (Current)" marker (`README.md:439`), add `phase-7.2` and `phase-8`
  to the `docs/` listings in `README.md:228-239` and `AGENTS.md:107-117`, and
  update the roadmap/status blocks (`README.md:496-499`, `README.md:537`) for
  Phase 8.
- **PATTERN:** the existing README structure; `AGENTS.md:20` (the lifecycle
  sentence that must be kept current).
- **DEPENDENCIES:** Task 21 (the measured numbers) for the figures; the rest is
  independent.
- **GOTCHA:** do not restate numbers from memory — read them from the actual run.
  Do not rewrite sections unrelated to Phase 8.
- **VALIDATE:** `grep -n "1,141\|\.env\.template" README.md` (expect no matches)

### 20. REFRESH the data dictionary and add a connector limitations index

- **IMPLEMENT:** Add a short "Connector status and limitations" section (in
  `docs/architecture.md` or `README.md`) that, per source, states: type,
  frequency, implemented/deferred status, and the recorded reason for any
  deferral, linking `docs/phase-4/VALIDATION.md`, `docs/phase-5/VALIDATION.md`
  and `docs/phase-6/VALIDATION.md`. Reconcile
  `docs/phase-2/data_dictionary.md` with the currently registered indicators if
  it has drifted.
- **PATTERN:** `README.md:289-310` (the existing source table and its
  cross-references); `AGENTS.md:718` ("Document limitations … if a source is
  blocked, do not work around it — record the evidence and defer").
- **DEPENDENCIES:** Task 16.
- **GOTCHA:** deferred sources must stay visibly deferred; do not imply OPEC,
  CBI or the missing TSETMC series are planned for this phase.
- **VALIDATE:** manual review against `src/connectors/*.py` and the phase records

### 21. RUN the fresh-clone acceptance walkthrough

- **IMPLEMENT:** In a scratch clone (or a scratch directory with a fresh venv and
  a `docker compose down -v`), follow only the documented README quickstart, and
  time it end to end: clone → `poetry install` → `.env` → `make db-up` →
  `alembic upgrade head` → `make check` → `make dashboard`. Record every place
  the docs were wrong or incomplete and fix them (folding corrections back into
  Tasks 17–19).
- **PATTERN:** `PRD.md:764` ("a new developer can run the system in <1 hour")
  and `PRD.md:700` ("Follow README on a fresh machine or VM").
- **DEPENDENCIES:** Tasks 16–20.
- **GOTCHA:** this must be a genuinely fresh environment — a warm venv or an
  existing database volume invalidates the walkthrough. `make db-reset` deletes
  data; use a scratch project directory or a separate compose project name
  rather than destroying the live volume.
- **VALIDATE:** `time <the documented sequence>`

### 22. WRITE the Phase 8 validation record and update project status

- **IMPLEMENT:** Create `docs/phase-8/VALIDATION.md` mirroring
  `docs/phase-7.2/VALIDATION.md`'s verified/not-automated split: the baseline
  (Task 1), the measured coverage including `dashboard`, the pinned database
  version and image digest, the CI run IDs and their job results, the
  health-check output, the backup/restore roundtrip evidence (row counts +
  hypertable presence), the **benchmark baseline written to
  `docs/phase-8/benchmarks.json` with its first-run timings and the index-usage
  result**, and the fresh-clone walkthrough time. Then update `README.md:537` and
  `AGENTS.md:20` to mark Phase 8 complete and name what remains deferred.
- **PATTERN:** `docs/phase-7.2/VALIDATION.md` (structure); `docs/phase-7.2/README.md`
  (the "Status: … pending owner acceptance" convention).
- **DEPENDENCIES:** Tasks 6–21.
- **GOTCHA:** keep the "not automated in this run" list honest — the screenshot
  script precedent (`scripts/dashboard_screenshots.py` is not a CI gate) is the
  model for declaring what remains manual.
- **VALIDATE:** `git status --short` (only intended files) and a link check

---

## TESTING & VALIDATION

### Unit Tests

- `evaluate_health` (Task 11): fresh / stale / failed / no-data /
  trading-session / unsupported-frequency cases, all with synthetic frames — no
  network, no database.
- `benchmark_queries.py` helpers (Task 15), tested against **captured** `EXPLAIN`
  JSON: plan parsing ("does this plan contain a sequential scan on table X"),
  the baseline serialization round-trip, and the regression comparison — slower /
  faster / unchanged, an index-usage loss, a first run with no baseline, and the
  "environment changed" case (differing version or row counts) which must not be
  reported as a regression.
- The gate changes (Tasks 2–4) are verified by the existing suite staying green
  plus the new targets running.

### Integration Tests

- The existing 136 integration tests must pass against a database created by
  `alembic upgrade head` in the CI service container, and the job must fail if
  any of them skip (Task 8).
- The backup/restore roundtrip (Task 14) is a manual integration check, not an
  automated test: it needs a populated database and writes a scratch database.

### Data Validation

- The restore roundtrip compares per-table row counts across all four schemas
  and asserts the hypertable and compression policy survived
  (`timescaledb_information.hypertables`).
- The health check asserts the metadata layer is self-consistent: a source whose
  latest `data_collection_log` row is `failed`, or whose last Gold observation is
  more than one expected period old, is reported non-`ok`.

### ML Validation

Not applicable — Phase 8 adds no model, feature or evaluation logic. The
"no data leakage / temporal validity" rules are untouched; the health check
reads stored timestamps and never fills or interpolates.

### Edge Cases

- Health check on an **empty** database (no collections yet) — must report
  "no data", not crash or claim healthy.
- Health check for a **trading-session** source (TSETMC) — the expectation is an
  estimate (`quality.py:324-331`); the check must not report a false gap.
- Health check for a frequency with **no expectation** — report "unknown", do
  not invent a threshold.
- Backup with **no running container** — fail with an actionable message, not a
  partial file.
- Restore over an **existing** database — refused without `--force`.
- Restore when the target lacks the `timescaledb` extension — the documented
  order (`CREATE EXTENSION` before `timescaledb_pre_restore()`) prevents it.
- CI integration job with the **service absent** — must fail, not skip.
- `poetry install` **without** the `airflow` extra — the DAG tests fail; CI must
  install the extra.
- A source that has **never** run — freshness is `NULL`, distinct from stale.
- Benchmark on a **first run** with no stored baseline — must record and report,
  not fail or divide by zero.
- Benchmark comparison when the **environment changed** (different PostgreSQL/
  TimescaleDB version or table row counts) — must be labelled "environment
  changed", not reported as a regression.
- Benchmark run **without `--write`** — must not modify the tracked
  `docs/phase-8/benchmarks.json`.

---

## VALIDATION COMMANDS

### Level 1: Static / Style

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src dashboard
make check                       # local, mutating formatter included
```

### Level 2: Unit Tests

```bash
poetry run pytest -m "not integration" -q          # baseline: 1473 passed, 3 skipped
poetry run pytest tests/unit/scripts -q --no-cov   # the new health-check tests
```

### Level 3: Integration / Pipeline Tests

```bash
make db-up
poetry run alembic upgrade head
poetry run pytest -m integration -q
```

### Level 4: Feature-Specific Validation

```bash
# CI
gh workflow run ci.yml && gh run watch
gh run view --log

# Image pin (D11) — expect no matches
grep -rn "latest-pg15" docker-compose.yml .github/ || echo "no floating tags"
docker compose config | grep image

# Monitoring
poetry run python scripts/health_check.py --json
make health

# Backup / restore
make backup
make restore BACKUP_FILE=backups/<name>.bak TARGET_DB=iran_macro_restore_test
docker compose exec postgres psql -U iran_macro -d iran_macro_restore_test \
  -c "SELECT count(*) FROM gold.gold_analytical;"
docker compose exec postgres psql -U iran_macro -d iran_macro_restore_test \
  -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"

# Performance — compare against the stored baseline, then refresh it
poetry run python scripts/benchmark_queries.py
poetry run python scripts/benchmark_queries.py --write
make benchmark
git diff --stat docs/phase-8/benchmarks.json
```

### Level 5: Manual Validation

- The fresh-clone acceptance walkthrough (Task 21) timed end to end against the
  PRD's <1 hour target.
- A browser walk of the dashboard to confirm the freshness surface the health
  check reports matches what the UI shows.
- Owner review of the validation record and the deferred list.

---

## ACCEPTANCE CRITERIA

Mapped to `PRD.md` §13 (Task 19/20) and §14.4.

- [ ] CI runs on every push to `main` and every PR, with static, unit (3.11 +
      3.12) and integration jobs (PRD Task 20).
- [ ] The integration job uses a real TimescaleDB service and **fails** when the
      tests would skip (no silent green).
- [ ] No floating `latest` image tag remains in `docker-compose.yml` or
      `.github/`; compose and CI pin the **same** TimescaleDB version (D11).
- [ ] `make check` typechecks `src/` **and** `dashboard/` (D4).
- [ ] Coverage measures `src/` **and** `dashboard/` as one aggregated ratio and
      meets the 80% gate (measured 90%; D3).
- [ ] `poetry.lock` is committed and CI installs from it (D2).
- [ ] `scripts/health_check.py` reports scraper health and data freshness and
      exits non-zero on a failed or stale source (PRD Task 20).
- [ ] Backup and restore procedures exist, are documented, and a **tested**
      roundtrip restores all four schemas and the hypertable (PRD §14.4).
- [ ] Benchmarks cover the dashboard's hot queries, report timings against the
      <1 s budget, and assert index usage as the only hard gate (PRD §14.1,
      §14.3).
- [ ] Each benchmark run is **persisted** to `docs/phase-8/benchmarks.json`, and
      a later run reports per-query deltas and highlights significant timing
      regressions against that baseline (D7).
- [ ] An architecture/data-flow document, an operational runbook, and a
      troubleshooting guide with **10+** scenarios exist (PRD Task 19, §14.4).
- [ ] A new developer can set up and run the system in <1 hour by following the
      documentation (PRD §14.4, §16 validation).
- [ ] No ETL, schema, migration or presentation behaviour changed.
- [ ] `docs/phase-8/VALIDATION.md` separates verified from not-automated.
- [ ] Existing project patterns are followed; no new dependency is added beyond
      what CI/tooling requires.
- [ ] No regressions: the full unit and integration suites pass.

---

## RISKS & TRADE-OFFS

1. **CI cost and scope.** GitHub Actions minutes are finite; a two-version matrix
   with a TimescaleDB service per run is the largest consumer. *Mitigation:* D10
   (static gates once), Poetry caching, and `concurrency` cancellation of
   superseded runs.
2. **Committing `poetry.lock` reverses a prior decision.** *Mitigation:* D2
   records the reversal and its reason; Task 5 verifies no resolved version
   changed before committing.
3. **Pinned image drifts from what the platform was validated against.** Pinning
   freezes the database, but the pin can become stale as TimescaleDB releases
   security and bug fixes. *Mitigation:* D11 pins the version already running
   locally (2.28.3 / PG 15.18) and records the digest; Task 1 confirms the pin is
   a no-op for the existing volume; a deliberate bump is a one-line change in two
   files plus a `--write` baseline refresh.
4. **Integration tests can pass vacuously.** *Mitigation:* Task 8's
   "no silent skips" assertion is a hard requirement, not a nicety.
5. **Restore is destructive.** *Mitigation:* the default target is a scratch
   database and `--force` is required to touch the live one; the documented
   order prevents a missing-extension restore.
6. **Benchmarks are environment-dependent.** *Mitigation:* D7 — gate on index
   usage (structural); report timings; persist a baseline so a delta is
   comparable; label a comparison "environment changed" when versions or row
   counts differ rather than reporting a false regression.
7. **A stale benchmark baseline produces permanent false regressions.**
   *Mitigation:* `--write` is the documented refresh step (runbook, Task 17) and
   is required after an intentional change (a new index, a schema change); the
   comparison reports the baseline's commit and timestamp so a stale baseline is
   visible.
8. **Phase 8 is three PRD deliverables in one phase.** *Mitigation:* wave gating;
   each wave ships and is verifiable on its own; documentation is written last so
   it describes behaviour that already exists.
9. **A future change could push the widened coverage ratio below 80%.** Adding
   `dashboard/` to the gate widens the measured set, and pytest-cov's single
   aggregated ratio means later dashboard code can lower it. *Mitigation:* D3 —
   the measured combined number is 90% (src 89%, dashboard 92%), so there is
   headroom; if it falls below 80, scope the gate back to `src/` and report
   `dashboard` separately, never lower the threshold.
10. **`make check` remains mutating locally.** *Mitigation:* documented in the
    runbook and CI never uses it (D9).
11. **Health-check thresholds could drift from the dashboard's.** *Mitigation:*
    reuse `expected_periods` and the repository queries rather than declaring a
    second rule set.

## NOTES

- **Phase 8 is not presentation work.** The Phase 7.2 boundary ("dashboard work
  changes nothing under `src/`, `alembic/` or `airflow/`") applies in the other
  direction here: Phase 8 may touch `Makefile`, `.github/`, `scripts/`, `docs/`,
  `pyproject.toml`, `.gitignore`, `docker-compose.yml`, `README.md` and
  `AGENTS.md`, but it must not change ETL, connector, schema or dashboard
  presentation behaviour. If a task seems to need one, it belongs in Deferred
  Scope.
- **One database version, two places (D11).** `docker-compose.yml` and
  `.github/workflows/ci.yml` must name the same pinned TimescaleDB tag
  (`2.28.3-pg15`). A future bump changes both files and is followed by a
  `benchmark_queries.py --write` baseline refresh, because a version change can
  move query plans.
- **`docs/phase-8/benchmarks.json` is committed on purpose.** It is a baseline,
  not a build artifact — the opposite of the gitignored `htmlcov/`, `.coverage`
  and `backups/`. It is written only under `--write`, so a normal benchmark run
  leaves the working tree clean.
- **Local port 5433 vs CI port 5432.** The local `.env` publishes 5433 because a
  system PostgreSQL holds 5432. CI uses the default. Never copy local connection
  facts into the workflow.
- **`make check` vs CI.** Locally, `make check` runs `ruff format .` in place and
  is the developer convenience target. CI runs `ruff format --check .` and
  `ruff check .` separately. A Verify that runs only pytest can miss formatting
  drift — the format check belongs in every wave's gate.
- **The `airflow` extra is mandatory for the unit suite** because the DAG import
  tests do not skip. The `tsetmc`/`hbsir` extras are optional and their tests
  skip. CI installs `--extras airflow`; it does **not** need `--all-extras`.
- **D1/D2 stay deferred.** They are recorded in the Phase 7.2 Deferred Scope
  (items 15 and 16) and are deliberately not fixed here (D8).
- **Open owner decisions (not engineering tasks):**
  - The LICENSE is still "to be determined" (`README.md:518`); no `LICENSE` is
    tracked.
  - Whether to enable branch protection / required checks on `main` (Task 9
    specifies them; only the owner can enable them).
- **Coverage: `dashboard` is gated, not merely reported (D3, resolved).** The
  earlier "report it and decide later" framing was dropped once the number was
  measured: combined 90% against an 80% gate. The pre-agreed fallback (scope the
  gate back to `src/` and report `dashboard` separately) exists so a future drop
  never tempts anyone to lower the threshold.
- **`htmlcov/`, `.coverage` and `backups/` are gitignored** (or will be, for
  `backups/`) — no generated artifact from this phase should be committed except
  `poetry.lock`.
- **Plan line references are snapshots.** Every `file:line` above records where a
  symbol sat when this plan was written; locate code by symbol name and re-verify
  before relying on a line number.
