"""Unit tests for pure Plotly chart construction."""

import math

import pandas as pd
import pytest
from plotly.basedatatypes import BaseFigure

from dashboard.components.charts import (
    CHART_MODE_FACETS,
    CHART_MODE_OVERLAY,
    CHART_MODE_SMALL_MULTIPLES,
    FACET_PANEL_HEIGHT,
    MAX_CHART_HEIGHT,
    MIN_CHART_HEIGHT,
    MIN_CORRELATION_OVERLAP,
    SMALL_MULTIPLES_COLUMNS,
    SMALL_MULTIPLES_MAX_SERIES,
    bounded_chart_height,
    build_chain_linking_chart,
    build_correlation_chart,
    build_scaled_time_series_chart,
    build_small_multiples_chart,
    build_time_series_chart,
    shared_series_unit,
)
from dashboard.components.direction import FONT_STACK
from dashboard.components.tokens import CHART_CATEGORICAL_COLORS
from dashboard.formatting import format_number, jalali_date_label
from dashboard.i18n import t
from dashboard.labels import derived_label


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


def multi_indicator_frame(count: int, *, unit: str = "index") -> pd.DataFrame:
    """A frame with ``count`` single-observation indicators in frame order."""
    return pd.DataFrame(
        {
            "indicator_id": [f"i{index}" for index in range(count)],
            "name": [f"Indicator {index}" for index in range(count)],
            "timestamp": [pd.Timestamp("2020-01-01", tz="UTC")] * count,
            "value": [float(index) for index in range(count)],
            "unit": [unit] * count,
        }
    )


def yaxis_count(figure: BaseFigure) -> int:
    """How many y-axes a figure declares (one per panel in facet modes)."""
    return sum(1 for key in figure.layout.to_plotly_json() if key.startswith("yaxis"))


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


def test_bounded_height_matches_the_old_formula_below_the_cap() -> None:
    # Up to five stacked panels the height is exactly the old 230 px per panel;
    # the minimum keeps a single panel at the historical 420 px floor.
    assert bounded_chart_height(1) == MIN_CHART_HEIGHT
    assert bounded_chart_height(2) == 2 * FACET_PANEL_HEIGHT
    assert bounded_chart_height(5) == 5 * FACET_PANEL_HEIGHT


def test_bounded_height_is_capped_for_wide_selections() -> None:
    assert bounded_chart_height(6) == MAX_CHART_HEIGHT
    assert bounded_chart_height(50) == MAX_CHART_HEIGHT


def test_bounded_height_wraps_the_small_multiples_grid() -> None:
    # Ten panels in three-column rows are four rows, not ten.
    assert bounded_chart_height(10, columns=SMALL_MULTIPLES_COLUMNS) == 4 * FACET_PANEL_HEIGHT
    assert bounded_chart_height(3, columns=SMALL_MULTIPLES_COLUMNS) == MIN_CHART_HEIGHT


def test_bounded_height_treats_an_empty_grid_as_one_panel() -> None:
    assert bounded_chart_height(0) == MIN_CHART_HEIGHT
    assert bounded_chart_height(-4) == MIN_CHART_HEIGHT


def test_facet_default_keeps_one_panel_per_indicator_and_a_bounded_height() -> None:
    frame = multi_indicator_frame(10)

    figure = build_time_series_chart(frame)

    assert len(figure.data) == 10
    assert yaxis_count(figure) == 10
    assert figure.layout.height == MAX_CHART_HEIGHT


def test_default_mode_is_facets_without_a_notice() -> None:
    scaled = build_scaled_time_series_chart(series_frame())

    assert scaled.mode == CHART_MODE_FACETS
    assert scaled.notice is None
    assert yaxis_count(scaled.figure) == 2


def test_unknown_mode_falls_back_to_facets() -> None:
    scaled = build_scaled_time_series_chart(series_frame(), mode="normalized")

    assert scaled.mode == CHART_MODE_FACETS
    assert scaled.notice is None


def test_overlay_shares_one_axis_labelled_with_the_shared_unit() -> None:
    scaled = build_scaled_time_series_chart(series_frame(), mode=CHART_MODE_OVERLAY)

    assert scaled.mode == CHART_MODE_OVERLAY
    assert scaled.notice is None
    assert yaxis_count(scaled.figure) == 1
    assert scaled.figure.layout.yaxis.title.text == "index"
    assert scaled.figure.layout.height == MIN_CHART_HEIGHT


def test_overlay_falls_back_to_facets_on_mixed_units() -> None:
    frame = series_frame()
    frame["unit"] = ["index", "index", "percent", "percent"]

    scaled = build_scaled_time_series_chart(frame, mode=CHART_MODE_OVERLAY)

    assert scaled.mode == CHART_MODE_FACETS
    assert scaled.notice == t("chart.overlay_mixed_units")
    assert yaxis_count(scaled.figure) == 2


