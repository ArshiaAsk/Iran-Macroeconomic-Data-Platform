"""Labor dashboard page.

The page is a thin delegate: the composition (filters, Gold load, derived-series
discovery, sections) lives in ``dashboard.page_view``.
"""

from dashboard.page_view import render_labor_page

render_labor_page()
