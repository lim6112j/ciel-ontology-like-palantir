"""Binds the function registry to the action service.

Keeping this in one place guarantees that declarative and function-backed
actions share the same apply/audit path and that nested verified actions
(proposal approval) can stage edits into the caller's EditContext.
"""

from __future__ import annotations

from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.functions.registry import FunctionRegistry
from ontology_runtime.registry import SchemaRegistry


class FunctionExecutor:
    def __init__(self, registry: SchemaRegistry) -> None:
        self.registry = registry
        self.functions = FunctionRegistry(registry)

    async def execute_write(
        self, api_name: str, context: EditContext, params: dict[str, Any]
    ) -> None:
        # Nested actions need a way to reach this executor (build_action_edits).
        context.scratch["__function_executor__"] = self.execute_write
        await self.functions.execute_write(api_name, context, params)

    async def execute_read(
        self, api_name: str, context: EditContext, params: dict[str, Any]
    ) -> Any:
        from ontology_runtime.functions.registry import execute_read

        return await execute_read(self.registry, api_name, context, params)