def test_overlay_falls_back_when_a_unit_is_unknown() -> None:
    frame = series_frame()
    frame["unit"] = ["index", None, "index", "index"]

    scaled = build_scaled_time_series_chart(frame, mode=CHART_MODE_OVERLAY)

    assert scaled.mode == CHART_MODE_FACETS
    assert scaled.notice == t("chart.overlay_mixed_units")


def test_overlay_labels_a_derived_row_after_its_parent() -> None:
    frame = pd.DataFrame(
        [
            {
                "indicator_id": "a",
                "name": "A",
                "timestamp": pd.Timestamp("2020-01-01", tz="UTC"),
                "value": 1.0,
                "unit": "index",
                "derived_from": None,
            },
            {
                "indicator_id": "WB.A.YOY",
                "name": "A",
                "timestamp": pd.Timestamp("2020-01-01", tz="UTC"),
                "value": 2.0,
                "unit": "index",
                "derived_from": "a",
            },
        ]
    )

    scaled = build_scaled_time_series_chart(frame, mode=CHART_MODE_OVERLAY)

    names = {trace.name for trace in scaled.figure.data}
    assert scaled.mode == CHART_MODE_OVERLAY
    assert any(derived_label("YOY") in name for name in names)
    assert not any("WB.A.YOY" in name for name in names)


def test_small_multiples_caps_the_series_count_with_a_notice() -> None:
    frame = multi_indicator_frame(SMALL_MULTIPLES_MAX_SERIES + 3)

    scaled = build_small_multiples_chart(frame)

    assert scaled.mode == CHART_MODE_SMALL_MULTIPLES
    assert len(scaled.figure.data) == SMALL_MULTIPLES_MAX_SERIES
    assert scaled.notice == t("chart.small_multiples_capped", count=format_number(3))
    assert scaled.figure.layout.height == bounded_chart_height(
        SMALL_MULTIPLES_MAX_SERIES, columns=SMALL_MULTIPLES_COLUMNS
    )


def test_small_multiples_below_the_cap_has_no_notice() -> None:
    scaled = build_scaled_time_series_chart(
        multi_indicator_frame(3), mode=CHART_MODE_SMALL_MULTIPLES
    )

    assert scaled.mode == CHART_MODE_SMALL_MULTIPLES
    assert scaled.notice is None
    assert yaxis_count(scaled.figure) == 3


def test_small_multiples_rejects_a_non_positive_cap() -> None:
    with pytest.raises(ValueError, match="max_series must be positive"):
        build_small_multiples_chart(series_frame(), max_series=0)


def test_small_multiples_keeps_frame_order() -> None:
    scaled = build_small_multiples_chart(multi_indicator_frame(3), max_series=2)

    assert scaled.notice == t("chart.small_multiples_capped", count=format_number(1))
    assert yaxis_count(scaled.figure) == 2


@pytest.mark.parametrize(
    "mode", [CHART_MODE_FACETS, CHART_MODE_OVERLAY, CHART_MODE_SMALL_MULTIPLES]
)
def test_empty_selection_builds_an_empty_figure_in_every_mode(mode: str) -> None:
    scaled = build_scaled_time_series_chart(pd.DataFrame(), mode=mode)

    assert scaled.figure.data == ()
    assert scaled.notice is None


@pytest.mark.parametrize(
    "units",
    [
        pd.DataFrame({"unit": ["index", "index"]}),
        pd.DataFrame({"unit": ["  index  ", "index"]}),
    ],
)
def test_shared_series_unit_accepts_one_consistent_unit(units: pd.DataFrame) -> None:
    assert shared_series_unit(units) == "index"


@pytest.mark.parametrize(
    "units",
    [
        pd.DataFrame({"unit": ["index", "percent"]}),
        pd.DataFrame({"unit": ["index", None]}),
        pd.DataFrame({"unit": ["index", ""]}),
        pd.DataFrame({"unit": [None, None]}),
        pd.DataFrame({"value": [1.0, 2.0]}),
        pd.DataFrame({"unit": []}),
    ],
)
def test_shared_series_unit_rejects_anything_but_one_known_unit(units: pd.DataFrame) -> None:
    assert shared_series_unit(units) is None


def test_time_series_chart_localizes_titles_ticks_and_hover() -> None:
    figure = build_time_series_chart(series_frame())

    assert figure.layout.xaxis.title.text == t("chart.timestamp")
    assert figure.layout.yaxis.title.text == t("chart.value")
    # Jalali tick labels carry Persian digits and a Gregorian echo in the hover.
    assert t("chart.gregorian") in figure.data[0].hovertemplate
    assert t("chart.value") in figure.data[0].hovertemplate
    assert tuple(figure.layout.xaxis.ticktext) == tuple(
        jalali_date_label(timestamp)
        for timestamp in (
            pd.Timestamp("2020-01-01", tz="UTC"),
            pd.Timestamp("2021-01-01", tz="UTC"),
        )
    )


def test_chart_legends_use_the_label_layer_with_a_catalog_fallback() -> None:
    # Unmapped ids fall back to the catalog name (never hidden), and the unit is
    # carried through the label layer into the legend.
    figure = build_time_series_chart(series_frame())

    assert {trace.name for trace in figure.data} == {"A (index)", "B (index)"}


