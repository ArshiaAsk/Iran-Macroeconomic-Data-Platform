"""Trade and energy dashboard page.

The page's file name keeps its pre-split spelling (it is only a routing handle;
the sidebar label comes from the navigation registry), but its composition is
``trade`` + ``energy`` only -- the ``welfare`` domain and every HBSIR caveat live
on the Welfare & Survey page.
"""

from dashboard.page_view import render_domain_page

render_domain_page(
    "Trade & Energy",
    ("trade", "energy"),
    "trade_energy",
)
