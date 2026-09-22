# Troubleshooting guide

Concrete, reachable failures on this platform, each as **symptom → diagnosis →
fix**. Every fix cites the evidence it is based on (a command, a file, or a phase
record). The runbook is [runbook.md](runbook.md); the architecture is
[../architecture.md](../architecture.md).

The dashboard's own Troubleshooting section in the README is the short version of
scenarios 1–4; this is the expanded, linked guide.

---

## 1. Every `docker` command fails: `Cannot connect to the Docker daemon`

**Symptom**

```text
Cannot connect to the Docker daemon at unix:///…/docker.sock. Is the docker daemon running?
```

**Diagnosis.** A stopped Docker Desktop can leave the CLI pointed at its socket,
even when a system daemon is running. Check which context is active:

```bash
docker context ls
```

**Fix.** Use the system daemon for the command:

```bash
DOCKER_CONTEXT=default make db-up
```

Or switch the context for the session. This is documented in
[`README.md`](../../README.md) (Quick Start / Troubleshooting) and
[`AGENTS.md`](../../AGENTS.md).

---

## 2. `make db-up` starts but the database is unreachable on 5432

**Symptom.** `make db-up` succeeds, but `make db-check` or `alembic upgrade head`
fails to connect; or the container exits because port 5432 is already bound.

**Diagnosis.** A system PostgreSQL already holds port 5432. The compose file maps
`${DATABASE_PORT:-5432}:5432`, so the container can coexist on another host port,
but the client must use the same port.

```bash
docker compose ps        # check the published host port
```

**Fix.** Set a free host port in `.env` and update the URL to match:

```bash
DATABASE_PORT=5433
DATABASE_URL=postgresql://iran_macro:iran_macro_pass@localhost:5433/iran_macro_db
```

Then `make db-up`. This is the reason the local environment in the Phase 8 record
publishes **5433** while CI uses the default 5432
([`docs/phase-8/wave-0-spike.md`](../phase-8/wave-0-spike.md)).

---

## 3. Integration tests skip instead of running (a silent green)

**Symptom.** `poetry run pytest -m integration` reports `skipped`, not `passed`,
and exits 0.

**Diagnosis.** The integration fixture calls `pytest.skip` when PostgreSQL is
unreachable (`tests/integration/test_database.py:53`), so a run with no database
**passes while testing nothing**.

```bash
poetry run pytest -m integration -q -rs      # -rs shows the skip reasons
```

**Fix.** Start the database and re-run:

```bash
make db-up
poetry run pytest -m integration -q --cov-fail-under=0
```

CI defends against this explicitly: the integration job asserts **zero skips**
via a JUnit-XML check and fails otherwise ([ci.md](ci.md)). The `live`-marked
network tests are expected skips and are excluded from that job.

---

## 4. `TimescaleDB extension not found`

**Symptom.** `make db-check` prints:

```text
✗ TimescaleDB extension not found
```

or a query fails with `type "hypertable" does not exist`.

**Diagnosis.** The image ships the extension but it is not created in *this*
database. On a fresh container, `scripts/init-db.sql` only runs on the first
initialisation.

**Fix.**

```bash
docker compose exec postgres psql -U iran_macro -d iran_macro_db \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
make db-check
```

