"""Function definitions (read-only and write)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ontology_runtime.meta.action_type import ParameterDef


class FunctionKind(StrEnum):
    READ = "read"
    WRITE = "write"


class FunctionDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=r"^[a-z][a-zA-Z0-9]*$")
    displayName: str
    description: str | None = None
    kind: FunctionKind = FunctionKind.READ  # functions are camelCase by OSDK convention
    parameters: dict[str, ParameterDef] = Field(default_factory=dict)
    #: Dotted path of the Python implementation, e.g. `functions.read.orders.compute_order_totals`.
    implementation: str
    resultDescription: str | None = None
    #: Agents may only call read functions unless explicitly allowed.
    agentCallable: bool = False
    timeoutSeconds: int = 30

    @model_validator(mode="after")
    def _check(self) -> FunctionDef:
        for name, param in self.parameters.items():
            if param.apiName != name:
                raise ValueError(
                    f"function {self.apiName!r}: parameter key {name!r} "
                    f"does not match apiName {param.apiName!r}"
                )
        if self.kind is FunctionKind.WRITE and self.agentCallable:
            raise ValueError(f"function {self.apiName!r}: write functions cannot be agent-callable")
        return self

    def agent_parameters(self) -> dict[str, ParameterDef]:
        return {k: v for k, v in self.parameters.items() if v.agentVisible}


class FunctionResult(BaseModel):
    """Envelope returned by every function execution."""

    model_config = {"extra": "allow"}

    data: Any = None
    violations: list[dict[str, Any]] = Field(default_factory=list)
