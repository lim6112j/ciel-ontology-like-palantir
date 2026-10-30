"""Write functions for brewing: batch creation, fermentation/aging completion, waste."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.makgeolli.functions.write.common import (
    as_date,
    bump_warehouse_stock,
    invalid,
    next_no,
)

BATCH_PREFIX = "BATCH"


def _temp_in_range(temp: float, minimum: Any, maximum: Any) -> bool:
    return float(minimum) <= temp <= float(maximum)


async def _require_batch(context: EditContext, rid: Any) -> Any:
    batch = await context.require(rid)
    if batch.object_type != "Batch":
        raise invalid("batch", "배치를 찾을 수 없습니다.")
    return batch


def _resolve_target_temps(product: Any, params: dict[str, Any]) -> tuple[float, float]:
    """Target temps default to each product's recommended range floor."""
    fermentation_temp = float(
        params.get("fermentationTempC") or product.properties["fermentationTempMinC"]
    )
    if not _temp_in_range(
        fermentation_temp,
        product.properties["fermentationTempMinC"],
        product.properties["fermentationTempMaxC"],
    ):
        minimum = product.properties["fermentationTempMinC"]
        maximum = product.properties["fermentationTempMaxC"]
        raise invalid(
            "fermentationTempC",
            f"발효 목표온도는 제품 권장 범위 ({minimum}~{maximum}°C) 안이어야 합니다.",
        )
    aging_temp = float(params.get("agingTempC") or product.properties["agingTempMinC"])
    if not _temp_in_range(
        aging_temp,
        product.properties["agingTempMinC"],
        product.properties["agingTempMaxC"],
    ):
        minimum = product.properties["agingTempMinC"]
        maximum = product.properties["agingTempMaxC"]
        raise invalid(
            "agingTempC",
            f"숙성 목표온도는 제품 권장 범위 ({minimum}~{maximum}°C) 안이어야 합니다.",
        )
    return fermentation_temp, aging_temp


def _check_tank(tank: Any, volume_l: float, fermentation_temp: float) -> None:
    if tank.properties.get("status") != "idle":
        raise invalid("tank", "사용 중이거나 정비 중인 탱크입니다.")
    capacity = float(tank.properties["capacityL"])
    if volume_l > capacity:
        raise invalid("tank", f"탱크 용량({capacity}L)을 초과할 수 없습니다.")
    if not _temp_in_range(
        fermentation_temp, tank.properties["tempMinC"], tank.properties["tempMaxC"]
    ):
        minimum = tank.properties["tempMinC"]
        maximum = tank.properties["tempMaxC"]
        raise invalid(
            "tank",
            f"탱크 조절범위({minimum}~{maximum}°C)에서 "
            f"발효 목표온도 {fermentation_temp}°C를 유지할 수 없습니다.",
        )


async def _link_materials(context: EditContext, batch_rid: str, entries: list[Any]) -> None:
    for entry in entries:
        material = await context.require(entry["materialRid"])
        if material.object_type != "RawMaterial":
            raise invalid("materials", "원자재를 찾을 수 없습니다.")
        amount = float(entry["amount"])
        if amount <= 0:
            raise invalid("materials", "투입량은 0보다 커야 합니다.")
        if amount > float(material.properties["currentStock"]):
            raise invalid(
                "materials",
                f"{material.properties['name']} 재고({material.properties['currentStock']}"
                f"{material.properties['unit']})를 초과했습니다.",
            )
        context.link("recipeMaterials", batch_rid, material.rid)


async def create_batch(context: EditContext, params: dict[str, Any]) -> None:
    product = await context.require(params["product"])
    if product.object_type != "Product":
        raise invalid("product", "제품을 찾을 수 없습니다.")
    if product.properties.get("active") is False:
        raise invalid("product", "판매 중지된 제품입니다.")

    volume_l = float(params["volumeL"])
    if volume_l <= 0:
        raise invalid("volumeL", "양조량은 0보다 커야 합니다.")

    brew_date = as_date(params.get("brewDate")) or dt.date.today()
    fermentation_days = int(product.properties["fermentationDays"])
    aging_days = int(product.properties["agingDays"])
    fermentation_due = brew_date + dt.timedelta(days=fermentation_days)
    aging_due = fermentation_due + dt.timedelta(days=aging_days)
    fermentation_temp, aging_temp = _resolve_target_temps(product, params)

    tank = None
    tank_rid = params.get("tank")
    if tank_rid:
        tank = await context.require(tank_rid)
        if tank.object_type != "Tank":
            raise invalid("tank", "탱크를 찾을 수 없습니다.")
        _check_tank(tank, volume_l, fermentation_temp)

    properties: dict[str, Any] = {
        "productRid": product.rid,
        "brewDate": brew_date.isoformat(),
        "fermentationDueOn": fermentation_due.isoformat(),
        "agingDueOn": aging_due.isoformat(),
        "fermentationTempC": fermentation_temp,
        "agingTempC": aging_temp,
        "volumeL": volume_l,
        "status": "fermenting",
    }
    if tank is not None:
        properties["tankRid"] = tank.rid

    batch_no = await next_no(context, "Batch", BATCH_PREFIX)
    batch_rid = context.create("Batch", {"batchNo": batch_no, **properties})
    context.link("productBatches", product.rid, batch_rid)
    if tank is not None:
        context.link("tankBatches", tank.rid, batch_rid)
        await context.modify(tank.rid, {"status": "in_use"})

    await _link_materials(context, batch_rid, params.get("materials") or [])
    context.scratch["batchId"] = batch_rid


