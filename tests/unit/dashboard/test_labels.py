"""Label-registry coverage for dashboard/labels.py.

The connector registries are the authoritative source inventory, so these tests
enumerate them instead of duplicating a list of ids: a new indicator without a
Persian label fails here rather than surfacing as an English string in the UI.
"""

from datetime import timedelta

import pytest

from dashboard.labels import (
    CADENCE_ANNUAL,
    CADENCE_DAILY,
    CADENCE_MONTHLY,
    CADENCE_WEEKLY,
    DERIVED_SUFFIX_LABELS,
    DOMAIN_LABELS,
    DOMAIN_ORDER,
    FREQUENCY_LABELS,
    INDICATOR_LABELS,
    SOURCE_EXPECTED_CADENCE,
    SOURCE_LABELS,
    derived_label,
    domain_label,
    frequency_label,
    indicator_label,
    is_derived,
    source_expected_cadence,
    source_label,
)
from src.connectors import eia, hbsir, imf, sci_scraper, tgju_scraper, tsetmc, world_bank
from src.etl.gold import (
    DERIVED_MA30_SUFFIX,
    DERIVED_MONTH_END_SUFFIX,
    DERIVED_RET1D_SUFFIX,
    DERIVED_YOY_SUFFIX,
)

PLAN_DOMAINS = frozenset(
    {"gdp", "inflation", "trade", "welfare", "energy", "fx", "gold", "labor", "market"}
)
SUFFIXES = (
    DERIVED_YOY_SUFFIX,
    DERIVED_RET1D_SUFFIX,
    DERIVED_MA30_SUFFIX,
    DERIVED_MONTH_END_SUFFIX,
)


def _registry_ids() -> set[str]:
    ids = set(world_bank.INDICATOR_DOMAINS)
    ids |= set(imf.IMF_INDICATORS)
    ids |= set(eia.EIA_INDICATORS)
    ids |= {metadata[0] for metadata in tgju_scraper.INDICATOR_REGISTRY.values()}
    ids |= set(sci_scraper.SCI_CANONICAL_INDICATORS)
    for publication in sci_scraper.SCI_INDICATOR_REGISTRY.values():
        ids |= set(publication.member_ids)
    ids |= set(tsetmc.TSETMC_INDICATORS)
    ids |= set(hbsir.HBSIR_INDICATORS)
    return ids


def _registry_domains() -> set[str]:
    domains = set(world_bank.INDICATOR_DOMAINS.values())
    domains |= {indicator.domain for indicator in imf.IMF_INDICATORS.values()}
    domains |= {indicator.domain for indicator in eia.EIA_INDICATORS.values()}
    domains |= {metadata[2] for metadata in tgju_scraper.INDICATOR_REGISTRY.values()}
    domains |= {indicator.domain for indicator in sci_scraper.SCI_CANONICAL_INDICATORS.values()}
    domains |= {indicator.domain for indicator in tsetmc.TSETMC_INDICATORS.values()}
    domains |= {indicator.domain for indicator in hbsir.HBSIR_INDICATORS.values()}
    return domains


def _registry_frequencies() -> set[str]:
    frequencies = {"annual"}
    frequencies |= {
        indicator.frequency for indicator in sci_scraper.SCI_CANONICAL_INDICATORS.values()
    }
    frequencies |= {world_bank.FREQUENCY_ANNUAL, tgju_scraper.FREQUENCY_DAILY}
    frequencies |= {tsetmc.FREQUENCY_DAILY}
    frequencies |= {"monthly", "quarterly"}
    return frequencies


def _registry_sources() -> set[str]:
    return {
        world_bank.SOURCE_NAME,
        imf.SOURCE_NAME,
        eia.SOURCE_NAME,
        tgju_scraper.SOURCE_NAME,
        sci_scraper.SOURCE_NAME,
        tsetmc.SOURCE_NAME,
        hbsir.SOURCE_NAME,
    }


def test_every_registry_indicator_has_a_persian_label() -> None:
    assert set(INDICATOR_LABELS) == _registry_ids()


def test_registry_size_matches_the_plan() -> None:
    ids = _registry_ids()
    segment_ids = {
        segment_id
        for canonical in sci_scraper.SCI_CANONICAL_INDICATORS.values()
        for segment_id in canonical.segment_ids
    }

    # 50 active ids plus the 4 inactive SCI base-year segments.
    assert len(ids) == 54
    assert len(INDICATOR_LABELS) == 54
    assert len(segment_ids) == 4
    assert segment_ids.issubset(ids)


def test_indicator_labels_are_translations_not_ids() -> None:
    for indicator_id, label in INDICATOR_LABELS.items():
        assert label.strip(), indicator_id
        assert label != indicator_id, indicator_id


def test_known_indicator_labels() -> None:
    assert indicator_label("FP.CPI.TOTL.ZG") == "تورم قیمت مصرف‌کننده (درصد سالانه)"
    assert indicator_label("TGJU.USD.FREE") == "نرخ دلار آزاد"
    assert indicator_label("TSETMC.TEDPIX") == "شاخص کل بورس تهران (تدپیکس)"
    assert indicator_label("HBSIR.GINI") == "ضریب جینی درآمد خانوار (وزنی)"
    assert indicator_label("SCI.UNEMPLOYMENT.QUARTERLY") == "نرخ بیکاری (آمارگیری نیروی کار، فصلی)"


