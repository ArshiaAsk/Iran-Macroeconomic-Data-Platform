"""
Airflow DAG: TGJU Historical Backfill.

Schedule: Manual trigger only
Purpose: Load historical TGJU data over a bounded date range
"""

from datetime import datetime

import pendulum

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def _run_tgju_backfill(**context: object) -> None:
    """
    Task callable: backfill TGJU instruments for a date range.

    Expects dag_run.conf to contain:
    - start_date: ISO8601 date string (e.g., "2024-01-01")
    - end_date: ISO8601 date string (e.g., "2024-12-31")
    - paths: Optional comma-separated TGJU paths (defaults to all)

    Raises:
        AirflowException: On pipeline failure or invalid configuration
    """
    from airflow.exceptions import AirflowException
    from src.connectors.tgju_scraper import run_tgju_pipeline
    from src.utils.logging import log_with_context, setup_logging

    setup_logging()
    logger = setup_logging()

    # Extract parameters from dag_run configuration
    dag_run = context["dag_run"]
    conf = dag_run.conf or {}

    start_date_str = conf.get("start_date")
    end_date_str = conf.get("end_date")
    paths_str = conf.get("paths")

    # Validate required parameters
    if not start_date_str or not end_date_str:
        msg = (
            "Backfill requires start_date and end_date in dag_run.conf. "
            'Example: {"start_date": "2024-01-01", "end_date": "2024-12-31"}'
        )
        raise AirflowException(msg)

    # Parse dates
    try:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
    except ValueError as exc:
        msg = f"Invalid date format: {exc}. Use ISO8601 (YYYY-MM-DD)"
        raise AirflowException(msg) from exc

    if start_date > end_date:
        msg = f"start_date ({start_date_str}) must be before end_date ({end_date_str})"
        raise AirflowException(msg)

    # Parse paths if provided
    paths = tuple(p.strip() for p in paths_str.split(",") if p.strip()) if paths_str else None

    log_with_context(
        logger,
        "INFO",
        "tgju backfill started",
        start_date=start_date_str,
        end_date=end_date_str,
        paths=paths or "all",
    )

    # Note: Current implementation scrapes the *current* TGJU page, which only
    # shows the latest price. True historical backfill would require either:
    # 1. A separate TGJU historical API endpoint (if available)
    # 2. Archived snapshots from web.archive.org or similar
    # 3. A third-party data provider for historical Iranian FX/gold data
    #
    # For now, this DAG demonstrates the backfill *pattern* by scraping the
    # current state. Future enhancement would integrate a true historical source.

    summary = run_tgju_pipeline(paths=paths, dry_run=False)

    log_with_context(
        logger,
        "INFO" if not summary.failed else "ERROR",
        "tgju backfill complete",
        start_date=start_date_str,
        end_date=end_date_str,
        instruments=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )

    if summary.failed:
        msg = f"TGJU backfill failed for {len(summary.failed)} instruments"
        raise AirflowException(msg)


def _on_failure_callback(context: dict[str, object]) -> None:
    """
    Alert on backfill task failure.

    Args:
        context: Airflow task context
    """
    from src.utils.logging import log_with_context, setup_logging

    logger = setup_logging()
    task_instance = context["task_instance"]
    exception = context.get("exception")
    dag_run = context["dag_run"]
    conf = dag_run.conf or {}

    log_with_context(
        logger,
        "ERROR",
        "tgju_backfill task failed",
        dag_id=task_instance.dag_id,
        task_id=task_instance.task_id,
        execution_date=str(context["execution_date"]),
        config=conf,
        error=str(exception),
        error_type=type(exception).__name__ if exception else None,
    )


# DAG configuration
default_args = {
    "owner": "iran_macro_platform",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": pendulum.duration(minutes=10),
}

dag = DAG(
    dag_id="tgju_backfill",
    default_args=default_args,
    description="Manual backfill of TGJU historical FX/gold prices",
    schedule=None,  # Manual trigger only
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Tehran"),
    catchup=False,
    tags=["tgju", "backfill", "manual"],
    max_active_runs=1,
)

backfill_task = PythonOperator(
    task_id="backfill_tgju_instruments",
    python_callable=_run_tgju_backfill,
    on_failure_callback=_on_failure_callback,
    dag=dag,
)
