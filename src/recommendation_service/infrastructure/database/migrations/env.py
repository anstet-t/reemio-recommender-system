"""Alembic environment configuration."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from recommendation_service.config import get_settings
from recommendation_service.infrastructure.database.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = Base.metadata

# Schema for recommendation tables
RECOMMENDER_SCHEMA = "recommender"


def get_url() -> str:
    """Get database URL from settings."""
    settings = get_settings()
    return settings.database_url_sync


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=RECOMMENDER_SCHEMA,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Create the recommender schema if it doesn't exist
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {RECOMMENDER_SCHEMA}"))
        connection.commit()

        # Try to create pgvector extension (may fail if not installed)
        try:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.commit()
        except Exception as e:
            connection.rollback()
            print(f"Note: pgvector extension not available, using JSON for embeddings.")
            print("Install pgvector for native vector search functionality.")

        # Create pg_trgm extension for fuzzy text search
        try:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            connection.commit()
        except Exception as e:
            connection.rollback()
            print(f"Note: pg_trgm extension not available: {e}")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=RECOMMENDER_SCHEMA,
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
