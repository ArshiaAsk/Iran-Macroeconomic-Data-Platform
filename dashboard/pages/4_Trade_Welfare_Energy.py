"""Trade, welfare, and energy dashboard page."""

from dashboard.page_view import render_domain_page

render_domain_page(
    "Trade, Welfare & Energy",
    ("trade", "welfare", "energy"),
    "trade_welfare_energy",
)
