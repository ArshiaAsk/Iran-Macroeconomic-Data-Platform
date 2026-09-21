"""AST guard for the D11 page-layout contract (Task 33).

The contract (``design-system.md`` §12) says a **migrated** page function opens
with ``render_page_header``, renders KPI values through ``render_kpi_band``,
section titles through ``render_section_header``, filters through
``render_filter_bar``, and empty/error/loading through ``components/states.py``.
It does not call raw ``st.title``, ``st.metric``, ``st.warning``/``st.info``/
``st.error``, or ``unsafe_allow_html`` where a shared component exists.

This guard is the static half of that contract, modelled on
``test_literal_guard.py``. Two decisions are load-bearing:

- **Function-scoped, not file-scoped.** Every page composition lives in one large
  module (AM-14), so ``MIGRATED_PAGES`` maps module → migrated *function names*
  and grows once per wave. A function that is not listed is not checked, which is
  what lets the migration land page by page without a flag day.
- **The whitelist is the shared-component modules, not the page modules.** The
  components must call the banned APIs themselves — ``render_callout`` *is* a
  ``st.warning`` — so scanning them would report the contract's own
  implementation. The whitelist is pinned against the design-system document by
  :func:`test_the_whitelist_matches_the_design_system_contract`, so the two cannot
  drift apart.
"""

import ast
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

DESIGN_SYSTEM_DOC: Final[Path] = REPOSITORY_ROOT / "docs" / "phase-7.2" / "design-system.md"

#: Streamlit calls the contract replaces with a shared component. Exactly the
#: list §12 names -- no more, so the guard cannot drift ahead of the contract.
BANNED_FUNCTIONS: Final[frozenset[str]] = frozenset({"title", "metric", "warning", "info", "error"})

#: The raw-HTML escape hatch, banned where a shared component exists. Checked as a
#: keyword, because it is an argument rather than a call.
BANNED_KEYWORDS: Final[frozenset[str]] = frozenset({"unsafe_allow_html"})

#: Module → the migrated page functions in it. Starts with the Overview (Wave C)
#: and grows once per wave; the plan writes the same map with a trailing ``...``.
#: The Overview's two section renderers are listed alongside its entry function so
#: the guard covers the whole page composition, not just its first call.
MIGRATED_PAGES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "dashboard/page_view.py": frozenset(
            {
                "render_overview_page",
                "_render_domain_counts",
                "_render_coverage_section",
            }
        ),
    }
)

#: Modules that own the contract's implementation and therefore must call the
#: banned APIs. Kept equal to the §12 list by its own test.
LAYOUT_WHITELIST: Final[frozenset[str]] = frozenset(
    {
        "dashboard/components/layout.py",
        "dashboard/components/states.py",
        "dashboard/components/html_table.py",
        "dashboard/components/direction.py",
    }
)


@dataclass(frozen=True)
class LayoutFinding:
    """One contract violation inside a migrated function."""

    module: str
    function: str
    call: str
    line: int


def find_layout_violations(
    source: str,
    *,
    module: str = "<source>",
    migrated: Mapping[str, frozenset[str]] = MIGRATED_PAGES,
    whitelisted: frozenset[str] = LAYOUT_WHITELIST,
) -> list[LayoutFinding]:
    """Return the layout-contract violations in one module's source.

    Only calls that sit inside a function named in ``migrated[module]`` are
    reported, so an un-migrated function in a migrated module stays clean. A
    whitelisted module is skipped entirely. A nested function's body is attributed
    to its enclosing migrated function, which is the conservative reading.

    Args:
        source: Python source text
        module: Module path used for the migrated and whitelist lookups
        migrated: The migrated functions per module path
        whitelisted: Modules that implement the contract and are not scanned

    Returns:
        Findings in source order (empty when the module is clean)
    """
    if module in whitelisted:
        return []
    migrated_functions = migrated.get(module, frozenset())
    if not migrated_functions:
        return []
    tree = ast.parse(source)
    findings: list[LayoutFinding] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name not in migrated_functions:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            banned = _banned_call(call)
            if banned is not None:
                findings.append(LayoutFinding(module, node.name, banned, call.lineno))
    return findings


