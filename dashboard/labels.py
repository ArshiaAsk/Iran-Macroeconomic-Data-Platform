"""Persian display labels for indicators, domains, sources and derived series.

This module is presentation-only configuration. It reads nothing and writes
nothing: the catalog ``name`` in PostgreSQL remains the canonical English and
auditable value, and the connector registries in ``src/connectors/`` remain the
authoritative source inventory. Nothing here is ever persisted, so a label change
cannot alter Gold data or a pipeline.

Ownership boundaries:

- indicator / domain / source / frequency display names and the expected update
  cadence live here;
- UI chrome lives in :mod:`dashboard.i18n`;
- numbers, dates, Jalali and Tehran display live in :mod:`dashboard.formatting`;
- discovering *which* Gold series are derived is a repository concern
  (``record_metadata -> 'derived_from'``). This module only labels a series that
  is already known to be derived, via :func:`is_derived` plus the suffix map.
"""

from collections.abc import Mapping
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Final

__all__ = [
    "CADENCE_ANNUAL",
    "CADENCE_DAILY",
    "CADENCE_MONTHLY",
    "CADENCE_WEEKLY",
    "DERIVED_SUFFIX_LABELS",
    "DOMAIN_LABELS",
    "DOMAIN_ORDER",
    "FREQUENCY_LABELS",
    "INDICATOR_LABELS",
    "SOURCE_EXPECTED_CADENCE",
    "SOURCE_LABELS",
    "UNCLASSIFIED_DOMAIN",
    "derived_label",
    "domain_label",
    "frequency_label",
    "indicator_label",
    "is_derived",
    "source_expected_cadence",
    "source_label",
]

UNCLASSIFIED_DOMAIN: Final[str] = "unclassified"
"""Domain label used by the connectors for an unmapped indicator."""

# Expected *collection* refresh interval per source, used by the Overview
# staleness view. This is how often a pipeline run is expected, not the data
# frequency (World Bank publishes annual data but is checked monthly) and not an
# SQL concern: the repository returns the last collection timestamp as stored.
CADENCE_DAILY: Final[timedelta] = timedelta(days=1)
CADENCE_WEEKLY: Final[timedelta] = timedelta(days=7)
CADENCE_MONTHLY: Final[timedelta] = timedelta(days=31)
CADENCE_ANNUAL: Final[timedelta] = timedelta(days=366)

#: Persian display name per catalog domain. Insertion order is the display order
#: used by :data:`DOMAIN_ORDER`.
DOMAIN_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "gdp": "تولید ناخالص داخلی",
        "inflation": "تورم و شاخص قیمت",
        "trade": "تجارت خارجی",
        "energy": "انرژی",
        "fx": "ارز",
        "gold": "طلا",
        "welfare": "رفاه و بودجه خانوار",
        "labor": "بازار کار",
        "market": "بازار سرمایه",
        UNCLASSIFIED_DOMAIN: "دسته‌بندی‌نشده",
    }
)

DOMAIN_ORDER: Final[tuple[str, ...]] = tuple(DOMAIN_LABELS)
"""Domains in display order (every key of :data:`DOMAIN_LABELS`)."""

#: Persian display name per connector ``source_name`` slug.
SOURCE_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "world_bank": "بانک جهانی",
        "imf": "صندوق بین‌المللی پول",
        "eia": "اداره اطلاعات انرژی آمریکا",
        "tgju": "تی‌جی‌جی‌یو",
        "sci": "مرکز آمار ایران",
        "tsetmc": "بورس تهران",
        "hbsir": "بررسی بودجه خانوار",
    }
)

#: Expected refresh interval per ``source_name``; an unknown source has no
#: expectation and therefore no staleness claim.
SOURCE_EXPECTED_CADENCE: Final[Mapping[str, timedelta]] = MappingProxyType(
    {
        "tgju": CADENCE_DAILY,
        "tsetmc": CADENCE_DAILY,
        "sci": CADENCE_WEEKLY,
        "world_bank": CADENCE_MONTHLY,
        "imf": CADENCE_MONTHLY,
        "eia": CADENCE_MONTHLY,
        "hbsir": CADENCE_ANNUAL,
    }
)

FREQUENCY_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "daily": "روزانه",
        "weekly": "هفتگی",
        "monthly": "ماهانه",
        "quarterly": "فصلی",
        "annual": "سالانه",
    }
)

#: Label fragment per derived-series suffix. Only applied to a series that is
#: already known to be derived (``record_metadata["derived_from"]`` is set), never
#: used to guess derivedness from an id.
DERIVED_SUFFIX_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "YOY": "رشد سالانه",
        "RET1D": "بازده روزانه",
        "MA30": "میانگین متحرک ۳۰ روزه",
        "ME": "ماهانه (پایان ماه)",
    }
)

