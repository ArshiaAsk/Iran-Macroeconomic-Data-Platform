"""
Airflow DAG: Weekly SCI Domestic Statistics Scraper.

Schedule: Friday 03:00 Asia/Tehran (weekend, low domestic traffic)
Catchup: Disabled (no backfill on DAG activation)

Collects the Statistical Center of Iran (SCI) headline/decile consumer price
index (monthly) and unemployment rate (quarterly) publications into
Bronze/Silver/Gold. SCI releases on a monthly cadence, so a weekly check keeps
the platform within a few days of a new publication without stressing the
source. All logic lives in ``src.connectors.sci_scraper.run_sci_pipeline``; this
DAG only schedules it and surfaces failures.
"""

from datetime import timedelta

import pendulum

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def _run_sci_scrape() -> None:
    """
    Task callable: scrape SCI publications into Bronze/Silver/Gold.

    Raises:
        AirflowException: On pipeline failure (one or more publications failed)
    """
    from src.connectors.sci_scraper import run_sci_pipeline
    from src.utils.logging import log_with_context, setup_logging

    setup_logging()
    logger = setup_logging()

    summary = run_sci_pipeline(dry_run=False)

    log_with_context(
        logger,
        "INFO" if not summary.failed else "ERROR",
        "sci weekly scrape complete",
        publications=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )

    if summary.failed:
        # Raise so Airflow marks the task as failed and triggers retries/callbacks
        from airflow.exceptions import AirflowException

        msg = (
            f"SCI scrape failed for {len(summary.failed)} publication(s): "
            f"{[o.indicator_id for o in summary.failed]}"
        )
        raise AirflowException(msg)


def _on_failure_callback(context: dict[str, object]) -> None:
    """
    Alert on repeated task failures.

    Args:
        context: Airflow task context with exception, try_number, etc.
    """
    from src.utils.logging import log_with_context, setup_logging

    logger = setup_logging()
    task_instance = context["task_instance"]
    exception = context.get("exception")

    log_with_context(
        logger,
        "ERROR",
        "sci_weekly task failed",
        dag_id=task_instance.dag_id,
        task_id=task_instance.task_id,
        execution_date=str(context["execution_date"]),
        try_number=task_instance.try_number,
        max_tries=task_instance.max_tries,
        error=str(exception),
        error_type=type(exception).__name__ if exception else None,
    )

    # On repeated failures (exhausted retries), escalate the alert
    if task_instance.try_number >= task_instance.max_tries:
        log_with_context(
            logger,
            "CRITICAL",
            "sci_weekly exhausted retries - manual intervention required",
            dag_id=task_instance.dag_id,
            task_id=task_instance.task_id,
            tries=task_instance.try_number,
        )
        # Future: integrate with alerting system (email, Slack, PagerDuty)


# DAG configuration
default_args = {
    "owner": "iran_macro_platform",
    "depends_on_past": False,
    "email_on_failure": False,  # TODO: Enable when email is configured
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
}

dag = DAG(
    dag_id="sci_weekly",
    default_args=default_args,
    description="Scrape SCI CPI/unemployment publications weekly at 03:00 Asia/Tehran",
    schedule="0 3 * * 5",  # Cron: Fridays at 03:00 (Iranian weekend, low traffic)
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Tehran"),
    catchup=False,  # Don't backfill historical runs on DAG activation
    tags=["sci", "scraper", "weekly", "cpi", "unemployment"],
    max_active_runs=1,  # Prevent concurrent runs
)

scrape_task = PythonOperator(
    task_id="scrape_sci_publications",
    python_callable=_run_sci_scrape,
    on_failure_callback=_on_failure_callback,
    dag=dag,
)
