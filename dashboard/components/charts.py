"""Pure Plotly chart builders for dashboard pages."""

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.basedatatypes import BaseFigure

from dashboard.i18n import t
from dashboard.labels import indicator_label

#: Categorical x-axis column of a survey-year chart: the Jalali year label of each
#: stored period end (see ``dashboard.page_view.survey_year_frame``).
SURVEY_YEAR_COLUMN = "survey_year"


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


def build_survey_year_chart(
    series: pd.DataFrame,
    *,
    facet_indicators: bool = True,
) -> BaseFigure:
    """Build a line chart on a Jalali survey-year axis.

    The x-axis is the categorical Jalali year label of each stored period end
    (``SURVEY_YEAR_COLUMN``), which is how HBSIR's annual survey years are read:
    the survey year is the Jalali year containing the stored period end, never the
    Gregorian date's year. Rows are plotted chronologically, so the category order
    is the survey order even though the labels are strings.

    Args:
        series: Frame carrying ``SURVEY_YEAR_COLUMN``, ``value``, ``indicator_id``
            and (when the catalog resolved it) ``name``/``unit``
        facet_indicators: ``True`` (the default) gives every indicator its own
            panel, which is the unit-safe mode when the selected series carry
            different units (a Gini index next to a percentage share). Pass
            ``False`` for series that already share a unit, such as the ten
            decile shares.

    Returns:
        A Plotly figure, empty when there is nothing to plot
    """
    if series.empty:
        return go.Figure()
    frame = series.copy()
    frame["label"] = frame.apply(_indicator_label, axis=1)
    if "timestamp" in frame.columns:
        frame = frame.sort_values("timestamp")
    facet: dict[str, str] = {"facet_row": "indicator_id"} if facet_indicators else {}
    figure = px.line(
        frame,
        x=SURVEY_YEAR_COLUMN,
        y="value",
        color="label",
        markers=True,
        labels={SURVEY_YEAR_COLUMN: t("chart.survey_year"), "value": t("chart.value")},
        **facet,
    )
    if facet_indicators:
        figure.for_each_yaxis(lambda axis: axis.update(matches=None))
        figure.update_layout(height=max(420, 230 * frame["indicator_id"].nunique()))
    else:
        figure.update_layout(height=420)
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
    """Label a series by its display name, falling back to its Gold indicator id.

    The label comes from :func:`dashboard.labels.indicator_label`, so a derived
    row (``record_metadata["derived_from"]`` is set) is named after its parent
    plus the suffix fragment and is distinguishable from the level in the
    legend. ``load_series`` LEFT JOINs the catalog, so ``name`` is genuinely
    absent for a series without a catalog row (and for an unresolvable derived
    parent) — the label must then be the Gold id, never the string ``"None"``.
    """
    name = row.get("name")
    catalog_name = name.strip() if isinstance(name, str) and name.strip() else None
    derived_from = row.get("derived_from")
    parent = (
        derived_from.strip() if isinstance(derived_from, str) and derived_from.strip() else None
    )
    label = indicator_label(str(row["indicator_id"]), catalog_name, parent)
    unit = row.get("unit")
    suffix = f" ({unit})" if pd.notna(unit) else ""
    return f"{label}{suffix}"
