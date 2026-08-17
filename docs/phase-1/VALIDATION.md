# Phase 1 Validation Checklist

**Status:** ✅ VALIDATED — executed end to end on August 17, 2026.

Every command below was actually run against a live PostgreSQL + TimescaleDB
instance. The "Result" blocks record the real output, not the expected output.

## Verified Environment

| Component | Version |
|-----------|---------|
| Poetry | 2.4.1 |
| Python | 3.12.3 |
| Docker | 29.2.0 |
| Docker Compose | v2.40.3 |
| PostgreSQL | 15.18 |
| TimescaleDB | 2.28.3 |
| SQLAlchemy | 2.0.52 |
| Alembic | 1.19.1 |
| Pydantic | 2.13.4 |
| pandas | 2.3.3 |
| ruff | 0.1.15 |
| mypy | 1.20.2 |
| pytest | 7.4.4 |

## Prerequisites

1. Install Poetry:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Install Docker with the Compose plugin: https://docs.docker.com/get-docker/

3. Create your environment file:
   ```bash
   cp .env.template .env
   ```

### Two environment notes that will bite you

**Docker context.** If Docker Desktop is installed but not running, the CLI may
still point at its socket and every `docker` command fails with
`Cannot connect to the Docker daemon at unix:///…/.docker/desktop/docker.sock`.
Check with `docker context ls`. To use the system daemon for one command without
permanently switching your context:

```bash
DOCKER_CONTEXT=default make db-up
```

**Port 5432 conflict.** If a system PostgreSQL already owns 5432, the container
cannot bind and you get `address already in use`. The compose host port is
overridable, so pick a free port in `.env` instead of stopping your system
database:

```bash
DATABASE_PORT=5433
DATABASE_URL=postgresql://iran_macro:iran_macro_pass@localhost:5433/iran_macro_db
```

## Validation Steps

### Level 1: Environment Setup

```bash
poetry --version
docker --version
docker compose version
```

Expected: all three return version numbers. Note `docker compose` (plugin
subcommand), not the retired standalone `docker-compose` binary.

✅ **Result:** Poetry 2.4.1, Docker 29.2.0, Compose v2.40.3.

### Level 2: Install Dependencies

```bash
poetry install
```

✅ **Result:** all dependencies resolved and installed. Use `poetry run <cmd>`
to execute inside the environment (`poetry shell` is a plugin in Poetry 2.x).

### Level 3: Code Quality Checks

```bash
make format
make lint
make typecheck
```

✅ **Result:**
- `ruff format` — clean, 30 files left unchanged.
- `ruff check` — 0 errors.
- `mypy --strict` — `Success: no issues found in 13 source files`.

### Level 4: Start Docker Services

```bash
make db-up
make db-check
```

✅ **Result:**
```
✓ Database connection successful
 timescaledb | 2.28.3
✓ TimescaleDB extension installed
```

Container `iran_macro_postgres` is `Up (healthy)`, published on
`0.0.0.0:5433->5432/tcp`.

### Level 5: Database Migrations

The initial migration is committed as
`alembic/versions/20260817_1456_initial_schema.py` (revision `9a0d7ad75b18`),
so you only need to apply it:

```bash
poetry run alembic upgrade head
```

To regenerate from scratch instead, drop the file and run
`poetry run alembic revision --autogenerate -m "Initial schema"`.

Verify:

```bash
docker compose exec postgres psql -U iran_macro -d iran_macro_db \
  -c "SELECT table_schema, table_name FROM information_schema.tables
      WHERE table_schema IN ('bronze','silver','gold','metadata') ORDER BY 1,2;" \
  -c "SELECT hypertable_name, num_dimensions, compression_enabled
      FROM timescaledb_information.hypertables;"
```

✅ **Result:** 7 tables in the 4 owned schemas:

| Schema | Table |
|--------|-------|
| bronze | `bronze_raw` |
| silver | `silver_cleaned` |
| gold | `gold_analytical` |
| metadata | `indicator_catalog` |
| metadata | `data_collection_log` |
| metadata | `transformation_log` |
| metadata | `chain_linking_log` |

