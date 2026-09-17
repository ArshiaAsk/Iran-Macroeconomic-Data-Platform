"""Declarative navigation registry for the dashboard information architecture.

The registry is plain data. ``st.Page`` objects are built from it inside the
running Streamlit entrypoint (``dashboard/app.py``), never at import time: outside
a script run ``st.Page`` silently degrades to a stub
(see ``docs/phase-7.1/wave-0-spike.md``). Page paths are relative to the
entrypoint, which is what ``st.Page`` resolves against.

Owned domains mirror the Phase 7.1 plan: the all-domain views (Overview,
Comparison & Correlation, Data Catalog) own no domain, and every other page owns
exactly the domains it renders. ``economy`` is a dead domain and is never
claimed. The Welfare & Survey, Labor and Market pages land in Tasks 10-12, so
``welfare``, ``labor`` and ``market`` stay unowned until those pages are
registered here; until Task 12 splits it, ``pages/4_Trade_Welfare_Energy.py``
still renders the ``welfare`` indicators standalone.
"""

from dataclasses import dataclass
from typing import Final

GROUPS: Final[tuple[str, ...]] = ("Overview & Analysis", "Domains")
"""Sidebar sections in display order; every page belongs to exactly one."""


@dataclass(frozen=True, slots=True)
class PageSpec:
    """One dashboard page: routing, presentation and ownership metadata.

    ``key`` is the stable per-page identifier used as the i18n namespace
    (``nav.<key>`` / ``page.<key>``) once the string catalog lands.
    """

    key: str
    path: str
    title: str
    icon: str
    group: str
    domains: tuple[str, ...] = ()
    is_default: bool = False


PAGES: Final[tuple[PageSpec, ...]] = (
    PageSpec(
        key="overview",
        path="pages/1_Overview.py",
        title="Overview",
        icon="🧭",
        group="Overview & Analysis",
        is_default=True,
    ),
    PageSpec(
        key="correlation",
        path="pages/6_Correlation.py",
        title="Comparison & Correlation",
        icon="🔗",
        group="Overview & Analysis",
    ),
    PageSpec(
        key="catalog",
        path="pages/7_Data_Catalog.py",
        title="Data Catalog",
        icon="📚",
        group="Overview & Analysis",
    ),
    PageSpec(
        key="inflation",
        path="pages/2_Inflation.py",
        title="Inflation",
        icon="📈",
        group="Domains",
        domains=("inflation",),
    ),
    PageSpec(
        key="gdp",
        path="pages/3_GDP_Economy.py",
        title="GDP & Economy",
        icon="📊",
        group="Domains",
        domains=("gdp",),
    ),
    PageSpec(
        key="trade_energy",
        path="pages/4_Trade_Welfare_Energy.py",
        title="Trade, Welfare & Energy",
        icon="🚢",
        group="Domains",
        domains=("trade", "energy"),
    ),
    PageSpec(
        key="fx_gold",
        path="pages/5_FX_Gold.py",
        title="FX & Gold",
        icon="💱",
        group="Domains",
        domains=("fx", "gold"),
    ),
)
"""Dashboard pages in sidebar order, grouped by :data:`GROUPS`."""
