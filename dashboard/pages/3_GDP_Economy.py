"""GDP and economy dashboard page."""

from dashboard.page_view import render_domain_page

render_domain_page(
    "GDP & Economy",
    ("gdp", "economy"),
    "gdp_economy",
    default_indicators=["NY.GDP.MKTP.CD"],
)
