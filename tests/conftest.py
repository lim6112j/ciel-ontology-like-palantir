"""Shared pytest fixtures.

Integration tests need a live PostgreSQL (see `docker compose up -d db`).
Set `ONTOLOGY_TEST_DATABASE_URL` to override the default local URL.
"""

from __future__ import annotations

import os

import asyncpg
import pytest
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "ONTOLOGY_TEST_DATABASE_URL",
    "postgresql+asyncpg://ontology:ontology@localhost:55432/ontology_test",
)

#: Migration tests need their own database because they downgrade to base.
MIGRATION_DATABASE_URL = os.environ.get(
    "ONTOLOGY_MIGRATION_DATABASE_URL",
    "postgresql+asyncpg://ontology:ontology@localhost:55432/ontology_migrations",
)

#: API tests seed one database for the whole module.
API_DATABASE_URL = os.environ.get(
    "ONTOLOGY_API_DATABASE_URL",
    "postgresql+asyncpg://ontology:ontology@localhost:55432/ontology_api",
)


@pytest.fixture(scope="session")
def api_database_url() -> str:
    _ensure_database_sync(API_DATABASE_URL)
    return API_DATABASE_URL


def _ensure_database_sync(url: str) -> None:
    """Create the database if missing, using a sync driver (safe inside any loop)."""
    import psycopg
    from psycopg import sql

    parsed = make_url(url)
    with (
        psycopg.connect(
            host=parsed.host,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            dbname="postgres",
            autocommit=True,
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (parsed.database,))
        if cursor.fetchone() is None:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(parsed.database)))


async def _ensure_database(url: str) -> None:
    """Create the target database if it does not exist yet."""
    parsed = make_url(url)
    connection = await asyncpg.connect(
        host=parsed.host,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", parsed.database
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def database_url() -> str:
    _ensure_database_sync(TEST_DATABASE_URL)
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def migration_database_url() -> str:
    _ensure_database_sync(MIGRATION_DATABASE_URL)
    return MIGRATION_DATABASE_URL
