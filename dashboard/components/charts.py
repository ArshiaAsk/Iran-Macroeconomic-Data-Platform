"""Pure Plotly chart builders for dashboard pages."""

import math
from dataclasses import dataclass
from typing import Final, Literal

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.basedatatypes import BaseFigure

from dashboard.components.direction import apply_plotly_typography
from dashboard.formatting import format_number, jalali_date_label
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

#: Upper bound on Jalali tick labels drawn on a date axis. Plotly renders tick
#: labels client-side, so Persian digits need explicit ``ticktext``; a bounded
#: sample keeps a 4,000-session daily series legible instead of drawing every day.
MAX_JALALI_TICKS: Final[int] = 8

#: Frame columns passed to Plotly as hover ``customdata``: the Jalali label, the
#: Gregorian echo and the digit-grouped value.
_TIME_CUSTOM_DATA: Final[list[str]] = ["__jalali", "__gregorian", "__value"]


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
    """Build a time-series chart with a separate panel per indicator.

    Axis titles, legend/panel names and hover text are Persian; the date axis is
    labelled with Jalali ticks and the hover names the Gregorian date alongside
    the Jalali one. The underlying scale, facets and heights are unchanged from
    Task 15 -- only the presentation is localized.
    """
    if series.empty:
        return go.Figure()
    frame = _time_frame(series)
    figure = px.line(
        frame,
        x="timestamp",
        y="value",
        color="label",
        facet_row="indicator_id",
        markers=True,
        custom_data=_TIME_CUSTOM_DATA,
        labels=_time_axis_labels(),
    )
    figure.for_each_yaxis(lambda axis: axis.update(matches=None))
    figure.update_layout(height=bounded_chart_height(frame["indicator_id"].nunique()))
    return _style_time_figure(figure, frame)


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
    frame = _time_frame(series)
    figure = px.line(
        frame,
        x="timestamp",
        y="value",
        color="label",
        markers=True,
        custom_data=_TIME_CUSTOM_DATA,
        labels=_time_axis_labels(),
    )
    unit = shared_series_unit(frame)
    if unit is not None:
        figure.update_layout(yaxis_title=unit)
    figure.update_layout(height=MIN_CHART_HEIGHT, legend={"orientation": "h"})
    return _style_time_figure(figure, frame)


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
    ordered = list(dict.fromkeys(series["indicator_id"]))
    kept = ordered[:max_series]
    dropped = len(ordered) - len(kept)
    frame = _time_frame(series[series["indicator_id"].isin(kept)])
    figure = px.line(
        frame,
        x="timestamp",
        y="value",
        color="label",
        facet_col="indicator_id",
        facet_col_wrap=SMALL_MULTIPLES_COLUMNS,
        markers=True,
        custom_data=_TIME_CUSTOM_DATA,
        labels=_time_axis_labels(),
    )
    figure.for_each_yaxis(lambda axis: axis.update(matches=None))
    figure.update_layout(
        height=bounded_chart_height(len(kept), columns=SMALL_MULTIPLES_COLUMNS),
    )
    _style_time_figure(figure, frame)
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
    frame["__gregorian"] = _gregorian_dates(frame)
    frame["__value"] = [format_number(value) for value in frame["value"]]
    facet: dict[str, str] = {"facet_row": "indicator_id"} if facet_indicators else {}
    figure = px.line(
        frame,
        x=SURVEY_YEAR_COLUMN,
        y="value",
        color="label",
        markers=True,
        custom_data=["__gregorian", "__value"],
        labels={SURVEY_YEAR_COLUMN: t("chart.survey_year"), "value": t("chart.value")},
        **facet,
    )
    figure.update_traces(hovertemplate=_survey_year_hover_template())
    if facet_indicators:
        _localize_facet_titles(figure, frame)
        figure.for_each_yaxis(lambda axis: axis.update(matches=None))
        figure.update_layout(
            height=bounded_chart_height(frame["indicator_id"].nunique()),
        )
    else:
        figure.update_layout(height=MIN_CHART_HEIGHT)
    return apply_plotly_typography(figure)


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
            name=t("chart.chain_linked"),
            mode="lines+markers",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["original_value"],
            name=t("chart.original"),
            mode="lines+markers",
            line={"dash": "dash"},
        )
    )
    figure.update_layout(
        xaxis_title=t("chart.timestamp"),
        yaxis_title=t("chart.value"),
        legend={"orientation": "h"},
    )
    tickvals, ticktext = _jalali_tick_labels(frame["timestamp"])
    figure.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return apply_plotly_typography(figure)


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
            colorbar={"title": t("chart.pearson_r")},
        )
    )
    figure.update_layout(xaxis_title=t("chart.indicator"), yaxis_title=t("chart.indicator"))
    apply_plotly_typography(figure)
    return CorrelationBundle(figure, correlation, join_counts)