def test_indicator_label_falls_back_to_catalog_name_then_id() -> None:
    assert indicator_label("NEW.INDICATOR", catalog_name="A new indicator") == "A new indicator"
    assert indicator_label("NEW.INDICATOR") == "NEW.INDICATOR"
    assert indicator_label("", catalog_name="Named later") == "Named later"


def test_domain_labels_cover_the_plan_and_registries() -> None:
    assert PLAN_DOMAINS.issubset(DOMAIN_LABELS)
    assert _registry_domains().issubset(DOMAIN_LABELS)


def test_domain_order_covers_every_label() -> None:
    assert set(DOMAIN_ORDER) == set(DOMAIN_LABELS)
    assert DOMAIN_ORDER[0] == "gdp"
    assert len(set(DOMAIN_ORDER)) == len(DOMAIN_ORDER)


def test_domain_label_falls_back_to_the_raw_slug() -> None:
    assert domain_label("inflation") == "تورم و شاخص قیمت"
    assert domain_label("economy") == "economy"


def test_source_labels_cover_the_registry_sources() -> None:
    assert _registry_sources().issubset(SOURCE_LABELS)


def test_source_label_falls_back_to_the_raw_slug() -> None:
    assert source_label("tgju") == "تی‌جی‌جی‌یو"
    assert source_label("unknown_source") == "unknown_source"


def test_frequency_labels_cover_the_registry_frequencies() -> None:
    assert _registry_frequencies().issubset(FREQUENCY_LABELS)
    assert frequency_label("monthly") == "ماهانه"
    assert frequency_label("hourly") == "hourly"


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_every_derived_suffix_has_a_translated_label(suffix: str) -> None:
    assert suffix in DERIVED_SUFFIX_LABELS
    assert derived_label(suffix) != suffix


def test_derived_suffix_map_is_exactly_the_supported_set() -> None:
    assert set(DERIVED_SUFFIX_LABELS) == set(SUFFIXES)


def test_derived_label_falls_back_to_the_raw_suffix() -> None:
    assert derived_label("YOY") == "رشد سالانه"
    assert derived_label("NEWSUF") == "NEWSUF"


def test_expected_cadence_values() -> None:
    assert source_expected_cadence("tgju") == CADENCE_DAILY
    assert source_expected_cadence("tsetmc") == CADENCE_DAILY
    assert source_expected_cadence("sci") == CADENCE_WEEKLY
    assert source_expected_cadence("world_bank") == CADENCE_MONTHLY
    assert source_expected_cadence("imf") == CADENCE_MONTHLY
    assert source_expected_cadence("eia") == CADENCE_MONTHLY
    assert source_expected_cadence("hbsir") == CADENCE_ANNUAL


def test_expected_cadence_covers_every_labelled_source() -> None:
    assert set(SOURCE_EXPECTED_CADENCE) == set(SOURCE_LABELS)


def test_unknown_source_has_no_cadence_claim() -> None:
    assert source_expected_cadence("unknown_source") is None


def test_cadence_is_ordered_from_daily_to_annual() -> None:
    assert CADENCE_DAILY < CADENCE_WEEKLY < CADENCE_MONTHLY < CADENCE_ANNUAL
    assert isinstance(CADENCE_WEEKLY, timedelta)


def test_is_derived_reads_metadata_not_the_id_shape() -> None:
    # A level id that merely looks suffixed stays a level without metadata.
    assert is_derived({"indicator_id": "TGJU.USD.FREE.MA30"}) is False
    assert is_derived({"method": "daily_return"}) is False
    assert is_derived({"derived_from": None}) is False
    assert is_derived({}) is False
    assert is_derived(None) is False
    # The ETL-written parent id is what makes a series derived.
    assert is_derived({"derived_from": "TGJU.USD.FREE"}) is True


def test_derived_label_composes_parent_and_suffix() -> None:
    label = indicator_label("WB.FP.CPI.TOTL.ZG.YOY", derived_from="FP.CPI.TOTL.ZG")

    assert label == f"{indicator_label('FP.CPI.TOTL.ZG')} – {derived_label('YOY')}"
    assert label == "تورم قیمت مصرف‌کننده (درصد سالانه) – رشد سالانه"


def test_derived_composition_uses_the_catalog_name_for_an_unmapped_parent() -> None:
    label = indicator_label(
        "WB.NEW.IND.YOY",
        catalog_name="A new indicator",
        derived_from="NEW.IND",
    )

    assert label == "A new indicator – رشد سالانه"


def test_unknown_derived_suffix_falls_back_without_inventing_a_fragment() -> None:
    # An unrecognised suffix is never translated: the accessor falls back to the
    # catalog value (the parent's name, per the provenance fill) and then the id.
    assert (
        indicator_label("WB.NEW.IND.NEWSUF", catalog_name="Parent name", derived_from="NEW.IND")
        == "Parent name"
    )
    assert indicator_label("WB.NEW.IND.NEWSUF", derived_from="NEW.IND") == "WB.NEW.IND.NEWSUF"
