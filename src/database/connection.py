"""
Database connection utilities.

Provides connection pooling and session management for PostgreSQL + TimescaleDB.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool

from src.database.schema import Base


class DatabaseConnection:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str, echo: bool = False) -> None:
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection string
            echo: Whether to log SQL statements
        """
        self.database_url = database_url
        self.engine: Engine = create_engine(
            database_url,
            echo=echo,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Register connection pool event listeners
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners for connection pool."""

        @event.listens_for(Pool, "connect")
        def set_search_path(dbapi_conn: object, connection_record: object) -> None:
            """Set search path to include all schemas."""
            cursor = dbapi_conn.cursor()  # type: ignore
            cursor.execute(
                "SET search_path TO public, bronze, silver, gold, metadata"
            )
            cursor.close()

    def create_all_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

    def drop_all_tables(self) -> None:
        """Drop all database tables (use with caution!)."""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Yields:
            Database session

        Example:
            with db.get_session() as session:
                result = session.query(Model).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_hypertables(self) -> None:
        """
        Create TimescaleDB hypertables for time-series tables.

        Must be called after create_all_tables().
        """
        with self.get_session() as session:
            # Create hypertable for gold_analytical
            session.execute(
                """
                SELECT create_hypertable(
                    'gold.gold_analytical',
                    'timestamp',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 month'
                );
                """
            )

            # Optionally add compression policy for older data
            session.execute(
                """
                SELECT add_compression_policy(
                    'gold.gold_analytical',
                    INTERVAL '6 months',
                    if_not_exists => TRUE
                );
                """
            )

            session.commit()

    def test_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute("SELECT 1")  # type: ignore
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close all database connections."""
        self.engine.dispose()


# Global database connection instance (to be initialized by config)
_db_connection: DatabaseConnection | None = None


def init_database(database_url: str, echo: bool = False) -> DatabaseConnection:
    """
    Initialize global database connection.

    Args:
        database_url: PostgreSQL connection string
        echo: Whether to log SQL statements

    Returns:
        Database connection instance
    """
    global _db_connection
    _db_connection = DatabaseConnection(database_url=database_url, echo=echo)
    return _db_connection


def get_db() -> DatabaseConnection:
    """
    Get global database connection instance.

    Returns:
        Database connection instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_connection is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _db_connection
