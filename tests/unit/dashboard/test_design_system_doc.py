"""Completeness guards for ``docs/phase-7.2/design-system.md`` (Task 23).

The design system is the reference for every later phase, so it is checked the
way a hand-written document actually drifts: a renderer that exists in code but
not in the catalogue, a relative link whose target was renamed or never created,
and a section the plan asked for that quietly went missing. Both the component
names and the link targets are derived from the source tree and the document, so
nothing is duplicated here and a new component fails the guard until it is
documented.
"""

import ast
import re
from pathlib import Path
from typing import Final

from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

DOC_PATH: Final[Path] = REPOSITORY_ROOT / "docs" / "phase-7.2" / "design-system.md"
COMPONENTS_ROOT: Final[Path] = REPOSITORY_ROOT / "dashboard" / "components"

#: Prefixes of the components a page composes with: the renderers, plus the
#: figure/table builders. The other public helpers (``serialize_*``,
#: ``find_chromium_executable``, ...) are engine internals, not components.
COMPONENT_PREFIXES: Final[tuple[str, ...]] = ("render_", "build_")

#: The typed HTML-table cells the document's typed-cell model lists.
CELL_CLASSES: Final[frozenset[str]] = frozenset(
    {"Text", "Ltr", "UnitChip", "StatusChip", "Dot", "TwoLine"}
)

#: Sections the plan requires in the first draft, pinned by their heading.
REQUIRED_HEADINGS: Final[tuple[str, ...]] = (
    "## 2. Design tokens",
    "## 4. Component catalogue",
    "## 5. CSS ownership and the hook pattern",
    "## 8. Tables: classification and the typed-cell model (D1)",
    "## 9. Calendar rule (D3) and the theme lock (D14)",
    "## 12. The page-layout contract (D11)",
    "## 13. Do / Don't",
)

_MARKDOWN_LINK: Final[re.Pattern[str]] = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_REMOTE_SCHEMES: Final[tuple[str, ...]] = ("http://", "https://", "mailto:", "#")


def document_text() -> str:
    """The design-system document as text."""
    return DOC_PATH.read_text("utf-8")


def public_components() -> dict[str, str]:
    """Every public component name in the package, mapped to its module."""
    components: dict[str, str] = {}
    for path in sorted(COMPONENTS_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name.startswith(COMPONENT_PREFIXES):
                components[node.name] = path.name
    return components


def undocumented_components(document: str) -> list[str]:
    """The component names that do not appear in ``document``."""
    return sorted(name for name in public_components() if name not in document)


def relative_links(document: str) -> list[str]:
    """The link targets in ``document`` that point at a repository file."""
    targets: list[str] = []
    for match in _MARKDOWN_LINK.finditer(document):
        target = match.group(1).split("#", 1)[0]
        if not target or target.startswith(_REMOTE_SCHEMES):
            continue
        targets.append(target)
    return targets


def test_the_document_exists() -> None:
    assert DOC_PATH.is_file()
    assert DOC_PATH.stat().st_size > 0


def test_the_guard_scans_the_components_package() -> None:
    components = public_components()

    # Not vacuous: the scan sees the Wave A components and the older renderers.
    assert "render_page_header" in components
    assert "render_kpi_band" in components
    assert "render_bar_list" in components
    assert "render_html_table" in components
    assert "build_correlation_chart" in components
    assert len(components) > 15


def test_every_public_component_is_documented() -> None:
    assert undocumented_components(document_text()) == []


def test_the_guard_flags_a_component_missing_from_the_document() -> None:
    document = document_text()

    # The real document is complete, but an empty one is not accepted.
    assert undocumented_components("") != []
    assert "render_page_header" in undocumented_components("")
    # Every name is matched, so removing one from a copy of the document fails.
    stripped = document.replace("render_page_header", "render_page_hdr")
    assert undocumented_components(stripped) == ["render_page_header"]


def test_the_page_header_component_is_documented() -> None:
    """The plan calls this one out by name: the single page-header pattern."""
    document = document_text()

    assert "render_page_header" in document
    assert "page-header pattern" in document


def test_the_typed_cells_are_documented() -> None:
    document = document_text()

    for cell in sorted(CELL_CLASSES):
        assert f"`{cell}(" in document, cell


def test_the_document_covers_the_planned_sections() -> None:
    document = document_text()

    for heading in REQUIRED_HEADINGS:
        assert heading in document, heading
    # The catalogue carries a worked example (the plan asks for one).
    assert "```python" in document


def test_the_layout_contract_matches_the_d11_decision() -> None:
    """The contract section must state the guard D11 actually specifies."""
    section = document_text().split("## 12.", 1)[1].split("## 13.", 1)[0]

    # Function-scoped, because every page composition lives in one module.
    assert "MIGRATED_PAGES" in section
    assert "function-scoped" in section
    # The whitelist is the shared-component modules, not the page modules.
    for module in (
        "components/layout.py",
        "components/states.py",
        "components/html_table.py",
        "components/direction.py",
    ):
        assert module in section, module
    # ...and it names the five shared layout components.
    for component in (
        "render_page_header",
        "render_callout",
        "render_kpi_band",
        "render_section_header",
        "render_filter_bar",
    ):
        assert component in section, component


def test_every_relative_link_resolves() -> None:
    links = relative_links(document_text())

    assert links, "the document should link its sources"
    missing = [link for link in links if not (DOC_PATH.parent / link).resolve().exists()]
    assert missing == []


def test_the_link_check_ignores_remote_and_anchor_targets() -> None:
    document = (
        "[web](https://example.com/x.md) "
        "[anchor](#section) "
        "[mail](mailto:a@b.c) "
        "[local](wave-0-spike.md) "
        "[anchored](wave-0-spike.md#part)"
    )

    assert relative_links(document) == ["wave-0-spike.md", "wave-0-spike.md"]
