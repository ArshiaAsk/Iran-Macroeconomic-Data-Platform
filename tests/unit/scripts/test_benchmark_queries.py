"""Unit tests for the benchmark helpers, against synthetic EXPLAIN plans.

No database: ``parse_explain``, ``evaluate_result``, the baseline
serialization round-trip and ``compare_runs`` / ``environment_changed`` are all
pure and are exercised with captured-shaped JSON here.
"""

import json
from pathlib import Path

import pytest

from scripts.benchmark_queries import (
    BenchmarkQuery,
    BenchmarkRun,
    QueryResult,
    compare_runs,
    environment_changed,
    evaluate_result,
    latest_run,
    load_baseline,
    parse_explain,
    serialize_baseline,
    upsert_run,
)

GUARDED = ("gold.gold_analytical",)


def plan_node(
    node_type: str,
    *,
    schema: str | None = None,
    relation: str | None = None,
    rows: int = 1,
    hit: int = 0,
    read: int = 0,
    children: list[dict] | None = None,
) -> dict:
    """One EXPLAIN plan node."""
    node: dict = {"Node Type": node_type, "Actual Rows": rows, "Plans": children or []}
    if schema is not None:
        node["Schema"] = schema
    if relation is not None:
        node["Relation Name"] = relation
    node["Shared Hit Blocks"] = hit
    node["Shared Read Blocks"] = read
    return node


def explain(
    root: dict,
    *,
    execution_ms: float = 1.0,
    planning_ms: float = 0.5,
) -> list[dict]:
    """A one-element EXPLAIN (FORMAT JSON) payload."""
    return [{"Plan": root, "Execution Time": execution_ms, "Planning Time": planning_ms}]


def result(name: str, execution_ms: float, *, index_used: bool = True) -> QueryResult:
    """A minimal stored query result."""
    return QueryResult(
        name=name,
        sql="SELECT 1",
        index_used=index_used,
        seq_scan_tables=() if index_used else ("gold.gold_analytical",),
        planning_ms=0.1,
        execution_ms=execution_ms,
        rows=1,
        shared_hit_blocks=1,
        shared_read_blocks=0,
    )


def run(commit: str, timestamp: str, queries: list[QueryResult], **env: object) -> BenchmarkRun:
    """A stored benchmark run with a default environment."""
    environment = {
        "python": "3.12.3",
        "postgres": "15.18",
        "timescaledb": "2.28.3",
        "row_counts": {"gold.gold_analytical": 20000},
        **env,
    }
    return BenchmarkRun(
        commit=commit, timestamp=timestamp, environment=environment, queries=tuple(queries)
    )


def test_parse_explain_reads_timings_rows_and_blocks() -> None:
    payload = explain(
        plan_node(
            "Index Scan",
            schema="gold",
            relation="gold_analytical",
            rows=42,
            hit=10,
            read=2,
            children=[plan_node("Index Only Scan", hit=5, read=1)],
        ),
        execution_ms=12.5,
        planning_ms=0.75,
    )
    metrics = parse_explain(payload)
    assert metrics.execution_ms == 12.5
    assert metrics.planning_ms == 0.75
    assert metrics.rows == 42
    assert metrics.shared_hit_blocks == 15
    assert metrics.shared_read_blocks == 3
    assert metrics.seq_scan_tables == ()


def test_parse_explain_finds_nested_seq_scan_with_schema() -> None:
    payload = explain(
        plan_node(
            "Hash Join",
            children=[
                plan_node("Seq Scan", schema="gold", relation="gold_analytical", rows=20000),
                plan_node("Seq Scan", schema="metadata", relation="indicator_catalog"),
            ],
        )
    )
    metrics = parse_explain(payload)
    assert metrics.seq_scan_tables == (
        "gold.gold_analytical",
        "metadata.indicator_catalog",
    )


def test_parse_explain_accepts_a_bare_plan_mapping() -> None:
    metrics = parse_explain({"Plan": plan_node("Result"), "Execution Time": 3.0})
    assert metrics.execution_ms == 3.0


@pytest.mark.parametrize("payload", [[], {"nope": 1}, "not a plan"])
def test_parse_explain_rejects_unrecognised_payloads(payload: object) -> None:
    with pytest.raises(ValueError):
        parse_explain(payload)


def test_evaluate_result_flags_a_guarded_seq_scan() -> None:
    query = BenchmarkQuery(name="load_series", sql="SELECT 1", guarded_tables=GUARDED)
    metrics = parse_explain(
        explain(plan_node("Seq Scan", schema="gold", relation="gold_analytical"))
    )
    evaluated = evaluate_result(query, metrics)
    assert evaluated.index_used is False
    assert "gold.gold_analytical" in evaluated.seq_scan_tables


def test_evaluate_result_allows_an_unguarded_seq_scan() -> None:
    # A small metadata table may legitimately be sequentially scanned.
    query = BenchmarkQuery(name="catalog_read", sql="SELECT 1", guarded_tables=())
    metrics = parse_explain(
        explain(plan_node("Seq Scan", schema="metadata", relation="indicator_catalog"))
    )
    assert evaluate_result(query, metrics).index_used is True


