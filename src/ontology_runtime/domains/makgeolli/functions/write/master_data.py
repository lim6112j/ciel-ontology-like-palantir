"""Write functions for master data: products and customers."""

from __future__ import annotations

from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.makgeolli.functions.write.common import invalid

MAX_SHELF_LIFE_DAYS = 30


async def upsert_product(context: EditContext, params: dict[str, Any]) -> None:
    sku = str(params.get("sku") or "")
    if not sku:
        raise invalid("sku", "SKU가 필요합니다.")

    required = ("name", "category", "fermentationDays", "agingDays", "volumeMl", "unitPrice")
    missing = [field for field in required if params.get(field) in (None, "")]
    if missing:
        raise invalid(", ".join(missing), "필수 값이 누락되었습니다.")

    shelf_life = int(params.get("shelfLifeDays") or 0)
    if not 1 <= shelf_life <= MAX_SHELF_LIFE_DAYS:
        raise invalid("shelfLifeDays", f"유통기한은 1~{MAX_SHELF_LIFE_DAYS}일이어야 합니다.")

    fermentation_min = float(params["fermentationTempMinC"])
    fermentation_max = float(params["fermentationTempMaxC"])
    if fermentation_min > fermentation_max:
        raise invalid("fermentationTempMaxC", "발효 권장 최저온도가 최고온도보다 클 수 없습니다.")
    aging_min = float(params["agingTempMinC"])
    aging_max = float(params["agingTempMaxC"])
    if aging_min > aging_max:
        raise invalid("agingTempMaxC", "숙성 권장 최저온도가 최고온도보다 클 수 없습니다.")

    properties: dict[str, Any] = {
        "name": params["name"],
        "category": params["category"],
        "alcoholPercent": float(params["alcoholPercent"]),
        "shelfLifeDays": shelf_life,
        "fermentationDays": int(params["fermentationDays"]),
        "agingDays": int(params["agingDays"]),
        "fermentationTempMinC": fermentation_min,
        "fermentationTempMaxC": fermentation_max,
        "agingTempMinC": aging_min,
        "agingTempMaxC": aging_max,
        "volumeMl": int(params["volumeMl"]),
        "unitPrice": int(params["unitPrice"]),
    }
    if params.get("active") is not None:
        properties["active"] = bool(params["active"])

    existing = [
        product
        for product in await context.search("Product")
        if product.properties.get("sku") == sku
    ]
    if existing:
        await context.modify(existing[0].rid, properties)
        context.scratch["productId"] = existing[0].rid
        context.scratch["created"] = False
        return

    product_rid = context.create("Product", {"sku": sku, **properties})
    context.scratch["productId"] = product_rid
    context.scratch["created"] = True


async def upsert_customer(context: EditContext, params: dict[str, Any]) -> None:
    customer_no = str(params.get("customerNo") or "")
    if not customer_no:
        raise invalid("customerNo", "판매처번호가 필요합니다.")
    if not params.get("name"):
        raise invalid("name", "명칭이 필요합니다.")

    properties: dict[str, Any] = {
        "name": params["name"],
        "type": params["type"],
    }
    if params.get("region"):
        properties["region"] = params["region"]

    existing = [
        customer
        for customer in await context.search("Customer")
        if customer.properties.get("customerNo") == customer_no
    ]
    if existing:
        await context.modify(existing[0].rid, properties)
        context.scratch["customerId"] = existing[0].rid
        context.scratch["created"] = False
        return

    customer_rid = context.create("Customer", {"customerNo": customer_no, **properties})
    context.scratch["customerId"] = customer_rid
    context.scratch["created"] = True
