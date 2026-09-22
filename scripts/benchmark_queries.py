"""Benchmark the dashboard's hot queries and compare against a stored baseline.

Usage::

    poetry run python scripts/benchmark_queries.py
    poetry run python scripts/benchmark_queries.py --write
    poetry run python scripts/benchmark_queries.py --regression-threshold 0.5 --fail-on-regression

Each run executes ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` on the dashboard's
hot read paths and reports, per query, the planning/execution time, rows and
buffer usage. **Index usage is the only hard gate**: a sequential scan on a
guarded table (``gold.gold_analytical``) makes the run exit non-zero. Timings
are environment-dependent, so they are *reported* and compared against the
stored baseline, never gated — unless ``--fail-on-regression`` is passed.

``--write`` persists the run to :data:`DEFAULT_BASELINE_PATH`
(``docs/phase-8/benchmarks.json``, committed on purpose: it is the baseline, not
a build artifact). A normal run never mutates that file. A later run loads the
most recent stored run and prints a per-query delta; when the environment
differs materially (a different PostgreSQL/TimescaleDB version, or a large row
count change) the comparison is labelled "environment changed" instead of
reporting a false regression.

Refresh the baseline with ``--write`` after an intentional change (a new index,
a schema change, a database version bump) or every later run reports the same
stale regression.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from src.database.connection import get_db, init_database
from src.utils.config import get_config

DEFAULT_BASELINE_PATH: Final[Path] = Path("docs/phase-8/benchmarks.json")
DEFAULT_REGRESSION_THRESHOLD: Final[float] = 0.25

#: PRD §14.1: "Queries return in <1 second." Reported, never gated.
QUERY_BUDGET_MS: Final[float] = 1000.0

#: The guarded tables: a sequential scan on one of these is unexpected for a
#: filtered query and is the only hard failure. Small metadata tables may
#: legitimately seq-scan.
GUARDED_TABLES: Final[tuple[str, ...]] = ("gold.gold_analytical",)

#: A row-count difference larger than this share counts as an environment
#: change. Data grows between runs, so an exact match is not required; a large
#: shift (a reload, a new source) means the timings are not comparable.
ROW_COUNT_TOLERANCE: Final[float] = 0.10

#: Absolute floor for a timing regression. Sub-millisecond queries move by tens
#: of percent run to run, so a percentage alone would report a permanent false
#: regression on noise (the plan's stale-baseline risk); a change must also
#: exceed this many milliseconds to be called significant.
REGRESSION_MIN_MS: Final[float] = 5.0

#: Row counts recorded with every run.
COUNTED_TABLES: Final[tuple[str, ...]] = (
    "bronze.bronze_raw",
    "silver.silver_cleaned",
    "gold.gold_analytical",
    "metadata.indicator_catalog",
    "metadata.data_collection_log",
)

#: SQL mirrors of the repository's hot paths (dashboard/repository.py). They are
#: written out rather than imported because the repository builds and executes
#: its statements inline; each is documented with the method it mirrors so drift
#: is visible in review.
LOAD_SERIES_SQL: Final[str] = """
SELECT gold.gold_analytical.indicator_id,
       catalog.name,
       gold.gold_analytical.timestamp,
       gold.gold_analytical.value,
       gold.gold_analytical.original_value,
       gold.gold_analytical.is_chain_linked,
       gold.gold_analytical.chain_linking_confidence,
       gold.gold_analytical.unit,
       gold.gold_analytical.frequency,
       gold.gold_analytical.domain,
       catalog.source_name,
       catalog.source_url,
       gold.gold_analytical.metadata,
       catalog.indicator_id AS catalog_indicator_id,
       parent_catalog.name AS parent_name,
       parent_catalog.source_name AS parent_source_name,
       parent_catalog.source_url AS parent_source_url
FROM gold.gold_analytical
LEFT OUTER JOIN metadata.indicator_catalog AS catalog
    ON catalog.indicator_id = gold.gold_analytical.indicator_id
