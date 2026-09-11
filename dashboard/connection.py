"""Streamlit-specific database connection management."""

from collections.abc import Generator
from contextlib import contextmanager

import streamlit as st

from dashboard.repository import DashboardRepository
from src.database.connection import DatabaseConnection
from src.utils.config import get_config


@st.cache_resource(show_spinner="Connecting to database...")
def get_connection() -> DatabaseConnection:
    """Create one cached database pool for the dashboard process."""
    return DatabaseConnection(database_url=get_config().database.url)


@contextmanager
def repository_session() -> Generator[DashboardRepository, None, None]:
    """Yield a repository bound to a request-scoped database session."""
    with get_connection().get_session() as session:
        yield DashboardRepository(session)
