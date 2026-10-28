"""Write functions for batch waste and manual store-stock adjustments."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.bakery.functions.write.common import (
    as_date,
    bump_stock,
    find_stock,
    invalid,
    next_no,
)

WASTE_PREFIX = "WST"
WASTABLE_STATUSES = {"planned", "baked"}


async def waste_batch(context: EditContext, params: dict[str, Any]) -> None:
    batch = await context.require(params["batch"])
    if batch.object_type != "Batch":
        raise invalid("batch", "배치를 찾을 수 없습니다.")
    status = batch.properties.get("status")
    if status not in WASTABLE_STATUSES:
        raise invalid("batch", f"{status} 상태의 배치는 폐기할 수 없습니다.")

    batch_quantity = int(batch.properties.get("quantity") or 0)
    quantity = int(params["quantity"]) if params.get("quantity") is not None else batch_quantity
    if quantity <= 0:
        raise invalid("quantity", "폐기수량은 1 이상이어야 합니다.")
    if quantity > batch_quantity:
        raise invalid("quantity", f"배치 수량({batch_quantity})을 초과할 수 없습니다.")

    wasted_on = as_date(params.get("wastedOn")) or dt.date.today()
    waste_no = await next_no(context, "WasteRecord", WASTE_PREFIX)
    record_rid = context.create(
        "WasteRecord",
        {
            "wasteNo": waste_no,
            "wastedOn": wasted_on.isoformat(),
            "batchRid": batch.rid,
            "quantity": quantity,
            "reason": params["reason"],
        },
    )
    context.link("batchWaste", batch.rid, record_rid)

    remaining = batch_quantity - quantity
    if remaining <= 0:
        await context.modify(batch.rid, {"status": "wasted"})
    else:
        await context.modify(batch.rid, {"quantity": remaining})


async def adjust_store_stock(context: EditContext, params: dict[str, Any]) -> None:
    store = await context.require(params["store"])
    if store.object_type != "Store":
        raise invalid("store", "매장을 찾을 수 없습니다.")
    product = await context.require(params["product"])
    if product.object_type != "Product":
        raise invalid("product", "제품을 찾을 수 없습니다.")

    delta = int(params["delta"])
    today = dt.date.today()
    stock = await find_stock(context, store.rid, product.rid)
    current = int(stock.properties["quantity"]) if stock is not None else 0
    if current + delta < 0:
        raise invalid("delta", f"재고({current})를 음수로 만들 수 없습니다.")

    if stock is not None:
        await context.modify(
            stock.rid, {"quantity": current + delta, "updatedOn": today.isoformat()}
        )
        return
    await bump_stock(context, store.rid, product.rid, delta, today)
