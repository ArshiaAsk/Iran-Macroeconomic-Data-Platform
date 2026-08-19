"""
Unit tests for the chain-linking algorithms.

Correctness is proven on **synthetic** series where the right answer is known
in advance: a segment scaled by a factor of exactly 2.5 must be recovered as
2.5, and growth rates must survive linking untouched. No database or network is
involved -- ``src.chain_linking.splice`` is deliberately pure.
"""

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from src.chain_linking.splice import (
    CONFIDENCE_OVERLAP_FLOOR,
    DETECTED_BY_LEVEL_SHIFT,
    DETECTED_BY_METADATA,
    GROWTH_TOLERANCE,
    IS_LINKED_COLUMN,
    LINKING_METHOD_LEVEL_SHIFT,
    LINKING_METHOD_OVERLAP,
    ORIGINAL_VALUE_COLUMN,
    SCALE_FACTOR_COLUMN,
    BaseYearBreak,
    calculate_confidence,
    chain_link,
    detect_base_year_breaks,
    min_overlap_periods,
    months_per_period,
    normalise_series,
    splice_series,
)
from src.utils.exceptions import ChainLinkingError

SCALE = 2.5


def annual_series(values: list[float | None], start_year: int = 2000) -> pd.DataFrame:
    """Build an annual series with period-end timestamps."""
    return pd.DataFrame(
        {
            "timestamp": [
                datetime(start_year + offset, 12, 31, tzinfo=UTC) for offset in range(len(values))
            ],
            "value": values,
        }
    )


def growth_of(frame: pd.DataFrame, column: str) -> pd.Series:
    """Year-over-year growth of one column."""
    return frame[column].pct_change(fill_method=None)


# ------------------------------------------------------------------- utilities


def test_min_overlap_periods_per_frequency() -> None:
    """Each frequency demands at least twelve months of overlap."""
    assert min_overlap_periods("annual") == 3
    assert min_overlap_periods("quarterly") == 6
    assert min_overlap_periods("monthly") == 12
    assert min_overlap_periods("unknown") == 3


def test_months_per_period_per_frequency() -> None:
    """Overlap length is reported in months regardless of frequency."""
    assert months_per_period("annual") == 12
    assert months_per_period("quarterly") == 3
    assert months_per_period("monthly") == 1
    assert months_per_period("unknown") == 12


def test_normalise_series_sorts_and_drops_nulls() -> None:
    """A clean, ascending, null-free frame is what the algorithms assume."""
    frame = pd.DataFrame(
        {
            "timestamp": [
                datetime(2002, 12, 31, tzinfo=UTC),
                datetime(2000, 12, 31, tzinfo=UTC),
                datetime(2001, 12, 31, tzinfo=UTC),
            ],
            "value": [102.0, 100.0, None],
        }
    )

    cleaned = normalise_series(frame)

    assert list(cleaned["value"]) == [100.0, 102.0]
    assert cleaned["timestamp"].is_monotonic_increasing
    assert cleaned["value"].dtype == "float64"


def test_normalise_series_rejects_missing_columns() -> None:
    """A frame without the contract columns cannot be linked."""
    with pytest.raises(ChainLinkingError, match="missing required column"):
        normalise_series(pd.DataFrame({"period": [1], "level": [2.0]}))


def test_normalise_series_does_not_mutate_the_input() -> None:
    """Silver frames are shared; linking must never edit them in place."""
    frame = annual_series([100.0, 110.0])
    before = frame.copy()

    normalise_series(frame)

    pd.testing.assert_frame_equal(frame, before)


# ------------------------------------------------------------------ confidence


def test_confidence_rises_with_overlap() -> None:
    """More overlap means a better-estimated scale factor."""
    short = calculate_confidence(12.0, 0.0)
    long = calculate_confidence(36.0, 0.0)

    assert short < long
    assert long == pytest.approx(1.0)


def test_confidence_falls_with_variance() -> None:
    """Disagreeing segment growth rates erode confidence."""
    stable = calculate_confidence(36.0, 0.0)
    noisy = calculate_confidence(36.0, 0.05)

    assert noisy < stable


