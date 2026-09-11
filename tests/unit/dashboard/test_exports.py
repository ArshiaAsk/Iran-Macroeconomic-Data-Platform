"""Unit tests for data and chart exports."""

from io import BytesIO

import pandas as pd
import plotly.graph_objects as go

import dashboard.components.exports as exports_module
from dashboard.components.exports import (
    prepare_export_frame,
    serialize_csv,
    serialize_excel,
    serialize_figure_html,
    serialize_figure_image,
)


def selected_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "indicator_id": ["a"],
            "name": ["تورم"],
            "timestamp": [pd.Timestamp("2024-01-01T12:30:00+00:00")],
            "value": [12.5],
            "unit": ["%"],
            "is_chain_linked": [True],
            "record_metadata": [{"method": "test"}],
        }
    )


def test_csv_preserves_metadata_and_iso_timestamp() -> None:
    content = serialize_csv(selected_frame()).decode("utf-8")

    assert "2024-01-01T12:30:00+00:00" in content
    assert "تورم" in content
    assert "method" in content


def test_excel_round_trip_preserves_selected_rows() -> None:
    output = BytesIO(serialize_excel(selected_frame()))
    frame = pd.read_excel(output, engine="openpyxl")

    assert len(frame) == 1
    assert frame.loc[0, "indicator_id"] == "a"
    assert frame.loc[0, "value"] == 12.5


def test_prepare_export_frame_keeps_quality_columns() -> None:
    frame = prepare_export_frame(selected_frame())

    assert list(frame.columns) == list(selected_frame().columns)
    assert isinstance(frame.loc[0, "record_metadata"], str)


def test_chart_exports_html_and_svg(monkeypatch) -> None:
    figure = go.Figure(go.Scatter(x=[1], y=[2]))
    monkeypatch.setattr(exports_module, "find_chromium_executable", lambda: "/fake/chrome")

    class FakeKaleido:
        def __init__(self, **kwargs: object) -> None:
            return None

        async def open(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def calc_fig(self, figure: object, opts: dict[str, str]) -> bytes:
            return opts["format"].encode()

    monkeypatch.setattr(exports_module, "Kaleido", FakeKaleido)

    assert b"plotly" in serialize_figure_html(figure)
    assert serialize_figure_image(figure, "svg") == b"svg"
