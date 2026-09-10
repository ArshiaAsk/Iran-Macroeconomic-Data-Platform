# Airflow Deployment

This directory contains Apache Airflow DAGs and configuration for orchestrating the Iran Macroeconomic Data Platform's data collection pipelines.

## Structure

```
airflow/
├── config/
│   └── airflow.env          # Airflow environment configuration
├── dags/
│   ├── tgju_daily.py        # Daily TGJU scraper (23:00 Asia/Tehran)
│   └── tgju_backfill.py     # Manual backfill DAG
└── README.md                # This file
```

## Setup

### 1. Prerequisites

Ensure the PostgreSQL database is running and the `airflow_db` database exists:

```bash
# Start database
make db-up

# Create airflow_db (if not already created)
docker compose exec postgres psql -U iran_macro -d postgres -c "CREATE DATABASE airflow_db OWNER iran_macro;"
```

### 2. Initialize Airflow Database

```bash
make airflow-init
```

This will:
- Run database migrations to create Airflow metadata tables
- Display auto-generated credentials for admin and viewer users
- Show the passwords from `airflow/simple_auth_manager_passwords.json`

**Note:** Airflow 3.x uses Simple Auth Manager by default. Users are defined in configuration (`airflow/config/airflow.env`) and passwords are auto-generated on first run.

### 3. Start Airflow Services

```bash
make airflow-up
```

This starts Airflow in **standalone mode**, which includes:
- **API Server / Webserver** at http://localhost:8080
- **Scheduler** for DAG execution
- **Triggerer** for deferred operators
- **DAG Processor** for DAG parsing

### 4. Access the Web UI

Navigate to http://localhost:8080 and log in with credentials from `airflow/simple_auth_manager_passwords.json`:

To view your credentials:
```bash
cat airflow/simple_auth_manager_passwords.json
```

Or retrieve them from the init output:
```bash
make airflow-init
```

**Default users:**
- **admin**: Full permissions (role: admin)
- **viewer**: Read-only permissions (role: viewer)

### 5. Stop Airflow

```bash
make airflow-down
```

Or press **Ctrl+C** if Airflow is running in the foreground (all processes will be cleaned up automatically).

## DAGs

### `tgju_daily` - Daily FX/Gold Scraper

**Schedule:** Every day at 23:00 Asia/Tehran  
**Purpose:** Scrape TGJU daily FX and gold prices into Bronze/Silver/Gold layers

**Instruments:**
- USD/IRR exchange rate
- Emami gold coin price
- 18K gold price

**Behavior:**
- Runs automatically at 23:00 Iran time
- 3 retries with exponential backoff (5min, 15min, 30min max delay)
- `catchup=False` - no historical backfill on activation
- `max_active_runs=1` - prevents concurrent scraping

**Manual Trigger:**
```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
poetry run airflow dags trigger tgju_daily
```

### `tgju_backfill` - Historical Backfill

**Schedule:** Manual trigger only  
**Purpose:** Backfill historical TGJU data for a date range

**Configuration:**
Trigger with parameters:
```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
poetry run airflow dags trigger tgju_backfill \
  --conf '{"start_date": "2024-01-01", "end_date": "2024-12-31", "paths": "profile/price_dollar_rl,seke-emami,geram18"}'
```

**Parameters:**
- `start_date` (required): ISO8601 date (YYYY-MM-DD)
- `end_date` (required): ISO8601 date (YYYY-MM-DD)
- `paths` (optional): Comma-separated TGJU paths; defaults to all 3 instruments

**Note:** Current implementation scrapes the *current* TGJU page. True historical backfill would require archived data from web.archive.org or a third-party provider.

## Configuration

### Environment Variables

All Airflow configuration is in `airflow/config/airflow.env`:

#### Core Settings
- **`AIRFLOW_HOME`**: Absolute path to airflow directory (required for Airflow 3.x)
- **`AIRFLOW__CORE__EXECUTOR`**: `LocalExecutor` (single-machine)
- **`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`**: Separate `airflow_db` on the same PostgreSQL instance
- **`AIRFLOW__CORE__DAGS_FOLDER`**: Absolute path to DAGs directory
- **`AIRFLOW__CORE__LOAD_EXAMPLES`**: `False` (no example DAGs)
- **`AIRFLOW__CORE__DEFAULT_TIMEZONE`**: `Asia/Tehran`

#### API Configuration (Airflow 3.x)
- **`AIRFLOW__API__PORT`**: `8080` (replaces `AIRFLOW__WEBSERVER__WEB_SERVER_PORT`)
- **`AIRFLOW__API__BASE_URL`**: `http://localhost:8080`
- **`AIRFLOW__API__EXPOSE_CONFIG`**: `True`

