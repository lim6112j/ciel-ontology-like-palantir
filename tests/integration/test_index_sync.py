"""Index sync creates declared indexes, is idempotent, and drops stale ones."""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.index_sync import IndexSync


async def _index_names(session: AsyncSession) -> set[str]:
    rows = await session.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'objects'")
    )
    return {row[0] for row in rows}


def test_index_expressions_use_declared_casts(demo_registry: SchemaRegistry) -> None:
    specs = {spec.name: spec for spec in demo_registry.indexes()}
    status = specs["ix_ont_outlet_status"]
    assert status.expressions == ("((properties->>'status')::text)",)
    weekday = specs["ix_ont_outlet_deliveryweekday"]
    assert weekday.expressions == ("((properties->>'deliveryWeekday')::integer)",)
    assert "object_type = 'Outlet'" in status.ddl()
    assert "deleted_at IS NULL" in status.ddl()


async def test_sync_creates_indexes(demo_registry: SchemaRegistry, session: AsyncSession) -> None:
    sync = IndexSync(demo_registry, session)
    result = await sync.sync()
    assert "ix_ont_outlet_status" in result.created
    assert await _index_names(session) >= {
        "ix_ont_outlet_status",
        "ix_ont_outlet_deliveryweekday",
        "ix_ont_order_totalamount",
        "ix_ont_order_status",
    }


async def test_sync_is_idempotent(demo_registry: SchemaRegistry, session: AsyncSession) -> None:
    sync = IndexSync(demo_registry, session)
    await sync.sync()
    second = await sync.sync()
    assert second.created == []
    assert second.dropped == []


async def test_sync_drops_stale_indexes(
    demo_registry: SchemaRegistry, session: AsyncSession, demo_schema: Path
) -> None:
    sync = IndexSync(demo_registry, session)
    await sync.sync()
    assert "ix_ont_order_status" in await _index_names(session)

    outlet_file = demo_schema / "object_types" / "Order.yaml"
    payload = yaml.safe_load(outlet_file.read_text(encoding="utf-8"))
    del payload["properties"]["status"]["indexed"]
    outlet_file.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

    shrunk = SchemaRegistry.from_directory(demo_schema)
    result = await IndexSync(shrunk, session).sync()
    assert "ix_ont_order_status" in result.dropped
    assert "ix_ont_order_status" not in await _index_names(session)
