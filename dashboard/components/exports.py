"""Selected-data and chart export helpers."""

import asyncio
import os
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from kaleido import Kaleido


def prepare_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert timestamps and JSON metadata into stable export representations."""
    result = frame.copy()
    if "timestamp" in result.columns:
        result["timestamp"] = result["timestamp"].map(_iso_timestamp)
    for column in ("record_metadata", "base_years"):
        if column in result.columns:
            result[column] = result[column].map(_json_value)
    return result


def serialize_csv(frame: pd.DataFrame) -> bytes:
    """Serialize a selected dataframe to UTF-8 CSV."""
    csv_text = prepare_export_frame(frame).to_csv(index=False)
    return csv_text.encode("utf-8")


def serialize_excel(frame: pd.DataFrame) -> bytes:
    """Serialize a selected dataframe to an Excel workbook."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        prepare_export_frame(frame).to_excel(writer, index=False, sheet_name="Selected data")
    return bytes(output.getvalue())


def serialize_figure_html(figure: go.Figure) -> bytes:
    """Serialize a Plotly figure to standalone interactive HTML."""
    html = str(figure.to_html(include_plotlyjs="cdn"))
    return html.encode("utf-8")


def serialize_figure_image(figure: go.Figure, image_format: str) -> bytes:
    """Serialize a Plotly figure to PNG or SVG."""
    return serialize_figure_images(figure, (image_format,))[image_format]


def serialize_figure_images(
    figure: go.Figure,
    image_formats: tuple[str, ...] = ("png", "svg"),
) -> dict[str, bytes]:
    """Render multiple static chart formats in one Chromium session."""

    async def render() -> dict[str, bytes]:
        renderer = Kaleido(path=find_chromium_executable())
        await renderer.open()
        try:
            rendered = await asyncio.gather(
                *(
                    renderer.calc_fig(figure, opts={"format": image_format})
                    for image_format in image_formats
                )
            )
        finally:
            await renderer.close()
        return dict(zip(image_formats, rendered, strict=True))

    return asyncio.run(render())


def render_data_downloads(frame: pd.DataFrame, file_prefix: str) -> None:
    """Render CSV and Excel download buttons for the selected data."""
    columns = st.columns(2)
    with columns[0]:
        st.download_button(
            "Download CSV",
            data=serialize_csv(frame),
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            disabled=frame.empty,
        )
    with columns[1]:
        st.download_button(
            "Download Excel",
            data=serialize_excel(frame),
            file_name=f"{file_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=frame.empty,
        )


def render_chart_downloads(figure: go.Figure, file_prefix: str) -> None:
    """Render HTML, PNG, and SVG chart download buttons."""
    images = serialize_figure_images(figure, ("png", "svg"))
    columns = st.columns(3)
    with columns[0]:
        st.download_button(
            "Download HTML",
            data=serialize_figure_html(figure),
            file_name=f"{file_prefix}.html",
            mime="text/html",
        )
    with columns[1]:
        st.download_button(
            "Download PNG",
            data=images["png"],
            file_name=f"{file_prefix}.png",
            mime="image/png",
        )
    with columns[2]:
        st.download_button(
            "Download SVG",
            data=images["svg"],
            file_name=f"{file_prefix}.svg",
            mime="image/svg+xml",
        )


def _iso_timestamp(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _json_value(value: object) -> object:
    if value is None:
        return value
    if isinstance(value, dict | list):
        return str(value)
    return value


def find_chromium_executable() -> str:
    """Find a usable Chromium executable without relying on Snap wrappers."""
    configured = os.environ.get("DASHBOARD_CHROME_PATH")
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path)
        msg = f"DASHBOARD_CHROME_PATH does not point to a Chromium executable: {configured}"
        raise RuntimeError(msg)

    for executable in ("google-chrome", "google-chrome-stable"):
        found = shutil.which(executable)
        if found:
            return found

    playwright_root = Path.home() / ".cache" / "ms-playwright"
    candidates = sorted(playwright_root.glob("chromium-*/chrome-linux*/chrome"), reverse=True)
    if candidates:
        return str(candidates[0])

    choreographer_root = Path.home() / ".local" / "share" / "choreographer" / "deps"
    candidates = sorted(choreographer_root.glob("**/chrome"))
    if candidates:
        return str(candidates[0])

    msg = (
        "No Chromium executable found. Install Chrome, run `poetry run plotly_get_chrome`, "
        "or set DASHBOARD_CHROME_PATH."
    )
    raise RuntimeError(msg)