def test_every_chart_builder_applies_the_persian_typography_template() -> None:
    frame = series_frame()
    frame["original_value"] = [None, 1.5, None, None]
    frame["is_chain_linked"] = [True, True, False, False]

    figures = (
        build_time_series_chart(frame),
        build_scaled_time_series_chart(frame, mode=CHART_MODE_OVERLAY).figure,
        build_small_multiples_chart(frame).figure,
        build_correlation_chart(frame).figure,
    )

    for figure in figures:
        assert figure.layout.template.layout.font.family == FONT_STACK


def test_every_chart_builder_applies_the_token_categorical_palette() -> None:
    frame = series_frame()
    frame["original_value"] = [None, 1.5, None, None]
    frame["is_chain_linked"] = [True, True, False, False]

    figures = (
        build_time_series_chart(frame),
        build_scaled_time_series_chart(frame, mode=CHART_MODE_OVERLAY).figure,
        build_small_multiples_chart(frame).figure,
        build_correlation_chart(frame).figure,
    )

    for figure in figures:
        assert list(figure.layout.template.layout.colorway) == list(CHART_CATEGORICAL_COLORS)


def test_shared_template_blanks_the_plotly_express_legend_title() -> None:
    """F3 (Task 35): ``color="label"`` must not surface as an English legend title.

    Plotly Express names the legend after the ``color`` column, and every
    time-series builder passes ``color="label"``, so without the shared
    ``apply_plotly_typography`` blanking the figure carried a literal "label"
    heading above the Persian series names.
    """
    frame = series_frame()

    figures = (
        build_time_series_chart(frame),
        build_scaled_time_series_chart(frame, mode=CHART_MODE_OVERLAY).figure,
        build_small_multiples_chart(frame).figure,
    )

    for figure in figures:
        assert not figure.layout.legend.title.text


def test_correlation_chart_localizes_its_axis_and_colorbar_titles() -> None:
    bundle = build_correlation_chart(series_frame())

    assert bundle.figure.layout.xaxis.title.text == t("chart.indicator")
    assert bundle.figure.layout.yaxis.title.text == t("chart.indicator")
    assert bundle.figure.data[0].colorbar.title.text == t("chart.pearson_r")


def overlapping_frame() -> pd.DataFrame:
    """Two indicators sharing exactly two timestamps (below the overlap guard)."""
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
            "value": [1.0, 2.0, 3.0, 4.0],
            "unit": ["index"] * 4,
        }
    )


def test_correlation_axes_use_display_names_not_ids() -> None:
    bundle = build_correlation_chart(series_frame())

    assert list(bundle.figure.data[0].x) == ["A", "B"]
    assert list(bundle.figure.data[0].y) == ["A", "B"]


def test_correlation_suppresses_cells_below_the_minimum_overlap() -> None:
    bundle = build_correlation_chart(overlapping_frame())

    # Two paired observations: the coefficient exists but is below the guard, so
    # the raw frame keeps it while the drawn cell is masked (insufficient overlap,
    # never read as zero).
    assert bundle.join_counts.loc["a", "b"] == 2
    assert bundle.min_overlap == MIN_CORRELATION_OVERLAP
    assert not pd.isna(bundle.correlation.loc["a", "b"])
    assert bundle.suppressed_pairs == (("a", "b"),)
    assert math.isnan(bundle.figure.data[0].z[0][1])


def test_correlation_keeps_cells_meeting_the_minimum_overlap() -> None:
    timestamps = [pd.Timestamp(f"20{year}-01-01", tz="UTC") for year in (20, 21, 22)]
    frame = pd.DataFrame(
        {
            "indicator_id": ["a"] * 3 + ["b"] * 3,
            "name": ["A"] * 3 + ["B"] * 3,
            "timestamp": timestamps * 2,
            "value": [1.0, 2.0, 3.0, 3.0, 4.0, 5.0],
            "unit": ["index"] * 6,
        }
    )

    bundle = build_correlation_chart(frame)

    assert bundle.join_counts.loc["a", "b"] == MIN_CORRELATION_OVERLAP
    assert bundle.suppressed_pairs == ()
    assert not math.isnan(bundle.figure.data[0].z[0][1])


def test_correlation_summary_reports_matched_observations_per_pair() -> None:
    bundle = build_correlation_chart(overlapping_frame())

    summary = bundle.overlap_summary
    assert list(summary.columns) == ["indicator_pair", "matched_observations", "meets_minimum"]
    assert summary.loc[0, "indicator_pair"] == "A ↔ B"
    assert summary.loc[0, "matched_observations"] == 2
    assert bool(summary.loc[0, "meets_minimum"]) is False


def test_empty_correlation_bundle_has_stable_summary_columns() -> None:
    bundle = build_correlation_chart(pd.DataFrame())

    assert bundle.figure.data == ()
    assert bundle.suppressed_pairs == ()
    assert list(bundle.overlap_summary.columns) == [
        "indicator_pair",
        "matched_observations",
        "meets_minimum",
    ]
