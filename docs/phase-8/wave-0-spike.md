# Phase 8 — Wave 0 spike (Task 1)

Verification spike + baseline capture for the Phase 8 production-readiness work.
No production file was changed; this note plus the plan corrections are the only
outputs.

Owner: executor (Wave 0). Branch: `development`. Date: **2026-09-22** (UTC).
Pre-change HEAD: `92eff6f` (tag `phase-7.2-complete`).

---

## 1. Environment

| Item | Value | Evidence |
|---|---|---|
| Date | 2026-09-22 (UTC) | `date -u` |
| Branch | `development` | `git branch --show-current` |
| Pre-change HEAD | `92eff6f` (tag `phase-7.2-complete`) | `git log` |
| Python | 3.12.3 | `poetry run python --version` |
| Poetry | 2.4.1 | `poetry --version` |
| ruff | 0.1.15 | `poetry run ruff --version` |
| mypy | 1.20.2 | `poetry run mypy --version` |
| pytest | 7.4.4 | `poetry run pytest --version` |
| Database | `iran_macro_postgres` Up (healthy), host port **5433** (read-only use) | `docker ps` |
| Image | `timescale/timescaledb:latest-pg15` (floating — the tag D11 pins) | `docker ps` |
| Running digest | `sha256:6343bdc87ca132c6b53acb26113a6bad1821d188fa39975a745f32ddd9757634` | `docker inspect --format '{{index .RepoDigests 0}}'` |
| TimescaleDB / PostgreSQL | **2.28.3** / **15.18** | `SELECT extversion …`; `SHOW server_version;` |
| `gh` CLI | installed; `origin` = `https://github.com/ArshiaAsk/Iran-Macroeconomic-Data-Platform.git` | `gh --version`; `git remote -v` |

The local container publishes host port **5433** (the local `.env` overrides the
compose default of 5432, because a system PostgreSQL holds 5432). CI will use the
default 5432 inside the runner network — local port numbers are **not** CI facts.

---

## 2. Results — Task 1 (VERIFY CI, service container, backup tooling, baseline)

| item | result | evidence | status |
|---|---|---|---|
| Unit baseline | **1473 passed, 3 skipped, 136 deselected** (116.36 s) | `poetry run pytest -m "not integration" -q --no-cov` | VERIFIED |
| Integration baseline | **132 passed, 4 skipped, 1476 deselected** (612.97 s; 136 selected) | `poetry run pytest -m integration -q --no-cov` against the live DB | VERIFIED |
| Integration skips | the 4 skips are live-network tests gated on `RUN_LIVE_API_TESTS=1` (`test_{imf,sci,tgju,world_bank}_pipeline.py`) | `-rs` output | VERIFIED |
| Static — typecheck | clean, **68 source files** | `poetry run mypy src dashboard` | VERIFIED |
| Static — lint | clean | `poetry run ruff check .` | VERIFIED |
| Static — format | **165 files already formatted** | `poetry run ruff format --check .` | VERIFIED |
| `poetry.lock` | **219 packages**, sha256 `ea85d3ec0d0877c101b33fa0e55161f5013677abbda089b46c40ba79adc7aa79`, `poetry check --lock` exit 0 (deprecation warnings only) | `poetry check --lock` | VERIFIED |
| `pg_dump` / `pg_restore` | **15.18** present in the container; the `iran_macro` role can dump (`pg_dump -Fc` exit 0, 33.7 MB) | `docker compose exec postgres pg_dump --version`; a real dump | VERIFIED (with a benign warning — see below) |
| Live DB versions | TimescaleDB **2.28.3** / PostgreSQL **15.18** | `SELECT extversion FROM pg_extension WHERE extname='timescaledb';`; `SHOW server_version;` | VERIFIED |
| Live DB row counts | `bronze_raw` 100, `silver_cleaned` 8446, `gold_analytical` 20074, `indicator_catalog` 54, `data_collection_log` 100 | `psql` count queries | VERIFIED |
| Pinned tag resolves to the running digest | **yes** — `2.28.3-pg15` → `sha256:6343bdc8…` (identical to the running image) | `docker pull` + digest compare (see §5, assumption 2) | VERIFIED |
| Compose pin is a no-op locally | **yes** — the pinned image opens the existing `postgres_data` volume unchanged (2.28.3 / 15.18 / 20074 gold rows / hypertable intact) | scratch container against the volume with `PGDATA` set | VERIFIED |
| Coverage (`src` + `dashboard`) | combined **90%** (6806 statements, 658 missed); `src/` 89% (4433/478), `dashboard/` 92% (2373/180) | `pytest -m "not integration" --cov=src --cov=dashboard --cov-fail-under=0` | VERIFIED |

