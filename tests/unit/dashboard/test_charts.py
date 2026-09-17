"""Unit tests for pure Plotly chart construction."""

import pandas as pd
import pytest

from dashboard.components.charts import (
    build_chain_linking_chart,
    build_correlation_chart,
    build_time_series_chart,
)


def series_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indicator_id": ["a", "a", "b", "b"],
            "name": ["A", "A", "B", "B"],
            "timestamp": [
                pd.Timestamp("2020-01-01", tz="UTC"),
                pd.Timestamp("2021-01-01", tz="UTC"),
                pd.Timestamp("2020-01-01", tz="UTC"),
                pd.Timestamp("2021-01-01", tz="UTC"),
            ],
            "value": [1.0, 2.0, 2.0, 4.0],
            "unit": ["index", "index", "index", "index"],
        }
    )


def test_time_series_chart_has_one_trace_per_indicator() -> None:
    figure = build_time_series_chart(series_frame())

    assert len(figure.data) == 2


def test_chain_linking_chart_uses_only_rows_with_original_values() -> None:
    frame = series_frame()
    frame["original_value"] = [None, 1.5, None, None]
    frame["is_chain_linked"] = [True, True, False, False]
    figure = build_chain_linking_chart(frame)

    assert len(figure.data) == 2
    assert len(figure.data[0].x) == 1


def test_correlation_uses_exact_timestamp_matches() -> None:
    frame = series_frame()
    frame.loc[3, "timestamp"] = pd.Timestamp("2022-01-01", tz="UTC")
    bundle = build_correlation_chart(frame)

    assert bundle.join_counts.loc["a", "b"] == 1
    assert pd.isna(bundle.correlation.loc["a", "b"])


@pytest.mark.parametrize("missing", [None, float("nan"), "", "   "])
def test_time_series_chart_labels_catalog_less_series_by_indicator_id(missing: object) -> None:
    frame = series_frame()
    frame["name"] = [missing, missing, "B", "B"]

    figure = build_time_series_chart(frame)

    assert {trace.name for trace in figure.data} == {"a (index)", "B (index)"}
