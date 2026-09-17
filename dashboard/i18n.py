"""Persian UI string catalog for the dashboard.

The dashboard ships exactly one locale: Persian (``fa``). Every user-visible
string lives here, keyed by a stable identifier, so a later localization pass can
replace a literal with ``t("...")`` without touching this module. There is
deliberately no runtime locale switcher and no second (English) catalog: the
catalog ``name`` in the database stays the canonical English/auditable value, and
indicator, domain and source names belong to :mod:`dashboard.labels`.

Key namespaces mirror the page registry (``nav.<page>`` / ``page.<page>``) and the
layer that renders the string (``filter.*``, ``chart.*``, ``table.*``,
``export.*``, ``empty.*``, ``warn.*``). Strings may contain ``{placeholder}``
fields, which callers fill through ``t(key, **kwargs)``.

A missing key raises rather than degrading to an English placeholder:
``docs/plans/phase-7.1-dashboard-refresh.md`` requires the untranslated-literal
guard to be enforceable, and a silent fallback would hide exactly the literals the
guard exists to find.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

__all__ = ["LOCALE", "STRING_CATALOG", "TranslationError", "has_string", "string_keys", "t"]

LOCALE: Final[str] = "fa"
"""The only active UI locale."""

#: Namespace prefixes the catalog is allowed to use; a stray prefix means a key
#: was invented outside the agreed structure.
KEY_PREFIXES: Final[tuple[str, ...]] = (
    "app.",
    "group.",
    "nav.",
    "page.",
    "section.",
    "metric.",
    "filter.",
    "chart.",
    "table.",
    "export.",
    "empty.",
    "warn.",
    "value.",
)

#: The single home for every Persian UI string in the dashboard.
STRING_CATALOG: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Shell chrome.
        "app.title": "سامانه داده‌های اقتصاد کلان ایران",
        "app.db_connected": "اتصال به پایگاه داده برقرار است",
        "app.db_unavailable": (
            "پایگاه داده در دسترس نیست. پستگرس را با «make db-up» اجرا و مهاجرت‌ها را اعمال کنید."
        ),
        # Sidebar groups (mirror dashboard.navigation.GROUPS).
        "group.overview_analysis": "مرور و تحلیل",
        "group.domains": "حوزه‌ها",
        # Navigation labels (one per dashboard.navigation.PAGES key).
        "nav.overview": "مرور کلی",
        "nav.correlation": "مقایسه و همبستگی",
        "nav.catalog": "فهرست داده‌ها",
        "nav.inflation": "تورم",
        "nav.gdp": "تولید ناخالص داخلی و اقتصاد",
        "nav.trade_energy": "تجارت و انرژی",
        "nav.fx_gold": "ارز و طلا",
        # In-page titles (same keys as nav.*, kept separate so they cannot drift
        # from the routing label without a failing test).
        "page.overview": "مرور کلی",
        "page.correlation": "مقایسه و همبستگی",
        "page.catalog": "فهرست داده‌ها",
        "page.inflation": "تورم",
        "page.gdp": "تولید ناخالص داخلی و اقتصاد",
        "page.trade_energy": "تجارت و انرژی",
        "page.fx_gold": "ارز و طلا",
        # Subheaders and expanders.
        "section.indicators_by_domain": "شاخص‌ها به تفکیک حوزه",
        "section.available_coverage": "پوشش موجود",
        "section.source_freshness": "تازگی داده‌های هر منبع",
        "section.key_indicators": "شاخص‌های کلیدی",
        "section.exact_join_counts": "تعداد تطابق‌های دقیق زمانی",
        "section.observations": "مشاهدات",
        # Metric blocks.
        "metric.matching_indicators": "شاخص‌های منطبق",
        "metric.active_indicators": "شاخص‌های فعال",
        "metric.gold_observations": "مشاهدات لایه طلایی",
        "metric.domains": "حوزه‌ها",
        "metric.sources": "منابع",
        "metric.selected_indicators": "{count} شاخص انتخاب‌شده",
        # Filter controls.
        "filter.domain": "حوزه",
        "filter.frequency": "تواتر",
        "filter.source": "منبع",
        "filter.indicators": "شاخص‌ها",
        "filter.start_date": "تاریخ شروع",
        "filter.end_date": "تاریخ پایان",
        "filter.include_derived": "نمایش سری‌های مشتق‌شده در صورت وجود",
        "filter.start_after_end": "تاریخ شروع باید پیش از تاریخ پایان یا برابر آن باشد.",
        # Chart labels and legends.
        "chart.timestamp": "زمان",
        "chart.value": "مقدار",
        "chart.indicator": "شاخص",
        "chart.gold_observations": "مشاهدات لایه طلایی",
        "chart.chain_linked": "زنجیره‌شده",
        "chart.original": "مقدار اصلی",
        "chart.pearson_r": "ضریب همبستگی پیرسون",
        # Table and export column headers.
        "table.indicator_id": "شناسه شاخص",
        "table.name": "نام",
        "table.description": "توضیح",
        "table.unit": "واحد",
        "table.frequency": "تواتر",
        "table.domain": "حوزه",
        "table.source_name": "منبع",
        "table.source_url": "نشانی منبع",
        "table.availability_start": "آغاز پوشش",
        "table.availability_end": "پایان پوشش",
        "table.observed_start": "آغاز مشاهده‌شده",
        "table.observed_end": "پایان مشاهده‌شده",
        "table.observation_count": "تعداد مشاهدات",
        "table.chain_linked_count": "ردیف‌های زنجیره‌شده",
        "table.confidence": "میانگین اطمینان",
        "table.has_base_year_changes": "تغییر سال پایه",
        "table.base_years": "سال‌های پایه",
        "table.is_active": "فعال",
        "table.timestamp": "زمان",
        "table.value": "مقدار",
        "table.original_value": "مقدار اصلی",
        "table.is_chain_linked": "زنجیره‌شده",
        "table.chain_linking_confidence": "اطمینان زنجیره‌سازی",
        "table.record_metadata": "فراداده",
        "table.rows_returned": "تعداد ردیف",
        "table.expected_observations": "مشاهدات مورد انتظار",
        "table.missing_periods": "دوره‌های مفقود",
        "table.collection_timestamp": "زمان گردآوری",
        "table.status": "وضعیت",
        "table.records_collected": "رکوردهای گردآوری‌شده",
        "table.error_message": "پیام خطا",
        "table.indicator_count": "تعداد شاخص",
        # Export controls.
        "export.download_csv": "دریافت CSV",
        "export.download_excel": "دریافت Excel",
        "export.download_html": "دریافت HTML",
        "export.download_png": "دریافت PNG",
        "export.download_svg": "دریافت SVG",
        # Empty states.
        "empty.no_indicators_for_page": "هنوز شاخص فعالی برای این صفحه وجود ندارد.",
        "empty.select_indicators": "برای دیدن مشاهدات لایه طلایی، یک یا چند شاخص را انتخاب کنید.",
        "empty.select_two_indicators": "برای مقایسه، دست‌کم دو شاخص را انتخاب کنید.",
        "empty.catalog_empty": "فهرست شاخص‌ها خالی است.",
        "empty.no_observations": "هیچ مشاهده‌ای با شاخص‌ها و بازه زمانی انتخاب‌شده مطابقت ندارد.",
        "empty.no_collection_runs": "هنوز هیچ اجرای گردآوری ثبت نشده است.",
        "empty.no_quality_rows": "هیچ مشاهده لایه طلایی با پالایه‌های فعلی مطابقت ندارد.",
        # Warnings.
        "warn.catalog_empty": (
            "فهرست شاخص‌ها خالی است. پیش از استفاده از داشبورد، یک خط لوله ETL را اجرا کنید."
        ),
        "warn.tgju_snapshot": (
            "TGJU فقط قیمت لحظه‌ای منتشر می‌کند و تاریخچه گذشته را در اختیار نمی‌گذارد. "
            "گردآوری روزانه به‌تدریج سری زمانی را می‌سازد."
        ),
        "warn.mixed_frequencies": (
            "شاخص‌های انتخاب‌شده تواتر متفاوت دارند. همبستگی تنها بر تطابق دقیق زمان "
            "مبتنی است و هیچ مقداری جلو‌بری یا درون‌یابی نمی‌شود."
        ),
        "warn.single_observation": (
            "یک یا چند سری انتخاب‌شده تنها یک مشاهده دارد. TGJU منبعی لحظه‌ای است و "
            "تاریخچه از طریق گردآوری روزانه انباشته می‌شود."
        ),
        "warn.missing_periods": (
            "بازه زمانی انتخاب‌شده دوره‌های مفقود دارد. هیچ مقداری جایگزین نشده است."
        ),
        # Shared value placeholders.
        "value.unknown": "نامشخص",
    }
)


class TranslationError(KeyError):
    """Raised when a key is absent from :data:`STRING_CATALOG` or misused."""


def t(key: str, /, **kwargs: object) -> str:
    """Resolve a catalog key to its Persian string, filling placeholders.

    Placeholder values are inserted verbatim: digit conversion is a display
    concern owned by :mod:`dashboard.formatting`, so a caller that needs Persian
    digits formats the value first.

    Args:
        key: Catalog key, e.g. ``"nav.inflation"``
        **kwargs: Values for ``{placeholder}`` fields in the string

    Returns:
        The formatted Persian string

    Raises:
        TranslationError: If the key is unknown or a placeholder is unfilled

    Examples:
        >>> t("nav.inflation")
        'تورم'
        >>> t("metric.selected_indicators", count="۳")
        '۳ شاخص انتخاب‌شده'
    """
    try:
        template = STRING_CATALOG[key]
    except KeyError as exc:
        msg = f"Unknown dashboard string key: {key!r}"
        raise TranslationError(msg) from exc

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError) as exc:
        msg = f"Cannot format dashboard string {key!r} with {sorted(kwargs)}: {exc}"
        raise TranslationError(msg) from exc


def has_string(key: str) -> bool:
    """Report whether ``key`` exists in the catalog."""
    return key in STRING_CATALOG


def string_keys() -> tuple[str, ...]:
    """Return every catalog key, sorted, for coverage tests and tooling."""
    return tuple(sorted(STRING_CATALOG))