#### DAG Processing (Airflow 3.x)
- **`AIRFLOW__DAG_PROCESSOR__REFRESH_INTERVAL`**: `30` seconds (replaces `AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL`)

#### Security
- **`AIRFLOW__CORE__FERNET_KEY`**: Generated encryption key for sensitive data
- **`AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS`**: `admin:admin,viewer:viewer` (username:role pairs)
- **`AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE`**: Path to auto-generated passwords JSON

#### Logging
- **`AIRFLOW__LOGGING__BASE_LOG_FOLDER`**: Absolute path to logs directory
- **`AIRFLOW__LOGGING__LOGGING_LEVEL`**: `INFO`

### Authentication & Authorization (Simple Auth Manager)

Airflow 3.x introduces the **Simple Auth Manager** as the default authentication system, replacing Flask-AppBuilder (FAB). This is designed for development and small-scale deployments.

#### User Management

Users are defined in the configuration file, not through CLI commands:

```bash
# In airflow/config/airflow.env
AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS=admin:admin,viewer:viewer
```

Format: `username:role,username:role,...`

Passwords are auto-generated on first Airflow startup and stored in:
```
airflow/simple_auth_manager_passwords.json
```

**To change a password:**
1. Edit the JSON file directly
2. Restart Airflow services

#### Roles

Simple Auth Manager defines four built-in roles (cannot be modified):

| Role | Permissions |
|------|-------------|
| **viewer** | Read-only access to DAGs, assets, and pools |
| **user** | viewer + edit/create/delete DAGs |
| **op** | user + manage pools, assets, config, connections, variables |
| **admin** | All permissions |

#### Adding New Users

1. Edit `airflow/config/airflow.env`:
   ```bash
   AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS=admin:admin,viewer:viewer,analyst:user
   ```

2. Restart Airflow:
   ```bash
   make airflow-down
   make airflow-up
   ```

3. Check `airflow/simple_auth_manager_passwords.json` for the new user's password.

#### Production Warning

⚠️ **Simple Auth Manager is NOT recommended for production.** It lacks:
- Role-based access control (RBAC) customization
- LDAP/OAuth integration
- Audit logging
- Multi-factor authentication

For production, use the **FAB Auth Manager provider**:
```bash
pip install apache-airflow-providers-fab
```

And configure:
```bash
AIRFLOW__CORE__AUTH_MANAGER=airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager
```

### Database Separation

Airflow's metadata tables are stored in `airflow_db`, completely separate from the platform's `iran_macro_db` (bronze/silver/gold/metadata schemas). This prevents any collision between Airflow's internal tables and the data pipeline.

### Required Dependencies

Airflow 3.x requires `asyncpg` for async database operations with PostgreSQL:

```bash
poetry add asyncpg
```

This is already included in the project's `pyproject.toml`.

## Monitoring

### Check DAG Status

```bash
make airflow-status
```

Lists all DAGs and their states.

### View Logs

```bash
make airflow-logs
```

Tails all Airflow logs. Individual task logs are also available in the web UI.

### Check Task Execution

1. Open http://localhost:8080
2. Click on a DAG (e.g., `tgju_daily`)
3. Click on a task run
4. View logs, retries, and execution details

## Failure Handling

### Retries

The `tgju_daily` DAG retries failed tasks 3 times with exponential backoff:
- Retry 1: 5 minutes delay
- Retry 2: ~15 minutes delay
- Retry 3: ~30 minutes delay (capped)

### Failure Alerts

On repeated failures (all retries exhausted), the `_on_failure_callback` logs a `CRITICAL` message. Future enhancement: integrate with email, Slack, or PagerDuty.

### Manual Recovery

If a DAG run fails:
1. Check logs in the web UI
2. Fix the underlying issue (network, database, TGJU site change)
3. Clear the failed task: **Task Instance → Clear → Yes**
4. The task will retry automatically

## Testing

### Validate DAG Structure

```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
poetry run airflow dags list
```

Should show:
```
tgju_daily
tgju_backfill
```

### Test DAG Run (Dry Run)

```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
poetry run airflow dags test tgju_daily 2026-09-08
```

Runs the DAG for a specific date without committing to the scheduler.

### Unit Tests

Unit tests for DAG imports require a full Airflow setup with initialized database. After running `make airflow-init`, tests can be run with:

```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
poetry run pytest tests/unit/airflow/test_dag_import.py -v
```

**Note:** These tests are excluded from `make test` because they require Airflow initialization.

## Process Lifecycle Management

### How Airflow Processes Are Managed

