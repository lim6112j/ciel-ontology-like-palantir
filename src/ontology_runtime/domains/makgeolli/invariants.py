"""Domain-specific invariants for the makgeolli domain.

Imported automatically by ``Runtime._load_domain_invariants``; implementations
register themselves into the shared invariant registry at import time.
"""

from __future__ import annotations

import datetime as dt

from ontology_runtime.actions.context import EditContext
from ontology_runtime.validation.invariants import register
from ontology_runtime.validation.violations import ViolationList


async def batch_expiry_matches_shelf_life(
    context: EditContext,
    violations: ViolationList,
    *,
    productProperty: str,
    startProperty: str,
    expiryProperty: str,
    shelfLifeProperty: str,
) -> None:
    """A bottled batch's expiry must equal its bottling date plus the product shelf life."""
    for batch in await context.search("Batch"):
        start = batch.properties.get(startProperty)
        expiry = batch.properties.get(expiryProperty)
        if not start or not expiry:
            continue
        product = await context.get(str(batch.properties.get(productProperty)))
        shelf_life = int(product.properties.get(shelfLifeProperty) or 0) if product else 0
        expected = dt.date.fromisoformat(str(start)) + dt.timedelta(days=shelf_life)
        actual = dt.date.fromisoformat(str(expiry))
        if actual != expected:
            violations.add(
                "invariant_violated",
                expiryProperty,
                f"Batch {batch.rid} {expiryProperty} {actual} does not equal "
                f"{startProperty} {start} + {shelf_life}d shelf life",
                objectType="Batch",
                objectRef=batch.rid,
            )


async def line_amount_matches_unit_times_quantity(
    context: EditContext,
    violations: ViolationList,
    *,
    amountProperty: str,
    unitProperty: str,
    quantityProperty: str,
) -> None:
    """A sales order line's amount must equal unit price times quantity."""
    for line in await context.search("SalesOrderLine"):
        expected = int(line.properties.get(unitProperty) or 0) * int(
            line.properties.get(quantityProperty) or 0
        )
        actual = int(line.properties.get(amountProperty) or 0)
        if actual != expected:
            violations.add(
                "invariant_violated",
                amountProperty,
                f"SalesOrderLine {line.rid} {amountProperty} {actual} does not equal "
                f"{unitProperty}×{quantityProperty} = {expected}",
                objectType="SalesOrderLine",
                objectRef=line.rid,
            )


register("batchExpiryMatchesShelfLife", batch_expiry_matches_shelf_life)
register("lineAmountMatchesUnitTimesQuantity", line_amount_matches_unit_times_quantity)
