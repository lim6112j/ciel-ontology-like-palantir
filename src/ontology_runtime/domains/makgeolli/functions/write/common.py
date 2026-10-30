"""Shared helpers for makgeolli write functions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed


def invalid(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


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
