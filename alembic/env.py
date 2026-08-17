"""Alembic environment configuration."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from src.database.schema import Base
from src.utils.config import get_config

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The database URL comes from the application config (.env) so migrations always
# target the same server as the app; alembic.ini only supplies the fallback.
config.set_main_option("sqlalchemy.url", get_config().database.url)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Only these schemas are owned by this project. Autogenerate must ignore
# everything else (public, and TimescaleDB's internal catalog schemas) or it
# would emit spurious drops.
MANAGED_SCHEMAS = {"bronze", "silver", "gold", "metadata"}

# create_hypertable() silently adds a DESC index on the partitioning column.
# It exists in the database but not in the model metadata, so autogenerate
# would try to drop it on every run.
TIMESCALE_MANAGED_INDEXES = {"gold_analytical_timestamp_idx"}


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    """Restrict autogenerate comparison to the project's own schemas."""
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    if type_ == "table":
        return parent_names.get("schema_name") in MANAGED_SCHEMAS
    return True


def include_object(
    object_: object,  # noqa: ARG001 - signature fixed by Alembic
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object,  # noqa: ARG001 - signature fixed by Alembic
) -> bool:
    """Ignore database objects that TimescaleDB manages on our behalf."""
    return not (type_ == "index" and reflected and name in TIMESCALE_MANAGED_INDEXES)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
