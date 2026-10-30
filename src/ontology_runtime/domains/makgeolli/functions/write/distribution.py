"""Write functions for distribution: shipping batches and receiving shipments."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.makgeolli.functions.write.common import (
    as_date,
    bump_outlet_stock,
    bump_warehouse_stock,
    invalid,
    next_no,
)

SHIPMENT_PREFIX = "SHP"


async def ship_batch(context: EditContext, params: dict[str, Any]) -> None:
    batch = await context.require(params["batch"])
    if batch.object_type != "Batch":
        raise invalid("batch", "배치를 찾을 수 없습니다.")
    if batch.properties.get("status") != "ready":
        status = batch.properties.get("status")
        raise invalid(
            "batch",
            f"{status} 상태의 배치는 출하할 수 없습니다. 병입이 완료된 배치만 출하됩니다.",
        )

    customer = await context.require(params["customer"])
    if customer.object_type != "Customer":
        raise invalid("customer", "판매처를 찾을 수 없습니다.")
    if customer.properties.get("status") == "suspended":
        raise invalid("customer", "거래정지된 판매처로는 출하할 수 없습니다.")

    stock = None
    for candidate in await context.search("WarehouseStock"):
        if candidate.properties.get("batchRid") == batch.rid:
            stock = candidate
            break
    available = int(stock.properties["quantity"]) if stock is not None else 0
    quantity = int(params["quantity"]) if params.get("quantity") is not None else available
    if quantity <= 0:
        raise invalid("quantity", "출하수량은 1 이상이어야 합니다.")
    if quantity > available:
        raise invalid("quantity", f"창고 재고({available}병)를 초과할 수 없습니다.")

    ship_date = as_date(params.get("shipDate")) or dt.date.today()
    expires_on = batch.properties.get("expiresOn")
    if expires_on and dt.date.fromisoformat(str(expires_on)) < ship_date:
        raise invalid("batch", "소비기한이 지난 배치는 출하할 수 없습니다.")

    order = None
    order_rid = params.get("order")
    if order_rid:
        order = await context.require(order_rid)
        if order.object_type != "SalesOrder":
            raise invalid("order", "주문을 찾을 수 없습니다.")

    shipment_no = await next_no(context, "Shipment", SHIPMENT_PREFIX)
    shipment_properties: dict[str, Any] = {
        "shipmentNo": shipment_no,
        "shipDate": ship_date.isoformat(),
        "batchRid": batch.rid,
        "customerRid": customer.rid,
        "quantity": quantity,
        "status": "in_transit",
    }
    if order is not None:
        shipment_properties["orderRid"] = order.rid
    shipment_rid = context.create("Shipment", shipment_properties)
    context.link("batchShipments", batch.rid, shipment_rid)
    context.link("customerShipments", customer.rid, shipment_rid)
    if order is not None:
        context.link("orderShipments", order.rid, shipment_rid)
        if order.properties.get("status") == "confirmed":
            await context.modify(order.rid, {"status": "shipped"})

    await bump_warehouse_stock(context, batch, -quantity, ship_date)

    if quantity == available:
        await context.modify(batch.rid, {"status": "shipped"})


async def receive_shipment(context: EditContext, params: dict[str, Any]) -> None:
    shipment = await context.require(params["shipment"])
    if shipment.object_type != "Shipment":
        raise invalid("shipment", "출하를 찾을 수 없습니다.")
    if shipment.properties.get("status") != "in_transit":
        status = shipment.properties.get("status")
        raise invalid("shipment", f"{status} 상태의 출하는 입고할 수 없습니다.")

    received_on = as_date(params.get("receivedOn")) or dt.date.today()
    await context.modify(
        shipment.rid,
        {"status": "delivered", "deliveredOn": received_on.isoformat()},
    )
    await bump_outlet_stock(
        context,
        str(shipment.properties["customerRid"]),
        await _product_rid(context, shipment),
        int(shipment.properties["quantity"]),
        received_on,
    )

    order_rid = shipment.properties.get("orderRid")
    if order_rid:
        order = await context.get(str(order_rid))
        if order is not None and order.properties.get("status") == "shipped":
            await context.modify(order.rid, {"status": "delivered"})


async def _product_rid(context: EditContext, shipment: Any) -> str:
    # Shipment stores no product reference of its own; resolve it via the batch.
    batch = await context.get(str(shipment.properties["batchRid"]))
    return str(batch.properties["productRid"]) if batch else ""
