"""Trade and energy dashboard page.

The page's file name keeps its pre-split spelling (it is only a routing handle;
the sidebar label comes from the string catalog), but its composition is
``trade`` + ``energy`` only -- the ``welfare`` domain and every HBSIR caveat live
on the Welfare & Survey page. The title comes from the string catalog under the
same key as the sidebar label.
"""

from dashboard.i18n import t
from dashboard.page_view import render_domain_page

render_domain_page(
    t("page.trade_energy"),
    ("trade", "energy"),
    "trade_energy",
)
