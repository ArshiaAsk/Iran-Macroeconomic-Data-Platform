"""Unit tests for Gold quality summaries and calendar-aware expected periods."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pytest

from dashboard.components import quality as quality_module
from dashboard.components.quality import (
    CALENDAR_CALENDAR,
    CALENDAR_TRADING,
    DAYS_PER_YEAR,
    MISSING_PERIOD_WARNING_RATIO,
    PERIODS_PER_YEAR,
    SUPPORTED_FREQUENCIES,
    TRADING_SESSIONS_PER_YEAR,
    ExpectedPeriods,
    calendar_for_source,
    expected_observation_count,
    expected_periods,
    render_quality_summary,
    summarize_quality,
)
from dashboard.i18n import t
from dashboard.labels import FREQUENCY_LABELS

TSETMC_LIVE_START = datetime(2008, 12, 4, tzinfo=UTC)
TSETMC_LIVE_END = datetime(2026, 9, 15, tzinfo=UTC)
TSETMC_LIVE_SESSIONS = 4285


class RecordingStreamlit:
    """Minimal ``st`` stand-in that records what a render path emitted."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.frames: list[pd.DataFrame] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def info(self, message: str) -> None:
        self.infos.append(message)

    def dataframe(self, frame: pd.DataFrame, **kwargs: Any) -> None:
        self.frames.append(frame)


def quality_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indicator_id": ["tgju", "tgju", "tgju"],
            "name": ["USD", "USD", "USD"],
            "timestamp": [
                pd.Timestamp("2024-01-01", tz="UTC"),
                pd.Timestamp("2024-01-02", tz="UTC"),
                pd.Timestamp("2024-01-04", tz="UTC"),
            ],
            "value": [1.0, 2.0, 4.0],
            "original_value": [None, 2.0, None],
            "is_chain_linked": [False, True, False],
            "chain_linking_confidence": [None, 0.8, None],
            "frequency": ["daily", "daily", "daily"],
        }
    )


def daily_frame(
    timestamps: pd.DatetimeIndex,
    source_name: str,
    indicator_id: str = "TSETMC.TEDPIX",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indicator_id": [indicator_id] * len(timestamps),
            "name": ["TEDPIX"] * len(timestamps),
            "timestamp": timestamps,
            "value": [1.0] * len(timestamps),
            "is_chain_linked": [False] * len(timestamps),
            "chain_linking_confidence": [None] * len(timestamps),
            "frequency": ["daily"] * len(timestamps),
            "source_name": [source_name] * len(timestamps),
        }
    )


def expect_periods(
    frequency: str,
    start: datetime,
    end: datetime,
    **kwargs: Any,
) -> ExpectedPeriods:
    periods = expected_periods(frequency, start, end, **kwargs)
    assert periods is not None
    return periods


# --- Registry consistency -------------------------------------------------


def test_supported_frequencies_match_the_label_registry() -> None:
    assert frozenset(FREQUENCY_LABELS) == SUPPORTED_FREQUENCIES
    assert set(PERIODS_PER_YEAR) == SUPPORTED_FREQUENCIES
    for frequency in FREQUENCY_LABELS:
        periods = expected_periods(
            frequency, datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
        )
        assert periods is not None
        assert periods.count == 1


def test_calendar_for_source_is_keyed_by_source_slug() -> None:
    assert calendar_for_source("tsetmc") == CALENDAR_TRADING
    assert calendar_for_source("tgju") == CALENDAR_CALENDAR
    assert calendar_for_source(None) == CALENDAR_CALENDAR


# --- Daily ----------------------------------------------------------------


def test_daily_calendar_expects_every_tehran_day_in_a_multi_day_range() -> None:
    periods = expect_periods(
        "daily", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 4, tzinfo=UTC)
    )

    assert periods.period_keys == ("2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04")
    assert periods.count == 4
    assert periods.calendar == CALENDAR_CALENDAR
    assert periods.is_estimate is False
    assert periods.start == datetime(2024, 1, 1, tzinfo=UTC)
    assert periods.end == datetime(2024, 1, 4, tzinfo=UTC)


def test_daily_same_day_range_expects_one_period() -> None:
    periods = expect_periods(
        "daily", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
    )

    assert periods.period_keys == ("2024-01-01",)
    assert periods.count == 1


def test_daily_keys_follow_the_tehran_local_date_not_the_utc_date() -> None:
    # 2026-09-08T20:30Z is 2026-09-09T00:00 in Tehran: the stored UTC date differs.
    evening = datetime(2026, 9, 8, 20, 30, tzinfo=UTC)
    periods = expect_periods("daily", evening, evening)

    assert evening.date().isoformat() == "2026-09-08"
    assert periods.period_keys == ("2026-09-09",)
    assert periods.count == 1


