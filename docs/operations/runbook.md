# Operational runbook

Day-to-day operation of the Iran Macroeconomic Data Platform: what runs on a
schedule, how to run it by hand, how to tell whether the platform is healthy, and
how to back up, migrate and benchmark it.

Every command below is runnable as written against a local stack. The
architecture is in [../architecture.md](../architecture.md); CI is in
[ci.md](ci.md); failures are in [troubleshooting.md](troubleshooting.md).

## 0. Prerequisites and pinned versions

```bash
make db-up            # start PostgreSQL + TimescaleDB (Docker Compose)
poetry install        # install dependencies
```

| Component | Pinned / expected |
|---|---|
| Database image | `timescale/timescaledb:2.28.3-pg15` (TimescaleDB 2.28.3 / PostgreSQL 15.18), digest `sha256:6343bdc8…` |
| Python | 3.11 or 3.12 (CI tests both) |
| Poetry | 2.4.1 |

Local development may publish the database on host port **5433** (the `.env`
override, because a system PostgreSQL holds 5432). CI uses 5432. Never copy a
local port number into a CI or runbook fact.

> **Fresh database gotcha.** `scripts/init-db.sql` (extension + the four schemas)
> only runs on a container's *first* initialisation. On a brand-new container,
> `alembic upgrade head` alone fails with
> `InvalidSchemaName: schema "bronze" does not exist`. See §6.

---

## 1. Maintenance calendar

The DAGs in [`airflow/dags/`](../../airflow/dags/) are the schedule. All start
`2026-09-01` in `Asia/Tehran`, `catchup=False`.

| Cadence | What | How |
|---|---|---|
| **Daily** | TGJU FX/gold scrape | `tgju_daily` — `0 23 * * *` |
| **Daily** | TSETMC TEDPIX scrape | `tsetmc_daily` — `0 23 * * *` |
| **Weekly** | SCI CPI/unemployment check | `sci_weekly` — `0 3 * * 5` (Fri 03:00) |
| **On demand** | TGJU historical backfill | `tgju_backfill` — manual only |
| **Monthly** | Review the health report for stale sources (§3) | `make health` |
| **Monthly** | Refresh a backup and verify a restore (§4) | `make backup`, `make restore …` |
| **On change** | Refresh the benchmark baseline after an intentional change (§7) | `benchmark_queries.py --write` |

API sources (World Bank, IMF, EIA) and HBSIR have no DAG — their publication
cadence is monthly-to-annual, so they are run by hand (§2) when a new release is
expected.

Start and stop the scheduler:

```bash
make airflow-init     # initialise the Airflow metadata DB (once)
make airflow-up       # run webserver + scheduler in the foreground (Ctrl+C stops)
make airflow-down     # stop from another terminal
make airflow-status   # list DAGs
```

Trigger a DAG by hand:

```bash
poetry run airflow dags trigger tgju_daily
# The backfill DAG needs a window in its conf:
poetry run airflow dags trigger tgju_backfill \
  --conf '{"start_date": "2024-01-01", "end_date": "2024-12-31"}'
```

---

## 2. Running a pipeline by hand

Each connector is a `python -m` entry point that runs discover → Bronze → Silver
→ Gold for one source. **Exit code 0 = every indicator landed; 1 = at least one
indicator failed** (failures are logged and counted, the run continues).

```bash
# Full run
poetry run python -m src.connectors.world_bank
poetry run python -m src.connectors.imf
poetry run python -m src.connectors.eia          # needs a real EIA_API_KEY
poetry run python -m src.connectors.tgju_scraper
poetry run python -m src.connectors.sci_scraper
poetry run python -m src.connectors.tsetmc       # needs the tsetmc extra
poetry run python -m src.connectors.hbsir         # needs the hbsir extra

# Fetch + report, write nothing (exercises connectivity and parsing)
poetry run python -m src.connectors.world_bank --dry-run

# Read the exit code
poetry run python -m src.connectors.world_bank; echo "exit=$?"
```

Optional extras:

```bash
poetry install --extras "tsetmc hbsir"   # package-backed connectors
```

A re-run is idempotent: Silver upserts on `(indicator_id, timestamp)`, Gold
deletes and reinserts per indicator. Gold row **ids change** across runs — never
persist one as a long-lived reference.

---

## 3. Checking health

`scripts/health_check.py` reads `metadata.data_collection_log` (latest status per
source) and the Gold coverage summary, then classifies every source and exits
with a code. It is **read-only**.