LEFT OUTER JOIN metadata.indicator_catalog AS parent_catalog
    ON parent_catalog.indicator_id = (gold.gold_analytical.metadata ->> 'derived_from')
WHERE gold.gold_analytical.indicator_id IN :ids
ORDER BY gold.gold_analytical.timestamp ASC, gold.gold_analytical.indicator_id ASC
"""

COVERAGE_SQL: Final[str] = """
SELECT gold.gold_analytical.indicator_id,
       min(gold.gold_analytical.timestamp) AS observed_start,
       max(gold.gold_analytical.timestamp) AS observed_end,
       count(*) AS observation_count,
       sum(CAST(gold.gold_analytical.is_chain_linked AS INTEGER)) AS chain_linked_count,
       avg(gold.gold_analytical.chain_linking_confidence) AS confidence
FROM gold.gold_analytical
GROUP BY gold.gold_analytical.indicator_id
"""

FRESHNESS_SQL: Final[str] = """
SELECT source_name, collection_timestamp, status, records_collected, error_message
FROM (
    SELECT source_name, collection_timestamp, status, records_collected, error_message,
           row_number() OVER (
               PARTITION BY source_name ORDER BY collection_timestamp DESC
           ) AS row_number
    FROM metadata.data_collection_log
) AS ranked
WHERE row_number = 1
ORDER BY source_name ASC
"""

CATALOG_SQL: Final[str] = """
SELECT indicator_id, name, description, unit, frequency, domain, source_name,
       source_url, availability_start, availability_end, has_base_year_changes,
       base_years, is_active
