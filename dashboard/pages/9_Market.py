"""Market (TSETMC) dashboard page.

The page is a thin delegate: the composition (filters, Gold load, derived-series
discovery, sections) lives in ``dashboard.page_view``.
"""

from dashboard.page_view import render_market_page

render_market_page()