#: Persian display name per catalog indicator id: every id the connector
#: registries emit, including the four inactive SCI base-year segments that the
#: catalog keeps for the segment view.
INDICATOR_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        # World Bank (12).
        "NY.GDP.MKTP.CD": "تولید ناخالص داخلی (دلار جاری)",
        "NY.GDP.MKTP.KD": "تولید ناخالص داخلی (قیمت‌های ثابت)",
        "NY.GDP.MKTP.KN": "تولید ناخالص داخلی (قیمت‌های پایه)",
        "NY.GDP.MKTP.KD.ZG": "رشد تولید ناخالص داخلی (قیمت‌های ثابت)",
        "NY.GDP.PCAP.KD": "تولید ناخالص داخلی سرانه (قیمت‌های ثابت)",
        "FP.CPI.TOTL.ZG": "تورم قیمت مصرف‌کننده (درصد سالانه)",
        "NE.EXP.GNFS.CD": "صادرات کالا و خدمات (دلار جاری)",
        "NE.IMP.GNFS.CD": "واردات کالا و خدمات (دلار جاری)",
        "NE.RSB.GNFS.CD": "تراز تجاری کالا و خدمات (دلار جاری)",
        "SP.POP.TOTL": "جمعیت کل",
        "SP.POP.GROW": "رشد جمعیت (درصد سالانه)",
        "EG.USE.PCAP.KG.OE": "مصرف انرژی سرانه (کیلوگرم معادل نفت)",
        # IMF (6).
        "NGDP_RPCH": "رشد واقعی تولید ناخالص داخلی (درصد تغییر سالانه)",
        "PCPIPCH": "نرخ تورم، میانگین قیمت‌های مصرف‌کننده (درصد سالانه)",
        "NGDPD": "تولید ناخالص داخلی (میلیارد دلار جاری)",
        "NGDPDPC": "تولید ناخالص داخلی سرانه (دلار جاری)",
        "LUR": "نرخ بیکاری (درصد)",
        "BCA_NGDPD": "تراز حساب جاری (درصد تولید ناخالص داخلی)",
        # EIA (2).
        "EIA.IRN.CRUDE_PRODUCTION": "تولید نفت خام، مایعات گازی و سایر مایعات",
        "EIA.IRN.TOTAL_LIQUIDS": "تولید کل نفت و سایر مایعات",
        # TGJU (3).
        "TGJU.USD.FREE": "نرخ دلار آزاد",
        "TGJU.GOLD.EMAMI": "سکه طلای امامی",
        "TGJU.GOLD.18K": "طلای ۱۸ عیار (هر گرم)",
        # SCI canonical series (3) and their inactive base-year segments (4).
        "SCI.CPI.NATIONAL": "شاخص قیمت مصرف‌کننده — کل کشور (زنجیره‌شده)",
        "SCI.CPI.URBAN": "شاخص قیمت مصرف‌کننده — مناطق شهری (زنجیره‌شده)",
        "SCI.CPI.RURAL": "شاخص قیمت مصرف‌کننده — مناطق روستایی (زنجیره‌شده)",
        "SCI.CPI.NATIONAL.B2021": "شاخص قیمت مصرف‌کننده — کل کشور (پایه ۱۴۰۰=۲۰۲۱)",
        "SCI.CPI.URBAN.B2021": "شاخص قیمت مصرف‌کننده — مناطق شهری (پایه ۱۴۰۰=۲۰۲۱)",
        "SCI.CPI.RURAL.B2021": "شاخص قیمت مصرف‌کننده — مناطق روستایی (پایه ۱۴۰۰=۲۰۲۱)",
        "SCI.CPI.URBAN.B2016": "شاخص قیمت مصرف‌کننده — مناطق شهری (پایه ۱۳۹۵=۲۰۱۶)",
        # SCI CPI by expenditure decile (10) and labour force survey (1).
        "SCI.CPI.DECILE.B2021.D1": "شاخص قیمت مصرف‌کننده — دهک هزینه ۱",
        "SCI.CPI.DECILE.B2021.D2": "شاخص قیمت مصرف‌کننده — دهک هزینه ۲",
        "SCI.CPI.DECILE.B2021.D3": "شاخص قیمت مصرف‌کننده — دهک هزینه ۳",
        "SCI.CPI.DECILE.B2021.D4": "شاخص قیمت مصرف‌کننده — دهک هزینه ۴",
        "SCI.CPI.DECILE.B2021.D5": "شاخص قیمت مصرف‌کننده — دهک هزینه ۵",
        "SCI.CPI.DECILE.B2021.D6": "شاخص قیمت مصرف‌کننده — دهک هزینه ۶",
        "SCI.CPI.DECILE.B2021.D7": "شاخص قیمت مصرف‌کننده — دهک هزینه ۷",
        "SCI.CPI.DECILE.B2021.D8": "شاخص قیمت مصرف‌کننده — دهک هزینه ۸",
        "SCI.CPI.DECILE.B2021.D9": "شاخص قیمت مصرف‌کننده — دهک هزینه ۹",
        "SCI.CPI.DECILE.B2021.D10": "شاخص قیمت مصرف‌کننده — دهک هزینه ۱۰",
        "SCI.UNEMPLOYMENT.QUARTERLY": "نرخ بیکاری (آمارگیری نیروی کار، فصلی)",
        # TSETMC (1).
        "TSETMC.TEDPIX": "شاخص کل بورس تهران (تدپیکس)",
        # HBSIR (12).
        "HBSIR.GINI": "ضریب جینی درآمد خانوار (وزنی)",
        "HBSIR.POVERTY.RATE": "نرخ فقر نسبی (۵۰٪ میانه وزنی درآمد)",
        "HBSIR.INCOME.DECILE.D1": "سهم درآمدی دهک ۱ (وزنی)",
        "HBSIR.INCOME.DECILE.D2": "سهم درآمدی دهک ۲ (وزنی)",
        "HBSIR.INCOME.DECILE.D3": "سهم درآمدی دهک ۳ (وزنی)",
        "HBSIR.INCOME.DECILE.D4": "سهم درآمدی دهک ۴ (وزنی)",
        "HBSIR.INCOME.DECILE.D5": "سهم درآمدی دهک ۵ (وزنی)",
        "HBSIR.INCOME.DECILE.D6": "سهم درآمدی دهک ۶ (وزنی)",
        "HBSIR.INCOME.DECILE.D7": "سهم درآمدی دهک ۷ (وزنی)",
        "HBSIR.INCOME.DECILE.D8": "سهم درآمدی دهک ۸ (وزنی)",
        "HBSIR.INCOME.DECILE.D9": "سهم درآمدی دهک ۹ (وزنی)",
        "HBSIR.INCOME.DECILE.D10": "سهم درآمدی دهک ۱۰ (وزنی)",
    }
)

