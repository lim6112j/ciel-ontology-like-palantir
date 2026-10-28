"""The bakery domain runs end to end on the same runtime as liquor.

Uses its own database so the two domains never share rows — the same isolation
guarantee the per-instance deployment relies on.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.bakery.seed.generator import SeedGenerator
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime

TODAY = dt.date(2026, 10, 25)


@pytest.fixture
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("bakery")


@pytest.fixture
def runtime(registry: SchemaRegistry, session: AsyncSession) -> Runtime:
    return Runtime(registry, session)


async def test_seed_creates_batches_and_links(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    generator = SeedGenerator(registry, session, seed=42, today=TODAY)
    await generator.reset()
    summary = await generator.run()
    await session.commit()

    assert summary.products == 5
    assert summary.stores == 4
    assert summary.batches == 5

    page = await Runtime(registry, session).sets.search("Batch", page_size=10)
    assert page.total == 5


async def test_record_batch_action_computes_expiry(runtime: Runtime) -> None:
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "B0001",
            "name": "우유식빵",
            "category": "식빵",
            "shelfLifeDays": 5,
            "unitPrice": 3500,
            "active": True,
        },
    )
    produced_on = "2026-10-25"

    result = await runtime.apply(
        "RecordBatch",
        {"product": product.rid, "quantity": 12, "producedOn": produced_on},
        actor="tester",
    )
    assert result.status == "succeeded"

    batches = await runtime.sets.search("Batch", page_size=10)
    batch = batches.objects[0]
    assert batch.properties["expiresOn"] == "2026-10-30"
    assert batch.properties["quantity"] == 12
    assert batch.properties["status"] == "planned"


async def test_expiring_function_returns_only_live_batches(runtime: Runtime) -> None:
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "B0002",
            "name": "크루아상",
            "category": "페이스트리",
            "shelfLifeDays": 2,
            "unitPrice": 2800,
            "active": True,
        },
    )
    today = dt.date.today()
    await runtime.apply(
        "RecordBatch",
        {"product": product.rid, "quantity": 6, "producedOn": today.isoformat()},
        actor="tester",
    )

    result = await runtime.run_function("expiringBatches", {"withinDays": 3})
    assert result["count"] == 1
    assert result["batches"][0]["quantity"] == 6


async def test_bakery_rejects_liquor_object_types(runtime: Runtime) -> None:
    from ontology_runtime.errors import ObjectTypeNotFound

    with pytest.raises(ObjectTypeNotFound):
        await runtime.sets.search("SalesOrder")