`gold.gold_analytical` is a hypertable with 1 time dimension and
`compression_enabled = true`, and the compression policy job is registered:

```
     proc_name      |             config
--------------------+--------------------------------
 policy_compression | {"compress_after": "6 mons"}
```

(`job_id` and `hypertable_id` are sequence-assigned, so they differ on every
re-provision — only `proc_name` and `compress_after` are stable.)

Two further checks were run:

```bash
poetry run alembic check                                   # model vs database drift
poetry run alembic downgrade base && poetry run alembic upgrade head   # roundtrip
```

✅ **Result:** `No new upgrade operations detected.` The downgrade drops all 7
tables and the re-upgrade restores them plus the hypertable and its compression
policy, leaving the DB at `9a0d7ad75b18 (head)`.

### Level 6: Run Tests

```bash
make test              # unit only — the default gate
make test-integration  # requires Docker
make test-all          # unit + integration
```

✅ **Result:**

| Target | Tests | Coverage |
|--------|-------|----------|
| `make test` | 40 passed, 13 deselected | 86.68% |
| `make test-integration` | 13 passed | n/a (see below) |
| `make test-all` | 53 passed | 95.30% |

The 80% coverage gate measures the project as a whole, so `make test-integration`
runs with `--cov-fail-under=0` — an integration-only subset legitimately does not
exercise the unit-tested modules and must not be judged by the global threshold.
`make test` and `make test-all` both enforce the gate.

### Level 7: Full Validation

```bash
make check
```

✅ **Result:** all four gates pass — `format`, `lint`, `typecheck`, `test`
(40 passed, 86.68% coverage, threshold 80%).

## Manual Verification

### 1. Database Connection

```bash
make db-shell
```

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';
\dn
\dt bronze.*
\dt silver.*
\dt gold.*
\dt metadata.*
\q
```

### 2. Configuration Test

```bash
poetry run python -c "from src.utils.config import get_config; print(get_config().database.url)"
```

✅ **Result:** prints the assembled URL, honouring `DATABASE_PORT` from `.env`.

## Troubleshooting

### Poetry not found after installation

```bash
export PATH="$HOME/.local/bin:$PATH"   # add to ~/.bashrc or ~/.zshrc
```

### `poetry shell` reports an unknown command

Poetry 2.x moved `shell` to a plugin. Prefix commands with `poetry run`, or
install the plugin: `poetry self add poetry-plugin-shell`.

### Cannot connect to the Docker daemon

See "Docker context" above — prefix with `DOCKER_CONTEXT=default`.

### Port already in use

See "Port 5432 conflict" above — set `DATABASE_PORT` in `.env`.

### Database connection issues

```bash
docker compose logs postgres
make db-down && make db-up
```

### Test failures after a dependency change

```bash
poetry install --sync
make clean
```

## Acceptance Criteria

All Phase 1 criteria are met **and verified by execution**:

- [x] Poetry project initialized, all dependencies installed
- [x] Docker Compose starts PostgreSQL 15.18 + TimescaleDB 2.28.3
- [x] Database connection works from Python
- [x] 4-layer schema models created (Bronze/Silver/Gold/Metadata)
- [x] TimescaleDB hypertable live on `gold.gold_analytical` with compression
- [x] Alembic migration generated, applied, and roundtrip-tested
- [x] `alembic check` reports no model/database drift
- [x] `DataConnector` abstract base class defined
- [x] Custom exception hierarchy implemented
- [x] Validation framework with quality checks
- [x] Logging configuration with JSON formatting
- [x] Configuration management with Pydantic
- [x] pytest framework with fixtures and markers
- [x] ruff (0 errors), mypy strict (0 errors), pytest all passing
- [x] Makefile provides common commands
- [x] README.md documents setup and usage
- [x] Unit tests pass — 40 tests, 86.68% coverage
- [x] Integration tests implemented and passing — 13 tests
- [x] `make check` passes all quality gates

## Next Steps (Phase 2)

1. Implement World Bank API connector
2. Implement TGJU scraper
3. Test end-to-end Bronze → Silver → Gold flow
4. Create data dictionary
5. Document connector patterns
