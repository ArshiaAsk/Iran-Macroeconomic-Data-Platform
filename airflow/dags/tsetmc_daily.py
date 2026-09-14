"""
Airflow DAG: Daily TSETMC Capital-Market Index Collector.

Schedule: 23:00 Asia/Tehran (nightly, after the Tehran market closes)
Catchup: Disabled (no backfill on DAG activation)

Collects the Tehran Stock Exchange total index (TEDPIX) daily history into
Bronze/Silver/Gold, together with its derived ``RET1D``/``MA30`` and month-end
``.ME`` series. All logic lives in
``src.connectors.tsetmc.run_tsetmc_pipeline`` (which drives the shared
``SourceSpec`` / ``run_pipeline`` path); this DAG only schedules it and surfaces
failures.

The optional ``finpy-tse`` package is imported inside the task callable, never
at DAG parse time, so the DAG is importable without the extra installed.
"""

from datetime import timedelta

import pendulum

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def _run_tsetmc_collection() -> None:
    """
    Task callable: collect TSETMC daily index history into Bronze/Silver/Gold.

    Raises:
        AirflowException: On pipeline failure (one or more indicators failed)
    """
    from src.connectors.tsetmc import run_tsetmc_pipeline
    from src.utils.logging import log_with_context, setup_logging

    setup_logging()
    logger = setup_logging()

    summary = run_tsetmc_pipeline(dry_run=False)

    log_with_context(
        logger,
        "INFO" if not summary.failed else "ERROR",
        "tsetmc daily collection complete",
        indicators=len(summary.outcomes),
        succeeded=len(summary.succeeded),
        failed=len(summary.failed),
        rows_written_silver=summary.rows_written_silver,
        rows_written_gold=summary.rows_written_gold,
    )

    if summary.failed:
        # Raise so Airflow marks the task as failed and triggers retries/callbacks
        from airflow.exceptions import AirflowException

        msg = (
            f"TSETMC collection failed for {len(summary.failed)} indicator(s): "
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
        "tsetmc_daily task failed",
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
            "tsetmc_daily exhausted retries - manual intervention required",
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
    dag_id="tsetmc_daily",
    default_args=default_args,
    description="Collect TSETMC daily index history at 23:00 Asia/Tehran",
    schedule="0 23 * * *",  # Cron: every day at 23:00 Asia/Tehran
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Tehran"),
    catchup=False,  # Don't backfill historical runs on DAG activation
    tags=["tsetmc", "package", "daily", "market", "tedpix"],
    max_active_runs=1,  # Prevent concurrent runs
)

collect_task = PythonOperator(
    task_id="collect_tsetmc_index",
    python_callable=_run_tsetmc_collection,
    on_failure_callback=_on_failure_callback,
    dag=dag,
)
