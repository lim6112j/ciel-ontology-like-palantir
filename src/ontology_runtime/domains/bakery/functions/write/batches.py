"""Write function: create a production batch and link it to its product/store."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed

BATCH_PREFIX = "B"


def _invalid(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


async def record_batch(context: EditContext, params: dict[str, Any]) -> None:
    product_rid = params.get("product")
    if not product_rid:
        raise _invalid("product", "제품이 필요합니다.")

    product = await context.get(str(product_rid))
    if product is None or product.object_type != "Product":
        raise _invalid("product", "제품을 찾을 수 없습니다.")
    if product.properties.get("active") is False:
        raise _invalid("product", "판매 중지된 제품입니다.")

    quantity = int(params.get("quantity") or 0)
    if quantity <= 0:
        raise _invalid("quantity", "수량은 1 이상이어야 합니다.")

    produced_on = _as_date(params.get("producedOn")) or dt.date.today()
    shelf_life = int(product.properties.get("shelfLifeDays") or 1)
    expires_on = produced_on + dt.timedelta(days=shelf_life)

    batch_no = await _next_batch_no(context)
    batch_rid = context.create(
        "Batch",
        {
            "batchNo": batch_no,
            "productRid": product.rid,
            "producedOn": produced_on.isoformat(),
            "expiresOn": expires_on.isoformat(),
            "quantity": quantity,
            "status": "planned",
        },
    )
    context.link("productBatches", product.rid, batch_rid)

    store_rid = params.get("store")
    if store_rid:
        store = await context.get(str(store_rid))
        if store is None or store.object_type != "Store":
            raise _invalid("store", "매장을 찾을 수 없습니다.")
        context.link("storeBatches", store.rid, batch_rid)


async def _next_batch_no(context: EditContext) -> str:
    existing = await context.search("Batch")
    return f"{BATCH_PREFIX}-{len(existing) + 1:05d}"


def _as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value:
        return dt.date.fromisoformat(value)
    return None
