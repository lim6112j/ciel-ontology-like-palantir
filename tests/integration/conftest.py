"""Integration fixtures: a migrated test database plus small schemas."""

from __future__ import annotations

import datetime as dt
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ontology_runtime.config import PROJECT_ROOT
from ontology_runtime.registry import SchemaRegistry


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_schema(alembic_config: Config) -> None:
    """Ensure the shared test database is at head (never downgraded here)."""
    command.upgrade(alembic_config, "head")


TRUNCATE_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_objects_type_property "
    "ON objects (object_type, ((properties->>'_uid'))) WHERE properties ? '_uid';"
)


@pytest.fixture
async def session(database_url: str) -> AsyncIterator[AsyncSession]:
    """A clean session per test; tables are truncated before and after."""
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    truncate = (
        "TRUNCATE objects, links, action_runs, action_edits, agent_runs, ontology_indexes "
        "RESTART IDENTITY CASCADE"
    )
    async with factory() as session:
        await session.execute(text(truncate))
        await session.commit()
        yield session
        await session.rollback()
        await session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
        await session.execute(text(truncate))
        await session.commit()
    await engine.dispose()


#: A minimal, real-on-disk domain fixture. Copying it into `tmp_path` keeps the
#: loader's "manifest name must match directory" check honest while isolating
#: mutations between tests.
PHONE_BOOK_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "domains" / "phonebook"


@pytest.fixture
def demo_schema(tmp_path: Path) -> Path:
    root = tmp_path / "phonebook"
    shutil.copytree(PHONE_BOOK_FIXTURE, root)
    return root


@pytest.fixture
def demo_registry(demo_schema: Path) -> SchemaRegistry:
    """A manifest-less registry: these tests exercise the bare store/query layer."""
    return SchemaRegistry.from_directory(demo_schema)


def _today() -> str:
    return dt.date.today().isoformat()
