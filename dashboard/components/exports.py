"""Selected-data and chart export helpers."""

import asyncio
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Final

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from kaleido import Kaleido

from dashboard.components.tables import (
    NUMBER_COLUMNS,
    localized_column_values,
    localized_header,
)
from dashboard.formatting import DigitMode
from dashboard.i18n import t
from src.utils.logging import get_logger

logger = get_logger(__name__)

#: Static chart formats that require Chromium and are rendered on demand.
IMAGE_EXPORT_FORMATS: Final[tuple[str, ...]] = ("png", "svg")

#: Byte-order mark prepended to CSV output so Excel decodes the Persian headers
#: and indicator names correctly. Spreadsheet tooling detects the encoding from it.
UTF8_BOM: Final[str] = "\ufeff"

#: Display column carrying the Jalali date of the stored timestamp. The ISO-8601
#: Gregorian ``timestamp`` column is kept alongside it, never replaced: the stored
#: value stays the auditable source of truth.
JALALI_EXPORT_COLUMN: Final[str] = "timestamp_jalali"

#: Download MIME types keyed by image format.
IMAGE_MIME_TYPES: Final[dict[str, str]] = {
    "png": "image/png",
    "svg": "image/svg+xml",
}


@dataclass(frozen=True)
class ChromiumCapability:
    """Result of probing for the Chromium executable used by image exports."""

    available: bool
    executable: str | None = None
    message: str = ""


def prepare_export_frame(
    frame: pd.DataFrame,
    *,
    digit_mode: DigitMode = "latin",
) -> pd.DataFrame:
    """Convert a selected frame into a localized, spreadsheet-ready export.

    The stored values stay the source of truth: the ISO-8601 Gregorian
    ``timestamp`` column is kept and a Jalali display column is added beside it,
    indicator names are shown through the label layer, and Persian headers come
    from the shared table registry (:mod:`dashboard.components.tables`) so the
    grid and the exports cannot drift.

    Numbers default to Latin digits and stay numeric, so downstream tooling keeps
    reading them; passing ``digit_mode="fa"`` renders them as Persian strings for
    a human-facing copy. ``record_metadata``, ``original_value``,
    ``is_chain_linked`` and the chain-linking confidence columns are always kept.

    Args:
        frame: Selected Gold frame
        digit_mode: ``"latin"`` (default) keeps numeric cells machine-readable;
            ``"fa"`` renders them with Persian digits

    Returns:
        A localized frame with Persian headers
    """
    result = frame.copy()
    if "timestamp" in result.columns:
        jalali = localized_column_values(result, "timestamp", digit_mode=digit_mode)
        position = list(result.columns).index("timestamp") + 1
        result.insert(position, JALALI_EXPORT_COLUMN, jalali)
        result["timestamp"] = result["timestamp"].map(_iso_timestamp)
    for column in list(result.columns):
        if column in ("timestamp", JALALI_EXPORT_COLUMN):
            continue
        if digit_mode == "latin" and column in NUMBER_COLUMNS:
            continue
        result[column] = localized_column_values(  # type: ignore[assignment]
            result, str(column), digit_mode=digit_mode
        )
    return result.rename(
        columns={str(column): localized_header(str(column)) for column in result.columns}
    )


def serialize_csv(frame: pd.DataFrame, *, digit_mode: DigitMode = "latin") -> bytes:
    """Serialize a selected dataframe to UTF-8 CSV with a BOM.

    The BOM makes Excel decode the Persian headers and indicator names correctly;
    the bytes are still UTF-8.
    """
    csv_text = prepare_export_frame(frame, digit_mode=digit_mode).to_csv(index=False)
    return (UTF8_BOM + csv_text).encode("utf-8")


