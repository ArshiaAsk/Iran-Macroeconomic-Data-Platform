"""Report connector health and Gold data freshness from the metadata layer.

Usage::

    poetry run python scripts/health_check.py
    poetry run python scripts/health_check.py --json
    poetry run python scripts/health_check.py --stale-after-days 3
    poetry run python scripts/health_check.py --fail-on-warning

The check is **read-only**: it reads ``metadata.data_collection_log`` (the latest
result per source) and the Gold coverage summary, then classifies every source
``ok`` / ``stale`` / ``failed`` (or ``degraded`` / ``no_data`` / ``unknown``) and
exits:

* ``0`` — every source is healthy;
* ``1`` — at least one source is degraded, stale, empty or has no expectation;
* ``2`` — at least one source's latest collection run failed.

Staleness is not a hand-rolled calendar rule: it reuses
:func:`dashboard.components.quality.expected_periods` (the same primitive the
dashboard's quality view uses) against the catalog frequency and the last
observed Gold timestamp, so the script and the UI cannot disagree. No value is
ever filled, interpolated or invented — the script reports what is stored.

``--fail-on-warning`` promotes a warning-only result from exit ``1`` to exit
``2`` so a scheduler can treat any degradation as a hard failure.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Final

import pandas as pd

from dashboard.components.quality import ExpectedPeriods, expected_periods
from dashboard.repository import DashboardRepository
from src.database.connection import get_db, init_database
from src.utils.config import get_config

EXIT_OK: Final[int] = 0
EXIT_WARNING: Final[int] = 1
EXIT_FAILED: Final[int] = 2

#: Source statuses, worst last. A source is reported at its worst state.
STATUS_OK: Final[str] = "ok"
STATUS_DEGRADED: Final[str] = "degraded"
STATUS_STALE: Final[str] = "stale"
STATUS_NO_DATA: Final[str] = "no_data"
STATUS_UNKNOWN: Final[str] = "unknown"
STATUS_FAILED: Final[str] = "failed"

#: Statuses that make the whole report a warning (non-fatal, exit 1).
WARNING_STATUSES: Final[frozenset[str]] = frozenset(
    {STATUS_DEGRADED, STATUS_STALE, STATUS_NO_DATA, STATUS_UNKNOWN}
)

#: An estimated (trading-session) expectation is a rate, not a calendar: a
#: session's data can lag by a session or two and a weekend adds two more days.
#: Up to this many estimated sessions of lag are tolerated before the source is
#: called stale, so a normal weekend never raises a false gap (the same reason
#: ``dashboard.components.quality`` gates its estimate residual behind
#: ``MISSING_PERIOD_WARNING_RATIO``).
_ESTIMATE_SLACK: Final[int] = 3

#: Callable signature of the expectation primitive, injectable for tests.
ExpectedFn = Callable[..., "ExpectedPeriods | None"]


@dataclass(frozen=True)
class SourceHealth:
    """Health of one data source, derived from collection and coverage rows."""

    source_name: str
    status: str
    last_collection: datetime | None
    collection_status: str | None
    last_observed: datetime | None
    frequency: str | None
    missed_periods: int | None
    detail: str | None

    @property
    def is_failed(self) -> bool:
        """Whether the source's latest collection run failed."""
        return self.status == STATUS_FAILED

    @property
    def is_warning(self) -> bool:
        """Whether the source is degraded but not failed."""
        return self.status in WARNING_STATUSES


@dataclass(frozen=True)
class HealthReport:
    """The full health picture: one :class:`SourceHealth` per source."""

    sources: tuple[SourceHealth, ...]

    @property
    def failed(self) -> tuple[SourceHealth, ...]:
        """Sources whose latest collection run failed."""
        return tuple(source for source in self.sources if source.is_failed)

    @property
    def warnings(self) -> tuple[SourceHealth, ...]:
        """Sources that are degraded, stale, empty or have no expectation."""
        return tuple(source for source in self.sources if source.is_warning)

    @property
    def healthy(self) -> tuple[SourceHealth, ...]:
        """Sources that are fully healthy."""
        return tuple(source for source in self.sources if source.status == STATUS_OK)

    def exit_code(self, *, fail_on_warning: bool = False) -> int:
        """Process exit code: 2 on failure, 1 on warning, 0 when all healthy."""
        if self.failed:
            return EXIT_FAILED
        if self.warnings:
            return EXIT_FAILED if fail_on_warning else EXIT_WARNING
        return EXIT_OK

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view of the report."""
        return {
            "sources": [
                {
                    **asdict(source),
                    "last_collection": _iso(source.last_collection),
                    "last_observed": _iso(source.last_observed),
                }
                for source in self.sources
            ],
            "summary": {
                "total": len(self.sources),
                "ok": len(self.healthy),
                "warnings": len(self.warnings),
                "failed": len(self.failed),
            },
        }


def _iso(value: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 string, or ``None``."""
    return None if value is None else value.isoformat()


