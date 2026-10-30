"""Write functions for inventory: warehouse stock adjustment and material restock."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.makgeolli.functions.write.common import invalid


async def adjust_warehouse_stock(context: EditContext, params: dict[str, Any]) -> None:
    stock = await context.require(params["stock"])
    if stock.object_type != "WarehouseStock":
        raise invalid("stock", "창고 재고를 찾을 수 없습니다.")

    delta = int(params["delta"])
    updated_on = dt.date.today()
    new_quantity = int(stock.properties["quantity"]) + delta
    if new_quantity < 0:
        raise invalid("delta", f"재고는 음수가 될 수 없습니다 (조정 후 {new_quantity}).")

    await context.modify(
        stock.rid,
        {"quantity": new_quantity, "updatedOn": updated_on.isoformat()},
    )
    context.scratch["quantity"] = new_quantity


async def restock_material(context: EditContext, params: dict[str, Any]) -> None:
    material = await context.require(params["material"])
    if material.object_type != "RawMaterial":
        raise invalid("material", "원자재를 찾을 수 없습니다.")

    amount = float(params["amount"])
    if amount <= 0:
        raise invalid("amount", "입고량은 0보다 커야 합니다.")

    current = float(material.properties["currentStock"])
    await context.modify(material.rid, {"currentStock": current + amount})
    context.scratch["currentStock"] = current + amount