def _banned_call(call: ast.Call) -> str | None:
    """The banned API this call uses, or ``None`` when it uses none."""
    for keyword in call.keywords:
        if keyword.arg in BANNED_KEYWORDS:
            return keyword.arg
    func = call.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr in BANNED_FUNCTIONS
        and isinstance(func.value, ast.Name)
        and func.value.id == "st"
    ):
        return f"st.{func.attr}"
    return None


def migrated_modules() -> list[tuple[str, Path]]:
    """Every module named in ``MIGRATED_PAGES`` as ``(module path, path)``."""
    return [(module, REPOSITORY_ROOT / module) for module in sorted(MIGRATED_PAGES)]


def contract_modules() -> set[str]:
    """The ``components/*.py`` module paths the design-system §12 list names."""
    section = DESIGN_SYSTEM_DOC.read_text("utf-8").split("## 12.", 1)[1].split("## 13.", 1)[0]
    return {f"dashboard/{match}" for match in re.findall(r"components/[a-z_]+\.py", section)}


def test_no_layout_violation_in_a_migrated_function() -> None:
    findings = [
        finding
        for module, path in migrated_modules()
        for finding in find_layout_violations(path.read_text("utf-8"), module=module)
    ]

    assert findings == []


def test_the_guard_scans_the_migrated_modules() -> None:
    modules = migrated_modules()

    # Not vacuous: the Overview's composition is actually scanned.
    assert [module for module, _ in modules] == ["dashboard/page_view.py"]
    assert all(path.is_file() for _, path in modules)
    assert "render_overview_page" in MIGRATED_PAGES["dashboard/page_view.py"]


def test_guard_flags_a_raw_metric_in_a_migrated_function() -> None:
    source = (
        "import streamlit as st\n"
        "def render_overview_page() -> None:\n"
        '    st.metric("Sources", 7)\n'
    )

    findings = find_layout_violations(source, module="dashboard/page_view.py")

    assert [(finding.function, finding.call) for finding in findings] == [
        ("render_overview_page", "st.metric")
    ]
    assert findings[0].line == 3


def test_guard_flags_every_banned_call() -> None:
    source = (
        "import streamlit as st\n"
        "def render_overview_page() -> None:\n"
        '    st.title("t")\n'
        '    st.warning("w")\n'
        '    st.info("i")\n'
        '    st.error("e")\n'
        "    st.markdown('<b>x</b>', unsafe_allow_html=True)\n"
    )

    calls = [
        finding.call for finding in find_layout_violations(source, module="dashboard/page_view.py")
    ]

    assert calls == ["st.title", "st.warning", "st.info", "st.error", "unsafe_allow_html"]


def test_guard_ignores_a_banned_call_outside_a_migrated_function() -> None:
    """The guard is function-scoped, so an un-migrated sibling is not reported."""
    source = "import streamlit as st\n" "def render_gdp_page() -> None:\n" '    st.title("GDP")\n'

    assert find_layout_violations(source, module="dashboard/page_view.py") == []


def test_guard_ignores_a_banned_call_in_an_unlisted_module() -> None:
    source = "import streamlit as st\ndef render_overview_page() -> None:\n    st.title('t')\n"

    assert find_layout_violations(source, module="dashboard/page_view_2.py") == []


def test_guard_ignores_a_banned_call_in_a_whitelisted_module() -> None:
    source = "import streamlit as st\ndef render_overview_page() -> None:\n    st.title('t')\n"

    for module in sorted(LAYOUT_WHITELIST):
        assert find_layout_violations(source, module=module) == []


def test_guard_allows_the_shared_components() -> None:
    """A migrated function may call the components, which is the whole point."""
    source = (
        "from dashboard.components.layout import render_callout, render_page_header\n"
        "def render_overview_page() -> None:\n"
        '    render_page_header("page.overview", callout_key="warn.x")\n'
        '    render_callout("warn.y")\n'
    )

    assert find_layout_violations(source, module="dashboard/page_view.py") == []


def test_the_whitelist_matches_the_design_system_contract() -> None:
    """The guard's whitelist and the §12 list are the same set of modules."""
    assert contract_modules() == set(LAYOUT_WHITELIST)


def test_the_contract_list_is_derived_from_the_document() -> None:
    """The comparison is not vacuous: the §12 section really names them."""
    section = DESIGN_SYSTEM_DOC.read_text("utf-8").split("## 12.", 1)[1]

    for module in sorted(LAYOUT_WHITELIST):
        assert module.removeprefix("dashboard/") in section, module
