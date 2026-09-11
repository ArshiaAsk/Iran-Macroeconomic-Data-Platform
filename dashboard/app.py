"""Streamlit entry point for the Iran Macroeconomic Data Platform."""

import streamlit as st

from dashboard.connection import get_connection


def main() -> None:
    """Configure and render the dashboard shell."""
    st.set_page_config(
        page_title="Iran Macroeconomic Data Platform",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("Iran Macroeconomic Data Platform")
    st.markdown("Explore validated, chain-linked Gold-layer time series without writing SQL.")
    connection = get_connection()
    if connection.test_connection():
        st.success("Database connected")
    else:
        st.error("Database unavailable. Start PostgreSQL with `make db-up` and run migrations.")
    st.markdown(
        "Use the sidebar to open the overview, domain pages, correlation analysis, and data catalog."
    )


if __name__ == "__main__":
    main()
