"""GDP dashboard page.

The page owns only the ``gdp`` domain: ``economy`` is a dead domain (no source
emits it) and is deliberately not claimed. The title key is the same one the
sidebar label uses, and ``render_domain_page`` resolves it through the shared
page header, so the two cannot drift.
"""

from dashboard.page_view import render_domain_page

render_domain_page(
    "page.gdp",
    ("gdp",),
    "gdp_economy",
    default_indicators=["NY.GDP.MKTP.CD"],
)
