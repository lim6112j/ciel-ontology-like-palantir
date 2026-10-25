"""Migration round-trip against the test database."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from ontology_runtime.config import PROJECT_ROOT

EXPECTED_TABLES = {
    "action_edits",
    "action_runs",
    "agent_runs",
    "links",
    "objects",
    "ontology_indexes",
}


def _sync_url(config: Config) -> str:
    url = make_url(config.get_main_option("sqlalchemy.url"))
    return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def _engine(config: Config):
    return create_engine(_sync_url(config))


def _tables(config: Config) -> set[str]:
    engine = _engine(config)
    with engine.connect() as connection:
        names = set(inspect(connection).get_table_names())
    engine.dispose()
    return names


@pytest.fixture(scope="module")
def isolated_config(migration_database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", migration_database_url)
    return config


def test_upgrade_creates_all_tables(isolated_config: Config) -> None:
    command.downgrade(isolated_config, "base")
    command.upgrade(isolated_config, "head")
    try:
        assert _tables(isolated_config) >= EXPECTED_TABLES

        engine = _engine(isolated_config)
        with (
            engine.begin() as connection,
            pytest.raises(Exception, match="objects_properties_is_object"),
        ):
            connection.execute(
                text(
                    "INSERT INTO objects (rid, object_type, properties) "
                    "VALUES ('ri.test.object.bad', 'Outlet', '[]'::jsonb)"
                )
            )
        engine.dispose()
    finally:
        command.upgrade(isolated_config, "head")


def test_downgrade_removes_core_tables(isolated_config: Config) -> None:
    command.downgrade(isolated_config, "base")
    try:
        assert not EXPECTED_TABLES & _tables(isolated_config)
    finally:
        command.upgrade(isolated_config, "head")