_COMPOSITE_SEPARATOR: Final[str] = " – "


def domain_label(domain: str) -> str:
    """Return the Persian label for a catalog domain, or the raw domain.

    Args:
        domain: Catalog domain slug (e.g. ``"inflation"``)

    Returns:
        Persian display name, or ``domain`` unchanged when unmapped

    Examples:
        >>> domain_label("inflation")
        'تورم و شاخص قیمت'
        >>> domain_label("economy")
        'economy'
    """
    return DOMAIN_LABELS.get(domain, domain)


def source_label(source_name: str) -> str:
    """Return the Persian label for a ``source_name`` slug, or the raw slug."""
    return SOURCE_LABELS.get(source_name, source_name)


def source_expected_cadence(source_name: str) -> timedelta | None:
    """Return the expected collection refresh interval, or ``None`` if unknown."""
    return SOURCE_EXPECTED_CADENCE.get(source_name)


def frequency_label(frequency: str) -> str:
    """Return the Persian label for a catalog frequency, or the raw value."""
    return FREQUENCY_LABELS.get(frequency, frequency)


def derived_label(suffix: str) -> str:
    """Return the Persian label for a derived-series suffix, or the raw suffix."""
    return DERIVED_SUFFIX_LABELS.get(suffix, suffix)


def is_derived(record_metadata: Mapping[str, Any] | None) -> bool:
    """Report whether a Gold row is a platform-computed derived series.

    Derivedness is read from the ETL-written ``record_metadata["derived_from"]``
    key, never inferred from an indicator id: ``TGJU.USD.FREE`` is a level series
    without a derived suffix, and a new derivation strategy must not require a
    dashboard change.

    Args:
        record_metadata: The Gold row's ``record_metadata`` (JSONB) mapping

    Returns:
        True only when a parent indicator id is recorded

    Examples:
        >>> is_derived({"derived_from": "TGJU.USD.FREE"})
        True
        >>> is_derived({"method": "daily_return"})
        False
        >>> is_derived(None)
        False
    """
    if not record_metadata:
        return False
    return bool(record_metadata.get("derived_from"))


def _derived_fragment(indicator_id: str) -> str | None:
    """Label fragment for a known-derived id, or ``None`` when its suffix is new."""
    suffix = indicator_id.rsplit(".", 1)[-1]
    return DERIVED_SUFFIX_LABELS.get(suffix)


def indicator_label(
    indicator_id: str,
    catalog_name: str | None = None,
    derived_from: str | None = None,
) -> str:
    """Return the Persian display label for an indicator.

    Falls back, in order, to the catalog's canonical English ``name`` and then the
    raw id, so an unmapped indicator is displayed rather than hidden.

    Args:
        indicator_id: Catalog or Gold indicator id
        catalog_name: The catalog ``name`` for this id, when the caller has it
        derived_from: Parent indicator id for a row that is known to be derived

    Returns:
        Persian display label

    Examples:
        >>> indicator_label("FP.CPI.TOTL.ZG")
        'تورم قیمت مصرف‌کننده (درصد سالانه)'
        >>> indicator_label("NEW.INDICATOR", catalog_name="A new indicator")
        'A new indicator'
        >>> indicator_label("NEW.INDICATOR")
        'NEW.INDICATOR'
        >>> indicator_label("WB.FP.CPI.TOTL.ZG.YOY", derived_from="FP.CPI.TOTL.ZG")
        'تورم قیمت مصرف‌کننده (درصد سالانه) – رشد سالانه'
    """
    if derived_from:
        parent = indicator_label(derived_from, catalog_name)
        fragment = _derived_fragment(indicator_id)
        if fragment is not None:
            return f"{parent}{_COMPOSITE_SEPARATOR}{fragment}"
    return INDICATOR_LABELS.get(indicator_id) or catalog_name or indicator_id
