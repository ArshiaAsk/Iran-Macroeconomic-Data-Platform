"""Unit tests for dashboard filter helpers and Jalali-aware date selection."""

from datetime import UTC, date, datetime

import jdatetime
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.components.filters import (
    as_utc_datetime,
    default_date_bounds,
    resolve_jalali_preset,
    unique_values,
)
from dashboard.formatting import gregorian_to_jalali
from dashboard.i18n import STRING_CATALOG, t
from dashboard.labels import domain_label


def test_unique_values_ignores_nulls_and_sorts() -> None:
    frame = pd.DataFrame({"domain": ["gdp", None, "inflation", "gdp"]})

    assert unique_values(frame, "domain") == ["gdp", "inflation"]
    assert unique_values(frame, "missing") == []


def test_default_bounds_use_catalog_coverage() -> None:
    frame = pd.DataFrame(
        {
            "availability_start": [
                pd.Timestamp("2000-01-01", tz="UTC"),
                pd.Timestamp("1990-01-01", tz="UTC"),
                None,
            ],
            "availability_end": [
                pd.Timestamp("2024-06-30", tz="UTC"),
                pd.Timestamp("2020-01-01", tz="UTC"),
                None,
            ],
        }
    )

    start, end = default_date_bounds(frame)

    assert start == datetime(1990, 1, 1, tzinfo=UTC)
    assert end == datetime(2024, 6, 30, tzinfo=UTC)


def test_date_control_is_converted_to_utc() -> None:
    assert as_utc_datetime(date(2024, 3, 15)) == datetime(2024, 3, 15, tzinfo=UTC)


def test_jalali_day_preset_round_trips_including_an_evening_utc_instant() -> None:
    start, end = resolve_jalali_preset(None, None, "۱۴۰۵/۰۶/۱۸")

    # 1405/06/18 is the Tehran day 2026-09-09; its UTC bounds open the evening
    # before at 20:30Z.
    assert start == datetime(2026, 9, 8, 20, 30, tzinfo=UTC)
    assert end == datetime(2026, 9, 9, 20, 29, 59, 999999, tzinfo=UTC)
    evening = datetime(2026, 9, 8, 20, 30, tzinfo=UTC)
    assert start <= evening <= end
    assert gregorian_to_jalali(start) == jdatetime.date(1405, 6, 18)
    assert gregorian_to_jalali(end) == jdatetime.date(1405, 6, 18)


def test_jalali_year_and_month_presets_cover_the_whole_period() -> None:
    year_start, year_end = resolve_jalali_preset(1405, None, "")
    last_esfand = 30 if jdatetime.date(1405, 1, 1).isleap() else 29
    assert gregorian_to_jalali(year_start) == jdatetime.date(1405, 1, 1)
    assert gregorian_to_jalali(year_end) == jdatetime.date(1405, 12, last_esfand)

    month_start, month_end = resolve_jalali_preset(1405, 6, "")
    assert gregorian_to_jalali(month_start) == jdatetime.date(1405, 6, 1)
    assert gregorian_to_jalali(month_end) == jdatetime.date(1405, 6, 31)


def test_no_preset_returns_no_bounds_and_an_invalid_day_raises() -> None:
    assert resolve_jalali_preset(None, None, "") is None
    assert resolve_jalali_preset(None, None, "   ") is None
    with pytest.raises(ValueError, match="Not a Jalali"):
        resolve_jalali_preset(None, None, "not-a-date")
    with pytest.raises(ValueError, match="Invalid Jalali"):
        resolve_jalali_preset(None, None, "1405/13/40")


def _render_filters_probe() -> None:
    """Render ``render_filters`` over a tiny catalog, stashing the result."""
    import pandas as pd
    import streamlit as st

    from dashboard.components.filters import render_filters

    catalog = pd.DataFrame(
        {
            "indicator_id": ["FP.CPI.TOTL.ZG"],
            "domain": ["inflation"],
            "frequency": ["annual"],
            "source_name": ["world_bank"],
            "availability_start": [pd.Timestamp("2020-01-01", tz="UTC")],
            "availability_end": [pd.Timestamp("2022-01-01", tz="UTC")],
        }
    )
    st.session_state["probe_state"] = render_filters(catalog, "probe")


def test_filter_options_are_localized_but_the_state_keeps_raw_slugs() -> None:
    app = AppTest.from_function(_render_filters_probe).run()

    assert not app.exception
    # The domain option is shown through the label layer...
    assert list(app.multiselect(key="probe_domains").options) == [domain_label("inflation")]
    # ...while the indicator selection keeps the raw catalog id.
    app.multiselect(key="probe_indicators").set_value(["FP.CPI.TOTL.ZG"])
    app.run()
    state = app.session_state["probe_state"]
    assert state.indicator_ids == ["FP.CPI.TOTL.ZG"]
    assert state.domains == []
    assert all(domain_label("inflation") != value for value in state.indicator_ids)


def test_filter_widgets_carry_the_persian_placeholder() -> None:
    """F4 (Task 35): an empty widget shows the Persian placeholder.

    Streamlit's own default for an empty multiselect/selectbox is the English
    "Choose options", which must not appear in the Persian UI.
    """
    app = AppTest.from_function(_render_filters_probe).run()

    assert not app.exception
    placeholder = t("filter.placeholder")
    assert placeholder != "Choose options"
    for key in ("probe_domains", "probe_frequencies", "probe_sources", "probe_indicators"):
        assert app.multiselect(key=key).proto.placeholder == placeholder, key
    for key in ("probe_jalali_year", "probe_jalali_month"):
        assert app.selectbox(key=key).proto.placeholder == placeholder, key


def test_jalali_preset_echoes_the_applied_range_and_disables_manual_dates(
    fake_streamlit_connection,
) -> None:
    from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

    app = AppTest.from_file(
        REPOSITORY_ROOT / "dashboard" / "pages" / "2_Inflation.py",
        default_timeout=20,
    )
    app.run()
    # Pick a Jalali year inside the fake catalog's coverage (2020-2022 -> 1398-1401).
    app.selectbox(key="inflation_jalali_year").set_value(1401)
    app.run()

    assert not app.exception
    captions = [caption.value for caption in app.caption]
    assert t("filter.preset_active") in captions
    applied_prefix = STRING_CATALOG["filter.applied_range"].split("{", 1)[0]
    assert any(caption.startswith(applied_prefix) for caption in captions)