def test_daily_range_starting_before_tehran_midnight_spans_two_local_days() -> None:
    periods = expect_periods(
        "daily",
        datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
        datetime(2026, 9, 8, 21, 0, tzinfo=UTC),
    )

    assert periods.period_keys == ("2026-09-08", "2026-09-09")
    assert periods.count == 2


def test_daily_week_calendar_expects_seven_days_while_trading_expects_fewer() -> None:
    saturday = datetime(2024, 1, 6, tzinfo=UTC)
    friday = datetime(2024, 1, 12, tzinfo=UTC)

    calendar_rule = expect_periods("daily", saturday, friday)
    trading_rule = expect_periods("daily", saturday, friday, source_name="tsetmc")

    assert calendar_rule.count == 7
    assert trading_rule.calendar == CALENDAR_TRADING
    assert trading_rule.is_estimate is True
    assert trading_rule.period_keys == ()
    assert trading_rule.count == round(7 * TRADING_SESSIONS_PER_YEAR / DAYS_PER_YEAR)
    assert trading_rule.count < calendar_rule.count


def test_trading_daily_single_day_still_expects_one_session() -> None:
    day = datetime(2024, 1, 6, tzinfo=UTC)
    periods = expect_periods("daily", day, day, source_name="tsetmc")

    assert periods.count == 1
    assert periods.is_estimate is True


def test_trading_rule_is_an_empirical_rate_not_a_session_calendar() -> None:
    """The estimate carries no dates, so it cannot tell a session from a holiday."""
    iranian_weekend = expect_periods(
        "daily",
        datetime(2024, 1, 11, tzinfo=UTC),
        datetime(2024, 1, 12, tzinfo=UTC),
        source_name="tsetmc",
    )
    trading_days = expect_periods(
        "daily",
        datetime(2024, 1, 6, tzinfo=UTC),
        datetime(2024, 1, 7, tzinfo=UTC),
        source_name="tsetmc",
    )

    # Thursday 2024-01-11 / Friday 2024-01-12 are not TSE sessions and Saturday
    # 2024-01-06 / Sunday 2024-01-07 are, yet both two-day ranges get the same
    # rate-based count: the rule is date-agnostic, not a session list.
    assert iranian_weekend.period_keys == ()
    assert trading_days.period_keys == ()
    assert iranian_weekend.count == round(2 * TRADING_SESSIONS_PER_YEAR / DAYS_PER_YEAR)
    assert iranian_weekend.count == trading_days.count == 1


def test_trading_calendar_can_be_requested_explicitly() -> None:
    start = datetime(2024, 1, 6, tzinfo=UTC)
    end = datetime(2024, 1, 12, tzinfo=UTC)
    from_source = expect_periods("daily", start, end, source_name="tsetmc")
    from_argument = expect_periods("daily", start, end, calendar=CALENDAR_TRADING)

    assert from_argument == from_source


def test_non_daily_frequencies_ignore_the_trading_calendar() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 12, 31, tzinfo=UTC)

    assert expect_periods("monthly", start, end, source_name="tsetmc").count == 12


# --- Weekly ---------------------------------------------------------------


def test_weekly_expects_iso_weeks_not_seven_days() -> None:
    periods = expect_periods(
        "weekly", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 28, tzinfo=UTC)
    )

    assert periods.period_keys == ("2024-W01", "2024-W02", "2024-W03", "2024-W04")
    assert periods.count == 4


def test_weekly_one_week_range_and_monday_boundary() -> None:
    assert expect_periods(
        "weekly", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 7, tzinfo=UTC)
    ).period_keys == ("2024-W01",)

    periods = expect_periods(
        "weekly", datetime(2024, 1, 7, tzinfo=UTC), datetime(2024, 1, 8, tzinfo=UTC)
    )
    assert periods.period_keys == ("2024-W01", "2024-W02")
    assert periods.count == 2


def test_weekly_key_uses_the_iso_year_at_the_year_boundary() -> None:
    periods = expect_periods(
        "weekly", datetime(2024, 12, 30, tzinfo=UTC), datetime(2025, 1, 5, tzinfo=UTC)
    )

    assert periods.period_keys == ("2025-W01",)
    assert periods.count == 1


# --- Monthly --------------------------------------------------------------


def test_monthly_expects_one_period_per_calendar_month() -> None:
    periods = expect_periods(
        "monthly", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 12, 31, tzinfo=UTC)
    )

    assert periods.count == 12
    assert periods.period_keys[0] == "2024-01"
    assert periods.period_keys[-1] == "2024-12"


def test_monthly_single_month_and_month_end_key() -> None:
    periods = expect_periods(
        "monthly", datetime(2024, 2, 29, tzinfo=UTC), datetime(2024, 2, 29, tzinfo=UTC)
    )

    assert periods.period_keys == ("2024-02",)
    assert periods.count == 1