FROM metadata.indicator_catalog
WHERE is_active = TRUE
ORDER BY domain ASC, name ASC
"""


@dataclass(frozen=True)
class PlanMetrics:
    """What one ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` plan reports."""

    planning_ms: float
    execution_ms: float
    rows: int
    shared_hit_blocks: int
    shared_read_blocks: int
    seq_scan_tables: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkQuery:
    """A hot query to benchmark, with the tables it must index-scan."""

    name: str
    sql: str
    params: dict[str, Any] = field(default_factory=dict)
    guarded_tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryResult:
    """One benchmarked query's plan and timings."""

    name: str
    sql: str
    index_used: bool
    seq_scan_tables: tuple[str, ...]
    planning_ms: float
    execution_ms: float
    rows: int
    shared_hit_blocks: int
    shared_read_blocks: int

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryResult":
        """Rebuild a result from its stored form."""
        return cls(
            name=data["name"],
            sql=data["sql"],
            index_used=bool(data["index_used"]),
            seq_scan_tables=tuple(data.get("seq_scan_tables", ())),
            planning_ms=float(data["planning_ms"]),
            execution_ms=float(data["execution_ms"]),
            rows=int(data["rows"]),
            shared_hit_blocks=int(data["shared_hit_blocks"]),
            shared_read_blocks=int(data["shared_read_blocks"]),
        )


@dataclass(frozen=True)
class BenchmarkRun:
    """One stored benchmark run: the environment, and per-query results."""

    commit: str
    timestamp: str
    environment: dict[str, Any]
    queries: tuple[QueryResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view."""
        return {
            "commit": self.commit,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "queries": [query.to_dict() for query in self.queries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkRun":
        """Rebuild a run from its stored form."""
        return cls(
            commit=str(data.get("commit", "")),
            timestamp=str(data.get("timestamp", "")),
            environment=dict(data.get("environment", {})),
            queries=tuple(QueryResult.from_dict(q) for q in data.get("queries", [])),
        )


@dataclass(frozen=True)
class Comparison:
    """One query's delta against the baseline."""

    name: str
    status: str
    baseline_execution_ms: float | None
    current_execution_ms: float
    delta_ms: float | None
    delta_pct: float | None
    index_lost: bool


def parse_explain(payload: Any) -> PlanMetrics:
    """Extract timings, row/buffer counts and seq-scan tables from a JSON plan.

    Args:
        payload: The value ``EXPLAIN (FORMAT JSON)`` returns -- a one-element
            list whose element holds ``Plan``/``Planning Time``/``Execution
            Time`` (a bare plan mapping is also accepted).

    Returns:
        The parsed metrics. ``seq_scan_tables`` holds the ``schema.table`` of
        every sequential scan in the plan tree, in plan order.

    Raises:
        ValueError: If the payload is not a recognisable JSON plan.
    """
    if isinstance(payload, list):
        if not payload:
            msg = "empty EXPLAIN payload"
            raise ValueError(msg)
        payload = payload[0]
    if not isinstance(payload, dict) or "Plan" not in payload:
        msg = f"unrecognised EXPLAIN payload: {type(payload).__name__}"
        raise ValueError(msg)

    plan = payload["Plan"]
    seq_scans: list[str] = []

    def walk(node: dict[str, Any]) -> tuple[int, int]:
        hit = int(node.get("Shared Hit Blocks", 0) or 0)
        read = int(node.get("Shared Read Blocks", 0) or 0)
        if node.get("Node Type") == "Seq Scan":
            seq_scans.append(_qualified(node))
        for child in node.get("Plans", []) or []:
            child_hit, child_read = walk(child)
            hit += child_hit
            read += child_read
        return hit, read

    hit_blocks, read_blocks = walk(plan)
    return PlanMetrics(
        planning_ms=float(payload.get("Planning Time", 0.0) or 0.0),
        execution_ms=float(payload.get("Execution Time", 0.0) or 0.0),
        rows=int(plan.get("Actual Rows", 0) or 0),
        shared_hit_blocks=hit_blocks,
        shared_read_blocks=read_blocks,
        seq_scan_tables=tuple(seq_scans),
    )


def _qualified(node: dict[str, Any]) -> str:
    """``schema.table`` for a plan node, falling back to the relation name."""
    relation = str(node.get("Relation Name", "?"))
    schema = node.get("Schema")
    return f"{schema}.{relation}" if schema else relation


def evaluate_result(query: BenchmarkQuery, metrics: PlanMetrics) -> QueryResult:
    """Fold a parsed plan into a benchmark result and decide index usage.

    A query loses index usage when a sequential scan touches one of its
    ``guarded_tables``; a seq scan elsewhere (a small metadata table, an
    unfiltered aggregate) is legitimate and does not fail the gate.
    """
    offending = tuple(table for table in metrics.seq_scan_tables if table in query.guarded_tables)
    return QueryResult(
        name=query.name,
        sql=query.sql.strip(),
        index_used=not offending,
        seq_scan_tables=metrics.seq_scan_tables,
        planning_ms=metrics.planning_ms,
        execution_ms=metrics.execution_ms,
        rows=metrics.rows,
        shared_hit_blocks=metrics.shared_hit_blocks,
        shared_read_blocks=metrics.shared_read_blocks,
    )


def compare_runs(
    current: BenchmarkRun,
    baseline: BenchmarkRun | None,
    threshold: float = DEFAULT_REGRESSION_THRESHOLD,
) -> tuple[Comparison, ...]:
    """Compare ``current`` against ``baseline``, one entry per current query.

    ``baseline`` of ``None`` is a first run: every query is ``new``. A query
    whose execution time grew by more than ``threshold`` (a fraction) is
    ``regression``; one that lost index usage is ``index_lost`` (which takes
    precedence); one that got faster is ``improved``; otherwise ``ok``.
    """
    if baseline is None:
        return tuple(
            Comparison(
                name=query.name,
                status="new",
                baseline_execution_ms=None,
                current_execution_ms=query.execution_ms,
                delta_ms=None,
                delta_pct=None,
                index_lost=not query.index_used,
            )
            for query in current.queries
        )

    previous = {query.name: query for query in baseline.queries}
    comparisons: list[Comparison] = []
    for query in current.queries:
        base = previous.get(query.name)
        if base is None:
            comparisons.append(
                Comparison(
                    name=query.name,
                    status="new",
                    baseline_execution_ms=None,
                    current_execution_ms=query.execution_ms,
                    delta_ms=None,
                    delta_pct=None,
                    index_lost=not query.index_used,
                )
            )
            continue
        delta_ms = query.execution_ms - base.execution_ms
        delta_pct = (delta_ms / base.execution_ms) if base.execution_ms else None
        index_lost = base.index_used and not query.index_used
        material = abs(delta_ms) >= REGRESSION_MIN_MS
        if index_lost:
            status = "index_lost"
        elif delta_pct is not None and delta_pct > threshold and material:
            status = "regression"
        elif delta_pct is not None and delta_pct < -threshold and material:
            status = "improved"
        else:
            status = "ok"
        comparisons.append(
            Comparison(
                name=query.name,
                status=status,
                baseline_execution_ms=base.execution_ms,
                current_execution_ms=query.execution_ms,
                delta_ms=delta_ms,
                delta_pct=delta_pct,
                index_lost=index_lost,
            )
        )
    return tuple(comparisons)


def environment_changed(current: BenchmarkRun, baseline: BenchmarkRun) -> bool:
    """Whether two runs' environments are too different to compare timings.

    A different PostgreSQL or TimescaleDB version, or a row-count shift beyond
    :data:`ROW_COUNT_TOLERANCE` on any counted table, means the timings are not
    comparable and a delta must not be reported as a regression.
    """
    for key in ("postgres", "timescaledb"):
        if current.environment.get(key) != baseline.environment.get(key):
            return True
    current_counts = current.environment.get("row_counts", {}) or {}
    baseline_counts = baseline.environment.get("row_counts", {}) or {}
    for table in set(current_counts) | set(baseline_counts):
        before = baseline_counts.get(table)
        after = current_counts.get(table)
        if before in (None, 0) or after is None:
            if before != after:
                return True
            continue
        if abs(after - before) / before > ROW_COUNT_TOLERANCE:
            return True
    return False


def load_baseline(path: Path) -> list[BenchmarkRun]:
    """Load stored runs from ``path``; a missing file yields no runs."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkRun.from_dict(run) for run in data.get("runs", [])]


def latest_run(runs: Sequence[BenchmarkRun]) -> BenchmarkRun | None:
    """The most recent stored run, by timestamp, or ``None`` when empty."""
    if not runs:
        return None
    return max(runs, key=lambda run: run.timestamp)


def upsert_run(runs: Sequence[BenchmarkRun], run: BenchmarkRun) -> list[BenchmarkRun]:
    """Append ``run``, replacing an existing run with the same commit.

    Keyed by commit so re-running on the same commit does not pile up entries.
    """
    kept = [existing for existing in runs if existing.commit != run.commit]
    return [*kept, run]


def serialize_baseline(runs: Sequence[BenchmarkRun]) -> str:
    """Render runs as the committed baseline document."""
    return (
        json.dumps(
            {"version": 1, "runs": [run.to_dict() for run in runs]},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


# ---------------------------------------------------------------- database side


def _sample_indicator_ids(session: Session, limit: int = 5) -> list[str]:
    """The busiest Gold indicator ids, for a realistic ``load_series`` call."""
    rows = session.execute(
        text(
            "SELECT indicator_id FROM gold.gold_analytical "
            "GROUP BY indicator_id ORDER BY count(*) DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).scalars()
    return [str(row) for row in rows]


def build_queries(session: Session) -> list[BenchmarkQuery]:
    """The hot queries to benchmark, with their guarded tables."""
    ids = _sample_indicator_ids(session)
    return [
        BenchmarkQuery(
            name="load_series",
            sql=LOAD_SERIES_SQL,
            params={"ids": ids},
            guarded_tables=GUARDED_TABLES,
        ),
        BenchmarkQuery(name="coverage_summary", sql=COVERAGE_SQL),
        BenchmarkQuery(name="source_freshness", sql=FRESHNESS_SQL),
        BenchmarkQuery(name="catalog_read", sql=CATALOG_SQL),
    ]


def run_query(session: Session, query: BenchmarkQuery) -> QueryResult:
    """``EXPLAIN ANALYZE`` one query and return its measured result.

    Read-only: ``EXPLAIN ANALYZE`` executes the statement, but every query here
    is a ``SELECT``.
    """
    statement = text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query.sql)
    if "ids" in query.params:
        # ``IN :ids`` needs an expanding bind so the list becomes a parameter list.
        statement = statement.bindparams(bindparam("ids", expanding=True))
    payload = session.execute(statement, query.params).scalar()
    return evaluate_result(query, parse_explain(payload))


def collect_environment(session: Session) -> dict[str, Any]:
    """Record the versions, image digest and row counts for a run."""
    counts: dict[str, int] = {}
    for table in COUNTED_TABLES:
        counts[table] = int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0)
    return {
        "python": sys.version.split()[0],
        "postgres": str(session.execute(text("SHOW server_version")).scalar() or ""),
        "timescaledb": str(
            session.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
            ).scalar()
            or ""
        ),
        "image_digest": _image_digest(),
        "row_counts": counts,
    }


def _image_digest() -> str | None:
    """Best-effort resolved digest of the running postgres image, else ``None``.

    A benchmark run must not fail because Docker is unavailable or the
    credential helper is missing; the digest is provenance, not a gate.
    """
    try:
        container = subprocess.run(
            ["docker", "compose", "ps", "-q", "postgres"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
        if not container:
            return None
        # A container has no RepoDigests of its own; the resolved digest belongs
        # to its image, so read the image reference off the container first.
        image = subprocess.run(
            ["docker", "inspect", "--format", "{{.Config.Image}}", container],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
        if not image:
            return None
        digest = subprocess.run(
            ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", image],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
        return digest or None
    except (OSError, subprocess.SubprocessError):
        return None


def _git_commit() -> str:
    """Current commit hash, or ``unknown`` outside a repository."""
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
            or "unknown"
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# ----------------------------------------------------------------------- output


def render_report(
    current: BenchmarkRun,
    comparisons: Sequence[Comparison],
    *,
    baseline: BenchmarkRun | None,
    environment_changed_flag: bool,
) -> str:
    """Human-readable timing table, deltas and a highlighted summary."""
    lines = [f"benchmark @ {current.commit} ({current.timestamp})"]
    lines.append(
        f"environment: python {current.environment.get('python')}, "
        f"PostgreSQL {current.environment.get('postgres')}, "
        f"TimescaleDB {current.environment.get('timescaledb')}"
    )
    header = f"{'QUERY':<18} {'EXEC ms':>9} {'PLAN ms':>8} {'ROWS':>7} {'INDEX':<6} STATUS"
    lines.append(header)
    by_name = {comparison.name: comparison for comparison in comparisons}
    for query in current.queries:
        comparison = by_name[query.name]
        index = "yes" if query.index_used else "NO"
        over_budget = "  (>1s budget)" if query.execution_ms > QUERY_BUDGET_MS else ""
        lines.append(
            f"{query.name:<18} {query.execution_ms:>9.3f} {query.planning_ms:>8.3f} "
            f"{query.rows:>7} {index:<6} {comparison.status}{over_budget}"
        )

    if baseline is None:
        lines.append("baseline: none (first recorded run)")
    elif environment_changed_flag:
        lines.append(f"baseline: {baseline.commit} -- environment changed, timings not compared")
    else:
        lines.append(f"baseline: {baseline.commit} ({baseline.timestamp})")
        for comparison in comparisons:
            if comparison.baseline_execution_ms is None:
                continue
            pct = "n/a" if comparison.delta_pct is None else f"{comparison.delta_pct:+.1%}"
            lines.append(
                f"  {comparison.name:<18} {comparison.baseline_execution_ms:>9.3f} -> "
                f"{comparison.current_execution_ms:>9.3f} ms  "
                f"({comparison.delta_ms:+.3f} ms, {pct})"
            )

    failures = [q for q in current.queries if not q.index_used]
    regressions = [c for c in comparisons if c.status == "regression"]
    lost = [c for c in comparisons if c.status == "index_lost"]
    if failures:
        lines.append("FAIL: unexpected sequential scan on a guarded table:")
        for query in failures:
            lines.append(f"  - {query.name}: {', '.join(query.seq_scan_tables)}")
    if lost:
        lines.append("REGRESSION: index usage lost vs baseline: " + ", ".join(c.name for c in lost))
    if regressions and not environment_changed_flag:
        lines.append(
            "REGRESSION: slower than baseline by more than "
            f"{DEFAULT_REGRESSION_THRESHOLD:.0%}: " + ", ".join(c.name for c in regressions)
        )
    if not failures and not lost and not regressions:
        lines.append("OK: index usage intact, no timing regression")
    return "\n".join(lines)


def run_cli(
    *,
    write: bool = False,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    regression_threshold: float = DEFAULT_REGRESSION_THRESHOLD,
    fail_on_regression: bool = False,
    json_output: bool = False,
) -> int:
    """Run the benchmarks, report, optionally persist, and return an exit code."""
    try:
        get_db()
    except RuntimeError:
        config = get_config()
        init_database(config.database.url, echo=config.debug)

    with get_db().get_session() as session:
        queries = build_queries(session)
        results = tuple(run_query(session, query) for query in queries)
        environment = collect_environment(session)

    current = BenchmarkRun(
        commit=_git_commit(),
        timestamp=datetime.now(UTC).isoformat(),
        environment=environment,
        queries=results,
    )

    stored = load_baseline(baseline_path)
    # Compare against the most recent stored run. A run on the same commit is
    # still a valid comparison: it measures run-to-run variance against the
    # recorded baseline, and --write replaces that commit's entry rather than
    # piling up duplicates.
    baseline = latest_run(stored)
    changed = baseline is not None and environment_changed(current, baseline)
    comparisons = compare_runs(current, baseline, regression_threshold)

    if json_output:
        print(
            json.dumps(
                {
                    "run": current.to_dict(),
                    "baseline_commit": None if baseline is None else baseline.commit,
                    "environment_changed": changed,
                    "comparisons": [asdict(c) for c in comparisons],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(
            render_report(
                current,
                comparisons,
                baseline=baseline,
                environment_changed_flag=changed,
            )
        )

    if write:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(serialize_baseline(upsert_run(stored, current)), encoding="utf-8")
        print(f"baseline written: {baseline_path}")

    if any(not query.index_used for query in results):
        return 1
    if fail_on_regression and any(
        comparison.status in {"regression", "index_lost"} for comparison in comparisons
    ):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone entry point: ``python scripts/benchmark_queries.py``."""
    parser = argparse.ArgumentParser(
        prog="python scripts/benchmark_queries.py",
        description="Benchmark the dashboard's hot queries against a stored baseline.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist this run to the baseline file (append/replace by commit)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help=f"Baseline file (default: {DEFAULT_BASELINE_PATH})",
    )
    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=DEFAULT_REGRESSION_THRESHOLD,
        help=(
            "Fraction slower than the baseline that counts as a regression "
            f"(default: {DEFAULT_REGRESSION_THRESHOLD})"
        ),
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero on a timing regression or lost index usage",
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    args = parser.parse_args(argv)

    try:
        return run_cli(
            write=args.write,
            baseline_path=args.baseline,
            regression_threshold=args.regression_threshold,
            fail_on_regression=args.fail_on_regression,
            json_output=args.json,
        )
    except Exception as exc:  # - CLI boundary: report and exit non-zero
        print(f"error: benchmark failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
