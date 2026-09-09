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

### 1. Initialize Airflow Database

```bash
make airflow-init
```

This will:
- Create the Airflow metadata database
- Create an admin user (username: `admin`, password: `admin`)

### 2. Start Airflow Services

```bash
make airflow-up
```

This starts:
- **Webserver** at http://localhost:8080
- **Scheduler** for DAG execution

### 3. Access the Web UI

Navigate to http://localhost:8080 and log in with:
- Username: `admin`
- Password: `admin`

### 4. Stop Airflow

```bash
make airflow-down
```

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

- **`AIRFLOW_HOME`**: `./airflow` (local deployment)
- **`AIRFLOW__CORE__EXECUTOR`**: `LocalExecutor` (single-machine)
- **`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`**: Separate `airflow_db` on the same PostgreSQL instance
- **`AIRFLOW__CORE__DAGS_FOLDER`**: `./airflow/dags`
- **`AIRFLOW__CORE__LOAD_EXAMPLES`**: `False` (no example DAGs)
- **`AIRFLOW__CORE__DEFAULT_TIMEZONE`**: `Asia/Tehran`

### Database Separation

Airflow's metadata tables are stored in `airflow_db`, completely separate from the platform's `iran_macro_db` (bronze/silver/gold/metadata schemas). This prevents any collision between Airflow's internal tables and the data pipeline.

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

## Troubleshooting

### "No module named 'airflow'"

Install Airflow dependencies:
```bash
poetry install --extras airflow
```

### "Can't locate the AIRFLOW_HOME"

Export the environment:
```bash
export $(cat airflow/config/airflow.env | grep -v '^#' | xargs)
```

### DAG not showing in web UI

1. Check DAG folder path: `airflow/dags/`
2. Verify no Python syntax errors: `python -m py_compile airflow/dags/tgju_daily.py`
3. Refresh DAGs in web UI or restart scheduler

### "partially initialized module 'airflow'"

This is a circular import issue when importing DAGs outside the Airflow context. Always set `AIRFLOW_HOME` and other environment variables before importing DAGs.

### Timezone Issues

Airflow is configured for `Asia/Tehran` timezone. All cron schedules are interpreted in Iran time. The DAG run at 23:00 Asia/Tehran will trigger at:
- 19:30 UTC (no DST in Iran as of 2026)

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
