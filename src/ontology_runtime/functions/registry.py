"""Function registry: resolves YAML implementations to Python callables."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import FunctionNotFound, SchemaError
from ontology_runtime.meta import FunctionDef, FunctionKind
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.validation.violations import ViolationList

ReadFn = Callable[..., Awaitable[Any]]
WriteFn = Callable[[EditContext, dict[str, Any]], Awaitable[None]]


def _resolve(implementation: str) -> Callable[..., Any]:
    """Resolve `module.path.function` to a callable."""
    if "." not in implementation:
        raise SchemaError(f"implementation {implementation!r} must be a dotted path")
    module_name, _, attribute = implementation.rpartition(".")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise SchemaError(f"cannot import {module_name!r}: {exc}") from exc
    try:
        target = getattr(module, attribute)
    except AttributeError as exc:
        raise SchemaError(f"{module_name!r} has no attribute {attribute!r}") from exc
    if not callable(target):
        raise SchemaError(f"{implementation!r} does not resolve to a callable")
    return cast(Callable[..., Any], target)


class FunctionRegistry:
    """Executes functions declared in `functions.yaml`."""

    def __init__(self, registry: SchemaRegistry) -> None:
        self.registry = registry
        self._resolved: dict[str, Callable[..., Any]] = {}

    def _resolve_definition(self, api_name: str) -> tuple[FunctionDef, Callable[..., Any]]:
        definition = self.registry.function(api_name)
        if api_name not in self._resolved:
            self._resolved[api_name] = _resolve(definition.implementation)
        return definition, self._resolved[api_name]

    def is_registered(self, api_name: str) -> bool:
        return api_name in self.registry.bundle.functions

    def resolve_read(self, api_name: str) -> ReadFn:
        definition, implementation = self._resolve_definition(api_name)
        if definition.kind is not FunctionKind.READ:
            raise FunctionNotFound(f"function {api_name!r} is a write function")
        return cast(ReadFn, implementation)

    async def execute_write(
        self, api_name: str, context: EditContext, params: dict[str, Any]
    ) -> None:
        definition, implementation = self._resolve_definition(api_name)
        if definition.kind is not FunctionKind.WRITE:
            raise FunctionNotFound(f"function {api_name!r} is not a write function")
        await implementation(context, params)


async def execute_read(
    registry: SchemaRegistry,
    api_name: str,
    context: EditContext,
    params: dict[str, Any],
) -> Any:
    """Run a read function.

    Read functions are declared as `async def name(context, **params)`; the
    context is always the first argument so functions can traverse the ontology.
    """
    from ontology_runtime.errors import ValidationFailed

    definition = registry.function(api_name)
    implementation = FunctionRegistry(registry).resolve_read(api_name)
    kwargs: dict[str, Any] = {}
    missing: list[dict[str, Any]] = []
    for name, spec in definition.parameters.items():
        if name in params:
            kwargs[name] = params[name]
        elif spec.required:
            missing.append(
                {
                    "code": "missing_parameter",
                    "path": name,
                    "message": f"function {api_name!r} requires parameter {name!r}",
                }
            )
    if missing:
        raise ValidationFailed(missing)
    result = implementation(context, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


def check_violations(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, ViolationList):
        return result.to_dicts()
    if isinstance(result, dict) and "violations" in result:
        return list(result["violations"])
    return []