**Benign dump warning.** `pg_dump -Fc` emits a warning about circular foreign
keys on TimescaleDB's `continuous_agg` catalog table. It does not affect the dump
(`pg_dump` exits 0) and is expected for a TimescaleDB database; the restore path
is verified in Task 14, not here.

---

## 3. Baseline (Task 1) and the per-wave gate rule

`git status --short` before Wave 0: **clean** (working tree clean at `0303ec4`).

| Baseline command | Result |
|---|---|
| `poetry run pytest -m "not integration" -q --no-cov` | **1473 passed, 3 skipped, 136 deselected** in 116.36 s |
| `poetry run pytest -m integration -q --no-cov` (live DB) | **132 passed, 4 skipped, 1476 deselected** in 612.97 s |
| `poetry run mypy src dashboard` | **0 errors** (`Success: no issues found in 68 source files`) |
| `poetry run ruff check .` | clean |
| `poetry run ruff format --check .` | **165 files already formatted** |
| `poetry check --lock` | exit 0 (deprecation warnings only) |

**Per-wave gate rule.**

- **No regressions** against the counts above: the unit suite stays **1473
  passed, 3 skipped, 136 deselected**; the integration suite stays **132 passed,
  4 skipped**; `mypy src dashboard` stays **zero errors**; `ruff format --check`
  stays clean at **165 files**.
- The **format check belongs in every wave's gate** — a Verify that runs only
  pytest misses formatting drift (`make check` reformats in place; CI uses
  `ruff format --check`).

---

## 4. Decisions for Waves A/B

| Decision | Outcome | Evidence |
|---|---|---|
| **Gate closure (Wave A)** | The three gate changes are safe: `mypy src dashboard` already clean (68 files); `ruff format --check` already clean (165 files); the widened coverage set (`src` + `dashboard`) measures **90%** against the 80% gate. | §2 |
| **Coverage set (D3)** | Add `--cov=dashboard` alongside `--cov=src`; keep `--cov-fail-under=80`. pytest-cov aggregates both sources into one ratio (90%), so the gate clears with headroom. | §2 |
| **`poetry.lock` (D2)** | Committed; the resolved set is 219 packages and `poetry check --lock` passes. Re-run `poetry lock` and confirm no version changed before committing (Task 5). | §2 |
| **Database pin (D11)** | Pin `timescale/timescaledb:2.28.3-pg15` in both `docker-compose.yml` and CI; it resolves to the running digest `sha256:6343bdc8…` and opens the existing volume unchanged. Verify the pin by **pull + digest compare**, not `docker manifest inspect` (geo-blocked). | §2, §5 |
| **Integration job must create schemas first (Wave B)** | `alembic upgrade head` **cannot** create a fresh database — apply `scripts/init-db.sql` (or the `CREATE SCHEMA` statements) before migrating. | §5, assumption 1 |
| **Backup tooling** | `pg_dump`/`pg_restore` 15.18 are present and the `iran_macro` role can dump. Wave D may proceed with `pg_dump -Fc`. | §2 |

---

## 5. The two failed assumptions (and their resolutions)