def _as_datetime(value: object) -> datetime | None:
    """Normalize a frame cell to a timezone-aware datetime, or ``None``.

    ``NaT``/``NaN`` (a source that has never run or never produced a Gold row)
    becomes ``None`` -- distinct from a real timestamp, and never coerced to a
    value.
    """
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return None


def _missed_periods(
    expected: ExpectedFn,
    frequency: str | None,
    source_name: str,
    observed_end: datetime,
    now: datetime,
) -> int | None:
    """Periods the source is behind, or ``None`` when there is no expectation.

    ``expected_periods`` is applied over the inclusive range
    ``[observed_end, now]``. The first key is the period that holds
    ``observed_end`` (observed) and the last is the period that holds ``now``
    (still open), so everything strictly between them is missed. For an
    enumerated frequency that is ``count - 2``; for an estimated trading rate it
    is ``count - _ESTIMATE_SLACK`` so a weekend alone does not raise a false gap.
    """
    periods = expected(frequency, observed_end, now, source_name=source_name)
    if periods is None:
        return None
    if periods.is_estimate:
        return max(0, periods.count - _ESTIMATE_SLACK)
    return max(0, periods.count - 2)


def _classify(
    collection_status: str | None,
    has_data: bool,
    missed: int | None,
) -> str:
    """Pick a source status from its collection result and staleness."""
    if collection_status == "failed":
        return STATUS_FAILED
    if not has_data:
        return STATUS_NO_DATA
    if missed is None:
        return STATUS_UNKNOWN
    if missed > 0:
        return STATUS_STALE
    if collection_status == "partial":
        return STATUS_DEGRADED
    return STATUS_OK


def evaluate_health(
    freshness: pd.DataFrame,
    coverage: pd.DataFrame,
    expected: ExpectedFn = expected_periods,
    *,
    now: datetime | None = None,
    stale_after_days: int | None = None,
) -> HealthReport:
    """Classify every source from its latest collection row and Gold coverage.

    Pure: no database, no network. The two frames are exactly what
    :meth:`dashboard.repository.DashboardRepository.source_freshness` and
    :meth:`~dashboard.repository.DashboardRepository.coverage_summary` return.

    Args:
        freshness: Latest collection row per source (``source_name``, ``status``,
            ``collection_timestamp``, ``error_message``)
        coverage: One row per catalog indicator (``source_name``, ``frequency``,
            ``observed_end``)
        expected: Expectation primitive, injectable for tests
        now: Reference instant; defaults to the current UTC time
        stale_after_days: Explicit day threshold overriding the
            frequency-derived expectation (``None`` uses the frequency)

    Returns:
        A :class:`HealthReport` with one entry per source, ordered by name.
    """
    reference = now or datetime.now(UTC)
    collection = _latest_collection_by_source(freshness)
    observed = _coverage_by_source(coverage)

    names = sorted(set(collection) | set(observed))
    sources: list[SourceHealth] = []
    for name in names:
        last_collection, collection_status, error = collection.get(name, (None, None, None))
        rows = observed.get(name, [])
        last_observed = max((end for _, end in rows), default=None)
        frequency = _dominant_frequency(rows)

        if stale_after_days is not None and last_observed is not None:
            elapsed = (reference - last_observed).days
            missed: int | None = max(0, elapsed - stale_after_days)
        elif last_observed is not None:
            missed = _missed_periods(expected, frequency, name, last_observed, reference)
        else:
            missed = None

        status = _classify(collection_status, last_observed is not None, missed)
        sources.append(
            SourceHealth(
                source_name=name,
                status=status,
                last_collection=last_collection,
                collection_status=collection_status,
                last_observed=last_observed,
                frequency=frequency,
                missed_periods=missed,
                detail=error,
            )
        )
    return HealthReport(sources=tuple(sources))


