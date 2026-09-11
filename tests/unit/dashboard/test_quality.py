"""Unit tests for Gold quality summaries."""

from datetime import UTC, datetime

import pandas as pd

from dashboard.components.quality import expected_observation_count, summarize_quality


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


def test_quality_summary_counts_rows_gaps_and_chain_links() -> None:
    quality = summarize_quality(
        quality_frame(),
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 4, tzinfo=UTC),
    )

    row = quality.loc[0]
    assert row["rows_returned"] == 3
    assert row["expected_observations"] == 4
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


def test_invalid_date_range_has_zero_expected_observations() -> None:
    assert (
        expected_observation_count(
            "daily", datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)
        )
        == 0
    )
