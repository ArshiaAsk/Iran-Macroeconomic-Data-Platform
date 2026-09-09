"""
Airflow DAG: Daily TGJU FX/Gold Price Scraper.

Schedule: 23:00 Asia/Tehran (nightly, after markets close)
Catchup: Disabled (no backfill on DAG activation)
"""

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def _run_tgju_scrape() -> None:
    """
    Task callable: scrape TGJU instruments into Bronze/Silver/Gold.

    Raises:
        AirflowException: On pipeline failure (non-zero exit)
    """
    from src.connectors.tgju_scraper import run_tgju_pipeline
    from src.utils.logging import log_with_context, setup_logging

    setup_logging()
    logger = setup_logging()

    summary = run_tgju_pipeline(dry_run=False)

    log_with_context(
        logger,
        "INFO" if not summary.failed else "ERROR",
        "tgju daily scrape complete",
        instruments=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )

    if summary.failed:
        # Raise so Airflow marks the task as failed and triggers retries/callbacks
        from airflow.exceptions import AirflowException

        raise AirflowException(
            f"TGJU scrape failed for {len(summary.failed)} instruments: "
            f"{[o.indicator_id for o in summary.failed]}"
        )


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
        "tgju_daily task failed",
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
            "tgju_daily exhausted retries - manual intervention required",
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
    dag_id="tgju_daily",
    default_args=default_args,
    description="Scrape TGJU daily FX/gold prices at 23:00 Asia/Tehran",
    schedule="0 23 * * *",  # Cron: every day at 23:00
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Tehran"),
    catchup=False,  # Don't backfill historical runs on DAG activation
    tags=["tgju", "scraper", "daily", "fx", "gold"],
    max_active_runs=1,  # Prevent concurrent runs
)

scrape_task = PythonOperator(
    task_id="scrape_tgju_instruments",
    python_callable=_run_tgju_scrape,
    on_failure_callback=_on_failure_callback,
    dag=dag,
)