def _latest_collection_by_source(
    freshness: pd.DataFrame,
) -> dict[str, tuple[datetime | None, str | None, str | None]]:
    """Map source name to its latest ``(timestamp, status, error_message)``."""
    result: dict[str, tuple[datetime | None, str | None, str | None]] = {}
    if freshness.empty or "source_name" not in freshness.columns:
        return result
    for row in freshness.to_dict("records"):
        name = str(row["source_name"])
        status = row.get("status")
        error = row.get("error_message")
        result[name] = (
            _as_datetime(row.get("collection_timestamp")),
            None if status is None or pd.isna(status) else str(status),
            None if error is None or pd.isna(error) else str(error),
        )
    return result


def _coverage_by_source(
    coverage: pd.DataFrame,
) -> dict[str, list[tuple[str | None, datetime]]]:
    """Map source name to its indicators' ``(frequency, observed_end)`` pairs.

    Indicators with no Gold observation (``observed_end`` is null) contribute no
    pair, so "the source has data" means at least one stored Gold timestamp.
    """
    result: dict[str, list[tuple[str | None, datetime]]] = {}
    if coverage.empty or "source_name" not in coverage.columns:
        return result
    for row in coverage.to_dict("records"):
        end = _as_datetime(row.get("observed_end"))
        if end is None:
            continue
        name = row.get("source_name")
        if name is None or pd.isna(name):
            continue
        frequency = row.get("frequency")
        frequency = None if frequency is None or pd.isna(frequency) else str(frequency)
        result.setdefault(str(name), []).append((frequency, end))
    return result


def _dominant_frequency(
    rows: Sequence[tuple[str | None, datetime]],
) -> str | None:
    """Frequency of the source's most recently observed indicator.

    A source usually publishes one cadence; when it does not, the frequency of
    the indicator with the latest ``observed_end`` governs the staleness check,
    because that is the series most likely to be behind.
    """
    if not rows:
        return None
    return max(rows, key=lambda item: item[1])[0]


def _render(report: HealthReport) -> str:
    """One line per source plus a totals line, for the human CLI."""
    lines = [f"{'STATUS':<9} {'SOURCE':<14} {'LAST OBSERVED':<20} {'MISSED':<7} DETAIL"]
    for source in report.sources:
        observed = source.last_observed.isoformat() if source.last_observed else "-"
        missed = "-" if source.missed_periods is None else str(source.missed_periods)
        detail = source.detail or source.collection_status or ""
        lines.append(
            f"{source.status:<9} {source.source_name:<14} {observed:<20} {missed:<7} {detail}"
        )
    lines.append(
        f"totals: {len(report.sources)} sources, "
        f"{len(report.healthy)} ok, {len(report.warnings)} warning, "
        f"{len(report.failed)} failed"
    )
    return "\n".join(lines)


def _ensure_database() -> None:
    """Initialize the global connection if the process has not done so yet."""
    try:
        get_db()
    except RuntimeError:
        config = get_config()
        init_database(config.database.url, echo=config.debug)


def run_cli(
    json_output: bool = False,
    stale_after_days: int | None = None,
    fail_on_warning: bool = False,
) -> int:
    """Read the database, evaluate health, print it and return the exit code."""
    _ensure_database()
    with get_db().get_session() as session:
        repository = DashboardRepository(session)
        freshness = repository.source_freshness()
        coverage = repository.coverage_summary()

    report = evaluate_health(
        freshness,
        coverage,
        expected_periods,
        stale_after_days=stale_after_days,
    )
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(_render(report))
    return report.exit_code(fail_on_warning=fail_on_warning)


def main(argv: Sequence[str] | None = None) -> int:
    """Standalone entry point: ``python scripts/health_check.py``."""
    parser = argparse.ArgumentParser(
        prog="python scripts/health_check.py",
        description="Report connector health and Gold data freshness.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    parser.add_argument(
        "--stale-after-days",
        type=int,
        default=None,
        help=(
            "Override the frequency-derived staleness threshold with a fixed "
            "number of days (default: derive it from the catalog frequency)"
        ),
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Treat a degraded/stale source as a hard failure (exit 2, not 1)",
    )
    args = parser.parse_args(argv)

    try:
        return run_cli(
            json_output=args.json,
            stale_after_days=args.stale_after_days,
            fail_on_warning=args.fail_on_warning,
        )
    except Exception as exc:  # - CLI boundary: report and exit non-zero
        print(f"error: health check failed: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
