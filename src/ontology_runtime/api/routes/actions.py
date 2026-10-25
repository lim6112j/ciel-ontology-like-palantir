"""Action validate/apply endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ontology_runtime.api.deps import runtime_dependency
from ontology_runtime.api.errors import envelope
from ontology_runtime.errors import ValidationFailed
from ontology_runtime.runtime import Runtime

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ApplyBody(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("/{action_name}/validate")
async def validate_action(
    action_name: str,
    body: ApplyBody,
    runtime: Runtime = Depends(runtime_dependency),
    x_actor: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    result = await runtime.validate(action_name, body.params, actor=x_actor or "anonymous")
    return envelope(result.to_dict())


@router.post("/{action_name}/apply")
async def apply_action(
    action_name: str,
    body: ApplyBody,
    runtime: Runtime = Depends(runtime_dependency),
    x_actor: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, Any]:
    result = await runtime.apply(
        action_name,
        body.params,
        actor=x_actor or "anonymous",
        idempotency_key=idempotency_key,
    )
    if result.status == "failed":
        raise ValidationFailed(result.violations)
    return envelope(result.to_dict())
