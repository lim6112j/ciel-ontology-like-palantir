"""Seed generator: determinism, referential integrity, and plausible volumes."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.config import SCHEMA_DIR
from ontology_runtime.db.models import ActionEditRow, ActionRunRow, AgentRunRow, LinkRow, ObjectRow
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime
from ontology_runtime.seed.generator import SeedGenerator

TODAY = dt.date(2026, 10, 25)


@pytest.fixture
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_directory(SCHEMA_DIR)


@pytest.fixture
def generator(registry: SchemaRegistry, session: AsyncSession) -> SeedGenerator:
    return SeedGenerator(registry, session, seed=42, today=TODAY)


async def _counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(ObjectRow.object_type, func.count()).group_by(ObjectRow.object_type)
    )
    return {object_type: count for object_type, count in rows.all()}


async def test_seed_is_deterministic(registry: SchemaRegistry, session: AsyncSession) -> None:
    first = await SeedGenerator(registry, session, seed=7, today=TODAY).run()
    await session.execute(select(ObjectRow).where(ObjectRow.object_type == "nonexistent"))
    first_counts = await _counts(session)

    from sqlalchemy import text

    await session.execute(
        text(
            "TRUNCATE objects, links, action_runs, action_edits, agent_runs RESTART IDENTITY CASCADE"
        )
    )
    second = await SeedGenerator(registry, session, seed=7, today=TODAY).run()
    second_counts = await _counts(session)

    assert first.to_dict() == second.to_dict()
    assert first_counts == second_counts


async def test_seed_produces_expected_volumes(generator: SeedGenerator) -> None:
    summary = await generator.run().to_dict() if False else (await generator.run()).to_dict()
    assert summary["depots"] == 3
    assert summary["outlets"] == 120
    assert summary["products"] == 16
    assert summary["salesReps"] == 25
    assert summary["drivers"] == 30
    assert summary["vehicles"] == 20
    assert summary["routes"] == 18
    assert summary["orders"] > 200
    assert summary["deliveries"] > 10
    assert summary["stops"] > 200
    assert summary["invoices"] > 100


async def test_seed_has_no_dangling_links(generator: SeedGenerator, session: AsyncSession) -> None:
    await generator.run()
    orphanded = await session.scalar(
        text_select_orphans := select(func.count())
        .select_from(LinkRow)
        .where(
            ~LinkRow.from_rid.in_(select(ObjectRow.rid))
            | ~LinkRow.to_rid.in_(select(ObjectRow.rid))
        )
    )
    del text_select_orphans
    assert orphanded == 0


async def test_seed_clears_audit_tables(generator: SeedGenerator, session: AsyncSession) -> None:
    session.add(
        ActionRunRow(id=__import__("uuid").uuid4(), action_type="X", status="succeeded", params={})
    )
    await session.flush()
    await generator.reset()
    assert await session.scalar(select(func.count()).select_from(ActionRunRow)) == 0
    assert await session.scalar(select(func.count()).select_from(ActionEditRow)) == 0
    assert await session.scalar(select(func.count()).select_from(AgentRunRow)) == 0


async def test_seeded_order_status_follows_delivery_outcome(
    generator: SeedGenerator, registry: SchemaRegistry, session: AsyncSession
) -> None:
    await generator.run()
    runtime = Runtime(registry, session)

    orders = await runtime.search("SalesOrder", page_size=1000)
    assert orders.total > 0
    statuses = {order.properties["status"] for order in orders.objects}
    # Delivered orders are fulfilled; ones with a failed stop are partial.
    assert statuses <= {"confirmed", "fulfilled", "partially_fulfilled", "cancelled"}
    assert "fulfilled" in statuses

    # The trailing days are deliberately left unplanned for the demo, so the
    # seed must leave dispatchable work: confirmed orders with no stop yet.
    confirmed = [order for order in orders.objects if order.properties["status"] == "confirmed"]
    assert confirmed, "the demo window should contain unplanned orders"
    stops = await runtime.search("DeliveryStop", page_size=1000)
    linked_order_rids = {
        stop.properties.get("orderRid") for stop in stops.objects if stop.properties.get("orderRid")
    }
    assert not any(order.rid in linked_order_rids for order in confirmed)


async def test_seeded_invoices_match_order_totals(
    generator: SeedGenerator, registry: SchemaRegistry, session: AsyncSession
) -> None:
    await generator.run()
    runtime = Runtime(registry, session)
    invoices = await runtime.search("SalesInvoice", page_size=500)
    for invoice in invoices.objects[:25]:
        lines = await runtime.links.targets(registry.link_on("SalesInvoice", "lines"), invoice.rid)
        assert sum(int(line.properties["lineAmount"]) for line in lines) == int(
            invoice.properties["totalAmount"]
        )