Airflow standalone mode launches multiple processes:
- API Server / Webserver
- Scheduler
- Triggerer
- DAG Processor
- Worker processes (32 per LocalExecutor)

All processes share a **process group** for coordinated lifecycle management.

### Startup

```bash
make airflow-up
```

- Creates PID file at `airflow/airflow-standalone.pid`
- Tracks the process group ID
- Runs in foreground by default
- Sets up signal handlers for clean shutdown

### Shutdown

**Option 1: Clean stop**
```bash
make airflow-down
```

**Option 2: Ctrl+C (if running in foreground)**
- Press Ctrl+C in the terminal
- All processes terminate cleanly via signal trap

**Shutdown sequence:**
1. Sends SIGTERM to all processes (graceful shutdown)
2. Waits up to 5 seconds
3. Sends SIGKILL if processes don't exit (forced kill)
4. Removes PID file

### Safety Features

- **Process group isolation**: Only kills the tracked process group
- **Graceful first**: Always tries SIGTERM before SIGKILL
- **Idempotent**: Safe to run `make airflow-down` multiple times
- **Fallback**: If PID file is missing, falls back to pattern matching

### Notes

- `make airflow-up` runs in **foreground** by default (Ctrl+C works)
- For background operation: `make airflow-up &` or use a terminal multiplexer (tmux/screen)
- PID file ensures only the correct Airflow instance is stopped
- PostgreSQL is **not** stopped by `make airflow-down` (use `make db-down` separately)

## Troubleshooting

### "ModuleNotFoundError: No module named 'asyncpg'"

Airflow 3.x requires `asyncpg` for async database operations:
```bash
poetry add asyncpg
```

### "No module named 'airflow'"

Install Airflow dependencies:
```bash
poetry install
```

### "Can't locate the AIRFLOW_HOME"

Export the environment variables:
```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
```

Or ensure `AIRFLOW_HOME` is set to an absolute path in `airflow/config/airflow.env`.

### DAG not showing in web UI

1. Check DAG folder path: `airflow/dags/`
2. Verify no Python syntax errors: `python -m py_compile airflow/dags/tgju_daily.py`
3. Check DAG processor logs in the Airflow UI
4. Refresh DAGs: Click the refresh button in the UI
5. Verify DAG is not paused (toggle the switch in the UI)

### "partially initialized module 'airflow'"

This is a circular import issue when importing DAGs outside the Airflow context. Always set `AIRFLOW_HOME` and other environment variables before importing DAGs.

### "airflow users create command not working"

Airflow 3.x uses **Simple Auth Manager** by default, which doesn't support the `airflow users create` CLI command. Users are managed through configuration in `airflow/config/airflow.env`.

To add users:
1. Edit `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS`
2. Restart Airflow
3. Check `airflow/simple_auth_manager_passwords.json` for passwords

### Timezone Issues

Airflow is configured for `Asia/Tehran` timezone. All cron schedules are interpreted in Iran time. The DAG run at 23:00 Asia/Tehran will trigger at:
- 19:30 UTC (no DST in Iran as of 2026)

### Configuration Deprecation Warnings

If you see warnings like:
```
The dag_dir_list_interval option in [scheduler] has been moved to the refresh_interval option in [dag_processor]
The web_server_port option in [webserver] has been moved to the port option in [api]
```

These are expected when migrating from Airflow 2.x config patterns. The updated config in `airflow/config/airflow.env` uses Airflow 3.x settings, but the old settings still work (with warnings).

### Database Connection Issues

Ensure the `airflow_db` database exists:
```bash
docker compose exec postgres psql -U iran_macro -d postgres -c "SELECT datname FROM pg_database WHERE datname='airflow_db';"
```

If it doesn't exist:
```bash
docker compose exec postgres psql -U iran_macro -d postgres -c "CREATE DATABASE airflow_db OWNER iran_macro;"
```

## Production Considerations

This is a **local development** deployment using `LocalExecutor`. For production:

1. **Use CeleryExecutor or KubernetesExecutor** for distributed task execution
2. **Set up proper monitoring** (Prometheus + Grafana)
3. **Configure alerting** (PagerDuty, Slack, email)
4. **Enable RBAC** with real user accounts
5. **Use secrets backend** (Vault, AWS Secrets Manager) instead of environment variables
6. **Set up log aggregation** (ELK stack, CloudWatch)
7. **Configure database backups** for Airflow metadata
8. **Use external database** (RDS, Cloud SQL) instead of local PostgreSQL

See PRD.md §8 Phase 8 (Production Readiness) for the full production roadmap.

## Further Reading

- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [LocalExecutor Configuration](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/local.html)