See [`scripts/init-db.sql`](../../scripts/init-db.sql) and
[`docs/architecture.md`](../architecture.md#7-databases-versions-and-the-fresh-database-gotcha).

---

## 5. `alembic upgrade head` fails: `schema "bronze" does not exist`

**Symptom**

```text
psycopg2.errors.InvalidSchemaName: schema "bronze" does not exist
```

**Diagnosis.** No migration contains `CREATE SCHEMA`; the four layer schemas come
from `scripts/init-db.sql`, which runs only on a container's first init. On a
fresh database the migration has nothing to create tables in.

**Fix.** Create the extension and schemas before migrating (exactly what the CI
integration job does):

```bash
docker compose exec -T postgres psql -U iran_macro -d iran_macro_db \
  -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/init-db.sql
poetry run alembic upgrade head
```

Evidence: [`docs/phase-8/wave-0-spike.md`](../phase-8/wave-0-spike.md) §5,
assumption 1.

---

## 6. `alembic check` reports drift

**Symptom.** `poetry run alembic check` reports new upgrade operations (when
clean it prints `No new upgrade operations detected.`).

**Diagnosis.** The SQLAlchemy models and the database have diverged — a model was
changed without a migration.

**Fix.** Generate a migration, review it, and apply it:

```bash
poetry run alembic revision --autogenerate -m "Describe the change"
poetry run alembic upgrade head
poetry run alembic check
```

If the reported change is a TimescaleDB-managed index, add it to
`TIMESCALE_MANAGED_INDEXES` in `alembic/env.py` instead of letting it show up as
a spurious drop ([`AGENTS.md`](../../AGENTS.md), Database Conventions).

---

## 7. A scraper breaks: `ParsingError`

**Symptom.** A TGJU/SCI run exits non-zero with a `ParsingError`, or a series
lands with no new rows.

**Diagnosis.** Domestic sites change their HTML/structure without notice; a
selector no longer matches. Check the raw HTML first — Bronze keeps it:

```sql
SELECT raw_data -> 'rows' -> 0 ->> 'html'
FROM bronze.bronze_raw
WHERE source_name = 'tgju'
ORDER BY collection_timestamp DESC LIMIT 1;
```

**Fix.** Capture the new HTML as a fixture, update the parser selectors, and add
a regression test with old + new fixtures. Scrapers and parsers are separate
modules (`tgju_scraper.py` + `tgju_parser.py`) precisely so the parser is
unit-testable with fixture HTML and no browser ([`AGENTS.md`](../../AGENTS.md),
Scraper-Specific Patterns).

---

## 8. A value fails to parse: Persian digits or a Jalali date

**Symptom.** `ParsingError` on a price or date, or an implausible value (e.g.
`۱٬۲۳۴` read as a number).

**Diagnosis.** TGJU/SCI publish Persian (Farsi) digits (`۰۱۲۳۴۵۶۷۸۹`) and Jalali
(`YYYY/MM/DD`) dates. Values must be normalised before parsing and converted to
Gregorian UTC for storage.

**Fix.** Use the shared helpers in
[`src/utils/persian.py`](../../src/utils/persian.py) — `normalise_digits`,
`parse_price`, `jalali_to_gregorian` — rather than re-implementing conversion.
Verify a conversion in isolation:

```bash
poetry run python -c "from src.utils.persian import normalise_digits, parse_price; \
print(normalise_digits('۱٬۲۳۴'), parse_price('۱٬۲۳۴'))"
```

Original Persian values are kept in row metadata for auditability.

---

## 9. A source shows no data at all (`no_data` in the health check)

**Symptom.** `make health` reports a source as `no_data`, or the dashboard shows
an empty chart.

**Diagnosis.** The catalog names the source but no Gold observation exists — the
source has never run successfully, or its run produced no usable rows (nulls are
skipped, never imputed).

```bash
poetry run python scripts/health_check.py --json
docker compose exec postgres psql -U iran_macro -d iran_macro_db -c \
  "SELECT status, records_collected, error_message FROM metadata.data_collection_log \
   WHERE source_name = '<source>' ORDER BY collection_timestamp DESC LIMIT 5;"
```

**Fix.** Run the source's pipeline by hand (§2 of the runbook) and inspect the
run. If the source is genuinely deferred (OPEC, CBI, part of TSETMC), it will not
appear in the catalog at all — see the limitations index in
[../architecture.md](../architecture.md#connector-status-and-limitations).

---

## 10. A source is `stale` in the health check

**Symptom.** `make health` reports a source as `stale` with a non-zero `MISSED`
count.

**Diagnosis.** The source's last Gold observation is more than its expected
number of periods old. `MISSED` is derived from the catalog frequency via the
dashboard's `expected_periods` primitive — the same rule the UI uses — so this is
not a second, hand-rolled threshold.

**Fix.** Check the source's own publication cadence first: a monthly source
(`sci`) lagging by one period may simply not have published yet. Then re-run the
pipeline. To re-check with an explicit day threshold (a temporary override, not a
new rule):

```bash
poetry run python scripts/health_check.py --stale-after-days 3
```

A `stale` result is a **warning** (exit 1), not a failure. If you want any
degradation to be fatal for a scheduler, pass `--fail-on-warning` (exit 2).

---

## 11. Restore fails: the extension is missing on the target

**Symptom.** `pg_restore` errors on TimescaleDB catalog objects, or
`timescaledb_pre_restore()` fails.

**Diagnosis.** The `timescaledb` extension must exist on the target **before**
`timescaledb_pre_restore()` and `pg_restore`. A missing extension is the
documented restore failure.

**Fix.** Use `scripts/restore_db.sh`, which enforces the documented order
(`CREATE DATABASE` → `CREATE EXTENSION IF NOT EXISTS timescaledb` →
`timescaledb_pre_restore()` → `pg_restore` → `timescaledb_post_restore()`) and
never passes `-j`:

```bash
make restore BACKUP_FILE=backups/<name>.bak
```

If you restore by hand, run the `CREATE EXTENSION` step first. See
[`scripts/restore_db.sh`](../../scripts/restore_db.sh) and the TimescaleDB
logical-restore procedure.

---

## 12. The dashboard shows stale data after a pipeline run

**Symptom.** A pipeline has completed, but a dashboard page still shows the old
value.

**Diagnosis.** The dashboard caches the freshness query for
`FRESHNESS_CACHE_TTL_SECONDS` (900 s = 15 min) in
[`dashboard/queries.py`](../../dashboard/queries.py). A run within that window is
not yet visible.

**Fix.** Wait up to 15 minutes, or restart the dashboard to see it immediately:

```bash
make dashboard     # Ctrl+C, then re-run
```

A manual cache-refresh control is a deferred item, not implemented.

---

## 13. The benchmark reports a regression that is really an environment change

**Symptom.** `make benchmark` prints a `REGRESSION` or the timings look far
worse than the baseline.

**Diagnosis.** Timing is environment-dependent. If the PostgreSQL/TimescaleDB
version or a table's row count changed materially, the timings are not
comparable. The script detects this and labels the comparison
**environment changed** instead of a regression; a timing change must also exceed
the 5 ms `REGRESSION_MIN_MS` floor to be called significant, so sub-millisecond
noise does not trigger a false regression.

**Fix.** Read the label in the report:

```bash
make benchmark
```

- If it says *environment changed*, the timings were not compared — re-run in the
  matching environment, or refresh the baseline if the change is intentional.
- If it is a genuine regression after an intentional change (a new index, a
  schema change, a database version bump), refresh the committed baseline:

```bash
poetry run python scripts/benchmark_queries.py --write
```

Only **lost index usage** (a sequential scan on `gold.gold_analytical`) is a hard
failure, and it is never a false positive from timing noise. See
[`scripts/benchmark_queries.py`](../../scripts/benchmark_queries.py) and
[runbook §7](runbook.md#7-query-benchmarks-and-the-committed-baseline).

---

## 14. CI integration job is red but the database is fine

**Symptom.** The `Integration tests (pinned TimescaleDB)` job fails while the
same tests pass locally.

**Diagnosis.** The job excludes `live`-marked network tests and **fails if any
test skips** — a skip means the service container was unreachable, so the run
proved nothing. The marker expression also deliberately does not scope to
`tests/integration/`, because one integration-marked export test lives under
`tests/unit/dashboard/`.

**Fix.** Reproduce it locally exactly ([ci.md](ci.md)):

```bash
make db-up
poetry run alembic upgrade head
poetry run pytest -m "integration and not live" -q \
  --cov-fail-under=0 --junitxml=integration-report.xml
```

Expected: **132 passed, 0 skipped**. If the job failed on the schema step, see
scenario 5.