def test_monthly_leap_year_february_counts_once_across_the_leap_day() -> None:
    periods = expect_periods(
        "monthly", datetime(2024, 2, 1, tzinfo=UTC), datetime(2024, 2, 29, tzinfo=UTC)
    )
    assert periods.period_keys == ("2024-02",)

    span = expect_periods(
        "monthly", datetime(2023, 1, 31, tzinfo=UTC), datetime(2024, 2, 29, tzinfo=UTC)
    )
    assert span.count == 14
    assert span.period_keys[-1] == "2024-02"


def test_monthly_keys_use_the_storage_calendar_not_the_tehran_day() -> None:
    # Period ends are stamped at UTC midnight, so a late-evening UTC bound keeps
    # its UTC month while the Tehran day-based key rolls into the next day.
    bound = datetime(2024, 12, 31, 21, 0, tzinfo=UTC)

    assert expect_periods("monthly", bound, bound).period_keys == ("2024-12",)
    assert expect_periods("daily", bound, bound).period_keys == ("2025-01-01",)


# --- Quarterly ------------------------------------------------------------


def test_quarterly_single_quarter_and_full_year() -> None:
    quarter = expect_periods(
        "quarterly", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 3, 31, tzinfo=UTC)
    )
    assert quarter.period_keys == ("2024-Q1",)
    assert quarter.count == 1

    year = expect_periods(
        "quarterly", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 12, 31, tzinfo=UTC)
    )
    assert year.period_keys == ("2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4")
    assert year.count == 4


def test_quarterly_crosses_the_year_boundary() -> None:
    periods = expect_periods(
        "quarterly", datetime(2024, 10, 1, tzinfo=UTC), datetime(2025, 3, 31, tzinfo=UTC)
    )

    assert periods.period_keys == ("2024-Q4", "2025-Q1")
    assert periods.count == 2


# --- Annual ---------------------------------------------------------------


def test_annual_single_year_multiple_years_and_year_boundary() -> None:
    one = expect_periods(
        "annual", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 12, 31, tzinfo=UTC)
    )
    assert one.period_keys == ("2024",)
    assert one.count == 1

    many = expect_periods(
        "annual", datetime(2022, 12, 31, tzinfo=UTC), datetime(2024, 12, 31, tzinfo=UTC)
    )
    assert many.period_keys == ("2022", "2023", "2024")
    assert many.count == 3

    boundary = expect_periods(
        "annual", datetime(2024, 12, 31, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)
    )
    assert boundary.period_keys == ("2024", "2025")
    assert boundary.count == 2


# --- Contracts and edge cases --------------------------------------------


def test_missing_or_unsupported_frequency_has_no_expectation() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 4, tzinfo=UTC)

    assert expected_periods(None, start, end) is None
    assert expected_periods("irregular", start, end) is None
    assert expected_observation_count("irregular", start, end) is None
    assert expected_observation_count("", start, end) is None


def test_unknown_calendar_rule_raises() -> None:
    with pytest.raises(ValueError, match="unsupported calendar rule"):
        expected_periods(
            "daily",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 4, tzinfo=UTC),
            calendar="lunar",  # type: ignore[arg-type]
        )


def test_reversed_range_is_empty_rather_than_swapped() -> None:
    periods = expect_periods(
        "monthly", datetime(2024, 6, 30, tzinfo=UTC), datetime(2024, 1, 31, tzinfo=UTC)
    )

    assert periods.period_keys == ()
    assert periods.count == 0
    assert (
        expected_observation_count(
            "daily", datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
        )
        == 0
    )


def test_aware_bounds_are_normalized_to_utc() -> None:
    tehran_offset = timezone(timedelta(hours=3, minutes=30))
    start = datetime(2024, 1, 1, 3, 30, tzinfo=tehran_offset)
    end = datetime(2024, 1, 2, 3, 30, tzinfo=tehran_offset)

    periods = expect_periods("daily", start, end)

    assert periods.start == datetime(2024, 1, 1, tzinfo=UTC)
    assert periods.end == datetime(2024, 1, 2, tzinfo=UTC)
    assert periods.period_keys == ("2024-01-01", "2024-01-02")


def test_naive_bounds_are_read_as_utc() -> None:
    # Naive bounds are the documented "read as UTC" contract, not a bug.
    naive = expect_periods(
        "daily",
        datetime.fromisoformat("2024-01-01"),
        datetime.fromisoformat("2024-01-02"),
    )
    aware = expect_periods(
        "daily", datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 2, tzinfo=UTC)
    )

    assert naive == aware


# --- summarize_quality / render_quality_summary ---------------------------


