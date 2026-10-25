"""Alembic environment wired to the application's metadata."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from ontology_runtime.config import settings
from ontology_runtime.db.models import metadata

config = context.config
# Respect a URL supplied by the caller (tests point at their own database);
# only fall back to the application setting when none was configured.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_sync(url: str) -> None:
    """Synchronous path used when an event loop is already running (tests)."""
    from sqlalchemy import create_engine

    engine = create_engine(url)
    with engine.begin() as connection:
        _do_run_migrations(connection)
    engine.dispose()


def _run() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
        return
    url = config.get_main_option("sqlalchemy.url")
    if url.startswith("postgresql+asyncpg"):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(run_migrations_online())
            return
        run_migrations_sync(url.replace("+asyncpg", "+psycopg"))
        return
    run_migrations_sync(url)


_run()
