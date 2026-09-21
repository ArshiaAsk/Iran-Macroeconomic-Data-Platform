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
    "shell.",
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
    "note.",
    "state.",
    "value.",
)

#: The single home for every Persian UI string in the dashboard.
STRING_CATALOG: Final[Mapping[str, str]] = MappingProxyType(
    {
        # Shell chrome.
        "app.title": "سامانه داده‌های اقتصاد کلان ایران",
        "app.brand": "سامانهٔ داده‌ها",
        "app.db_status_label": "وضعیت پایگاه داده",
        "app.db_status_online": "متصل",
        "app.db_status_offline": "قطع",
        "shell.breadcrumb_root": "سامانه",
        "shell.last_collection": "آخرین گردآوری: {date}",
        "shell.timezone": "منطقهٔ زمانی تهران",
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
        "nav.welfare": "رفاه و آمارگیری خانوار",
        "nav.fx_gold": "ارز و طلا",
        "nav.market": "بازار سرمایه",
        "nav.labor": "بازار کار",
        # In-page titles (same keys as nav.*, kept separate so they cannot drift
        # from the routing label without a failing test).
        "page.overview": "مرور کلی",
        "page.correlation": "مقایسه و همبستگی",
        "page.catalog": "فهرست داده‌ها",
        "page.inflation": "تورم",
        "page.gdp": "تولید ناخالص داخلی و اقتصاد",
        "page.trade_energy": "تجارت و انرژی",
        "page.welfare": "رفاه و آمارگیری خانوار",
        "page.fx_gold": "ارز و طلا",
        "page.market": "بازار سرمایه",
        "page.labor": "بازار کار",
        # Subheaders and expanders.
        "section.indicators_by_domain": "شاخص‌ها به تفکیک حوزه",
        "section.indicators_by_domain_total": "جمع",
        "section.available_coverage": "پوشش موجود",
        "section.source_freshness": "تازگی داده‌های هر منبع",
        # The stale count is coloured with the markdown orange directive (P4): the
        # theme maps orange to the warn palette (`orangeColor = #9A5B00`), so the
        # mockup's amber stale count renders without an HTML fragment. The section
        # header's trailing slot is markdown, so the directive is the native route.
        "section.freshness_summary": "{fresh} به‌روز · :orange[{stale}] کهنه",
        "section.key_indicators": "شاخص‌های کلیدی",
        "section.exact_join_counts": "تعداد تطابق‌های دقیق زمانی",
        "section.observations": "مشاهدات",
        # Welfare & Survey page (owns the `welfare` domain).
        "section.hbsir_gini_poverty": "روند جینی و فقر نسبی",
        "section.hbsir_deciles": "سهم درآمدی دهک‌ها",
        "section.hbsir_survey_years": "سال‌های آمارگیری موجود",
        "section.welfare_other_indicators": "سایر شاخص‌های حوزه رفاه",
        # Chain-linking transparency (Task 23) and the correlation overlap
        # summary (Task 24).
        "section.chain_linking": "شفافیت زنجیره‌سازی و سال پایه",
        "section.matched_observations": "مشاهدات منطبق",
        # Inflation page (Task 13): the SCI expenditure-decile comparison, the
        # canonical chain-linked comparison, and the generic composition below.
        "section.cpi_deciles": "شاخص قیمت مصرف‌کننده به تفکیک دهک هزینه",
        "section.cpi_canonical": "مقایسه شاخص قیمت مصرف‌کننده (کل کشور، شهری، روستایی)",
        "section.inflation_all_indicators": "سایر شاخص‌های تورم",
        # Market (TSETMC) page: the daily level panel. Every derived panel is
        # titled through dashboard.labels (parent name + derivation), not here.
        "section.market_level": "شاخص کل بورس تهران (سطح روزانه)",
        # Metric blocks.
        "metric.matching_indicators": "شاخص‌های منطبق",
        "metric.active_indicators": "شاخص‌های فعال",
        "metric.gold_observations": "مشاهدات لایه طلایی",
        "metric.domains": "حوزه‌ها",
        "metric.sources": "منابع",
        "metric.selected_indicators": "{count} شاخص انتخاب‌شده",
        # The indicators-by-domain bar list's footer total (Task 31): the mockup's
        # "۵۰ شاخص". `table.indicator_count` ("تعداد شاخص") is the column/section
        # label, which is why this is a separate count phrase.
        "metric.indicator_count": "{count} شاخص",
        "metric.market_sessions": "نشست‌های معاملاتی مشاهده‌شده",
        # Overview series inventory (Task 16): the derived and orphan Gold series
        # that have no catalog row of their own.
        "metric.derived_series": "سری‌های مشتق‌شده",
        "metric.orphan_series": "سری‌های بدون ردیف فهرست",
        # KPI band tooltips and tag (Task 19). The copy is deliberately
        # data-agnostic (AM-9): it describes each set and how they nest, never a
        # current count and never a claim about today's data.
        "metric.derived_series_help": (
            "سری‌هایی که این سامانه از سری والد محاسبه کرده و ردیف فهرست مستقل ندارند."
        ),
        "metric.orphan_series_help": (
            "سری‌های لایهٔ طلایی که ردیف فهرست ندارند. سری‌های مشتق‌شده معمولاً در این "
            "مجموعه قرار می‌گیرند؛ بنابراین این دو شمارنده می‌توانند هم‌پوشانی داشته باشند."
        ),
        "metric.gold_observations_help": (
            "تنها مشاهدات متصل به یک ردیف فهرست را می‌شمارد؛ سری‌های مشتق‌شده و بدون "
            "فهرست در این عدد نیستند."
        ),
        "metric.orphan_series_tag": "نیازمند بررسی",
        "section.series_inventory": "سری‌های طلایی خارج از فهرست",
        # Filter controls.
        "filter.domain": "حوزه",
        "filter.frequency": "تواتر",
        "filter.source": "منبع",
        "filter.indicators": "شاخص‌ها",
        "filter.start_date": "تاریخ شروع",
        "filter.end_date": "تاریخ پایان",
        "filter.include_derived": "نمایش سری‌های مشتق‌شده در صورت وجود",
        "filter.start_after_end": "تاریخ شروع باید پیش از تاریخ پایان یا برابر آن باشد.",
        # Catalog-page search and the inactive base-year segment toggle (Task 25).
        "filter.search": "جست‌وجو در فهرست",
        "filter.clear": "پاک‌کردن پالایه‌ها",
        "filter.include_inactive_segments": "نمایش بازه‌های غیرفعال سال پایه",
        # Jalali-aware date selection (Task 18): convenience presets that resolve
        # to the same UTC Gregorian bounds, plus the echo of what was applied.
        "filter.jalali_presets": "میانبرهای تاریخ شمسی",
        "filter.jalali_year": "سال شمسی",
        "filter.jalali_month": "ماه شمسی",
        "filter.jalali_day": "روز شمسی (نمونه: ۱۴۰۵/۰۶/۱۸)",
        "filter.jalali_none": "بدون میانبر",
        "filter.jalali_day_invalid": "روز شمسی نامعتبر است؛ قالب درست به‌صورت ۱۴۰۵/۰۶/۱۸ است.",
        "filter.preset_active": (
            "میانبر شمسی فعال است؛ کرانه‌های تاریخ از همان میانبر محاسبه می‌شود و "
            "تاریخ‌های میلادی زیر غیرفعال‌اند."
        ),
        "filter.applied_range": (
            "بازه اعمال‌شده: {jalali_start} تا {jalali_end} — "
            "کرانه‌های میلادی (UTC): {start} تا {end}"
        ),
        # Filter-bar chrome (Task 21): the "all" option every catalog select
        # carries, the row-count echo and the density toggle. The bar itself
        # renders whatever controls it is handed, so these are the only strings it
        # owns.
        "filter.all": "همه",
        "filter.showing_rows": "نمایش {count} ردیف",
        "filter.density": "چگالی",
        "filter.density_comfortable": "راحت",
        "filter.density_compact": "فشرده",
        # CPI decile selector on the Inflation page (Task 13).
        "filter.cpi_deciles": "دهک‌های هزینه",
        # Chart labels and legends.
        "chart.timestamp": "زمان",
        "chart.gregorian": "میلادی",
        "chart.survey_year": "سال آمارگیری",
        "chart.value": "مقدار",
        "chart.indicator": "شاخص",
        "chart.gold_observations": "مشاهدات لایه طلایی",
        "chart.chain_linked": "زنجیره‌شده",
        "chart.original": "مقدار اصلی",
        "chart.pearson_r": "ضریب همبستگی پیرسون",
        # Chart scaling (Task 15): the facet default plus the two opted-in modes.
        # Overlay is only safe for a shared unit, so its fallback note says why.
        "chart.mode": "حالت نمودار",
        "chart.mode.facets": "پنل جداگانه برای هر شاخص",
        "chart.mode.overlay": "نمودار هم‌پوشان (واحد مشترک)",
        "chart.mode.small_multiples": "چندگانه‌های کوچک",
        "chart.overlay_mixed_units": (
            "شاخص‌های انتخاب‌شده واحد یکسانی ندارند؛ برای پرهیز از یک محور مشترک "
            "گمراه‌کننده، هر شاخص در پنل جداگانه خود رسم شده است."
        ),
        "chart.small_multiples_capped": (
            "در حالت چندگانه‌های کوچک تنها {count} سری نخست نمایش داده می‌شود؛ "
            "برای دیدن سری‌های بیشتر، انتخاب را محدودتر کنید."
        ),
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
        # Coverage-table headers (Task 32). The Overview coverage table names its
        # own columns rather than borrowing the catalog grid's, exactly as P3 gave
        # the freshness table its own `table.last_collection`: the two surfaces can
        # then be reworded independently. `table.chained_rows` and
        # `table.average_confidence` happen to read the same as the grid's
        # `table.chain_linked_count` / `table.confidence` today; the pair of range
        # headers is genuinely new wording (one range per pair of bounds).
        "table.indicator": "شاخص",
        "table.coverage_range": "بازهٔ پوشش",
        "table.observed_range": "بازهٔ مشاهده‌شده",
        "table.chained_rows": "ردیف‌های زنجیره‌شده",
        "table.average_confidence": "میانگین اطمینان",
        "table.has_base_year_changes": "تغییر سال پایه",
        "table.base_years": "سال‌های پایه",
        "table.is_active": "فعال",
        "table.timestamp": "زمان",
        "table.jalali_date": "تاریخ شمسی",
        "table.value": "مقدار",
        "table.original_value": "مقدار اصلی",
        "table.is_chain_linked": "زنجیره‌شده",
        "table.chain_linking_confidence": "اطمینان زنجیره‌سازی",
        "table.record_metadata": "فراداده",
        "table.series_kind": "نوع سری",
        "table.derived_from": "سری والد",
        "table.has_catalog_metadata": "فراداده فهرست",
        "table.rows_returned": "تعداد ردیف",
        "table.expected_observations": "مشاهدات مورد انتظار",
        "table.expected_is_estimated": "برآوردی",
        "table.missing_periods": "دوره‌های مفقود",
        "table.collection_timestamp": "زمان گردآوری",
        # The Overview freshness table's own header (P3). The mockup reads
        # "آخرین گردآوری" for that column; `table.collection_timestamp` stays the
        # generic header for every other table (the freshness display frame and
        # the exports), so the two do not share one wording.
        "table.last_collection": "آخرین گردآوری",
        "table.status": "وضعیت",
        "table.records_collected": "رکوردهای گردآوری‌شده",
        "table.error_message": "پیام خطا",
        "table.indicator_count": "تعداد شاخص",
        # Overview freshness (Task 16): the staleness verdict against the
        # source's expected collection cadence (dashboard.labels).
        "table.staleness": "وضعیت تازگی",
        # The freshness table's run-status column (Task 30). The verdict column
        # reuses `table.staleness` (the same "وضعیت تازگی" header) rather than
        # duplicating it under a second key.
        "table.run_status": "وضعیت اجرا",
        # Chain-linking provenance (Task 23) and the correlation matched-
        # observation summary (Task 24).
        "table.base_year_segments": "بازه‌های سال پایه",
        "table.indicator_pair": "جفت شاخص",
        "table.matched_observations": "مشاهدات منطبق",
        "table.meets_minimum_overlap": "حداقل همپوشانی",
        # HBSIR survey-year metadata panel.
        "table.survey_year": "سال آمارگیری",
        "table.survey_year_end": "پایان سال آمارگیری (شمسی)",
        "table.period_end": "پایان دوره ذخیره‌شده (میلادی)",
        "table.coverage_footnote": (
            "تاریخ مشاهدهٔ منابع میلادی (مانند بانک جهانی) به‌صورت سال میلادی نمایش "
            "داده می‌شود؛ تاریخ دقیق در راهنمای هر خانه است."
        ),
        "table.hbsir_indicators": "سری‌های HBSIR",
        "table.hbsir_observations": "مشاهدات HBSIR",
        # Observations-table row cap (Task 15): the grid is a bounded preview and
        # the full selection remains available in the downloads.
        "table.rows_capped": (
            "برای خوانایی، تنها {shown} ردیف از {total} ردیف نمایش داده می‌شود. "
            "برای دیدن ردیف‌های بیشتر بازه زمانی را محدودتر کنید."
        ),
        # Export controls.
        "export.download_csv": "دریافت CSV",
        "export.download_excel": "دریافت Excel",
        "export.download_html": "دریافت HTML",
        "export.download_png": "دریافت PNG",
        "export.download_svg": "دریافت SVG",
        "export.image_failed": "ساخت تصویر {format} ناموفق بود: {error}",
        "export.image_unavailable": (
            "نمایش تصویری نمودار (PNG/SVG) در دسترس نیست؛ برای فعال‌سازی، کرومیوم را نصب کنید."
        ),
        "export.persian_digits": "ارقام فارسی در خروجی",
        "export.sheet_name": "داده‌های انتخاب‌شده",
        # Empty states.
        "empty.no_indicators_for_page": "هنوز شاخص فعالی برای این صفحه وجود ندارد.",
        "empty.select_indicators": "برای دیدن مشاهدات لایه طلایی، یک یا چند شاخص را انتخاب کنید.",
        "empty.select_two_indicators": "برای مقایسه، دست‌کم دو شاخص را انتخاب کنید.",
        "empty.catalog_empty": "فهرست شاخص‌ها خالی است.",
        "empty.no_observations": "هیچ مشاهده‌ای با شاخص‌ها و بازه زمانی انتخاب‌شده مطابقت ندارد.",
        "empty.no_collection_runs": "هنوز هیچ اجرای گردآوری ثبت نشده است.",
        "empty.no_quality_rows": "هیچ مشاهده لایه طلایی با پالایه‌های فعلی مطابقت ندارد.",
        "empty.no_coverage_rows": "هیچ شاخصی با پالایه‌های پوشش مطابقت ندارد.",
        "empty.no_hbsir_observations": "هیچ مشاهده HBSIR در بازه زمانی انتخاب‌شده موجود نیست.",
        "empty.no_cpi_deciles": "هیچ سری شاخص قیمت مصرف‌کننده به تفکیک دهک هزینه در فهرست شاخص‌ها موجود نیست.",
        "empty.no_cpi_canonical": "هیچ سری زنجیره‌شده شاخص قیمت مصرف‌کننده در فهرست شاخص‌ها موجود نیست.",
        "empty.search_no_match": "هیچ شاخصی با عبارت جست‌وجو مطابقت ندارد.",
        "empty.no_chain_linked": "هیچ شاخصی با تغییر سال پایه در فهرست این صفحه وجود ندارد.",
        "empty.no_chain_linked_observations": (
            "در بازه انتخاب‌شده هیچ ردیف زنجیره‌شده‌ای برای نمایش وجود ندارد."
        ),
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
        # Chain-linking transparency (Task 23): the linked and original values are
        # stored fields, and the segment overlap is what identifies the splice.
        "warn.chain_linking_stored": (
            "مقادیر زنجیره‌شده و مقادیر اصلی هر دو به‌صورت ذخیره‌شده نمایش داده می‌شوند؛ "
            "هیچ بازمحاسبه، درون‌یابی یا نرمال‌سازی در این صفحه انجام نمی‌شود."
        ),
        "warn.chain_linking_overlap": (
            "سری زنجیره‌شده از هم‌پوشانی مشاهدات بازه‌های سال پایه ساخته می‌شود و مقادیر "
            "پیش از سال پایه جدید با ضریبی که از همین هم‌پوشانی برآورد شده مقیاس شده‌اند. "
            "بازه‌های سال پایه در جدول بالا آمده است."
        ),
        # Correlation guardrails (Task 24): low overlap is suppressed rather than
        # drawn, and the exact-timestamp join's limitation stays visible.
        "warn.correlation_low_overlap": (
            "برای {count} جفت شاخص، تعداد مشاهدات منطبق کمتر از حداقل {minimum} است؛ این "
            "خانه‌ها در نقشه همبستگی نمایش داده نمی‌شوند تا مقدار نامعتبر به‌جای همبستگی "
            "خوانده نشود."
        ),
        "warn.correlation_exact_join": (
            "همبستگی تنها بر تطابق دقیق زمان مبتنی است و هیچ درون‌یابی، جلو‌بری یا "
            "هم‌تواترسازی انجام نمی‌شود؛ خانه خالی یعنی هم‌پوشانی ناکافی، نه مقدار صفر."
        ),
        # IMF forecast disclosure (Phase 7.1 deferral): forecast labeling needs an
        # ETL change, so forecast rows are indistinguishable in this release.
        "warn.forecasts_indistinguishable": (
            "ردیف‌های پیش‌بینی صندوق بین‌المللی پول در این نسخه از ردیف‌های واقعی قابل "
            "تشخیص نیستند و مانند هر مشاهده دیگری نمایش داده می‌شوند؛ برچسب‌گذاری "
            "پیش‌بینی به فاز بعد موکول شده است."
        ),
        # HBSIR caveats: the measure is relative and the values are computed by
        # this platform from the survey microdata, not published HBSIR figures.
        "warn.hbsir_relative_poverty": (
            "نرخ فقر این صفحه **نسبی** است: سهم وزنی خانوارهای زیر «k × میانه وزنی درآمد "
            "(k = {k})». این معیار خط فقر رسمی کالری‌پایه ایران نیست."
        ),
        # Market (TSETMC) caveats: the level is collected, the derived series
        # are computed in-platform, sessions are absent rather than zero, MA30
        # needs a full window and ``.ME`` is a month-end downsample.
        "warn.tsetmc_derived_not_official": (
            "سری‌های RET1D، MA30 و .ME توسط همین سامانه محاسبه شده‌اند و سری‌های "
            "رسمی بورس تهران نیستند؛ تنها شاخص کل، داده گردآوری‌شده است."
        ),
        "warn.tsetmc_trading_days_absent": (
            "روزهایی که بورس تهران معامله ندارد هیچ مشاهده‌ای تولید نمی‌کنند. این روزها "
            "غایب‌اند و به صفر تبدیل نشده‌اند؛ هیچ مقداری درون‌یابی، جای‌گذاری یا جلو‌بری نشده است."
        ),
        "warn.tsetmc_ma30_warmup": (
            "سری MA30 برای ۲۹ نشست نخست هیچ مقداری ندارد، چون میانگین متحرک به پنجره کامل "
            "نیاز دارد. این دوره گرم‌شدن ساخته‌شده است و کمبود داده به شمار نمی‌رود."
        ),
        "warn.tsetmc_month_end": (
            "سری .ME نمونه‌برداری پایان‌ماه از مشاهدات روزانه است: آخرین نشست هر ماه "
            "میلادی با برچسب پایان همان ماه. این سری یک ماهانه پیوسته نیست و روز معامله را نشان نمی‌دهد."
        ),
        "warn.tsetmc_deferred_metrics": (
            "ارزش معاملات، نسبت قیمت به درآمد (P/E) و ارزش بازار در این سامانه موجود نیستند: "
            "بسته finpy-tse سری تاریخی قابل‌اتکایی برای آن‌ها ارائه نمی‌دهد و گذشته از تصویر امروز بازسازی نمی‌شود."
        ),
        "warn.hbsir_computed_values": (
            "دوازده سری HBSIR از ریزمی‌کروداده آمارگیری بودجه خانوار محاسبه شده‌اند و ارقام "
            "رسمی منتشرشده نیستند؛ واحد تحلیل، خانوار (بدون تعدیل هم‌ارز) و وزن‌ها، وزن‌های نمونه‌گیری است."
        ),
        # Labor caveat: SCI releases one quarter per survey, so the series is
        # legitimately sparse and a lone observation must not read as a trend.
        "warn.labor_publication": (
            "مرکز آمار ایران نرخ بیکاری را بر پایه آمارگیری نیروی کار و به‌صورت فصلی منتشر "
            "می‌کند؛ در هر انتشار تنها یک فصل تازه افزوده می‌شود و ممکن است در یک بازه تنها "
            "یک فصل موجود باشد. یک مشاهدهٔ تنها روند را نشان نمی‌دهد و هیچ مقداری درون‌یابی، "
            "برون‌یابی یا جای‌گذاری نمی‌شود."
        ),
        # CPI decile caveat (Task 13): the ten deciles share one unit and one
        # base year, so the comparison needs no normalization.
        "warn.cpi_deciles_shared_base": (
            "دهک‌های هزینه با یک واحد مشترک (شاخص) و یک سال پایه مشترک منتشر می‌شوند؛ "
            "به همین دلیل مقایسه آن‌ها روی یک مقیاس مشترک انجام می‌شود و هیچ نرمال‌سازی "
            "یا تبدیل واحدی اعمال نمی‌شود."
        ),
        # Shared component chrome (Tasks 17-22). The callout label is rendered as
        # a bold prefix inside the callout body; the body text itself is passed to
        # ``render_callout`` as an existing key.
        "note.methodology_label": "یادداشت روش‌شناسی",
        # Shared value placeholders.
        "value.unknown": "نامشخص",
        "value.fresh": "به‌روز",
        "value.stale": "کهنه",
        "value.yes": "بله",
        "value.no": "خیر",
        # Collection-run status chips (Task 20). The slugs are the
        # ``src.etl.bronze`` STATUS_* constants; the chip mapping is total, so an
        # unrecognised slug renders the unknown chip rather than raising.
        "value.status_success": "موفق",
        "value.status_failed": "ناموفق",
        "value.status_partial": "ناقص",
        "value.status_unknown": "نامشخص",
        # Shared page states (Task 22). `state.error` is the generic failure body;
        # `state.retry_hint` is appended beneath it by `render_error`, and
        # `state.loading` is the placeholder shown while a page waits on a query.
        "state.loading": "در حال بارگذاری…",
        "state.error": "خطا در بارگذاری داده.",
        "state.retry_hint": "برای تلاش دوباره صفحه را بازخوانی کنید.",
        # Relative-time labels (Task 11): coarse Persian granularity for
        # freshness and provenance display. ``{count}`` is filled by the
        # caller with already-digit-converted text.
        "value.relative_today": "امروز",
        "value.relative_hours_ago": "{count} ساعت پیش",
        "value.relative_days_ago": "{count} روز پیش",
        "value.relative_months_ago": "{count} ماه پیش",
        # Gold series classification (repository ``series_kind``), displayed in
        # the observations grid and the exports.
        "value.base": "پایه",
        "value.derived": "مشتق‌شده",
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
