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
