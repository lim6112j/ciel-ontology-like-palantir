"""Read function execution endpoint."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ontology_runtime.api.deps import runtime_dependency  # noqa: F401
from ontology_runtime.api.errors import envelope
from ontology_runtime.meta import FunctionKind
from ontology_runtime.runtime import Runtime

router = APIRouter(prefix="/api/functions", tags=["functions"])


class ExecuteBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/{function_name}/execute")
async def execute_function(
    function_name: str,
    body: ExecuteBody,
    runtime: Runtime = Depends(runtime_dependency),
    x_actor: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    definition = runtime.registry.function(function_name)
    if definition.kind is not FunctionKind.READ:
        from ontology_runtime.errors import PolicyViolation

        raise PolicyViolation(
            f"{function_name!r} is a write function; run it through its action type instead",
            actionSuggested=definition.apiName,
        )
    result = await runtime.run_function(function_name, body.params, actor=x_actor or "anonymous")
    return envelope(result)