1. **`alembic upgrade head` cannot create a fresh database on its own.**
   `alembic/versions/20260817_1456_initial_schema.py` creates tables with
   `schema="bronze"` etc. but **no migration contains `CREATE SCHEMA`**. On a
   fresh TimescaleDB container (extension present, no schemas) it dies with
   `psycopg2.errors.InvalidSchemaName: schema "bronze" does not exist`. The four
   layer schemas come only from `scripts/init-db.sql`, which compose mounts as
   `docker-entrypoint-initdb.d` and which runs **only on a container's first
   initialisation** — a GitHub Actions `services:` container starts fresh every
   run and therefore never gets them. The integration tests do not depend on
   alembic (their fixture does `CREATE SCHEMA IF NOT EXISTS` +
   `create_all_tables()`), but the plan's CI integration job runs `alembic
   upgrade head` first.

   **Resolution (folded into the plan, Task 8):** the integration job must apply
   `scripts/init-db.sql` (or the equivalent `CREATE EXTENSION IF NOT EXISTS
   timescaledb` + `CREATE SCHEMA IF NOT EXISTS bronze/silver/gold/metadata`
   statements) **before** `alembic upgrade head`. Recorded as a new GOTCHA in
   Task 8 and in Task 1's re-verification note.

2. **The pin cannot be verified with `docker manifest inspect` here.**
   Docker Hub is geo-blocked from this network: `docker manifest inspect`
   returns `403` ("The Amazon CloudFront distribution is configured to block
   access from your country"). Image pulls still work because
   `/etc/docker/daemon.json` sets the `docker.arvancloud.ir` registry mirror —
   but only via `docker pull`/`docker run`, **not** via `docker manifest inspect`.

   **Resolution (folded into the plan, Task 1/Task 8/D11):** verify a tag by
   **pulling it and comparing its digest against the running image's digest**.
   Doing so confirms `timescale/timescaledb:2.28.3-pg15` resolves to
   `sha256:6343bdc8…`, identical to the running image. `docker manifest inspect`
   is replaced everywhere it was used as a validation step.

Two further local-environment gotchas surfaced while resolving the pin and are
recorded in the plan's NOTES so Wave B does not rediscover them:

- `~/.docker/config.json` sets `"credsStore": "desktop"`, but
  `docker-credential-desktop` is not on `$PATH`, so `docker pull`/`docker run`
  fail with `error getting credentials`. Workaround: write `{"auths":{}}` to a
  temp dir and run with `DOCKER_CONFIG=<tmpdir>`.
- The compose service sets `PGDATA=/var/lib/postgresql/data/pgdata`, so the real
  cluster is a **subdirectory** of the `postgres_data` volume. Starting a scratch
  container against that volume **without** the same `PGDATA` silently
  initialises a second, empty cluster at the volume root instead of opening the
  real one — a mis-set `PGDATA` therefore looks like it "worked".

---

## 6. Plan corrections applied

Minimal edits only (no other plan text changed). All are traceable to Task 1.

1. **Task 8 IMPLEMENT (job) + new GOTCHA:** the integration job applies
   `scripts/init-db.sql` (or the `CREATE SCHEMA` statements) before `alembic
   upgrade head`; a fresh service container has the extension but not the four
   layer schemas.
2. **Task 1 IMPLEMENT + the Wave 0 assumption list:** the "fresh database created
   by `alembic upgrade head`" assumption corrected to record the schema
   requirement.
3. **Review-outcome bullet, Task 1, Task 8's pin/VALIDATE, D11's rationale:**
   `docker manifest inspect` (geo-blocked, 403) replaced with "pull the tag and
   compare its digest against the running image's digest".
4. **NOTES:** a Docker-gotchas entry recording the geo-blocked registry, the
   missing `docker-credential-desktop` helper, and the `PGDATA`
   volume-subdirectory trap.

---

## 7. Owner checklist (only what could not be verified)

| Item | Why unverified | Exact manual steps |
|---|---|---|
| GitHub Actions minutes/permissions and acceptance of `.github/workflows/` | A repository/account setting, not derivable from the tree | Confirm Actions is enabled for `ArshiaAsk/Iran-Macroeconomic-Data-Platform` and that adding a workflow is acceptable. |
| A GitHub Actions `services:` container can run the pinned image | Requires the runner; not testable locally | Task 6/8 create the workflow; the first `gh run watch` proves it. |
| Owner acceptance of pinning `docker-compose.yml` to the same version as CI (D11) | An owner decision | Confirm the pin; it is a no-op for the existing volume (verified here). |
| Owner acceptance of committing `poetry.lock` (D2) | An owner decision; reverses a Phase 7.2 note | Confirm Task 5 may commit the lock. |

---

## 8. Final tree state

Wave 0 changed **no production file**. The only outputs are this note and the
plan corrections in `docs/plans/phase-8-production-readiness.md`. The working
tree contains only those committed docs changes; the running container and the
`postgres_data` volume are untouched.
