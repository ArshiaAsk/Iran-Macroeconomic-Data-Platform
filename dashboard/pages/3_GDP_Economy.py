"""GDP dashboard page.

The page owns only the ``gdp`` domain: ``economy`` is a dead domain (no source
emits it) and is deliberately not claimed. The title comes from the string
catalog under the same key as the sidebar label.
"""

from dashboard.i18n import t
from dashboard.page_view import render_domain_page

render_domain_page(
    t("page.gdp"),
    ("gdp",),
    "gdp_economy",
    default_indicators=["NY.GDP.MKTP.CD"],
)
