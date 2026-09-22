"""Unit tests for the health-check classifier.

No network and no database: ``evaluate_health`` is fed synthetic
``source_freshness`` / ``coverage_summary`` frames directly, so every branch
(fresh, stale, failed, empty, estimated, unsupported) is exercised in isolation.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from scripts.health_check import (
    EXIT_FAILED,
    EXIT_OK,
    EXIT_WARNING,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_NO_DATA,
    STATUS_OK,
    STATUS_STALE,
    STATUS_UNKNOWN,
    HealthReport,
    SourceHealth,
    evaluate_health,
)

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def freshness_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build a ``source_freshness``-shaped frame."""
    columns = [
        "source_name",
        "collection_timestamp",
        "status",
        "records_collected",
        "error_message",
    ]
    return pd.DataFrame(rows, columns=columns)


def coverage_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build a ``coverage_summary``-shaped frame."""
    columns = [
        "indicator_id",
        "name",
        "unit",
        "frequency",
        "domain",
        "source_name",
        "observed_start",
        "observed_end",
        "observation_count",
        "chain_linked_count",
        "confidence",
    ]
    return pd.DataFrame(rows, columns=columns)


def collection(
    source: str,
    status: str = "success",
    when: datetime | None = None,
    error: str | None = None,
) -> dict[str, object]:
    """One ``data_collection_log`` latest-row stand-in."""
    return {
        "source_name": source,
        "collection_timestamp": when or NOW - timedelta(hours=1),
        "status": status,
        "records_collected": 1,
        "error_message": error,
    }


def observation(
    source: str,
    frequency: str,
    observed_end: datetime | None,
    indicator: str | None = None,
) -> dict[str, object]:
    """One ``coverage_summary`` row for an indicator of ``source``."""
    return {
        "indicator_id": indicator or f"{source}.test",
        "name": indicator or f"{source} test",
        "unit": "index",
        "frequency": frequency,
        "domain": "test",
        "source_name": source,
        "observed_start": None,
        "observed_end": observed_end,
        "observation_count": 1 if observed_end is not None else None,
        "chain_linked_count": 0,
        "confidence": None,
    }


def health_of(report: HealthReport, source: str) -> SourceHealth:
    """Return the :class:`SourceHealth` for ``source`` (fails loudly if absent)."""
    for entry in report.sources:
        if entry.source_name == source:
            return entry
    message = f"no health entry for {source!r}"
    raise AssertionError(message)


def test_fresh_daily_source_is_ok() -> None:
    report = evaluate_health(
        freshness_frame([collection("tgju")]),
        coverage_frame([observation("tgju", "daily", NOW - timedelta(days=1))]),
        now=NOW,
    )
    assert health_of(report, "tgju").status == STATUS_OK
    assert report.exit_code() == EXIT_OK


def test_stale_beyond_one_period_is_flagged() -> None:
    # Monthly data last observed four months ago: at least one period is missed.
    report = evaluate_health(
        freshness_frame([collection("eia")]),
        coverage_frame([observation("eia", "monthly", NOW - timedelta(days=120))]),
        now=NOW,
    )
    entry = health_of(report, "eia")
    assert entry.status == STATUS_STALE
    assert entry.missed_periods is not None
    assert entry.missed_periods >= 1
    assert report.exit_code() == EXIT_WARNING


def test_failed_last_run_is_a_failure() -> None:
    report = evaluate_health(
        freshness_frame([collection("tgju", status="failed", error="selector broke")]),
        coverage_frame([observation("tgju", "daily", NOW - timedelta(days=1))]),
        now=NOW,
    )
    entry = health_of(report, "tgju")
    assert entry.status == STATUS_FAILED
    assert entry.detail == "selector broke"
    assert report.exit_code() == EXIT_FAILED


def test_no_data_at_all_is_reported_not_ok() -> None:
    report = evaluate_health(
        freshness_frame([collection("sci")]),
        coverage_frame([observation("sci", "monthly", None)]),
        now=NOW,
    )
    entry = health_of(report, "sci")
    assert entry.status == STATUS_NO_DATA
    assert entry.last_observed is None
    assert report.exit_code() == EXIT_WARNING


def test_source_that_never_ran_is_no_data() -> None:
    # A source present only in the catalog (never collected, never observed).
    report = evaluate_health(
        freshness_frame([]),
        coverage_frame([observation("cbi", "monthly", None)]),
        now=NOW,
    )
    assert health_of(report, "cbi").status == STATUS_NO_DATA


def test_trading_session_source_does_not_raise_a_false_gap() -> None:
    # TSETMC publishes only on exchange sessions; the estimate is a rate, not a
    # calendar, so a short gap (a weekend plus a pending session) must stay ok.
    report = evaluate_health(
        freshness_frame([collection("tsetmc")]),
        coverage_frame([observation("tsetmc", "daily", NOW - timedelta(days=2))]),
        now=NOW,
    )
    entry = health_of(report, "tsetmc")
    assert entry.status == STATUS_OK
    assert report.exit_code() == EXIT_OK


def test_trading_session_source_stale_after_a_long_gap() -> None:
    report = evaluate_health(
        freshness_frame([collection("tsetmc")]),
        coverage_frame([observation("tsetmc", "daily", NOW - timedelta(days=30))]),
        now=NOW,
    )
    assert health_of(report, "tsetmc").status == STATUS_STALE


def test_unsupported_frequency_has_no_expectation() -> None:
    report = evaluate_health(
        freshness_frame([collection("odd")]),
        coverage_frame([observation("odd", "hourly", NOW - timedelta(hours=2))]),
        now=NOW,
    )
    entry = health_of(report, "odd")
    assert entry.status == STATUS_UNKNOWN
    assert entry.missed_periods is None
    assert report.exit_code() == EXIT_WARNING


def test_partial_collection_is_degraded() -> None:
    report = evaluate_health(
        freshness_frame([collection("tgju", status="partial")]),
        coverage_frame([observation("tgju", "daily", NOW - timedelta(days=1))]),
        now=NOW,
    )
    assert health_of(report, "tgju").status == STATUS_DEGRADED
    assert report.exit_code() == EXIT_WARNING


def test_stale_after_days_overrides_the_frequency() -> None:
    coverage = coverage_frame([observation("eia", "monthly", NOW - timedelta(days=45))])
    freshness = freshness_frame([collection("eia")])

    # The frequency-derived rule (monthly) sees only one open period: ok.
    assert health_of(evaluate_health(freshness, coverage, now=NOW), "eia").status == STATUS_OK
    # An explicit 30-day threshold calls the same source stale.
    overridden = evaluate_health(freshness, coverage, now=NOW, stale_after_days=30)
    assert health_of(overridden, "eia").status == STATUS_STALE


def test_fail_on_warning_promotes_to_exit_2() -> None:
    report = evaluate_health(
        freshness_frame([collection("tgju", status="partial")]),
        coverage_frame([observation("tgju", "daily", NOW - timedelta(days=1))]),
        now=NOW,
    )
    assert report.exit_code() == EXIT_WARNING
    assert report.exit_code(fail_on_warning=True) == EXIT_FAILED


def test_empty_database_is_healthy_not_a_crash() -> None:
    report = evaluate_health(freshness_frame([]), coverage_frame([]), now=NOW)
    assert report.sources == ()
    assert report.exit_code() == EXIT_OK


def test_worst_indicator_governs_a_multi_indicator_source() -> None:
    report = evaluate_health(
        freshness_frame([collection("mixed")]),
        coverage_frame(
            [
                observation("mixed", "daily", NOW - timedelta(days=1), indicator="mixed.a"),
                observation("mixed", "monthly", NOW - timedelta(days=200), indicator="mixed.b"),
            ]
        ),
        now=NOW,
    )
    # The most recently observed indicator (daily, fresh) sets the frequency, so
    # the source is judged by the series most likely to be behind.
    assert health_of(report, "mixed").status == STATUS_OK


def test_to_dict_is_json_serializable() -> None:
    import json

    report = evaluate_health(
        freshness_frame([collection("tgju")]),
        coverage_frame([observation("tgju", "daily", NOW - timedelta(days=1))]),
        now=NOW,
    )
    payload = report.to_dict()
    assert payload["summary"] == {"total": 1, "ok": 1, "warnings": 0, "failed": 0}
    assert json.loads(json.dumps(payload))["sources"][0]["source_name"] == "tgju"


@pytest.mark.parametrize(
    ("status", "has_data", "missed", "expected"),
    [
        ("failed", True, 0, STATUS_FAILED),
        ("success", False, None, STATUS_NO_DATA),
        ("success", True, None, STATUS_UNKNOWN),
        ("success", True, 2, STATUS_STALE),
        ("partial", True, 0, STATUS_DEGRADED),
        ("success", True, 0, STATUS_OK),
    ],
)
def test_classification_precedence(
    status: str, has_data: bool, missed: int | None, expected: str
) -> None:
    from scripts.health_check import _classify

    assert _classify(status, has_data, missed) == expected
