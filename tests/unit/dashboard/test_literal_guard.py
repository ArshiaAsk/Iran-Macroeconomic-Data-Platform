"""AST guard against untranslated user-visible literals in the dashboard.

Every user-visible string belongs in :mod:`dashboard.i18n` (resolved through
``t(...)``); :mod:`dashboard.labels` holds the indicator/domain/source name maps.
This guard walks ``dashboard/**/*.py`` and flags a *string constant* passed as the
label of a Streamlit display function, because such a literal cannot be
translated. Variables, calls (``t(...)`` or any computed label), attributes and
docstrings are not literals and are deliberately allowed -- only a literal can be
proven untranslated statically.

The two presentation modules that *own* the literals are whitelisted, and a
documented allowlist exists for data-level English values (a catalog name or a
source slug) that must be shown verbatim.
"""

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

DASHBOARD_ROOT = REPOSITORY_ROOT / "dashboard"

#: Streamlit functions whose label argument is user-visible UI chrome. Kept in
#: step with the plan's explicit list (Task 27).
DISPLAY_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "title",
        "subheader",
        "metric",
        "button",
        "checkbox",
        "multiselect",
        "date_input",
        "warning",
        "info",
        "error",
        "download_button",
    }
)

#: Keyword the label may be passed under instead of positionally.
LABEL_KEYWORDS: Final[frozenset[str]] = frozenset({"label", "body"})

#: Modules that own user-visible literals by design and are therefore not scanned.
WHITELISTED_MODULES: Final[frozenset[str]] = frozenset(
    {
        "dashboard/i18n.py",
        "dashboard/labels.py",
    }
)

#: Documented data-level English values that must render verbatim (catalog names,
#: source slugs, units). Empty today -- every literal lives in the catalog -- but
#: kept explicit so a future data-level value is added deliberately rather than by
#: disabling the guard. Keyed by module path, valued by the allowed literal.
LITERAL_ALLOWLIST: Final[Mapping[str, frozenset[str]]] = MappingProxyType({})


@dataclass(frozen=True)
class LiteralFinding:
    """One untranslated literal passed to a Streamlit display function."""

    module: str
    function: str
    literal: str
    line: int


def find_untranslated_literals(
    source: str,
    *,
    module: str = "<source>",
    allowlist: Mapping[str, frozenset[str]] = LITERAL_ALLOWLIST,
) -> list[LiteralFinding]:
    """Return the untranslated display literals in one module's source.

    Only ``st.<display>(<string constant> ...)`` calls are reported; ``t(...)``
    calls, variables, computed labels and docstrings are not literals and are not
    reported. A whitelisted module is skipped entirely, and a literal present in
    the allowlist for that module is accepted.

    Args:
        source: Python source text
        module: Module path used for whitelist and allowlist lookups
        allowlist: Allowed data-level literals, keyed by module path

    Returns:
        Findings in source order (empty when the module is clean)
    """
    if module in WHITELISTED_MODULES:
        return []
    allowed = allowlist.get(module, frozenset())
    tree = ast.parse(source)
    findings: list[LiteralFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in DISPLAY_FUNCTIONS:
            continue
        if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "st"):
            continue
        literal = _label_literal(node)
        if literal is not None and literal not in allowed:
            findings.append(LiteralFinding(module, node.func.attr, literal, node.lineno))
    return findings


def _label_literal(node: ast.Call) -> str | None:
    """The label argument of a display call when it is a string constant."""
    candidates: list[ast.expr] = list(node.args[:1])
    candidates += [keyword.value for keyword in node.keywords if keyword.arg in LABEL_KEYWORDS]
    for candidate in candidates:
        if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
            return candidate.value
    return None


def dashboard_modules() -> list[tuple[str, Path]]:
    """Every ``dashboard/**/*.py`` module as ``(relative posix path, path)``."""
    return sorted(
        (path.relative_to(REPOSITORY_ROOT).as_posix(), path)
        for path in DASHBOARD_ROOT.rglob("*.py")
    )


def test_no_untranslated_literal_in_the_dashboard_tree() -> None:
    findings = [
        finding
        for module, path in dashboard_modules()
        for finding in find_untranslated_literals(path.read_text("utf-8"), module=module)
    ]

    assert findings == []


def test_the_guard_scans_the_whole_dashboard_tree() -> None:
    modules = {module for module, _ in dashboard_modules()}

    # The scan is not vacuous: it sees the page modules and the components.
    assert "dashboard/app.py" in modules
    assert "dashboard/page_view.py" in modules
    assert "dashboard/pages/1_Overview.py" in modules
    assert len(modules) > 10


def test_guard_flags_a_literal_title() -> None:
    findings = find_untranslated_literals('import streamlit as st\nst.title("Inflation")\n')

    assert [finding.literal for finding in findings] == ["Inflation"]
    assert findings[0].function == "title"
    assert findings[0].line == 2


def test_guard_allows_translated_variables_and_calls() -> None:
    source = (
        "import streamlit as st\n"
        'st.title(t("page.gdp"))\n'
        "st.title(title)\n"
        "st.subheader(market_series_label(rows))\n"
        "st.info(scaled.notice)\n"
    )

    assert find_untranslated_literals(source) == []


def test_guard_flags_a_literal_keyword_label() -> None:
    findings = find_untranslated_literals('import streamlit as st\nst.metric(label="Total")\n')

    assert [finding.literal for finding in findings] == ["Total"]


def test_guard_ignores_docstrings_and_non_display_calls() -> None:
    source = (
        '"""A docstring that mentions st.title("English") but is not code."""\n'
        "import streamlit as st\n"
        'st.write("not a guarded function")\n'
        'helper("also not guarded")\n'
    )

    assert find_untranslated_literals(source) == []


def test_guard_skips_whitelisted_modules() -> None:
    source = 'import streamlit as st\nst.title("کاتالوگ")\n'

    assert find_untranslated_literals(source, module="dashboard/i18n.py") == []
    assert find_untranslated_literals(source, module="dashboard/labels.py") == []
    assert find_untranslated_literals(source, module="dashboard/page_view.py") != []


def test_allowlist_accepts_a_documented_data_level_value() -> None:
    source = 'import streamlit as st\nst.info("world_bank")\n'
    module = "dashboard/page_view.py"
    allowlist = {module: frozenset({"world_bank"})}

    # Without the allowlist the literal is flagged...
    assert [finding.literal for finding in find_untranslated_literals(source, module=module)] == [
        "world_bank"
    ]
    # ...with it, the documented data-level value is accepted.
    assert find_untranslated_literals(source, module=module, allowlist=allowlist) == []
