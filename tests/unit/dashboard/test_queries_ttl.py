"""TTL contract for ``dashboard.queries`` (Task 26).

Only ``cached_source_freshness`` should receive a TTL; the other cached wrappers
keep their existing behaviour. The tests parse the source rather than exercising
Streamlit's internal cache expiry, which is the reliable check in this repo.
"""

import ast
from pathlib import Path
from typing import Final

from dashboard.queries import FRESHNESS_CACHE_TTL_SECONDS
from tests.unit.dashboard.app_smoke import REPOSITORY_ROOT

QUERIES_PATH: Final[Path] = REPOSITORY_ROOT / "dashboard" / "queries.py"

#: Every wrapper decorated with ``@st.cache_data`` in ``queries.py``.
CACHED_WRAPPERS: Final[tuple[str, ...]] = (
    "cached_list_indicators",
    "cached_load_series",
    "cached_coverage_summary",
    "cached_list_derived_ids",
    "cached_source_freshness",
    "cached_available_domains",
    "cached_series_inventory",
)


def _decorator_keywords(function_name: str) -> dict[str, ast.expr]:
    """Return the keyword arguments of the ``@st.cache_data`` decorator on
    ``function_name`` as a mapping from keyword name to AST expression node."""
    source = QUERIES_PATH.read_text("utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != function_name:
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "cache_data"
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "st"
            ):
                return {
                    keyword.arg: keyword.value
                    for keyword in decorator.keywords
                    if keyword.arg is not None
                }
    message = f"could not find @st.cache_data decorator on {function_name}"
    raise AssertionError(message)


def test_freshness_ttl_is_a_positive_number_of_seconds() -> None:
    """The constant is documented and has a sensible positive value."""

    assert isinstance(FRESHNESS_CACHE_TTL_SECONDS, int)
    assert FRESHNESS_CACHE_TTL_SECONDS > 0


def test_freshness_wrapper_passes_the_ttl() -> None:
    """Only the freshness wrapper passes ``ttl=FRESHNESS_CACHE_TTL_SECONDS``."""

    keywords = _decorator_keywords("cached_source_freshness")

    assert "ttl" in keywords
    ttl_expr = keywords["ttl"]
    assert isinstance(ttl_expr, ast.Name)
    assert ttl_expr.id == "FRESHNESS_CACHE_TTL_SECONDS"


def test_other_wrappers_do_not_pass_a_ttl() -> None:
    """Every wrapper except freshness keeps its original decorator arguments."""

    for name in CACHED_WRAPPERS:
        if name == "cached_source_freshness":
            continue
        keywords = _decorator_keywords(name)
        assert "ttl" not in keywords, f"{name} unexpectedly passes ttl="
