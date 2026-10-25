"""Registry of executable object invariants, keyed by their YAML apiName."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ontology_runtime.actions.context import EditContext
from ontology_runtime.validation.violations import ViolationList

InvariantImpl = Callable[..., Awaitable[None]]


async def order_totals_match_lines(context: EditContext, violations: ViolationList) -> None:
    """SalesOrder.totalAmount must equal the sum of its line amounts."""
    collected = await _collect_line_totals(context, "SalesOrder", "lines")
    for order in await context.search("SalesOrder"):
        expected = collected.get(order.rid, 0)
        actual = int(order.properties.get("totalAmount") or 0)
        if actual != expected:
            violations.add(
                "invariant_violated",
                "totalAmount",
                f"SalesOrder {order.rid} totalAmount {actual} does not match line sum {expected}",
                objectType="SalesOrder",
                objectRef=order.rid,
            )


async def invoice_totals_match_lines(context: EditContext, violations: ViolationList) -> None:
    collected = await _collect_line_totals(context, "SalesInvoice", "lines")
    for invoice in await context.search("SalesInvoice"):
        expected = collected.get(invoice.rid, 0)
        actual = int(invoice.properties.get("totalAmount") or 0)
        if actual != expected:
            violations.add(
                "invariant_violated",
                "totalAmount",
                f"SalesInvoice {invoice.rid} totalAmount {actual} "
                f"does not match line sum {expected}",
                objectType="SalesInvoice",
                objectRef=invoice.rid,
            )


async def stop_sequence_unique_per_delivery(
    context: EditContext, violations: ViolationList
) -> None:
    seen: dict[tuple[str, int], str] = {}
    for stop in await context.search("DeliveryStop"):
        delivery = stop.properties.get("deliveryRid")
        sequence = stop.properties.get("sequence")
        if not delivery or sequence is None:
            continue
        key = (str(delivery), int(sequence))
        if key in seen and seen[key] != stop.rid:
            violations.add(
                "invariant_violated",
                "sequence",
                f"Delivery {delivery} has duplicate stop sequence {sequence}",
                objectType="DeliveryStop",
                objectRef=stop.rid,
            )
        seen[key] = stop.rid


async def _collect_line_totals(
    context: EditContext, parent_type: str, link_name: str
) -> dict[str, int]:
    """Sum line amounts per parent, combining persisted links and pending edits."""
    totals: dict[str, int] = {}
    for parent in await context.search(parent_type):
        lines = await context.linked(parent.rid, link_name)
        totals[parent.rid] = sum(int(line.properties.get("lineAmount") or 0) for line in lines)
    return totals


INVARIANTS: dict[str, InvariantImpl] = {
    "orderTotalsMatchLines": order_totals_match_lines,
    "invoiceTotalsMatchLines": invoice_totals_match_lines,
    "stopSequenceUniquePerDelivery": stop_sequence_unique_per_delivery,
}


def register(name: str, implementation: InvariantImpl) -> None:
    INVARIANTS[name] = implementation
