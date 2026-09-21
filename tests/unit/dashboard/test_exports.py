"""Unit tests for data and chart exports."""

from contextlib import nullcontext
from io import BytesIO
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import pytest

import dashboard.components.exports as exports_module
from dashboard.components.direction import apply_plotly_typography
from dashboard.components.exports import (
    UTF8_BOM,
    ChromiumCapability,
    cached_figure_image,
    detect_chromium_capability,
    prepare_export_frame,
    render_chart_downloads,
    serialize_csv,
    serialize_excel,
    serialize_figure_html,
    serialize_figure_image,
    serialize_figure_images,
)
from dashboard.formatting import format_number, jalali_date_label
from dashboard.i18n import t

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
            "original_value": [12.0],
            "is_chain_linked": [True],
            "chain_linking_confidence": [0.9],
            "record_metadata": [{"method": "test"}],
        }
    )


def test_csv_preserves_metadata_and_iso_timestamp() -> None:
    payload = serialize_csv(selected_frame())
    content = payload.decode("utf-8")

    # UTF-8 with a BOM so Excel decodes the Persian headers correctly.
    assert payload.startswith(UTF8_BOM.encode("utf-8"))
    assert "2024-01-01T12:30:00+00:00" in content
    assert "تورم" in content
    assert "method" in content


def test_csv_carries_persian_headers_and_a_jalali_display_column() -> None:
    frame = prepare_export_frame(selected_frame())
    timestamp = selected_frame()["timestamp"].iloc[0]

    assert t("table.indicator_id") in frame.columns
    assert t("table.jalali_date") in frame.columns
    # The Jalali display column is additive: the ISO Gregorian value is kept.
    assert t("table.timestamp") in frame.columns
    assert frame.loc[0, t("table.jalali_date")] == jalali_date_label(timestamp, digit_mode="latin")


def test_excel_round_trip_preserves_selected_rows() -> None:
    output = BytesIO(serialize_excel(selected_frame()))
    frame = pd.read_excel(output, engine="openpyxl")

    assert len(frame) == 1
    # Latin digits keep the numeric cells machine-readable for downstream tooling.
    assert frame.loc[0, t("table.indicator_id")] == "a"
    assert frame.loc[0, t("table.value")] == 12.5


def test_excel_sheet_is_persian_and_right_to_left() -> None:
    import openpyxl

    output = BytesIO(serialize_excel(selected_frame()))
    workbook = openpyxl.load_workbook(output)

    assert t("export.sheet_name") in workbook.sheetnames
    assert workbook[t("export.sheet_name")].sheet_view.rightToLeft is True


def test_prepare_export_frame_keeps_quality_columns() -> None:
    frame = prepare_export_frame(selected_frame())

    # The underlying keys are still present (with Persian headers): the derived
    # provenance and the chain-linking fields are never dropped.
    assert t("table.record_metadata") in frame.columns
    assert t("table.original_value") in frame.columns
    assert t("table.is_chain_linked") in frame.columns
    assert t("table.chain_linking_confidence") in frame.columns
    assert isinstance(frame.loc[0, t("table.record_metadata")], str)


def test_prepare_export_frame_can_render_persian_digits() -> None:
    frame = prepare_export_frame(selected_frame(), digit_mode="fa")

    assert frame.loc[0, t("table.value")] == format_number(12.5)


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


@pytest.mark.integration()
def test_kaleido_renders_png_and_svg_with_the_new_template() -> None:
    """Real Chromium render smoke (AM-25): exercises the export path end to end.

    Needs a Chromium/Chrome executable discoverable by
    :func:`find_chromium_executable`, so it is marked ``integration`` and is
    deselected by ``make check`` (``-m "not integration"``). Run it explicitly::

        poetry run pytest tests/unit/dashboard/test_exports.py -m integration -q --no-cov
    """
    figure = apply_plotly_typography(go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 2, 5], name="سری")))

    images = serialize_figure_images(figure, ("png", "svg"))

    assert images["png"].startswith(b"\x89PNG\r\n\x1a\n")
    assert images["svg"].lstrip().startswith(b"<svg")


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
    assert set(downloads) == {t("export.download_html")}
    assert downloads[t("export.download_html")]["file_name"] == "iran-macro-test-chart.html"
    assert downloads[t("export.download_html")]["mime"] == "text/html"
    assert b"plotly" in downloads[t("export.download_html")]["data"]
    assert [button["label"] for button in fake_st.buttons] == [
        t("export.download_png"),
        t("export.download_svg"),
    ]
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
    assert set(downloads) == {
        t("export.download_html"),
        t("export.download_png"),
        t("export.download_svg"),
    }
    assert downloads[t("export.download_png")]["data"] == b"png"
    assert downloads[t("export.download_png")]["file_name"] == "iran-macro-test-chart.png"
    assert downloads[t("export.download_png")]["mime"] == "image/png"
    assert downloads[t("export.download_svg")]["data"] == b"svg"
    assert downloads[t("export.download_svg")]["file_name"] == "iran-macro-test-chart.svg"
    assert downloads[t("export.download_svg")]["mime"] == "image/svg+xml"
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
    assert {entry["label"] for entry in fake_st.download_buttons} == {t("export.download_html")}
    assert fake_st.captions == [t("export.image_unavailable")]
    assert fake_st.errors == []


def test_render_chart_downloads_surfaces_serialization_failure(
    monkeypatch: pytest.MonkeyPatch, available_chromium: None
) -> None:
    renderer = FakeFigureRenderer(error=RuntimeError("chromium crashed"))
    monkeypatch.setattr(exports_module, "serialize_figure_images", renderer)
    fake_st = FakeStreamlit(button_result=True)
    monkeypatch.setattr(exports_module, "st", fake_st)

    render_chart_downloads(chart_figure(), "iran-macro-test-chart")

    assert fake_st.errors[0] == t("export.image_failed", format="PNG", error="chromium crashed")
    assert t("export.download_png") not in {entry["label"] for entry in fake_st.download_buttons}
    assert {entry["label"] for entry in fake_st.download_buttons} == {t("export.download_html")}


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