def test_confidence_keeps_a_floor_for_zero_overlap() -> None:
    """A level-shift link is weak evidence, not zero evidence."""
    assert calculate_confidence(0.0, None) == pytest.approx(CONFIDENCE_OVERLAP_FLOOR)


def test_confidence_stays_within_zero_and_one() -> None:
    """The score is a probability-like quantity, and stays in range."""
    for overlap in (-10.0, 0.0, 12.0, 500.0):
        for variance in (None, 0.0, 0.5, 100.0):
            score = calculate_confidence(overlap, variance)
            assert 0.0 <= score <= 1.0


# --------------------------------------------------------------- break finding


def test_metadata_base_years_locate_the_break() -> None:
    """Catalog metadata is authoritative for where a rebase happened."""
    series = annual_series([100.0, 105.0, 110.0, 300.0, 315.0, 330.0])

    breaks = detect_base_year_breaks(series, base_years=[2000, 2003])

    assert len(breaks) == 1
    assert breaks[0].timestamp.year == 2003
    assert breaks[0].base_year_from == 2000
    assert breaks[0].base_year_to == 2003
    assert breaks[0].detected_by == DETECTED_BY_METADATA
    assert breaks[0].level_ratio == pytest.approx(300.0 / 110.0)


def test_metadata_base_years_handle_three_bases() -> None:
    """Two rebases produce two breaks, ordered oldest first."""
    series = annual_series([100.0, 105.0, 300.0, 315.0, 900.0, 950.0])

    breaks = detect_base_year_breaks(series, base_years=[2000, 2002, 2004])

    assert [item.timestamp.year for item in breaks] == [2002, 2004]


def test_no_break_is_reported_without_metadata_by_default() -> None:
    """A level jump alone is not evidence of a rebase -- it may be a shock."""
    series = annual_series([100.0, 105.0, 110.0, 400.0, 420.0, 440.0])

    assert detect_base_year_breaks(series) == []


def test_statistical_fallback_detects_a_level_shift_when_enabled() -> None:
    """Opt-in detection flags an isolated jump that dwarfs typical movement."""
    series = annual_series([100.0, 102.0, 104.0, 400.0, 408.0, 416.0])

    breaks = detect_base_year_breaks(series, statistical_fallback=True)

    assert len(breaks) == 1
    assert breaks[0].detected_by == DETECTED_BY_LEVEL_SHIFT
    assert breaks[0].timestamp.year == 2003


def test_statistical_fallback_ignores_short_series() -> None:
    """Too few observations to establish what 'typical' means."""
    series = annual_series([100.0, 400.0])

    assert detect_base_year_breaks(series, statistical_fallback=True) == []


def test_detect_returns_nothing_for_a_single_observation() -> None:
    """One point cannot contain a break."""
    assert detect_base_year_breaks(annual_series([100.0]), base_years=[2000, 2001]) == []


# -------------------------------------------------------- splicing two segments


def test_splice_recovers_a_known_scale_factor_exactly() -> None:
    """The synthetic answer is 2.5, so the splice must return 2.5."""
    old = annual_series([100.0, 110.0, 120.0, 130.0, 140.0])
    new = annual_series([value * SCALE for value in (120.0, 130.0, 140.0)], start_year=2002)

    spliced = splice_series(old, new)

    linked = spliced[spliced[IS_LINKED_COLUMN]]
    ratios = linked["value"] / linked[ORIGINAL_VALUE_COLUMN]
    assert ratios.to_numpy() == pytest.approx(SCALE)
    assert spliced[SCALE_FACTOR_COLUMN].iloc[0] == pytest.approx(SCALE)


def test_splice_preserves_growth_rates_within_tolerance() -> None:
    """Linking changes levels only -- the whole point of chain-linking."""
    old = annual_series([100.0, 108.0, 115.0, 121.0, 130.0])
    new = annual_series([value * SCALE for value in (115.0, 121.0, 130.0)], start_year=2002)

    spliced = splice_series(old, new)

    linked_growth = growth_of(spliced, "value")
    original_growth = growth_of(spliced, ORIGINAL_VALUE_COLUMN)
    junction = spliced[SCALE_FACTOR_COLUMN].diff().abs() > 0
    comparable = (~junction) & np.isfinite(linked_growth - original_growth)

    assert (linked_growth[comparable] - original_growth[comparable]).abs().max() <= (
        GROWTH_TOLERANCE
    )


