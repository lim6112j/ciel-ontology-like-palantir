"""Shared helpers for bakery write functions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed


def invalid(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


async def next_no(context: EditContext, object_type: str, prefix: str) -> str:
    """Deterministic sequential document number, e.g. ``SHP-00007``."""
    existing = await context.search(object_type)
    return f"{prefix}-{len(existing) + 1:05d}"


def as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value:
        return dt.date.fromisoformat(value)
    return None


async def find_stock(context: EditContext, store_rid: str, product_rid: str) -> Any | None:
    for stock in await context.search("StoreStock"):
        if (
            stock.properties.get("storeRid") == store_rid
            and stock.properties.get("productRid") == product_rid
        ):
            return stock
    return None


async def bump_stock(
    context: EditContext,
    store_rid: str,
    product_rid: str,
    delta: int,
    on_date: dt.date,
) -> None:
    """Add `delta` to the store's stock for the product, creating the row if needed."""
    stock = await find_stock(context, store_rid, product_rid)
    if stock is not None:
        await context.modify(
            stock.rid,
            {
                "quantity": int(stock.properties["quantity"]) + delta,
                "updatedOn": on_date.isoformat(),
            },
        )
        return

    if delta == 0:
        return
    stock_no = await next_no(context, "StoreStock", "STK")
    stock_rid = context.create(
        "StoreStock",
        {
            "stockNo": stock_no,
            "storeRid": store_rid,
            "productRid": product_rid,
            "quantity": delta,
            "updatedOn": on_date.isoformat(),
        },
    )
    context.link("storeStocks", store_rid, stock_rid)
    context.link("productStocks", product_rid, stock_rid)
