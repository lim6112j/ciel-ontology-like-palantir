"""Write functions for sales orders."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.makgeolli.functions.write.common import (
    as_date,
    invalid,
    next_no,
)

ORDER_PREFIX = "SO"
LINE_PREFIX = "SOL"


async def create_sales_order(context: EditContext, params: dict[str, Any]) -> None:
    customer = await context.require(params["customer"])
    if customer.object_type != "Customer":
        raise invalid("customer", "판매처를 찾을 수 없습니다.")
    if customer.properties.get("status") == "suspended":
        raise invalid("customer", "거래정지된 판매처에는 주문을 만들 수 없습니다.")

    lines = params.get("lines") or []
    if not lines:
        raise invalid("lines", "주문 라인이 필요합니다.")

    order_date = as_date(params.get("orderDate")) or dt.date.today()
    order_no = await next_no(context, "SalesOrder", ORDER_PREFIX)
    order_rid = context.create(
        "SalesOrder",
        {
            "orderNo": order_no,
            "customerRid": customer.rid,
            "orderDate": order_date.isoformat(),
            "status": "draft",
            "totalAmount": 0,
        },
    )
    context.link("customerOrders", customer.rid, order_rid)

    total = 0
    for index, entry in enumerate(lines, start=1):
        product = await context.require(entry["productRid"])
        if product.object_type != "Product":
            raise invalid(f"lines[{index}].productRid", "제품을 찾을 수 없습니다.")
        if product.properties.get("active") is False:
            raise invalid(f"lines[{index}].productRid", "판매 중지된 제품입니다.")

        cases = int(entry.get("cases") or 0)
        if cases <= 0:
            raise invalid(f"lines[{index}].cases", "수량은 1 이상이어야 합니다.")

        unit_price = int(product.properties["unitPrice"])
        line_amount = unit_price * cases
        total += line_amount

        line_no = await next_no(context, "SalesOrderLine", LINE_PREFIX)
        line_rid = context.create(
            "SalesOrderLine",
            {
                "lineNo": line_no,
                "orderRid": order_rid,
                "productRid": product.rid,
                "cases": cases,
                "unitPrice": unit_price,
                "lineAmount": line_amount,
                "productName": product.properties["name"],
            },
        )
        context.link("orderLines", order_rid, line_rid)
        context.link("lineProduct", product.rid, line_rid)

    await context.modify(order_rid, {"totalAmount": total})
    context.scratch["orderId"] = order_rid
    context.scratch["totalAmount"] = total
