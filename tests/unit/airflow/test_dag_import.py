"""
Unit tests for Airflow DAG structure and imports.

These tests validate that:
- DAGs can be imported without errors
- DAG IDs and schedules are correct
- No circular dependencies exist
- DAG structure matches specifications
"""

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def airflow_dags_path():
    """Return the path to the airflow/dags directory."""
    project_root = Path(__file__).parent.parent.parent.parent
    dags_path = project_root / "airflow" / "dags"
    assert dags_path.exists(), f"DAGs directory not found: {dags_path}"
    return dags_path


@pytest.fixture(scope="module")
def ensure_airflow_in_path(airflow_dags_path):
    """
    Add the airflow/dags directory to sys.path for DAG imports.
    
    Airflow's DagBag does this automatically, but direct imports in tests need it.
    """
    dags_str = str(airflow_dags_path)
    if dags_str not in sys.path:
        sys.path.insert(0, dags_str)
    yield
    if dags_str in sys.path:
        sys.path.remove(dags_str)


def test_tgju_daily_dag_imports_without_error(ensure_airflow_in_path):
    """Test that the tgju_daily DAG can be imported."""
    try:
        import tgju_daily  # noqa: F401
    except ImportError as exc:
        pytest.fail(f"Failed to import tgju_daily DAG: {exc}")


def test_tgju_backfill_dag_imports_without_error(ensure_airflow_in_path):
    """Test that the tgju_backfill DAG can be imported."""
    try:
        import tgju_backfill  # noqa: F401
    except ImportError as exc:
        pytest.fail(f"Failed to import tgju_backfill DAG: {exc}")


def test_tgju_daily_dag_has_correct_id(ensure_airflow_in_path):
    """Test that tgju_daily DAG has the expected dag_id."""
    import tgju_daily

    assert hasattr(tgju_daily, "dag"), "DAG object not found in tgju_daily module"
    assert tgju_daily.dag.dag_id == "tgju_daily"


def test_tgju_backfill_dag_has_correct_id(ensure_airflow_in_path):
    """Test that tgju_backfill DAG has the expected dag_id."""
    import tgju_backfill

    assert hasattr(tgju_backfill, "dag"), "DAG object not found in tgju_backfill module"
    assert tgju_backfill.dag.dag_id == "tgju_backfill"


def test_tgju_daily_dag_has_valid_schedule(ensure_airflow_in_path):
    """Test that tgju_daily DAG has a cron schedule for 23:00."""
    import tgju_daily

    assert tgju_daily.dag.schedule == "0 23 * * *", "Schedule should be 0 23 * * * (23:00 daily)"


def test_tgju_backfill_dag_is_manual_trigger_only(ensure_airflow_in_path):
    """Test that tgju_backfill DAG is manual trigger only (no schedule)."""
    import tgju_backfill

    assert tgju_backfill.dag.schedule is None, "Backfill DAG should have no schedule (manual trigger only)"


def test_tgju_daily_dag_has_catchup_disabled(ensure_airflow_in_path):
    """Test that tgju_daily DAG has catchup=False."""
    import tgju_daily

    assert tgju_daily.dag.catchup is False, "catchup should be disabled for daily DAG"


def test_tgju_daily_dag_has_expected_tags(ensure_airflow_in_path):
    """Test that tgju_daily DAG has the expected tags."""
    import tgju_daily

    expected_tags = {"tgju", "scraper", "daily", "fx", "gold"}
    actual_tags = set(tgju_daily.dag.tags or [])
    assert expected_tags.issubset(actual_tags), f"Expected tags {expected_tags}, got {actual_tags}"


def test_tgju_daily_dag_has_one_task(ensure_airflow_in_path):
    """Test that tgju_daily DAG has exactly one task."""
    import tgju_daily

    tasks = tgju_daily.dag.tasks
    assert len(tasks) == 1, f"Expected 1 task, found {len(tasks)}"
    assert tasks[0].task_id == "scrape_tgju_instruments"


def test_tgju_backfill_dag_has_one_task(ensure_airflow_in_path):
    """Test that tgju_backfill DAG has exactly one task."""
    import tgju_backfill

    tasks = tgju_backfill.dag.tasks
    assert len(tasks) == 1, f"Expected 1 task, found {len(tasks)}"
    assert tasks[0].task_id == "backfill_tgju_instruments"


def test_tgju_daily_dag_max_active_runs_is_one(ensure_airflow_in_path):
    """Test that tgju_daily DAG prevents concurrent runs."""
    import tgju_daily

    assert tgju_daily.dag.max_active_runs == 1, "max_active_runs should be 1 to prevent concurrent scraping"


def test_tgju_daily_dag_has_retries_configured(ensure_airflow_in_path):
    """Test that tgju_daily DAG has retry policy configured."""
    import tgju_daily

    default_args = tgju_daily.dag.default_args
    assert "retries" in default_args, "retries should be configured in default_args"
    assert default_args["retries"] == 3, "Expected 3 retries"
    assert "retry_delay" in default_args, "retry_delay should be configured"


def test_tgju_daily_task_has_failure_callback(ensure_airflow_in_path):
    """Test that the tgju_daily task has an on_failure_callback."""
    import tgju_daily

    task = tgju_daily.dag.tasks[0]
    assert task.on_failure_callback is not None, "Task should have on_failure_callback configured"