def test_splice_keeps_the_new_series_authoritative() -> None:
    """Where both bases report, the current base wins."""
    old = annual_series([100.0, 110.0, 120.0, 130.0, 140.0])
    new = annual_series([300.0, 325.0, 350.0], start_year=2002)

    spliced = splice_series(old, new)

    assert len(spliced) == 5
    assert list(spliced["value"].tail(3)) == [300.0, 325.0, 350.0]
    assert list(spliced[IS_LINKED_COLUMN]) == [True, True, False, False, False]


def test_splice_rejects_insufficient_overlap() -> None:
    """Fewer than three shared annual periods is not enough to estimate a ratio."""
    old = annual_series([100.0, 110.0, 120.0])
    new = annual_series([300.0, 325.0], start_year=2002)

    with pytest.raises(ChainLinkingError, match="insufficient overlap"):
        splice_series(old, new)


def test_splice_rejects_a_requested_overlap_below_the_minimum() -> None:
    """An explicit overlap request cannot undercut the documented floor."""
    old = annual_series([100.0, 110.0, 120.0, 130.0, 140.0])
    new = annual_series([300.0, 325.0, 350.0], start_year=2002)

    with pytest.raises(ChainLinkingError, match="below the"):
        splice_series(old, new, overlap=2)


def test_splice_rejects_unusable_overlap_observations() -> None:
    """Zero and sign-flipping observations cannot yield a ratio."""
    old = annual_series([100.0, 110.0, 0.0, 0.0, 0.0])
    new = annual_series([0.0, 0.0, 0.0], start_year=2002)

    with pytest.raises(ChainLinkingError, match="usable overlap ratio"):
        splice_series(old, new)


# ------------------------------------------------------------------ chain_link


def test_chain_link_passthrough_when_no_break_exists() -> None:
    """Real WDI series have no internal break: nothing is linked or fabricated."""
    result = chain_link(annual_series([100.0, 105.0, 110.0, 116.0]))

    assert result.is_chain_linked is False
    assert result.linking_method is None
    assert result.records_linked == 0
    # A fabricated 1.0 would make unlinked data look independently verified.
    assert result.avg_confidence_score is None
    assert list(result.frame["value"]) == list(result.frame[ORIGINAL_VALUE_COLUMN])
    assert not result.frame[IS_LINKED_COLUMN].any()


def test_chain_link_handles_an_empty_series() -> None:
    """An indicator with no observations must not raise."""
    result = chain_link(pd.DataFrame({"timestamp": [], "value": []}))

    assert result.is_chain_linked is False
    assert result.frame.empty


def test_chain_link_links_in_series_breaks_from_metadata() -> None:
    """One series carrying two bases is rescaled onto the newest base."""
    series = annual_series([100.0, 105.0, 110.0, 275.0, 288.75, 302.5])

    result = chain_link(series, metadata={"base_years": [2000, 2003]})

    assert result.is_chain_linked is True
    assert result.linking_method == LINKING_METHOD_LEVEL_SHIFT
    assert result.records_linked == 3
    assert result.base_year_from == 2000
    assert result.base_year_to == 2003
    assert result.overlap_period_months == 0
    assert result.avg_confidence_score == pytest.approx(CONFIDENCE_OVERLAP_FLOOR)
    # 275 / 110 = 2.5 applied to the pre-break segment.
    assert list(result.frame["value"].head(3)) == pytest.approx([250.0, 262.5, 275.0])
    assert list(result.frame[ORIGINAL_VALUE_COLUMN].head(3)) == [100.0, 105.0, 110.0]


