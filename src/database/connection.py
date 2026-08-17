"""
Database connection utilities.

Provides connection pooling and session management for PostgreSQL + TimescaleDB.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

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
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Register connection pool event listeners
        self._setup_event_listeners()

    def _setup_event_listeners(self) -> None:
        """Set up SQLAlchemy event listeners for connection pool."""

        # Registered on this engine's pool rather than the global Pool class, so
        # other engines in the process are unaffected.
        @event.listens_for(self.engine, "connect")
        def set_search_path(dbapi_conn: object, connection_record: object) -> None:  # noqa: ARG001 - signature required by SQLAlchemy
            """Set search path to include all schemas."""
            cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
            cursor.execute("SET search_path TO public, bronze, silver, gold, metadata")
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
                text(
                    """
                    SELECT create_hypertable(
                        'gold.gold_analytical',
                        'timestamp',
                        if_not_exists => TRUE,
                        migrate_data => TRUE,
                        chunk_time_interval => INTERVAL '1 month'
                    );
                    """
                )
            )

            # Compression must be enabled on the hypertable before a retention
            # policy can reference it.
            session.execute(
                text(
                    """
                    ALTER TABLE gold.gold_analytical
                    SET (timescaledb.compress,
                         timescaledb.compress_segmentby = 'indicator_id');
                    """
                )
            )

            # Compress chunks older than 6 months
            session.execute(
                text(
                    """
                    SELECT add_compression_policy(
                        'gold.gold_analytical',
                        INTERVAL '6 months',
                        if_not_exists => TRUE
                    );
                    """
                )
            )

    def test_connection(self) -> bool:
        """
        Test database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return False
        return True

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
    global _db_connection  # noqa: PLW0603 - module-level singleton by design
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
        msg = "Database not initialized. Call init_database() first."
        raise RuntimeError(msg)
    return _db_connection
