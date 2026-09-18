"""Pure Plotly chart builders for dashboard pages."""

import math
from dataclasses import dataclass
from typing import Final, Literal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.basedatatypes import BaseFigure

from dashboard.formatting import format_number
from dashboard.i18n import t
from dashboard.labels import indicator_label

#: Categorical x-axis column of a survey-year chart: the Jalali year label of each
#: stored period end (see ``dashboard.page_view.survey_year_frame``).
SURVEY_YEAR_COLUMN = "survey_year"

#: Floor of every chart height in pixels: a single panel is never shorter than
#: this, so a lone series and a shared-axis overlay read the same.
MIN_CHART_HEIGHT: Final[int] = 420

#: Height in pixels contributed by one row of facet panels. This is the old
#: ``230 px x indicator count`` coefficient, now one term of a bounded heuristic
#: rather than an unbounded formula.
FACET_PANEL_HEIGHT: Final[int] = 230

#: Hard ceiling on any chart height in pixels. Past this the chart scrolls rather
#: than pushing the quality panel and downloads off the page, so selecting 50
#: indicators cannot produce an 11,500 px figure.
MAX_CHART_HEIGHT: Final[int] = 1200

#: Panels per row in the small-multiples grid. The grid wraps panels into rows, so
#: a ten-series selection becomes four rows instead of ten stacked panels.
SMALL_MULTIPLES_COLUMNS: Final[int] = 3

#: Documented cap on how many series the small-multiples grid draws. A larger
#: selection keeps the first ``SMALL_MULTIPLES_MAX_SERIES`` and the caller shows
#: the truncation notice; the full selection is still exported.
SMALL_MULTIPLES_MAX_SERIES: Final[int] = 12

ChartMode = Literal["facets", "overlay", "small_multiples"]
"""How a multi-indicator selection is drawn."""

#: One facet per indicator. This is the default, already unit-safe (one y-axis
#: per panel), and the only mode that is safe for mixed units.
CHART_MODE_FACETS: Final[ChartMode] = "facets"

#: All series on one shared axis. Only valid when every series shares one unit;
#: :func:`build_scaled_time_series_chart` falls back to facets otherwise.
CHART_MODE_OVERLAY: Final[ChartMode] = "overlay"

#: A capped grid of per-indicator panels. Cheaper vertically than the stacked
#: facet default for wide selections, at the cost of a documented series cap.
CHART_MODE_SMALL_MULTIPLES: Final[ChartMode] = "small_multiples"

#: Selectable modes in display order; the first entry is the default.
CHART_MODES: Final[tuple[ChartMode, ...]] = (
    CHART_MODE_FACETS,
    CHART_MODE_OVERLAY,
    CHART_MODE_SMALL_MULTIPLES,
)


@dataclass(frozen=True)
class ScaledChart:
    """A built figure plus how it was scaled and any caveat the caller must show."""

    figure: BaseFigure
    mode: ChartMode
    notice: str | None = None


def bounded_chart_height(panel_count: int, *, columns: int = 1) -> int:
    """Height in pixels for a facet grid, bounded by a documented ceiling.

    Replaces the unbounded ``230 px x indicator count`` formula: the height grows
    by :data:`FACET_PANEL_HEIGHT` per row of panels (so it is unchanged for up to
    five stacked panels), then clamps to
    ``[MIN_CHART_HEIGHT, MAX_CHART_HEIGHT]``.

    Args:
        panel_count: Number of indicator panels to draw; values below one are
            treated as one panel so an empty selection still yields a usable
            figure height
        columns: Panels per row; ``1`` is the stacked facet default, while the
            small-multiples grid passes :data:`SMALL_MULTIPLES_COLUMNS`

    Returns:
        A height in pixels, never above :data:`MAX_CHART_HEIGHT`

    Examples:
        >>> bounded_chart_height(1)
        420
        >>> bounded_chart_height(10, columns=3)
        920
    """
    panels = max(panel_count, 1)
    per_row = max(columns, 1)
    rows = math.ceil(panels / per_row)
    return max(MIN_CHART_HEIGHT, min(MAX_CHART_HEIGHT, FACET_PANEL_HEIGHT * rows))


def shared_series_unit(series: pd.DataFrame) -> str | None:
    """Return the single unit every series shares, or ``None``.

    The overlay mode draws one shared y-axis, which is only honest when the units
    agree. A missing unit anywhere -- an orphan derived series, for instance --
    makes the unit unknown, and unknown is not shared, so such a selection falls
    back to facets instead of guessing.

    Args:
        series: Gold observations with an optional ``unit`` column

    Returns:
        The shared unit, stripped, or ``None`` when the units are missing, blank
        or not all equal

    Examples:
        >>> shared_series_unit(pd.DataFrame({"unit": ["index", "index"]}))
        'index'
        >>> shared_series_unit(pd.DataFrame({"unit": ["index", "percent"]})) is None
        True
    """
    if series.empty or "unit" not in series.columns:
        return None
    units = series["unit"].dropna().astype(str).str.strip()
    if len(units) != len(series):
        return None
    unique = set(units)
    if len(unique) != 1:
        return None
    unit = unique.pop()
    return unit or None


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
    figure.update_layout(height=bounded_chart_height(frame["indicator_id"].nunique()))
    return figure


