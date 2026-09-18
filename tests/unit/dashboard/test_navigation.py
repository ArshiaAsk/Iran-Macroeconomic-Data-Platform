"""Registry invariants for the dashboard navigation declaration.

Sidebar chrome is frontend-rendered and invisible to ``AppTest`` (Wave 0), so
order, grouping and domain ownership are asserted against the registry data —
the single declaration consumed by ``st.navigation``.
"""

from collections import Counter

from dashboard.navigation import GROUPS, PAGES
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

DASHBOARD_ROOT = REPOSITORY_ROOT / "dashboard"

# Domains of the Phase 7.1 target information architecture.
PLAN_DOMAINS = frozenset(
    {"gdp", "inflation", "trade", "welfare", "energy", "fx", "gold", "labor", "market"}
)
# Labor is a later task: its domain stays deliberately unowned until that page is
# registered here. `market` is owned by the Market page (Task 10) and `welfare` by
# the Welfare & Survey page.
PENDING_DOMAINS = frozenset({"labor"})


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
    assert set(owners) == PLAN_DOMAINS - PENDING_DOMAINS


def test_domain_exceptions_from_the_plan_hold() -> None:
    specs = {spec.key: spec for spec in PAGES}

    # `economy` is dead: no source emits it, so no page may claim it.
    assert "economy" not in _owner_counts()
    assert specs["gdp"].domains == ("gdp",)
    # `welfare` belongs to the Welfare & Survey page, not to the trade page.
    assert specs["trade_energy"].domains == ("trade", "energy")
    assert specs["welfare"].domains == ("welfare",)
    assert specs["inflation"].domains == ("inflation",)
    assert specs["fx_gold"].domains == ("fx", "gold")
    # The plan's all-domain views own no domain at all.
    assert {spec.key for spec in PAGES if not spec.domains} == {
        "overview",
        "correlation",
        "catalog",
    }