def _time_axis_labels() -> dict[str, str]:
    """Persian axis titles shared by the time-series builders."""
    return {"timestamp": t("chart.timestamp"), "value": t("chart.value")}


def _time_hover_template() -> str:
    """Hover text naming the Jalali date, its Gregorian echo and the value."""
    return (
        f"{t('chart.timestamp')}: %{{customdata[0]}}<br>"
        f"{t('chart.gregorian')}: %{{customdata[1]}}<br>"
        f"{t('chart.value')}: %{{customdata[2]}}"
        "<extra>%{fullData.name}</extra>"
    )


def _survey_year_hover_template() -> str:
    """Hover text for the categorical survey-year axis, with a Gregorian echo."""
    return (
        f"{t('chart.survey_year')}: %{{x}}<br>"
        f"{t('chart.gregorian')}: %{{customdata[0]}}<br>"
        f"{t('chart.value')}: %{{customdata[1]}}"
        "<extra>%{fullData.name}</extra>"
    )


def _time_frame(series: pd.DataFrame) -> pd.DataFrame:
    """Add the display label and hover columns a localized chart needs.

    The frame is copied; the caller's data is never mutated. ``label`` is the
    Persian indicator name (parent + derivation for a derived row, plus its unit),
    and the ``__*`` columns are pre-formatted display strings: Persian-digit
    Jalali labels, the ISO Gregorian echo and the digit-grouped value.
    """
    frame = series.copy()
    frame["label"] = frame.apply(_indicator_label, axis=1)
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    frame["__jalali"] = [jalali_date_label(timestamp) for timestamp in timestamps]
    frame["__gregorian"] = [timestamp.date().isoformat() for timestamp in timestamps]
    frame["__value"] = [format_number(value) for value in frame["value"]]
    return frame


def _gregorian_dates(frame: pd.DataFrame) -> list[str]:
    """ISO Gregorian date per row, or the unknown placeholder without timestamps."""
    if "timestamp" not in frame.columns:
        return [t("value.unknown")] * len(frame)
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    return [timestamp.date().isoformat() for timestamp in timestamps]


def _jalali_tick_labels(timestamps: pd.Series) -> tuple[list[pd.Timestamp], list[str]]:
    """Bounded Jalali tick positions and labels for a date axis.

    Returns ``(tickvals, ticktext)``: a chronological sample of at most
    :data:`MAX_JALALI_TICKS` stored timestamps and their Jalali labels. Persian
    digits cannot be produced by Plotly's client-side tick formatting, so the
    labels are pre-formatted here and handed to the axis explicitly.
    """
    unique = sorted({pd.Timestamp(value) for value in pd.to_datetime(timestamps, utc=True)})
    if not unique:
        return [], []
    if len(unique) > MAX_JALALI_TICKS:
        step = math.ceil(len(unique) / MAX_JALALI_TICKS)
        selected = unique[::step]
        if selected[-1] != unique[-1]:
            selected.append(unique[-1])
    else:
        selected = unique
    return selected, [jalali_date_label(timestamp) for timestamp in selected]


def _localize_facet_titles(figure: BaseFigure, frame: pd.DataFrame) -> None:
    """Replace ``indicator_id=<id>`` facet annotations with the display label.

    Plotly express titles a facet ``"<facet_column>=<value>"``. The facet column
    stays ``indicator_id`` so the grouping is unchanged from Task 15; only the
    rendered title is rewritten to the Persian label, which is what the analyst
    reads.
    """
    labels = {
        str(indicator): str(label)
        for indicator, label in zip(frame["indicator_id"], frame["label"], strict=True)
    }
    for annotation in figure.layout.annotations:
        _, separator, value = (annotation.text or "").partition("=")
        key = value.strip()
        if separator and key in labels:
            annotation.text = labels[key]


def _style_time_figure(figure: BaseFigure, frame: pd.DataFrame) -> BaseFigure:
    """Apply hover text, Jalali tick labels and Persian typography to a figure."""
    figure.update_traces(hovertemplate=_time_hover_template())
    _localize_facet_titles(figure, frame)
    tickvals, ticktext = _jalali_tick_labels(frame["timestamp"])
    figure.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext)
    return apply_plotly_typography(figure)


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
