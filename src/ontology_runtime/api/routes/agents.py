"""Agent invocation and proposal inbox endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ontology_runtime.agents.loop import AgentLoop
from ontology_runtime.api.deps import runtime_dependency
from ontology_runtime.api.errors import envelope
from ontology_runtime.runtime import Runtime

router = APIRouter(prefix="/api", tags=["agents"])


class InvokeBody(BaseModel):
    input: str
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("/agents/{agent_name}/invoke")
async def invoke_agent(
    agent_name: str,
    body: InvokeBody,
    runtime: Runtime = Depends(runtime_dependency),
    x_actor: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    agent = runtime.registry.agent(agent_name)
    result = await AgentLoop(runtime).invoke(agent, body.input, actor=x_actor or "anonymous")
    return envelope(result.to_dict())


@router.get("/proposals")
async def list_proposals(
    runtime: Runtime = Depends(runtime_dependency),
    status: str | None = None,
) -> dict[str, Any]:
    filter_spec = {"field": "status", "op": "eq", "value": status} if status else None
    page = await runtime.sets.search(
        "ActionProposal", filter=filter_spec, order_by=None, page_size=100
    )
    return envelope(
        [
            {
                **proposal.to_dict(),
                "actionType": proposal.properties.get("actionType"),
                "rationale": proposal.properties.get("rationale"),
                "confidence": proposal.properties.get("confidence"),
                "status": proposal.properties.get("status"),
                "violations": proposal.properties.get("violations"),
                "targetObjectType": proposal.properties.get("targetObjectType"),
                "targetRid": proposal.properties.get("targetRid"),
            }
            for proposal in page.objects
        ],
        meta={"count": page.total},
    )


@router.get("/agentRuns")
async def list_agent_runs(
    runtime: Runtime = Depends(runtime_dependency),
    limit: int = 50,
) -> dict[str, Any]:
    page = await runtime.sets.search("AgentRun", page_size=min(limit, 200))
    return envelope([run.to_dict() for run in page.objects], meta={"count": page.total})
