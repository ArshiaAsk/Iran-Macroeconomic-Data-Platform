# CI operations

The project's continuous integration runs on GitHub Actions from a single
workflow, [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml). It tests
the platform; it never deploys (the platform is local-only — see `AGENTS.md`).

## Pinned database image

Both the local Compose stack and the CI integration job run the **same pinned**
TimescaleDB image:

```text
timescale/timescaledb:2.28.3-pg15
resolved digest: sha256:6343bdc87ca132c6b53acb26113a6bad1821d188fa39975a745f32ddd9757634
```

- `docker-compose.yml` (`services.postgres.image`) — local development.
- `.github/workflows/ci.yml` (`jobs.integration.services.postgres.image`) — CI.

The pin was chosen because the platform is validated against **TimescaleDB
2.28.3 on PostgreSQL 15.18** (the running extension and server version), and a
floating `latest-pg15` tag would let local, CI and any future environment
silently diverge. A TimescaleDB minor upgrade changes extension behaviour and the
dump/restore contract, so a bump must change **both** files together and be
followed by a `scripts/benchmark_queries.py --write` baseline refresh (query
plans can move).

Verify the pin without Docker Hub's manifest API (which is geo-blocked in some
networks): pull the tag and compare its digest against the running image's.

```bash
docker pull timescale/timescaledb:2.28.3-pg15
docker inspect --format '{{index .RepoDigests 0}}' timescale/timescaledb:2.28.3-pg15
docker inspect --format '{{index .RepoDigests 0}}' timescale/timescaledb:latest-pg15
```

## Fresh service container: schemas are not created for you

A GitHub Actions `services:` container starts from an empty volume on every run,
so `scripts/init-db.sql` (mounted via `docker-entrypoint-initdb.d` locally) never
runs. No migration contains `CREATE SCHEMA`, so `alembic upgrade head` would fail
with `InvalidSchemaName: schema "bronze" does not exist`. The integration job
therefore applies `scripts/init-db.sql` (extension + the four layer schemas)
**before** running the migrations.

## The three jobs

The workflow defines three jobs. Their check names (what the Actions UI and any
branch-protection rule see) are:

| Job id | Check name | Runs |
|---|---|---|
| `static` | `Static gates (ruff, mypy)` | `ruff check`, `ruff format --check`, `mypy src dashboard` on Python 3.12 |
| `unit` | `Unit tests (Python 3.11)` and `Unit tests (Python 3.12)` | the unit suite; the 80% coverage gate runs on the 3.12 leg only |
| `integration` | `Integration tests (pinned TimescaleDB)` | the 132 DB-backed integration tests against the pinned service container |

## Running the jobs locally

Every job is a thin wrapper over commands that already exist as `make` targets,
so CI is reproducible by hand.

```bash
# static
poetry run ruff check .
poetry run ruff format --check .      # non-mutating; `make format` rewrites in place
poetry run mypy src dashboard

# unit (the coverage gate is the default addopts)
poetry run pytest -m "not integration"             # 3.12 leg: --cov=src --cov=dashboard --cov-fail-under=80
poetry run pytest -m "not integration" --no-cov    # 3.11 leg: same tests, coverage disabled
```

## Reproducing the integration job without CI

The CI integration step differs from `make test-integration` in two deliberate
ways: it excludes the `live`-marked network tests (which are gated on
`RUN_LIVE_API_TESTS` and would otherwise register as expected skips) and it
asserts that **nothing skipped**. Reproduce it exactly with:

```bash
make db-up
poetry run alembic upgrade head
poetry run pytest -m "integration and not live" -q \
  --cov-fail-under=0 --junitxml=integration-report.xml
```

Then confirm no test skipped — a skip means the database was unreachable and the
run proved nothing:

```bash
python - <<'PY'
import xml.etree.ElementTree as ET

root = ET.parse("integration-report.xml").getroot()
skipped = [c for c in root.iter("testcase") if c.find("skipped") is not None]
raise SystemExit(f"{len(skipped)} skipped — investigate the database" if skipped else "OK")
PY
```

Expected: **132 passed, 0 skipped** against a migrated database. The marker
expression deliberately does not scope to `tests/integration/`, because one
integration-marked export test lives under `tests/unit/dashboard/`; a path-scoped
run would collect only 131.

## Required checks and branch protection (owner action)

Branch protection is a **repository setting, not a file** — only the repository
owner can enable it, and this workflow does not do so. If protection is desired
for `main`, the owner should require these checks (the four expanded names above)
and require the branch to be up to date before merging:

```bash
# Owner only. Names must match the job `name:` values in the workflow.
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Static gates (ruff, mypy)",
      "Unit tests (Python 3.11)",
      "Unit tests (Python 3.12)",
      "Integration tests (pinned TimescaleDB)"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON

# Verify (returns 404 until the owner has enabled it):
gh api repos/:owner/:repo/branches/main/protection
```

Until the owner enables it, CI still runs on every push to `main` and every pull
request — the checks are simply advisory rather than blocking.
