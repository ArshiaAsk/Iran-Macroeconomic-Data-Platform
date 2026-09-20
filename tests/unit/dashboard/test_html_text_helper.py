"""Unit test for the AppTest HTML-text helper (Task 16)."""

from streamlit.testing.v1 import AppTest

from tests.unit.dashboard.app_smoke import html_texts

PROBE_SCRIPT = """
import streamlit as st

from dashboard.components.html_table import Text, build_html_table

st.html(build_html_table(("منبع",), ((Text("SCI"),),)))
st.html("<p>second</p>")
"""


def test_html_texts_returns_each_st_html_body_in_order() -> None:
    app = AppTest.from_string(PROBE_SCRIPT)
    app.run()

    assert not app.exception
    bodies = html_texts(app)
    assert len(bodies) == 2
    assert '<div class="dt-wrap" dir="rtl">' in bodies[0]
    assert "SCI" in bodies[0]
    assert bodies[1] == "<p>second</p>"


def test_html_texts_is_empty_without_any_st_html() -> None:
    app = AppTest.from_string("import streamlit as st\n\nst.write('no html')\n")
    app.run()

    assert html_texts(app) == []
