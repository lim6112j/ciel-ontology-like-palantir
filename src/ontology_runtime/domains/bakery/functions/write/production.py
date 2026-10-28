"""Write functions for product/store upserts and production plans."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.bakery.functions.write.common import (
    as_date,
    invalid,
    next_no,
)

PLAN_PREFIX = "PLAN"


async def upsert_product(context: EditContext, params: dict[str, Any]) -> None:
    sku = str(params["sku"]).strip()
    if not sku:
        raise invalid("sku", "SKU는 비어 있을 수 없습니다.")

    existing = [obj for obj in await context.search("Product") if obj.properties.get("sku") == sku]
    values: dict[str, Any] = {
        "sku": sku,
        "name": str(params["name"]).strip(),
        "category": params["category"],
        "shelfLifeDays": int(params["shelfLifeDays"]),
        "unitPrice": int(params["unitPrice"]),
    }
    if params.get("active") is not None:
        values["active"] = bool(params["active"])

    if existing:
        await context.modify(existing[0].rid, values)
    else:
        context.create("Product", {**values, "active": values.get("active", True)})


async def upsert_store(context: EditContext, params: dict[str, Any]) -> None:
    store_no = str(params["storeNo"]).strip()
    if not store_no:
        raise invalid("storeNo", "매장번호는 비어 있을 수 없습니다.")

    existing = [
        obj for obj in await context.search("Store") if obj.properties.get("storeNo") == store_no
    ]
    values: dict[str, Any] = {"storeNo": store_no, "name": str(params["name"]).strip()}
    opened_on = as_date(params.get("openedOn"))
    if opened_on:
        values["openedOn"] = opened_on.isoformat()

    if existing:
        await context.modify(existing[0].rid, values)
    else:
        values["status"] = "active"
        if "openedOn" not in values:
            values["openedOn"] = dt.date.today().isoformat()
        context.create("Store", values)


async def plan_production(context: EditContext, params: dict[str, Any]) -> None:
    product = await context.require(params["product"])
    if product.object_type != "Product":
        raise invalid("product", "제품을 찾을 수 없습니다.")
    if product.properties.get("active") is False:
        raise invalid("product", "판매 중지된 제품은 생산계획을 세울 수 없습니다.")

    planned_qty = int(params["plannedQty"])
    if planned_qty <= 0:
        raise invalid("plannedQty", "계획수량은 1 이상이어야 합니다.")

    plan_date = as_date(params.get("planDate")) or dt.date.today()
    plan_no = await next_no(context, "ProductionPlan", PLAN_PREFIX)
    values: dict[str, Any] = {
        "planNo": plan_no,
        "planDate": plan_date.isoformat(),
        "productRid": product.rid,
        "plannedQty": planned_qty,
        "producedQty": 0,
        "status": "planned",
    }
    if params.get("note"):
        values["note"] = str(params["note"])
    plan_rid = context.create("ProductionPlan", values)
    context.link("planProduct", plan_rid, product.rid)


async def complete_production_plan(context: EditContext, params: dict[str, Any]) -> None:
    plan = await context.require(params["plan"])
    if plan.object_type != "ProductionPlan":
        raise invalid("plan", "생산계획을 찾을 수 없습니다.")
    if plan.properties.get("status") != "in_progress":
        status = plan.properties.get("status")
        raise invalid("plan", f"{status} 상태의 계획은 완료할 수 없습니다. 먼저 생산을 시작하세요.")

    planned = int(plan.properties["plannedQty"])
    produced = int(params["producedQty"]) if params.get("producedQty") is not None else planned
    if produced <= 0:
        raise invalid("producedQty", "생산수량은 1 이상이어야 합니다.")

    plan_date = as_date(plan.properties.get("planDate")) or dt.date.today()
    product_rid = str(plan.properties["productRid"])
    product = await context.get(product_rid)
    if product is None:
        raise invalid("plan", "계획의 제품을 찾을 수 없습니다.")

    shelf_life = int(product.properties.get("shelfLifeDays") or 1)
    batch_no = await next_no(context, "Batch", "B")
    batch_rid = context.create(
        "Batch",
        {
            "batchNo": batch_no,
            "productRid": product_rid,
            "producedOn": plan_date.isoformat(),
            "expiresOn": (plan_date + dt.timedelta(days=shelf_life)).isoformat(),
            "quantity": produced,
            "status": "baked",
        },
    )
    context.link("planBatches", plan.rid, batch_rid)
    context.link("productBatches", product_rid, batch_rid)

    await context.modify(plan.rid, {"status": "completed", "producedQty": produced})