def build_overlay_chart(series: pd.DataFrame) -> BaseFigure:
    """Overlay every series on one shared axis labelled with its unit.

    The unit-aware axis label is the point of the mode: series that share a unit
    are comparable on one scale, and the label names that scale. Callers should
    confirm the unit with :func:`shared_series_unit` first (the selector
    :func:`build_scaled_time_series_chart` does); a mixed-unit selection must fall
    back to facets rather than share an axis.
    """
    if series.empty:
        return go.Figure()
    frame = series.copy()
    frame["label"] = frame.apply(_indicator_label, axis=1)
    figure = px.line(
        frame,
        x="timestamp",
        y="value",
        color="label",
        markers=True,
        labels={"timestamp": "Timestamp", "value": "Value"},
    )
    unit = shared_series_unit(frame)
    if unit is not None:
        figure.update_layout(yaxis_title=unit)
    figure.update_layout(height=MIN_CHART_HEIGHT, legend={"orientation": "h"})
    return figure


def build_small_multiples_chart(
    series: pd.DataFrame,
    *,
    max_series: int = SMALL_MULTIPLES_MAX_SERIES,
) -> ScaledChart:
    """Build a capped grid of per-indicator panels.

    The grid keeps the first ``max_series`` indicators in frame order and drops
    the rest, so a fifty-series selection stays legible; the caller renders the
    returned truncation notice naming the cap. Each panel keeps its own y-axis,
    so the mode is unit-safe exactly like the facet default.

    Args:
        series: Gold observations for the selection
        max_series: Series cap; must be positive

    Returns:
        The grid figure, its effective mode and a truncation notice when the
        selection exceeded the cap
    """
    if max_series <= 0:
        msg = "max_series must be positive"
        raise ValueError(msg)
    if series.empty:
        return ScaledChart(go.Figure(), CHART_MODE_SMALL_MULTIPLES)
    frame = series.copy()
    ordered = list(dict.fromkeys(frame["indicator_id"]))
    kept = ordered[:max_series]
    dropped = len(ordered) - len(kept)
    frame = frame[frame["indicator_id"].isin(kept)].copy()
    frame["label"] = frame.apply(_indicator_label, axis=1)
    figure = px.line(
        frame,
        x="timestamp",
        y="value",
        color="label",
        facet_col="indicator_id",
        facet_col_wrap=SMALL_MULTIPLES_COLUMNS,
        markers=True,
        labels={"timestamp": "Timestamp", "value": "Value"},
    )
    figure.for_each_yaxis(lambda axis: axis.update(matches=None))
    figure.update_layout(
        height=bounded_chart_height(len(kept), columns=SMALL_MULTIPLES_COLUMNS),
    )
    notice = None
    if dropped:
        notice = t("chart.small_multiples_capped", count=format_number(dropped))
    return ScaledChart(figure, CHART_MODE_SMALL_MULTIPLES, notice)


def build_scaled_time_series_chart(
    series: pd.DataFrame,
    *,
    mode: str = CHART_MODE_FACETS,
) -> ScaledChart:
    """Build the requested chart mode, falling back when the mode is unsafe.

    ``facets`` is the default and is returned for every selection. ``overlay`` is
    only honoured when every series shares one unit; a mixed or unknown-unit
    selection falls back to facets with a visible notice instead of sharing a
    misleading axis. ``small_multiples`` is capped at
    :data:`SMALL_MULTIPLES_MAX_SERIES`.

    Args:
        series: Gold observations for the selection, derived rows included
        mode: One of :data:`CHART_MODES`; an unknown value falls back to facets

    Returns:
        The figure, the mode actually drawn and an optional user-facing notice
    """
    if series.empty:
        return ScaledChart(go.Figure(), CHART_MODE_FACETS)
    if mode == CHART_MODE_OVERLAY:
        if shared_series_unit(series) is None:
            return ScaledChart(
                build_time_series_chart(series),
                CHART_MODE_FACETS,
                t("chart.overlay_mixed_units"),
            )
        return ScaledChart(build_overlay_chart(series), CHART_MODE_OVERLAY)
    if mode == CHART_MODE_SMALL_MULTIPLES:
        return build_small_multiples_chart(series)
    return ScaledChart(build_time_series_chart(series), CHART_MODE_FACETS)


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
        figure.update_layout(
            height=bounded_chart_height(frame["indicator_id"].nunique()),
        )
    else:
        figure.update_layout(height=MIN_CHART_HEIGHT)
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