```bash
make health
# or directly:
poetry run python scripts/health_check.py
poetry run python scripts/health_check.py --json
poetry run python scripts/health_check.py --stale-after-days 3
poetry run python scripts/health_check.py --fail-on-warning
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | every source is healthy |
| `1` | at least one source is degraded / stale / empty / has no expectation |
| `2` | at least one source's latest collection run **failed** (or any warning, with `--fail-on-warning`) |

Human output is one line per source:

```text
STATUS    SOURCE         LAST OBSERVED        MISSED  DETAIL
stale     tgju           2026-09-11T00:00:00+00:00 10  success
ok        world_bank     2025-12-31T00:00:00+00:00 0   success
totals: 7 sources, 3 ok, 4 warning, 0 failed
```

`MISSED` is how many expected periods the source is behind — derived from the
catalog frequency via the dashboard's own `expected_periods` primitive, so the
CLI and the UI cannot disagree. `stale` is a warning, not a failure: a domestic
source can legitimately lag.

`--json` prints the report as JSON for a scheduler to consume. With `DEBUG=true`
in `.env` the SQLAlchemy engine echo interleaves with stdout, so for clean
machine parsing run `DEBUG=false poetry run python scripts/health_check.py --json`.

A future alerting layer wraps this script's exit code (PRD §17.1 is post-MVP).

---

## 4. Backup and restore

The database holds every bronze/silver/gold row and all metadata in one volume.
Back up with `pg_dump -Fc`; the script records the PostgreSQL and TimescaleDB
versions in a sidecar because a version mismatch is the documented cause of a
failed restore.

**Cadence:** before any migration or schema change, before a database version
bump, and on a regular schedule you choose (the plan does not prescribe one).

```bash
make backup
# → backups/iran_macro_db_<UTC>.bak  (+ .bak.meta with the versions)
#   backups/ is gitignored; a backup is never committed
```

Restore into a **scratch** database by default (the procedure follows the
TimescaleDB logical-restore order: extension → `timescaledb_pre_restore()` →
`pg_restore` → `timescaledb_post_restore()`, and **never** `-j`):

```bash
make restore BACKUP_FILE=backups/iran_macro_db_<UTC>.bak
# optional: TARGET_DB=my_scratch_db

# Restoring over the live database is refused unless --force is passed:
bash scripts/restore_db.sh backups/<name>.bak --force
```

The restore prints row counts for the five key tables and the hypertables it
found. A verified roundtrip (2026-09-22) restored
`bronze_raw=100`, `silver_cleaned=8446`, `gold_analytical=20074`,
`indicator_catalog=54`, `data_collection_log=100`, with
`gold.gold_analytical` present as a hypertable.

---

## 5. Inspecting the database

```bash
make db-check          # connection + TimescaleDB extension version
make db-shell          # psql into iran_macro_db

docker compose exec postgres psql -U iran_macro -d iran_macro_db -c \
  "SELECT hypertable_name FROM timescaledb_information.hypertables;"
```

---

## 6. Applying a migration

```bash
# On an existing database (schemas already present):
poetry run alembic upgrade head
poetry run alembic check          # fails if models and database have drifted

# Roll back one migration:
poetry run alembic downgrade -1
```

**On a fresh database**, create the extension and the four layer schemas first —
`alembic upgrade head` alone cannot (no migration contains `CREATE SCHEMA`):

```bash
make db-up
docker compose exec -T postgres psql -U iran_macro -d iran_macro_db \
  -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/init-db.sql
poetry run alembic upgrade head
```

The CI integration job applies `scripts/init-db.sql` for exactly this reason
([ci.md](ci.md)).

---

## 7. Query benchmarks and the committed baseline

`scripts/benchmark_queries.py` runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` on
the dashboard's hot queries and reports timings against the PRD's **<1 s** query
budget. **Index usage is the only hard gate** — a sequential scan on a guarded
table (`gold.gold_analytical`) exits non-zero. Timings are environment-dependent
and are reported, never gated (unless `--fail-on-regression`).

```bash
make benchmark
# or directly:
poetry run python scripts/benchmark_queries.py
poetry run python scripts/benchmark_queries.py --json
```

A normal run **does not modify** the tracked baseline; it compares against the
most recent stored run in `docs/phase-8/benchmarks.json` and prints per-query
deltas. If the environment differs materially (a different PostgreSQL/TimescaleDB
version, or a large row-count change) the comparison is labelled *environment
changed* instead of reporting a false regression. A timing change must also
exceed an absolute floor (5 ms) to count as significant, so sub-millisecond
noise does not report a permanent false regression.

**Refresh the baseline after an intentional change** (a new index, a schema
change, a database version bump) — otherwise every later run reports the same
stale regression:

```bash
poetry run python scripts/benchmark_queries.py --write   # rewrites benchmarks.json
git diff --stat docs/phase-8/benchmarks.json             # review, then commit
```

`docs/phase-8/benchmarks.json` is **committed on purpose** — it is the baseline,
not a build artifact.

---

## 8. Restarting the dashboard

```bash
make dashboard        # streamlit run dashboard/app.py (foreground; Ctrl+C stops)
```

The dashboard is read-only against Gold + metadata. The only cache is a 15-minute
freshness TTL (`FRESHNESS_CACHE_TTL_SECONDS` in `dashboard/queries.py`), so a
pipeline run may take up to that long to appear; restart the app to see it
immediately.

Dev-only screenshots (not a CI gate):

```bash
make dashboard-screenshots   # requires the app running
```

---

## 9. CI

CI runs the same gates as `make check` (minus the mutating formatter) on GitHub
Actions. See [ci.md](ci.md) for the three jobs, the required-check names, and how
to reproduce the integration job locally.

---

## Quick command index

```bash
make db-up / db-down / db-check / db-shell / db-reset
make health
make backup
make restore BACKUP_FILE=backups/<name>.bak [TARGET_DB=<scratch>]
make benchmark
make dashboard
make check                       # format + lint + typecheck + unit tests
poetry run alembic upgrade head / check
```
