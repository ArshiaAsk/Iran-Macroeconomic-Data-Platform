"""Ten-page router smoke: every ``PageSpec`` renders through the entrypoint.

The Wave A gate used a throwaway script to prove all ten pages survive the
router. This module makes that safety net permanent so the shell changes in
Wave B (icons, brand, DB status, top bar) and every later wave keep a single
automated guard that catches a page raising where a per-page test does not
yet exercise it.

Each page is driven through ``app_smoke.app_test(..., use_router=True)``, which
runs ``dashboard/app.py`` and then ``switch_page`` to the requested page — the
path a real session takes. The only assertion is ``not app.exception``: this is
a "does it render?" net, not a per-page behavioural test.
"""

from pathlib import Path

import pytest

from dashboard.navigation import PAGES, PageSpec
from tests.unit.dashboard.app_smoke import app_test

#: One ``pytest.param`` per registry page, identified by its stable key so a
#: failure names the page rather than its file name. The id also carries the
#: group so the report reads "overview_analysis-overview" / "domains-inflation".
_PAGE_IDS = [f"{spec.group}-{spec.key}" for spec in PAGES]


@pytest.mark.parametrize(
    "spec",
    PAGES,
    ids=_PAGE_IDS,
)
def test_every_page_renders_through_the_router(
    spec: PageSpec,
    fake_streamlit_connection: None,
) -> None:
    """Render every page through the entrypoint and assert it does not raise."""
    page_filename = Path(spec.path).name
    app = app_test(page_filename, use_router=True)

    assert not app.exception, (
        f"page {spec.key!r} ({page_filename}) raised: "
        f"{app.exception[0].value if app.exception else ''}"
    )
