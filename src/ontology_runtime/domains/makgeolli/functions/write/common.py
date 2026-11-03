"""Shared helpers for makgeolli write functions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed

#: Canonical owning team per object type: (ownership link type, 팀 구분).
#: A new object is linked to the team that runs that kind of work.
TEAM_OWNERSHIP: dict[str, tuple[str, str]] = {
    "Batch": ("teamBatches", "양조"),
    "Tank": ("teamTanks", "양조"),
    "TempReading": ("teamTempReadings", "품질"),
    "WasteRecord": ("teamWaste", "품질"),
    "WarehouseStock": ("teamWarehouseStock", "포장"),
    "Shipment": ("teamShipments", "물류"),
    "SalesOrder": ("teamOrders", "영업"),
    "Customer": ("teamCustomers", "영업"),
    "RawMaterial": ("teamMaterials", "자재"),
}


def invalid(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


async def assign_owning_team(context: EditContext, rid: str) -> None:
    """Link an object to its canonical owning team, when that team exists."""
    obj = await context.require(rid)
    ownership = TEAM_OWNERSHIP.get(obj.object_type)
    if ownership is None:
        return
    link_type, kind = ownership
    team = await _team_of_kind(context, kind)
    if team is None:
        return
    await context.modify(rid, {"teamRid": team.rid})
    context.link(link_type, team.rid, rid)


async def _team_of_kind(context: EditContext, kind: str) -> Any | None:
    """The active team of a kind, picked by teamNo so the choice is stable."""
    teams = [
        team
        for team in await context.search("Team")
        if team.properties.get("kind") == kind and team.properties.get("status") != "inactive"
    ]
    if not teams:
        return None
    return min(teams, key=lambda team: str(team.properties.get("teamNo") or ""))


async def next_no(context: EditContext, object_type: str, prefix: str) -> str:
    """Deterministic sequential document number, e.g. ``BATCH-00007``."""
    existing = await context.search(object_type)
    return f"{prefix}-{len(existing) + 1:05d}"


def as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value:
        return dt.date.fromisoformat(value)
    return None


async def find_warehouse_stock(context: EditContext, batch_rid: str) -> Any | None:
    for stock in await context.search("WarehouseStock"):
        if stock.properties.get("batchRid") == batch_rid:
            return stock
    return None


async def bump_warehouse_stock(
    context: EditContext,
    batch: Any,
    delta: int,
    on_date: dt.date,
) -> None:
    """Add `delta` to the batch's warehouse stock row, creating it if needed."""
    product_rid = str(batch.properties["productRid"])
    stock = await find_warehouse_stock(context, batch.rid)
    if stock is not None:
        await context.modify(
            stock.rid,
            {
                "quantity": max(0, int(stock.properties["quantity"]) + delta),
                "updatedOn": on_date.isoformat(),
            },
        )
        return
    if delta <= 0:
        return
    stock_no = await next_no(context, "WarehouseStock", "WSTK")
    stock_rid = context.create(
        "WarehouseStock",
        {
            "stockNo": stock_no,
            "batchRid": batch.rid,
            "productRid": product_rid,
            "quantity": delta,
            "updatedOn": on_date.isoformat(),
        },
    )
    context.link("batchWarehouseStock", batch.rid, stock_rid)
    context.link("productWarehouseStock", product_rid, stock_rid)
    await assign_owning_team(context, stock_rid)


async def bump_outlet_stock(
    context: EditContext,
    customer_rid: str,
    product_rid: str,
    delta: int,
    on_date: dt.date,
) -> None:
    """Add `delta` to the customer's stock for the product, creating the row if needed."""
    for stock in await context.search("OutletStock"):
        if (
            stock.properties.get("customerRid") == customer_rid
            and stock.properties.get("productRid") == product_rid
        ):
            await context.modify(
                stock.rid,
                {
                    "quantity": max(0, int(stock.properties["quantity"]) + delta),
                    "updatedOn": on_date.isoformat(),
                },
            )
            return
    if delta <= 0:
        return
    stock_no = await next_no(context, "OutletStock", "OSTK")
    stock_rid = context.create(
        "OutletStock",
        {
            "stockNo": stock_no,
            "customerRid": customer_rid,
            "productRid": product_rid,
            "quantity": delta,
            "updatedOn": on_date.isoformat(),
        },
    )
    context.link("customerOutletStock", customer_rid, stock_rid)
    context.link("productOutletStock", product_rid, stock_rid)
