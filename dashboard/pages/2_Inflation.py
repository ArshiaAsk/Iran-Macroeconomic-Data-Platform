"""Inflation dashboard page."""

from dashboard.page_view import render_domain_page

render_domain_page(
    "Inflation",
    ("inflation",),
    "inflation",
    default_indicators=["FP.CPI.TOTL.ZG"],
)
