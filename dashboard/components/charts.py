"""Pure Plotly chart builders for dashboard pages."""

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.basedatatypes import BaseFigure


def build_time_series_chart(series: pd.DataFrame) -> BaseFigure:
    """Build a time-series chart with a separate panel per indicator."""
    if series.empty:
        return go.Figure()
    frame = series.copy()
    frame["label"] = frame.apply(_indicator_label, axis=1)
    figure = px.line(
        frame,
        x="timestamp",
        y="value",
        color="label",
        facet_row="indicator_id",
        markers=True,
        labels={"timestamp": "Timestamp", "value": "Value"},
    )
    figure.for_each_yaxis(lambda axis: axis.update(matches=None))
    figure.update_layout(height=max(420, 230 * frame["indicator_id"].nunique()))
    return figure


def build_chain_linking_chart(series: pd.DataFrame) -> BaseFigure:
    """Compare chain-linked values with original values where both exist."""
    frame = series[
        series.get("is_chain_linked", pd.Series(False, index=series.index)).astype(bool)
        & series["original_value"].notna()
    ].copy()
    if frame.empty:
        return go.Figure()
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["value"],
            name="Chain-linked",
            mode="lines+markers",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["original_value"],
            name="Original",
            mode="lines+markers",
            line={"dash": "dash"},
        )
    )
    figure.update_layout(
        xaxis_title="Timestamp",
        yaxis_title="Value",
        legend={"orientation": "h"},
    )
    return figure


@dataclass(frozen=True)
class CorrelationBundle:
    """Correlation output plus the exact-timestamp join diagnostics."""

    figure: BaseFigure
    correlation: pd.DataFrame
    join_counts: pd.DataFrame


def build_correlation_chart(series: pd.DataFrame) -> CorrelationBundle:
    """Build a correlation heatmap using only exact timestamp matches."""
    if series.empty:
        return CorrelationBundle(go.Figure(), pd.DataFrame(), pd.DataFrame())
    wide = series.pivot_table(
        index="timestamp",
        columns="indicator_id",
        values="value",
        aggfunc="first",
    )
    correlation = wide.corr()
    present = wide.notna()
    join_counts = present.astype(int).T.dot(present.astype(int))
    figure = go.Figure(
        go.Heatmap(
            z=correlation,
            x=correlation.columns.tolist(),
            y=correlation.columns.tolist(),
            zmin=-1,
            zmax=1,
            colorbar={"title": "Pearson r"},
        )
    )
    figure.update_layout(xaxis_title="Indicator", yaxis_title="Indicator")
    return CorrelationBundle(figure, correlation, join_counts)


def build_coverage_chart(coverage: pd.DataFrame) -> BaseFigure:
    """Build a compact coverage chart from repository output."""
    if coverage.empty:
        return go.Figure()
    frame = coverage.copy()
    frame["observation_count"] = pd.to_numeric(frame["observation_count"], errors="coerce").fillna(
        0
    )
    figure = px.bar(
        frame,
        x="indicator_id",
        y="observation_count",
        color="domain",
        hover_data=["observed_start", "observed_end"],
        labels={"observation_count": "Gold observations"},
    )
    figure.update_layout(xaxis_title="Indicator", height=max(420, 40 * len(frame)))
    return figure


def _indicator_label(row: pd.Series) -> str:
    unit = row.get("unit")
    suffix = f" ({unit})" if pd.notna(unit) else ""
    return f"{row.get('name', row['indicator_id'])}{suffix}"
