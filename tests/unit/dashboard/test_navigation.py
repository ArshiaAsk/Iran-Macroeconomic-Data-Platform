"""Registry invariants for the dashboard navigation declaration.

Sidebar chrome is frontend-rendered and invisible to ``AppTest`` (Wave 0), so
order, grouping and domain ownership are asserted against the registry data —
the single declaration consumed by ``st.navigation``.
"""

from collections import Counter

from dashboard.navigation import GROUPS, PAGES, page_for_domain
from src.connectors import eia, hbsir, imf, sci_scraper, tgju_scraper, tsetmc, world_bank
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

DASHBOARD_ROOT = REPOSITORY_ROOT / "dashboard"

# Domains of the Phase 7.1 target information architecture.
PLAN_DOMAINS = frozenset(
    {"gdp", "inflation", "trade", "welfare", "energy", "fx", "gold", "labor", "market"}
)
# Every plan domain has an owner now: `market` by the Market page (Task 10),
# `welfare` by the Welfare & Survey page and `labor` by the Labor page (Task 11).


def _active_registry_domains() -> set[str]:
    """Domains emitted by the active connector registries.

    The registries are the authoritative source inventory (the catalog is seeded
    from ``discover()``), so this is the set of domains a page must own. It
    includes the SCI publication domains -- notably ``labor`` -- which the
    canonical-only view of ``SCI_CANONICAL_INDICATORS`` would miss.
    """
    domains = set(world_bank.INDICATOR_DOMAINS.values())
    domains |= {indicator.domain for indicator in imf.IMF_INDICATORS.values()}
    domains |= {indicator.domain for indicator in eia.EIA_INDICATORS.values()}
    domains |= {metadata[2] for metadata in tgju_scraper.INDICATOR_REGISTRY.values()}
    domains |= {indicator.domain for indicator in sci_scraper.SCI_CANONICAL_INDICATORS.values()}
    domains |= {publication.domain for publication in sci_scraper.SCI_INDICATOR_REGISTRY.values()}
    domains |= {indicator.domain for indicator in tsetmc.TSETMC_INDICATORS.values()}
    domains |= {indicator.domain for indicator in hbsir.HBSIR_INDICATORS.values()}
    return domains


def _owner_counts() -> Counter[str]:
    return Counter(domain for spec in PAGES for domain in spec.domains)


def test_registered_page_paths_exist() -> None:
    for spec in PAGES:
        assert (DASHBOARD_ROOT / spec.path).is_file(), spec.path


def test_page_paths_and_keys_are_unique() -> None:
    assert len({spec.path for spec in PAGES}) == len(PAGES)
    assert len({spec.key for spec in PAGES}) == len(PAGES)


def test_exactly_one_default_page() -> None:
    defaults = [spec for spec in PAGES if spec.is_default]

    assert len(defaults) == 1
    # The registry's default page is the all-domain Overview.
    assert defaults[0].key == "overview"


def test_pages_declare_a_known_group_in_order() -> None:
    assert {spec.group for spec in PAGES} == set(GROUPS)
    group_order = [GROUPS.index(spec.group) for spec in PAGES]
    assert group_order == sorted(group_order)


def test_no_page_owns_a_domain_twice() -> None:
    for spec in PAGES:
        assert len(set(spec.domains)) == len(spec.domains), spec.key


def test_every_plan_domain_has_exactly_one_owner() -> None:
    owners = _owner_counts()

    assert [domain for domain, count in owners.items() if count > 1] == []
    assert set(owners) == PLAN_DOMAINS


def test_active_registry_domains_match_the_plan() -> None:
    # The plan's domain list is not a separate truth: it is exactly what the
    # active connector registries emit, `labor` included.
    assert _active_registry_domains() == PLAN_DOMAINS


def test_every_active_catalog_domain_is_claimed_by_exactly_one_page() -> None:
    owners = _owner_counts()
    active = _active_registry_domains()

    # Every active domain has exactly one owner...
    assert set(owners) == active
    assert [domain for domain, count in owners.items() if count > 1] == []
    # ...and every domain has at least one active indicator behind it.
    for domain in active:
        assert page_for_domain(domain) is not None, domain


def test_no_page_claims_a_domain_without_active_indicators() -> None:
    claimed = {domain for spec in PAGES for domain in spec.domains}

    assert claimed <= _active_registry_domains()


def test_domain_exceptions_from_the_plan_hold() -> None:
    specs = {spec.key: spec for spec in PAGES}

    # `economy` is dead: no source emits it, so no page may claim it.
    assert "economy" not in _owner_counts()
    assert specs["gdp"].domains == ("gdp",)
    # `welfare` belongs to the Welfare & Survey page, not to the trade page.
    assert specs["trade_energy"].domains == ("trade", "energy")
    assert specs["welfare"].domains == ("welfare",)
    # `labor` (SCI's quarterly unemployment) is its own page, not merged into
    # Welfare through IMF `LUR`, which stays domain `welfare`.
    assert specs["labor"].domains == ("labor",)
    assert specs["inflation"].domains == ("inflation",)
    assert specs["fx_gold"].domains == ("fx", "gold")
    # The plan's all-domain views own no domain at all.
    assert {spec.key for spec in PAGES if not spec.domains} == {
        "overview",
        "correlation",
        "catalog",
    }