def test_quality_summary_counts_rows_gaps_and_chain_links() -> None:
    quality = summarize_quality(
        quality_frame(),
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 4, tzinfo=UTC),
    )

    row = quality.loc[0]
    assert row["rows_returned"] == 3
    assert row["expected_observations"] == 4
    assert bool(row["expected_is_estimated"]) is False
    assert row["missing_periods"] == 1
    assert row["chain_linked_rows"] == 1
    assert row["average_confidence"] == 0.8


def test_unknown_frequency_does_not_invent_expected_coverage() -> None:
    frame = quality_frame()
    frame["frequency"] = "irregular"
    quality = summarize_quality(
        frame, datetime(2024, 1, 1, tzinfo=UTC), datetime(2024, 1, 4, tzinfo=UTC)
    )

    assert pd.isna(quality.loc[0, "expected_observations"])
    assert pd.isna(quality.loc[0, "missing_periods"])
    assert pd.isna(quality.loc[0, "expected_is_estimated"])


def test_invalid_date_range_has_zero_expected_observations() -> None:
    assert (
        expected_observation_count(
            "daily", datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
        )
        == 0
    )


def test_summarize_quality_marks_trading_estimates() -> None:
    timestamps = pd.date_range("2024-01-06", periods=5, freq="D", tz="UTC")
    quality = summarize_quality(
        daily_frame(timestamps, "tsetmc"),
        datetime(2024, 1, 6, tzinfo=UTC),
        datetime(2024, 1, 10, tzinfo=UTC),
    )

    row = quality.loc[0]
    assert bool(row["expected_is_estimated"]) is True
    assert row["expected_observations"] == round(5 * TRADING_SESSIONS_PER_YEAR / DAYS_PER_YEAR)


def test_derived_tsetmc_row_with_inherited_source_uses_the_session_estimate() -> None:
    # The repository fills ``source_name`` for a derived row from its parent
    # catalog row (``record_metadata['derived_from']``), so a derived TSETMC
    # series reaches this utility with the trading source slug, not a null.
    timestamps = pd.date_range("2024-01-06", periods=5, freq="D", tz="UTC")
    frame = daily_frame(timestamps, "tsetmc", indicator_id="TSETMC.TEDPIX.RET1D")
    quality = summarize_quality(
        frame, datetime(2024, 1, 6, tzinfo=UTC), datetime(2024, 1, 10, tzinfo=UTC)
    )

    row = quality.loc[0]
    assert row["indicator_id"] == "TSETMC.TEDPIX.RET1D"
    assert bool(row["expected_is_estimated"]) is True
    assert row["expected_observations"] == round(5 * TRADING_SESSIONS_PER_YEAR / DAYS_PER_YEAR)


def test_tsetmc_like_session_count_does_not_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = pd.date_range(TSETMC_LIVE_START, TSETMC_LIVE_END, periods=TSETMC_LIVE_SESSIONS)
    quality = summarize_quality(daily_frame(sessions, "tsetmc"), TSETMC_LIVE_START, TSETMC_LIVE_END)

    row = quality.loc[0]
    assert bool(row["expected_is_estimated"]) is True
    assert row["missing_periods"] < MISSING_PERIOD_WARNING_RATIO * row["expected_observations"]

    recorder = RecordingStreamlit()
    monkeypatch.setattr(quality_module, "st", recorder)
    render_quality_summary(quality)

    assert recorder.warnings == []


def test_calendar_daily_gap_for_the_same_rows_is_material_and_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = pd.date_range(TSETMC_LIVE_START, TSETMC_LIVE_END, periods=TSETMC_LIVE_SESSIONS)
    quality = summarize_quality(daily_frame(sessions, "tgju"), TSETMC_LIVE_START, TSETMC_LIVE_END)

    row = quality.loc[0]
    assert bool(row["expected_is_estimated"]) is False
    assert row["missing_periods"] > MISSING_PERIOD_WARNING_RATIO * row["expected_observations"]

    recorder = RecordingStreamlit()
    monkeypatch.setattr(quality_module, "st", recorder)
    render_quality_summary(quality)

    assert recorder.warnings == [t("warn.missing_periods")]


def test_small_gap_below_the_materiality_threshold_does_not_warn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    months = pd.date_range("2019-01-31", "2023-12-31", freq="ME", tz="UTC")
    partial = daily_frame(months.delete(-1), "world_bank")
    partial["frequency"] = "monthly"
    quality = summarize_quality(
        partial, datetime(2019, 1, 31, tzinfo=UTC), datetime(2023, 12, 31, tzinfo=UTC)
    )

    assert quality.loc[0, "missing_periods"] == 1
    assert quality.loc[0, "missing_periods"] < (
        MISSING_PERIOD_WARNING_RATIO * quality.loc[0, "expected_observations"]
    )

    recorder = RecordingStreamlit()
    monkeypatch.setattr(quality_module, "st", recorder)
    render_quality_summary(quality)

    assert recorder.warnings == []
