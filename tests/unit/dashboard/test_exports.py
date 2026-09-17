"""Unit tests for data and chart exports."""

from contextlib import nullcontext
from io import BytesIO
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import pytest

import dashboard.components.exports as exports_module
from dashboard.components.exports import (
    ChromiumCapability,
    cached_figure_image,
    detect_chromium_capability,
    prepare_export_frame,
    render_chart_downloads,
    serialize_csv,
    serialize_excel,
    serialize_figure_html,
    serialize_figure_image,
)

MISSING_CHROMIUM_MESSAGE = (
    "No Chromium executable found. Install Chrome, run `poetry run plotly_get_chrome`, "
    "or set DASHBOARD_CHROME_PATH."
)


class FakeStreamlit:
    """Minimal Streamlit stand-in that records export-control calls."""

    def __init__(self, button_result: bool = False) -> None:
        self.button_result = button_result
        self.buttons: list[dict[str, Any]] = []
        self.download_buttons: list[dict[str, Any]] = []
        self.captions: list[str] = []
        self.errors: list[str] = []

    def columns(self, spec: Any) -> list[Any]:
        count = len(spec) if isinstance(spec, list | tuple) else int(spec)
        return [nullcontext() for _ in range(count)]

    def button(self, label: str, key: str | None = None, disabled: bool = False) -> bool:
        self.buttons.append({"label": label, "key": key, "disabled": disabled})
        return self.button_result

    def download_button(self, label: str, data: Any = None, **kwargs: Any) -> None:
        self.download_buttons.append({"label": label, "data": data, **kwargs})

    def caption(self, message: str) -> None:
        self.captions.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


def chart_figure() -> go.Figure:
    return go.Figure(go.Scatter(x=[1], y=[2]))


class FakeFigureRenderer:
    """Records every on-demand image render request."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.error = error

    def __call__(self, figure: go.Figure, image_formats: tuple[str, ...]) -> dict[str, bytes]:
        self.calls.append(image_formats)
        if self.error is not None:
            raise self.error
        return {image_format: image_format.encode() for image_format in image_formats}


@pytest.fixture()
def available_chromium(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(exports_module, "find_chromium_executable", lambda: "/fake/chrome")
    cached_figure_image.clear()


@pytest.fixture()
def missing_chromium(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing() -> str:
        raise RuntimeError(MISSING_CHROMIUM_MESSAGE)

    monkeypatch.setattr(exports_module, "find_chromium_executable", raise_missing)
    cached_figure_image.clear()


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


def test_detect_chromium_capability_reports_available_executable(
    available_chromium: None,
) -> None:
    capability = detect_chromium_capability()

    assert capability == ChromiumCapability(available=True, executable="/fake/chrome")
    assert capability.message == ""


def test_detect_chromium_capability_reports_missing_chromium(missing_chromium: None) -> None:
    capability = detect_chromium_capability()

    assert capability.available is False
    assert capability.executable is None
    assert "plotly_get_chrome" in capability.message
    assert "DASHBOARD_CHROME_PATH" in capability.message


def test_render_chart_downloads_defers_image_serialization(
    monkeypatch: pytest.MonkeyPatch, available_chromium: None
) -> None:
    renderer = FakeFigureRenderer()
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)
    fake_st = FakeStreamlit(button_result=False)
    monkeypatch.setattr(exports_module, "st", fake_st)

    render_chart_downloads(chart_figure(), "iran-macro-test-chart")

    assert renderer.calls == []
    downloads = {entry["label"]: entry for entry in fake_st.download_buttons}
    assert set(downloads) == {"Download HTML"}
    assert downloads["Download HTML"]["file_name"] == "iran-macro-test-chart.html"
    assert downloads["Download HTML"]["mime"] == "text/html"
    assert b"plotly" in downloads["Download HTML"]["data"]
    assert [button["label"] for button in fake_st.buttons] == ["Download PNG", "Download SVG"]
    assert [button["disabled"] for button in fake_st.buttons] == [False, False]
    assert fake_st.captions == []


def test_render_chart_downloads_renders_images_on_explicit_request(
    monkeypatch: pytest.MonkeyPatch, available_chromium: None
) -> None:
    renderer = FakeFigureRenderer()
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)
    fake_st = FakeStreamlit(button_result=True)
    monkeypatch.setattr(exports_module, "st", fake_st)

    render_chart_downloads(chart_figure(), "iran-macro-test-chart")

    assert renderer.calls == [("png",), ("svg",)]
    downloads = {entry["label"]: entry for entry in fake_st.download_buttons}
    assert set(downloads) == {"Download HTML", "Download PNG", "Download SVG"}
    assert downloads["Download PNG"]["data"] == b"png"
    assert downloads["Download PNG"]["file_name"] == "iran-macro-test-chart.png"
    assert downloads["Download PNG"]["mime"] == "image/png"
    assert downloads["Download SVG"]["data"] == b"svg"
    assert downloads["Download SVG"]["file_name"] == "iran-macro-test-chart.svg"
    assert downloads["Download SVG"]["mime"] == "image/svg+xml"
    assert fake_st.errors == []


def test_render_chart_downloads_reports_missing_chromium(
    monkeypatch: pytest.MonkeyPatch, missing_chromium: None
) -> None:
    renderer = FakeFigureRenderer()
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)
    fake_st = FakeStreamlit(button_result=True)
    monkeypatch.setattr(exports_module, "st", fake_st)

    render_chart_downloads(chart_figure(), "iran-macro-test-chart")

    assert renderer.calls == []
    assert [button["disabled"] for button in fake_st.buttons] == [True, True]
    assert {entry["label"] for entry in fake_st.download_buttons} == {"Download HTML"}
    assert fake_st.captions == [MISSING_CHROMIUM_MESSAGE]
    assert fake_st.errors == []


def test_render_chart_downloads_surfaces_serialization_failure(
    monkeypatch: pytest.MonkeyPatch, available_chromium: None
) -> None:
    renderer = FakeFigureRenderer(error=RuntimeError("chromium crashed"))
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)
    fake_st = FakeStreamlit(button_result=True)
    monkeypatch.setattr(exports_module, "st", fake_st)

    render_chart_downloads(chart_figure(), "iran-macro-test-chart")

    assert "Download PNG failed: chromium crashed" in fake_st.errors[0]
    assert "Download PNG" not in {entry["label"] for entry in fake_st.download_buttons}
    assert {entry["label"] for entry in fake_st.download_buttons} == {"Download HTML"}


def test_cached_figure_image_reuses_bytes_for_unchanged_figure(
    monkeypatch: pytest.MonkeyPatch, available_chromium: None
) -> None:
    renderer = FakeFigureRenderer()
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)
    figure_json = chart_figure().to_json()

    first = cached_figure_image(figure_json, "png")
    second = cached_figure_image(figure_json, "png")

    assert first == second == b"png"
    assert renderer.calls == [("png",)]


def test_cached_figure_image_keys_on_figure_content(
    monkeypatch: pytest.MonkeyPatch, available_chromium: None
) -> None:
    renderer = FakeFigureRenderer()
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)

    cached_figure_image(chart_figure().to_json(), "png")
    cached_figure_image(go.Figure(go.Scatter(x=[1], y=[3])).to_json(), "png")

    assert renderer.calls == [("png",), ("png",)]