def test_baseline_serialization_round_trip(tmp_path: Path) -> None:
    stored = [run("abc1234", "2026-09-22T00:00:00+00:00", [result("load_series", 10.0)])]
    path = tmp_path / "benchmarks.json"
    path.write_text(serialize_baseline(stored), encoding="utf-8")

    loaded = load_baseline(path)
    assert loaded == stored
    assert json.loads(serialize_baseline(stored))["version"] == 1


def test_load_baseline_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_baseline(tmp_path / "absent.json") == []


def test_latest_run_picks_the_newest_timestamp() -> None:
    older = run("a", "2026-01-01T00:00:00+00:00", [result("q", 1.0)])
    newer = run("b", "2026-09-01T00:00:00+00:00", [result("q", 1.0)])
    assert latest_run([older, newer]) is newer
    assert latest_run([]) is None


def test_upsert_run_replaces_the_same_commit() -> None:
    first = run("abc", "2026-01-01T00:00:00+00:00", [result("q", 1.0)])
    second = run("abc", "2026-02-01T00:00:00+00:00", [result("q", 2.0)])
    other = run("def", "2026-01-15T00:00:00+00:00", [result("q", 3.0)])

    updated = upsert_run([first, other], second)
    assert len(updated) == 2
    assert {entry.commit for entry in updated} == {"abc", "def"}
    assert next(entry for entry in updated if entry.commit == "abc").timestamp == second.timestamp


def test_compare_runs_without_a_baseline_is_all_new() -> None:
    current = run("abc", "2026-09-22T00:00:00+00:00", [result("load_series", 10.0)])
    comparisons = compare_runs(current, None)
    assert [c.status for c in comparisons] == ["new"]
    assert comparisons[0].baseline_execution_ms is None


def test_compare_runs_classifies_slower_faster_and_unchanged() -> None:
    baseline = run(
        "base",
        "2026-09-01T00:00:00+00:00",
        [result("slow", 100.0), result("fast", 100.0), result("same", 100.0)],
    )
    current = run(
        "now",
        "2026-09-22T00:00:00+00:00",
        [result("slow", 150.0), result("fast", 50.0), result("same", 105.0)],
    )
    by_name = {c.name: c for c in compare_runs(current, baseline, 0.25)}
    assert by_name["slow"].status == "regression"
    assert by_name["fast"].status == "improved"
    assert by_name["same"].status == "ok"
    assert by_name["slow"].delta_pct == pytest.approx(0.5)


def test_compare_runs_ignores_sub_millisecond_noise() -> None:
    # +40% but only +0.04 ms: below the absolute floor, so not a regression.
    baseline = run("base", "2026-09-01T00:00:00+00:00", [result("q", 0.10)])
    current = run("now", "2026-09-22T00:00:00+00:00", [result("q", 0.14)])
    assert compare_runs(current, baseline, 0.25)[0].status == "ok"


def test_compare_runs_flags_lost_index_usage() -> None:
    baseline = run("base", "2026-09-01T00:00:00+00:00", [result("q", 100.0)])
    current = run("now", "2026-09-22T00:00:00+00:00", [result("q", 100.0, index_used=False)])
    comparison = compare_runs(current, baseline)[0]
    assert comparison.status == "index_lost"
    assert comparison.index_lost is True


def test_compare_runs_reports_a_new_query() -> None:
    baseline = run("base", "2026-09-01T00:00:00+00:00", [result("old", 1.0)])
    current = run("now", "2026-09-22T00:00:00+00:00", [result("added", 2.0)])
    assert compare_runs(current, baseline)[0].status == "new"


def test_environment_changed_on_a_version_bump() -> None:
    baseline = run("a", "2026-01-01T00:00:00+00:00", [result("q", 1.0)])
    current = run("b", "2026-01-02T00:00:00+00:00", [result("q", 1.0)], timescaledb="2.29.0")
    assert environment_changed(current, baseline) is True


def test_environment_changed_tolerates_small_row_growth() -> None:
    baseline = run("a", "2026-01-01T00:00:00+00:00", [result("q", 1.0)])
    current = run(
        "b",
        "2026-01-02T00:00:00+00:00",
        [result("q", 1.0)],
        row_counts={"gold.gold_analytical": 20500},
    )
    assert environment_changed(current, baseline) is False


def test_environment_changed_on_a_large_row_count_shift() -> None:
    baseline = run("a", "2026-01-01T00:00:00+00:00", [result("q", 1.0)])
    current = run(
        "b",
        "2026-01-02T00:00:00+00:00",
        [result("q", 1.0)],
        row_counts={"gold.gold_analytical": 40000},
    )
    assert environment_changed(current, baseline) is True


def test_environment_unchanged_when_identical() -> None:
    baseline = run("a", "2026-01-01T00:00:00+00:00", [result("q", 1.0)])
    current = run("b", "2026-01-02T00:00:00+00:00", [result("q", 1.0)])
    assert environment_changed(current, baseline) is False