async def complete_fermentation(context: EditContext, params: dict[str, Any]) -> None:
    batch = await _require_batch(context, params["batch"])
    if batch.properties.get("status") != "fermenting":
        status = batch.properties.get("status")
        raise invalid("batch", f"{status} 상태의 배치는 발효 완료 처리할 수 없습니다.")

    fermented_on = as_date(params.get("fermentedOn")) or dt.date.today()
    await context.modify(batch.rid, {"status": "aging", "fermentedOn": fermented_on.isoformat()})


async def complete_aging(context: EditContext, params: dict[str, Any]) -> None:
    batch = await _require_batch(context, params["batch"])
    if batch.properties.get("status") != "aging":
        status = batch.properties.get("status")
        raise invalid("batch", f"{status} 상태의 배치는 병입할 수 없습니다.")

    product = await context.require(batch.properties["productRid"])
    bottled_on = as_date(params.get("bottledOn")) or dt.date.today()
    shelf_life = int(product.properties["shelfLifeDays"])
    expires_on = bottled_on + dt.timedelta(days=shelf_life)

    volume_l = float(batch.properties["volumeL"])
    volume_ml = int(product.properties["volumeMl"])
    default_qty = int(volume_l * 1000 / volume_ml)
    bottled_qty = int(params["bottledQty"]) if params.get("bottledQty") is not None else default_qty
    if bottled_qty <= 0:
        raise invalid("bottledQty", "병입수량은 1 이상이어야 합니다.")

    await context.modify(
        batch.rid,
        {
            "status": "ready",
            "bottledOn": bottled_on.isoformat(),
            "expiresOn": expires_on.isoformat(),
            "bottledQty": bottled_qty,
        },
    )
    await bump_warehouse_stock(context, batch, bottled_qty, bottled_on)

    tank_rid = batch.properties.get("tankRid")
    if tank_rid:
        tank = await context.get(str(tank_rid))
        if tank is not None and tank.properties.get("status") == "in_use":
            await context.modify(tank.rid, {"status": "cleaning"})


async def waste_batch(context: EditContext, params: dict[str, Any]) -> None:
    batch = await _require_batch(context, params["batch"])
    status = batch.properties.get("status")
    if status not in {"fermenting", "aging", "ready"}:
        raise invalid("batch", f"{status} 상태의 배치는 폐기할 수 없습니다.")

    reason = params.get("reason")
    if reason not in {"quality", "expiry", "damage", "other"}:
        raise invalid("reason", "폐기 사유가 올바르지 않습니다.")

    wasted_on = as_date(params.get("wastedOn")) or dt.date.today()
    bottled_qty = int(batch.properties.get("bottledQty") or 0)
    quantity = int(params["quantity"]) if params.get("quantity") is not None else bottled_qty
    if quantity <= 0:
        raise invalid("quantity", "폐기수량은 1 이상이어야 합니다.")
    if bottled_qty and quantity > bottled_qty:
        raise invalid("quantity", f"병입수량({bottled_qty})을 초과할 수 없습니다.")

    record_no = await next_no(context, "WasteRecord", "WST")
    record_rid = context.create(
        "WasteRecord",
        {
            "wasteNo": record_no,
            "wastedOn": wasted_on.isoformat(),
            "batchRid": batch.rid,
            "quantity": quantity,
            "reason": reason,
        },
    )
    context.link("batchWaste", batch.rid, record_rid)

    if bottled_qty:
        await bump_warehouse_stock(context, batch, -quantity, wasted_on)

    if not bottled_qty or quantity == bottled_qty:
        await context.modify(batch.rid, {"status": "wasted"})
    else:
        await context.modify(batch.rid, {"bottledQty": bottled_qty - quantity})