def test_chain_link_preserves_growth_across_an_in_series_break() -> None:
    """Within-segment growth rates are identical before and after linking."""
    series = annual_series([100.0, 105.0, 110.0, 275.0, 288.75, 302.5])

    result = chain_link(series, metadata={"base_years": [2000, 2003]})

    linked_growth = growth_of(result.frame, "value")
    original_growth = growth_of(result.frame, ORIGINAL_VALUE_COLUMN)
    junction = result.frame[SCALE_FACTOR_COLUMN].diff().abs() > 0
    comparable = (~junction) & np.isfinite(linked_growth - original_growth)

    assert (linked_growth[comparable] - original_growth[comparable]).abs().max() <= (
        GROWTH_TOLERANCE
    )


def test_chain_link_refuses_a_break_with_an_undefined_ratio() -> None:
    """A zero at the junction makes the scale factor unknowable."""
    series = annual_series([100.0, 105.0, 0.0, 275.0, 288.75])

    with pytest.raises(ChainLinkingError, match="junction ratio is undefined"):
        chain_link(series, metadata={"base_years": [2000, 2003]})


def test_chain_link_uses_the_overlap_method_for_multiple_segments() -> None:
    """Two published series that overlap are spliced on their shared periods."""
    old = annual_series([100.0, 110.0, 120.0, 130.0, 140.0])
    new = annual_series([value * SCALE for value in (120.0, 130.0, 140.0)], start_year=2002)

    result = chain_link(pd.DataFrame(), metadata={"segments": [old, new]})

    assert result.is_chain_linked is True
    assert result.linking_method == LINKING_METHOD_OVERLAP
    assert result.overlap_period_months == 36
    assert result.avg_confidence_score is not None
    assert result.avg_confidence_score == pytest.approx(1.0)
    assert result.growth_rate_variance == pytest.approx(0.0)
    assert result.records_linked == 2


def test_chain_link_folds_three_segments_transitively() -> None:
    """Scale factors compose: the oldest base lands on the newest, not the middle."""
    levels = [100.0 * 1.05**offset for offset in range(15)]  # 2000-2014
    oldest = annual_series(levels[:7])
    middle = annual_series([value * 2.0 for value in levels[4:11]], start_year=2004)
    newest = annual_series([value * 3.0 for value in levels[8:]], start_year=2008)

    result = chain_link(pd.DataFrame(), metadata={"segments": [oldest, middle, newest]})

    assert result.linking_method == LINKING_METHOD_OVERLAP
    assert len(result.frame) == 15
    # Every period ends up on the newest base, including the oldest segment.
    assert list(result.frame["value"]) == pytest.approx([value * 3.0 for value in levels])
    # 2000-2003 came from the oldest base and 2004-2007 from the middle one.
    assert result.records_linked == 8
    assert result.overlap_period_months == 72


def test_chain_link_segments_confidence_falls_with_a_noisy_overlap() -> None:
    """A ragged overlap yields a lower confidence than a clean one."""
    old = annual_series([100.0, 110.0, 120.0, 130.0, 140.0])
    clean = annual_series([value * SCALE for value in (120.0, 130.0, 140.0)], start_year=2002)
    noisy = annual_series([120.0 * 2.0, 130.0 * 3.0, 140.0 * 2.5], start_year=2002)

    tidy = chain_link(pd.DataFrame(), metadata={"segments": [old, clean]})
    ragged = chain_link(pd.DataFrame(), metadata={"segments": [old, noisy]})

    assert tidy.avg_confidence_score is not None
    assert ragged.avg_confidence_score is not None
    assert ragged.avg_confidence_score < tidy.avg_confidence_score


def test_chain_link_single_segment_is_a_passthrough() -> None:
    """One segment has nothing to be linked to."""
    result = chain_link(
        pd.DataFrame(), metadata={"segments": [annual_series([100.0, 110.0, 120.0])]}
    )

    assert result.is_chain_linked is False
    assert result.avg_confidence_score is None


def test_base_year_break_is_immutable() -> None:
    """Breaks are audit records; they must not be edited after detection."""
    item = BaseYearBreak(
        timestamp=datetime(2011, 12, 31, tzinfo=UTC),
        base_year_from=1997,
        base_year_to=2011,
        detected_by=DETECTED_BY_METADATA,
    )

    with pytest.raises(AttributeError):
        item.base_year_to = 2016  # type: ignore[misc]
