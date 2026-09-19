"""Inflation dashboard page.

The page is a thin delegate: the composition (CPI decile and canonical views
plus the generic domain composition) lives in ``dashboard.page_view``.
"""

from dashboard.page_view import render_inflation_page

render_inflation_page()
