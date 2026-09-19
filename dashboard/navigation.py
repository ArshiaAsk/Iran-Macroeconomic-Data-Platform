"""Declarative navigation registry for the dashboard information architecture.

The registry is plain data. ``st.Page`` objects are built from it inside the
running Streamlit entrypoint (``dashboard/app.py``), never at import time: outside
a script run ``st.Page`` silently degrades to a stub
(see ``docs/phase-7.1/wave-0-spike.md``). Page paths are relative to the
entrypoint, which is what ``st.Page`` resolves against.

Sidebar labels are not stored here. Each page's nav label and in-page title are
both resolved from the string catalog (``nav.<key>`` / ``page.<key>``) so a
literal cannot survive outside ``dashboard/i18n.py`` and the two cannot drift.
Group names are stable keys for the same reason (``group.<key>``).

Owned domains mirror the Phase 7.1 plan: the all-domain views (Overview,
Comparison & Correlation, Data Catalog) own no domain, and every other page owns
exactly the domains it renders. ``economy`` is a dead domain and is never
claimed. The Welfare & Survey page owns ``welfare`` (split out of the old
Trade/Welfare/Energy page), the Market page owns ``market`` and the Labor page
owns ``labor`` (SCI's quarterly unemployment rate), so every plan domain has
exactly one owner.
"""

from dataclasses import dataclass
from typing import Final

GROUP_OVERVIEW_ANALYSIS: Final[str] = "overview_analysis"
GROUP_DOMAINS: Final[str] = "domains"

GROUPS: Final[tuple[str, ...]] = (GROUP_OVERVIEW_ANALYSIS, GROUP_DOMAINS)
"""Sidebar section keys in display order; every page belongs to exactly one.

The Persian section labels live in ``dashboard/i18n.py`` as ``group.<key>``.
"""


@dataclass(frozen=True, slots=True)
class PageSpec:
    """One dashboard page: routing and ownership metadata.

    ``key`` is the stable per-page identifier and the i18n namespace: the nav
    label is ``nav.<key>`` and the in-page title is ``page.<key>``.
    """

    key: str
    path: str
    icon: str
    group: str
    domains: tuple[str, ...] = ()
    is_default: bool = False


PAGES: Final[tuple[PageSpec, ...]] = (
    PageSpec(
        key="overview",
        path="pages/1_Overview.py",
        icon="🧭",
        group=GROUP_OVERVIEW_ANALYSIS,
        is_default=True,
    ),
    PageSpec(
        key="correlation",
        path="pages/6_Correlation.py",
        icon="🔗",
        group=GROUP_OVERVIEW_ANALYSIS,
    ),
    PageSpec(
        key="catalog",
        path="pages/7_Data_Catalog.py",
        icon="📚",
        group=GROUP_OVERVIEW_ANALYSIS,
    ),
    PageSpec(
        key="inflation",
        path="pages/2_Inflation.py",
        icon="📈",
        group=GROUP_DOMAINS,
        domains=("inflation",),
    ),
    PageSpec(
        key="gdp",
        path="pages/3_GDP_Economy.py",
        icon="📊",
        group=GROUP_DOMAINS,
        domains=("gdp",),
    ),
    PageSpec(
        key="trade_energy",
        path="pages/4_Trade_Welfare_Energy.py",
        icon="🚢",
        group=GROUP_DOMAINS,
        domains=("trade", "energy"),
    ),
    PageSpec(
        key="welfare",
        path="pages/8_Welfare_Survey.py",
        icon="🏠",
        group=GROUP_DOMAINS,
        domains=("welfare",),
    ),
    PageSpec(
        key="fx_gold",
        path="pages/5_FX_Gold.py",
        icon="💱",
        group=GROUP_DOMAINS,
        domains=("fx", "gold"),
    ),
    PageSpec(
        key="market",
        path="pages/9_Market.py",
        icon="📉",
        group=GROUP_DOMAINS,
        domains=("market",),
    ),
    PageSpec(
        key="labor",
        path="pages/10_Labor.py",
        icon="💼",
        group=GROUP_DOMAINS,
        domains=("labor",),
    ),
)
"""Dashboard pages in sidebar order, grouped by :data:`GROUPS`."""


def page_for_domain(domain: str) -> PageSpec | None:
    """Return the page that owns ``domain``, or ``None`` when unowned.

    Ownership is declared once in :data:`PAGES`, so the Overview's per-domain
    links and the domain-coverage test read the same declaration.

    Examples:
        >>> page_for_domain("inflation").key
        'inflation'
        >>> page_for_domain("economy") is None
        True
    """
    for spec in PAGES:
        if domain in spec.domains:
            return spec
    return None