def serialize_excel(frame: pd.DataFrame, *, digit_mode: DigitMode = "latin") -> bytes:
    """Serialize a selected dataframe to an RTL Excel workbook.

    The sheet name is Persian and the sheet direction is right-to-left so the
    Persian headers read naturally in a spreadsheet application.
    """
    output = BytesIO()
    sheet_name = t("export.sheet_name")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        prepare_export_frame(frame, digit_mode=digit_mode).to_excel(
            writer, index=False, sheet_name=sheet_name
        )
        writer.sheets[sheet_name].sheet_view.rightToLeft = True
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
    """Render the digit-mode control and CSV/Excel download buttons.

    Exports default to Latin digits (machine-readable); the toggle switches to
    Persian digits for a human-facing copy. File names stay ASCII so a browser
    cannot mangle them; the Persian label lives in the button and the sheet name.
    """
    digit_mode = _export_digit_mode(file_prefix)
    columns = st.columns(2)
    with columns[0]:
        st.download_button(
            t("export.download_csv"),
            data=serialize_csv(frame, digit_mode=digit_mode),
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            disabled=frame.empty,
        )
    with columns[1]:
        st.download_button(
            t("export.download_excel"),
            data=serialize_excel(frame, digit_mode=digit_mode),
            file_name=f"{file_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=frame.empty,
        )


def _export_digit_mode(file_prefix: str) -> DigitMode:
    """Render the export digit-mode toggle and return the chosen direction."""
    persian = st.toggle(
        t("export.persian_digits"),
        value=False,
        key=f"{file_prefix}-persian-digits",
    )
    return "fa" if persian else "latin"


def render_chart_downloads(figure: go.Figure, file_prefix: str) -> None:
    """Render an eager HTML download and lazy PNG/SVG chart download controls.

    HTML is cheap, so its control is ready on page load. PNG/SVG rendering needs
    Chromium: the page only reports whether it is usable, and the image bytes are
    rendered (and cached per figure content) when the matching control is
    activated. A missing browser disables those controls instead of failing the
    page.
    """
    capability = detect_chromium_capability()
    columns = st.columns(3)
    with columns[0]:
        st.download_button(
            t("export.download_html"),
            data=serialize_figure_html(figure),
            file_name=f"{file_prefix}.html",
            mime="text/html",
            key=f"{file_prefix}-html",
        )
    for column, image_format in zip(columns[1:], IMAGE_EXPORT_FORMATS, strict=True):
        with column:
            _render_image_download(figure, file_prefix, image_format, capability)
    if not capability.available:
        st.caption(t("export.image_unavailable"))


def _render_image_download(
    figure: go.Figure,
    file_prefix: str,
    image_format: str,
    capability: ChromiumCapability,
) -> None:
    """Render one on-demand image control inside the caller's column."""
    label = t(f"export.download_{image_format}")
    key = f"{file_prefix}-{image_format}"
    if not capability.available:
        st.button(label, key=f"{key}-trigger", disabled=True)
        return
    if not st.button(label, key=f"{key}-trigger"):
        return
    try:
        payload = cached_figure_image(figure.to_json(), image_format)
    except Exception as error:
        logger.exception("Chart image export failed for %s", image_format)
        st.error(t("export.image_failed", format=image_format.upper(), error=error))
        return
    st.download_button(
        label,
        data=payload,
        file_name=f"{file_prefix}.{image_format}",
        mime=IMAGE_MIME_TYPES[image_format],
        key=f"{key}-download",
        on_click="ignore",
    )


@st.cache_data(show_spinner=False, max_entries=32)
def cached_figure_image(figure_json: str, image_format: str) -> bytes:
    """Render one image format once per figure content and reuse the bytes."""
    return serialize_figure_image(pio.from_json(figure_json), image_format)


def detect_chromium_capability() -> ChromiumCapability:
    """Probe Chromium availability without raising, so pages load without it."""
    try:
        executable = find_chromium_executable()
    except RuntimeError as error:
        return ChromiumCapability(available=False, message=str(error))
    return ChromiumCapability(available=True, executable=executable)


def _iso_timestamp(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def find_chromium_executable() -> str:
    """Find a usable Chromium executable without relying on Snap wrappers.

    Raises:
        RuntimeError: If no usable executable is configured or installed. The
            message names the ``DASHBOARD_CHROME_PATH`` override and
            ``plotly_get_chrome`` so the caller can surface it to the user.
    """
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
