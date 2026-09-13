"""Unit tests for the SCI publication parser.

Exercised against the real fixtures captured in Task 1 (``tests/fixtures/sci``),
so these run with no network, no browser and no wall-clock cost.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.connectors.sci_parser import (
    FRAME_COLUMNS,
    UNIT_INDEX,
    UNIT_PERCENT,
    detect_base_year,
    detect_unit,
    parse_cpi_decile_excel,
    parse_cpi_excel,
    parse_cpi_html,
    parse_cpi_pdf,
    parse_unemployment_excel,
    parse_unemployment_pdf,
    split_segments,
)
from src.utils.exceptions import ParsingError

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "sci"

NATIONAL = FIXTURE_DIR / "cpi_national_timeseries.xlsx"
URBAN = FIXTURE_DIR / "cpi_urban_timeseries.xlsx"
RURAL = FIXTURE_DIR / "cpi_rural_timeseries.xlsx"
DECILE = FIXTURE_DIR / "cpi_decile_timeseries.xlsx"
BASE_1395 = FIXTURE_DIR / "cpi_base1395_timeseries.xlsx"
CPI_PDF = FIXTURE_DIR / "cpi_report_1405-05_base1400.pdf"
PRICES_HTML = FIXTURE_DIR / "prices_page.html"
UNEMPLOYMENT_XLS = FIXTURE_DIR / "unemployment_spring_1405.xls"
UNEMPLOYMENT_ANNUAL = FIXTURE_DIR / "unemployment_annual_1404.xlsx"
UNEMPLOYMENT_PDF = FIXTURE_DIR / "unemployment_report_1404.pdf"


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


class TestDetectBaseYear:
    """Base years come from explicit markers only."""

    def test_base_year_phrase(self):
        assert detect_base_year("شاخص قیمت مصرف کننده بر اساس سال پایه 1395") == 1395

    def test_equals_100_marker(self):
        assert detect_base_year("شاخص کل قیمت ... (100=1400)") == 1400

    def test_filename_marker(self):
        assert detect_base_year("ts_cpi_1395=100-14040208113537.xlsx") == 1395

    def test_persian_digits(self):
        assert detect_base_year("برمبنای سال پایه ۱۴۰۰") == 1400

    def test_plain_data_year_is_not_a_base_year(self):
        assert detect_base_year("سال 1395") is None
        assert detect_base_year("شاخص قیمت مصرف کننده خانوارهای کشور") is None

    def test_missing_or_blank(self):
        assert detect_base_year(None) is None
        assert detect_base_year("") is None


class TestDetectUnit:
    """Index and percentage publications are distinguished."""

    def test_index_title(self):
        assert detect_unit("شاخص کل قیمت مصرف کننده خانوارهای کشور (100=1400)") == UNIT_INDEX

    def test_percent_title(self):
        assert detect_unit("درصد تغییر ماهانه شاخص کل قیمت مصرف کننده") == UNIT_PERCENT
        assert detect_unit("نرخ تورم سالانه کل خانوارهای کشور") == UNIT_PERCENT

    def test_unknown(self):
        assert detect_unit("نیروی کار") is None


class TestParseCpiExcel:
    """Wide and tidy CPI workbook layouts."""

    def test_national_wide_monthly(self):
        frame = parse_cpi_excel(NATIONAL, base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400")
        assert list(frame.columns) == list(FRAME_COLUMNS)
        assert len(frame) == 185
        assert frame["timestamp"].iloc[0] == ts("2011-03-31")
        assert frame["timestamp"].iloc[-1] == ts("2026-07-31")
        assert frame["value"].iloc[0] == pytest.approx(10.855119360525528)
        assert frame["period_label"].iloc[0] == "1390/01"
        assert frame["unit"].unique().tolist() == [UNIT_INDEX]
        assert frame["base_year"].unique().tolist() == [1400]
        assert frame["obs_status"].unique().tolist() == ["A"]
        assert frame["frequency"].unique().tolist() == ["monthly"]
        assert frame["timestamp"].is_monotonic_increasing

    def test_national_metadata_keeps_persian_label(self):
        frame = parse_cpi_excel(NATIONAL, base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400")
        metadata = frame["record_metadata"].iloc[0]
        assert metadata["base_year"] == 1400
        assert metadata["period_label"] == "1390/01"
        assert metadata["source_period_label"] == "فروردین 1390"

    def test_explicit_group_row(self):
        frame = parse_cpi_excel(
            NATIONAL,
            base_year=1400,
            indicator_id="SCI.CPI.FOOD.B1400",
            row_label="خوراكي‌ها، آشاميدني‌ها",
        )
        assert len(frame) == 185
        assert frame["value"].iloc[0] == pytest.approx(7.04559542337505)

    def test_rural_mixed_frequency(self):
        frame = parse_cpi_excel(RURAL, base_year=1400, indicator_id="SCI.CPI.RURAL.B1400")
        frequencies = frame["frequency"].value_counts().to_dict()
        assert frequencies["quarterly"] == 52
        assert frequencies["monthly"] > 0
        assert frame["timestamp"].iloc[0] == ts("1982-05-31")

    def test_base1395_tidy_long_sheet(self):
        frame = parse_cpi_excel(
            BASE_1395,
            base_year=1395,
            indicator_id="SCI.CPI.HEADLINE.B1395",
            sheet="جدول 3",
        )
        assert len(frame) == 491
        assert frame["timestamp"].iloc[0] == ts("1982-03-31")
        assert frame["value"].iloc[0] == pytest.approx(0.31451908268397205)
        assert frame["timestamp"].iloc[-1] == ts("2023-01-31")
        assert frame["unit"].unique().tolist() == [UNIT_INDEX]

    def test_urban_percent_sheet_unit_autodetect(self):
        frame = parse_cpi_excel(
            URBAN,
            base_year=1400,
            indicator_id="SCI.CPI.URBAN.INFLATION.B1400",
            sheet="جدول 2",
        )
        assert frame["unit"].unique().tolist() == [UNIT_PERCENT]

    def test_missing_series_raises(self):
        with pytest.raises(ParsingError, match="not found"):
            parse_cpi_excel(
                NATIONAL,
                base_year=1400,
                indicator_id="SCI.CPI.X",
                row_label="does-not-exist",
            )

    def test_missing_sheet_raises(self):
        with pytest.raises(ParsingError, match="not found"):
            parse_cpi_excel(NATIONAL, base_year=1400, indicator_id="SCI.CPI.X", sheet="جدول 99")

    def test_unsupported_format_raises(self):
        with pytest.raises(ParsingError, match="Unsupported"):
            parse_cpi_excel(b"not an excel file", base_year=1400, indicator_id="SCI.CPI.X")

    def test_accepts_raw_bytes(self):
        frame = parse_cpi_excel(
            NATIONAL.read_bytes(), base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400"
        )
        assert len(frame) == 185


class TestParseCpiDecileExcel:
    """Transposed decile layout (columns = deciles)."""

    def test_all_ten_deciles(self):
        frame = parse_cpi_decile_excel(DECILE, base_year=1400, indicator_id_prefix="SCI.CPI.DECILE")
        assert len(frame) == 1250
        assert set(frame["indicator_id"].unique()) == {
            f"SCI.CPI.DECILE.D{index}" for index in range(1, 11)
        }
        assert frame["timestamp"].min() == ts("2016-03-31")
        assert frame["timestamp"].max() == ts("2026-07-31")
        assert frame["record_metadata"].iloc[0]["decile"] == 1


class TestParseCpiPdf:
    """The captured CPI PDF exposes no machine-readable table."""

    def test_real_report_has_no_extractable_table(self):
        with pytest.raises(ParsingError):
            parse_cpi_pdf(CPI_PDF, base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400")

    def test_unsupported_bytes_raise(self):
        with pytest.raises(ParsingError):
            parse_cpi_pdf(b"%PDF-1.4 broken", base_year=1400, indicator_id="SCI.CPI.X")


class TestParseCpiHtml:
    """HTML table parsing, including missing-value handling."""

    def test_synthetic_table(self):
        html = (
            "<table>"
            "<tr><td></td><td>1400</td><td></td><td></td><td></td><td></td><td></td></tr>"
            "<tr><td></td><td>فروردین</td><td>اردیبهشت</td><td>خرداد</td>"
            "<td>تیر</td><td>مرداد</td><td>شهریور</td></tr>"
            "<tr><td>شاخص کل</td><td>100</td><td>101.5</td><td>-</td>"
            "<td>103</td><td>104</td><td>105</td></tr>"
            "</table>"
        )
        frame = parse_cpi_html(html, base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400")
        assert frame["value"].tolist() == [100.0, 101.5, 103.0, 104.0, 105.0]
        assert frame["period_label"].tolist() == [
            "1400/01",
            "1400/02",
            "1400/04",
            "1400/05",
            "1400/06",
        ]

    def test_landing_page_has_no_table(self):
        html = PRICES_HTML.read_text(encoding="utf-8")
        with pytest.raises(ParsingError, match="No monthly CPI table"):
            parse_cpi_html(html, base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400")


class TestParseUnemploymentExcel:
    """Quarterly labour-force workbook (legacy .xls)."""

    def test_spring_1405_rate(self):
        frame = parse_unemployment_excel(
            UNEMPLOYMENT_XLS,
            indicator_id="SCI.UNEMPLOYMENT.RATE",
            jalali_year=1405,
            season="بهار",
        )
        assert len(frame) == 1
        assert frame["value"].iloc[0] == pytest.approx(9.1)
        assert frame["timestamp"].iloc[0] == ts("2026-05-31")
        assert frame["period_label"].iloc[0] == "1405/03"
        assert frame["unit"].iloc[0] == UNIT_PERCENT
        assert frame["frequency"].iloc[0] == "quarterly"
        assert frame["record_metadata"].iloc[0]["source_period_label"] == "بهار 1405"

    def test_unknown_season_raises(self):
        with pytest.raises(ParsingError, match="Unknown SCI season"):
            parse_unemployment_excel(
                UNEMPLOYMENT_XLS,
                indicator_id="SCI.UNEMPLOYMENT.RATE",
                jalali_year=1405,
                season="مونسون",
            )

    def test_annual_cross_tab_not_parseable_as_rate(self):
        """The annual workbook is a cross-tab; no clean rate row exists yet."""
        with pytest.raises(ParsingError):
            parse_unemployment_excel(
                UNEMPLOYMENT_ANNUAL,
                indicator_id="SCI.UNEMPLOYMENT.RATE",
                jalali_year=1404,
                season="زمستان",
            )


class TestParseUnemploymentPdf:
    """The narrative labour-force PDF has no extractable rate table."""

    def test_real_report_raises(self):
        with pytest.raises(ParsingError):
            parse_unemployment_pdf(
                UNEMPLOYMENT_PDF,
                indicator_id="SCI.UNEMPLOYMENT.RATE",
                jalali_year=1404,
                season="زمستان",
            )


class TestSplitSegments:
    """Base-year segmentation for chain-linking."""

    def test_splits_oldest_first(self):
        frame = parse_cpi_excel(NATIONAL, base_year=1400, indicator_id="SCI.CPI.HEADLINE.B1400")
        older = frame.copy()
        older["base_year"] = 1395
        combined = pd.concat([older, frame], ignore_index=True)
        segments = split_segments(combined)
        assert list(segments.keys()) == [1395, 1400]
        assert len(segments[1400]) == 185

    def test_missing_base_year_column_raises(self):
        with pytest.raises(ParsingError, match="base_year"):
            split_segments(pd.DataFrame({"value": [1.0]}))
