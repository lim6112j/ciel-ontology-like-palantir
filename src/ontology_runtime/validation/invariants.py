"""Registry of executable object invariants, keyed by their YAML apiName.

Implementations are deliberately domain-agnostic: an object type declares an
invariant name and passes the type/property names it applies to via `params`.
That way a new domain reuses the checks without editing this module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ontology_runtime.actions.context import EditContext
from ontology_runtime.validation.violations import ViolationList

InvariantImpl = Callable[..., Awaitable[None]]


async def totals_match_linked_lines(
    context: EditContext,
    violations: ViolationList,
    *,
    parentType: str,
    linkName: str,
    totalProperty: str,
    lineProperty: str,
) -> None:
    """A parent's roll-up total must equal the sum of its linked line amounts."""
    for parent in await context.search(parentType):
        lines = await context.linked(parent.rid, linkName)
        expected = sum(int(line.properties.get(lineProperty) or 0) for line in lines)
        actual = int(parent.properties.get(totalProperty) or 0)
        if actual != expected:
            violations.add(
                "invariant_violated",
                totalProperty,
                f"{parentType} {parent.rid} {totalProperty} {actual} "
                f"does not match line sum {expected}",
                objectType=parentType,
                objectRef=parent.rid,
            )


async def sequence_unique_per_group(
    context: EditContext,
    violations: ViolationList,
    *,
    objectType: str,
    groupProperty: str,
    sequenceProperty: str,
) -> None:
    """A sequence number must be unique within its group (e.g. per delivery)."""
    seen: dict[tuple[str, int], str] = {}
    for obj in await context.search(objectType):
        group = obj.properties.get(groupProperty)
        sequence = obj.properties.get(sequenceProperty)
        if not group or sequence is None:
            continue
        key = (str(group), int(sequence))
        if key in seen and seen[key] != obj.rid:
            violations.add(
                "invariant_violated",
                sequenceProperty,
                f"{groupProperty} {group} has duplicate {sequenceProperty} {sequence}",
                objectType=objectType,
                objectRef=obj.rid,
            )
        seen[key] = obj.rid


INVARIANTS: dict[str, InvariantImpl] = {
    "totalsMatchLinkedLines": totals_match_linked_lines,
    "sequenceUniquePerGroup": sequence_unique_per_group,
}


def register(name: str, implementation: InvariantImpl) -> None:
    """Register a domain-specific invariant at import time."""
    INVARIANTS[name] = implementation
