"""Write functions for shipping baked batches to stores."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.bakery.functions.write.common import (
    as_date,
    bump_stock,
    invalid,
    next_no,
)

SHIPMENT_PREFIX = "SHP"


async def ship_batch(context: EditContext, params: dict[str, Any]) -> None:
    batch = await context.require(params["batch"])
    if batch.object_type != "Batch":
        raise invalid("batch", "배치를 찾을 수 없습니다.")
    if batch.properties.get("status") != "baked":
        status = batch.properties.get("status")
        raise invalid(
            "batch", f"{status} 상태의 배치는 출하할 수 없습니다. 구운 배치만 출하됩니다."
        )

    store = await context.require(params["store"])
    if store.object_type != "Store":
        raise invalid("store", "매장을 찾을 수 없습니다.")
    if store.properties.get("status") == "closed":
        raise invalid("store", "휴업 중인 매장으로는 출하할 수 없습니다.")

    batch_quantity = int(batch.properties.get("quantity") or 0)
    quantity = int(params["quantity"]) if params.get("quantity") is not None else batch_quantity
    if quantity <= 0:
        raise invalid("quantity", "출하수량은 1 이상이어야 합니다.")
    if quantity > batch_quantity:
        raise invalid("quantity", f"배치 수량({batch_quantity})을 초과할 수 없습니다.")

    ship_date = as_date(params.get("shipDate")) or dt.date.today()
    shipment_no = await next_no(context, "Shipment", SHIPMENT_PREFIX)
    shipment_rid = context.create(
        "Shipment",
        {
            "shipmentNo": shipment_no,
            "shipDate": ship_date.isoformat(),
            "batchRid": batch.rid,
            "storeRid": store.rid,
            "quantity": quantity,
            "status": "in_transit",
        },
    )
    context.link("batchShipments", batch.rid, shipment_rid)
    context.link("storeShipments", store.rid, shipment_rid)

    await bump_stock(context, store.rid, str(batch.properties["productRid"]), quantity, ship_date)

    if quantity == batch_quantity:
        await context.modify(batch.rid, {"status": "shipped"})


async def receive_shipment(context: EditContext, params: dict[str, Any]) -> None:
    shipment = await context.require(params["shipment"])
    if shipment.object_type != "Shipment":
        raise invalid("shipment", "출하를 찾을 수 없습니다.")
    if shipment.properties.get("status") != "in_transit":
        raise invalid(
            "shipment", f"{shipment.properties.get('status')} 상태의 출하는 입고할 수 없습니다."
        )

    received_on = as_date(params.get("receivedOn")) or dt.date.today()
    await context.modify(
        shipment.rid,
        {"status": "delivered", "deliveredOn": received_on.isoformat()},
    )
