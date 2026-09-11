"""Data-quality summaries for Gold observations."""

from datetime import datetime

import pandas as pd
import streamlit as st

PERIODS_PER_YEAR = {"daily": 365.25, "weekly": 52.18, "monthly": 12, "quarterly": 4, "annual": 1}


def summarize_quality(
    series: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    """Summarize coverage, gaps, and chain-linking quality without filling data."""
    records: list[dict[str, object]] = []
    for indicator_id, frame in series.groupby("indicator_id", sort=False):
        frequency = str(frame["frequency"].iloc[0]) if not frame.empty else "unknown"
        expected = expected_observation_count(frequency, start_date, end_date)
        records.append(
            {
                "indicator_id": indicator_id,
                "name": frame["name"].iloc[0] if "name" in frame else indicator_id,
                "rows_returned": int(len(frame)),
                "expected_observations": expected,
                "missing_periods": None if expected is None else max(0, expected - len(frame)),
                "observed_start": frame["timestamp"].min(),
                "observed_end": frame["timestamp"].max(),
                "chain_linked_rows": int(
                    frame.get("is_chain_linked", pd.Series(False, index=frame.index)).sum()
                ),
                "average_confidence": frame.get(
                    "chain_linking_confidence", pd.Series(dtype="float64")
                ).mean(),
                "frequency": frequency,
            }
        )
    return pd.DataFrame(records)


def expected_observation_count(
    frequency: str,
    start_date: datetime,
    end_date: datetime,
) -> int | None:
    """Estimate expected periods for a supported frequency; never create observations."""
    if start_date > end_date:
        return 0
    periods_per_year = PERIODS_PER_YEAR.get(frequency)
    if periods_per_year is None:
        return None
    days = (end_date - start_date).total_seconds() / 86400 + 1
    return max(0, int(days * periods_per_year / 365.25))


def render_quality_summary(quality: pd.DataFrame) -> None:
    """Display quality diagnostics, including zero-row and sparse-history cases."""
    if quality.empty:
        st.info("No Gold observations match the current filters.")
        return
    st.dataframe(quality, use_container_width=True, hide_index=True)
    if (quality["rows_returned"] == 1).any():
        st.warning(
            "One or more selected series contains only one observation. "
            "TGJU is a snapshot source; history accumulates through scheduled daily collection."
        )
    if quality["missing_periods"].notna().any() and (quality["missing_periods"] > 0).any():
        st.warning("The selected date range contains missing periods. No values were filled.")
