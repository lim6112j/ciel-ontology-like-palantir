"""Integration fixtures: a migrated test database plus small schemas."""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import yaml
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


PHONE_BOOK_SCHEMA = {
    "object_types/Outlet.yaml": {
        "apiName": "Outlet",
        "displayName": "거래처",
        "primaryKey": "name",
        "properties": {
            "name": {"apiName": "name", "type": "string", "required": True},
            "outletType": {
                "apiName": "outletType",
                "type": "enum",
                "values": ["소매점", "음식점"],
                "required": True,
            },
            "status": {
                "apiName": "status",
                "type": "enum",
                "values": ["active", "closed"],
                "required": True,
                "indexed": True,
                "defaultValue": "active",
            },
            "deliveryWeekday": {"apiName": "deliveryWeekday", "type": "integer", "indexed": True},
        },
        "stateMachine": {
            "property": "status",
            "initial": "active",
            "transitions": [
                {"from": "active", "to": "closed"},
                {"from": "closed", "to": "active"},
            ],
        },
    },
    "object_types/Order.yaml": {
        "apiName": "Order",
        "displayName": "발주",
        "primaryKey": "orderNo",
        "properties": {
            "orderNo": {"apiName": "orderNo", "type": "string", "required": True},
            "outletRid": {"apiName": "outletRid", "type": "objectRef", "objectType": "Outlet"},
            "totalAmount": {"apiName": "totalAmount", "type": "integer", "indexed": True},
            "status": {
                "apiName": "status",
                "type": "enum",
                "values": ["draft", "submitted"],
                "required": True,
                "indexed": True,
                "defaultValue": "draft",
            },
        },
    },
    "link_types.yaml": {
        "linkTypes": [
            {
                "apiName": "orders",
                "displayName": "발주",
                "fromObjectType": "Outlet",
                "fromApiName": "orders",
                "fromCardinality": "many",
                "toObjectType": "Order",
                "toApiName": "outlet",
                "toCardinality": "one",
            }
        ]
    },
}


@pytest.fixture
def demo_schema(tmp_path: Path) -> Path:
    root = tmp_path / "schema"
    for relative, payload in PHONE_BOOK_SCHEMA.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return root


@pytest.fixture
def demo_registry(demo_schema: Path) -> SchemaRegistry:
    return SchemaRegistry.from_directory(demo_schema)


def _today() -> str:
    return dt.date.today().isoformat()
