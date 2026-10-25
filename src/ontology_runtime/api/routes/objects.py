"""Object CRUD, object set search/aggregate, and link traversal."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ontology_runtime.api.deps import runtime_dependency
from ontology_runtime.api.errors import envelope
from ontology_runtime.query.object_set import AggregateSpec, parse_order_by
from ontology_runtime.runtime import Runtime

router = APIRouter(prefix="/api", tags=["objects"])


class SearchBody(BaseModel):
    filter: Any = None
    orderBy: Any = Field(default=None, alias="orderBy")
    pageSize: int = 50
    pageToken: int = 0
    select: list[str] | None = None


class AggregateBody(BaseModel):
    groupBy: list[str] = Field(default_factory=list)
    select: list[dict[str, Any]] = Field(default_factory=list)
    filter: Any = None


class CreateBody(BaseModel):
    properties: dict[str, Any]


class UpdateBody(BaseModel):
    properties: dict[str, Any]
    expectedVersion: int | None = None


@router.post("/objectsets/{object_type}/search")
async def search_objects(
    object_type: str,
    body: SearchBody,
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    page = await runtime.sets.search(
        object_type,
        filter=body.filter,
        order_by=parse_order_by(body.orderBy),
        page_size=body.pageSize,
        page_token=body.pageToken,
        select_properties=body.select,
    )
    return envelope(page.to_dict()["data"], meta=page.to_dict()["meta"])


@router.post("/objectsets/{object_type}/aggregate")
async def aggregate_objects(
    object_type: str,
    body: AggregateBody,
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    rows = await runtime.sets.aggregate(
        object_type, AggregateSpec(groupBy=body.groupBy, select=body.select, filter=body.filter)
    )
    return envelope(rows, meta={"count": len(rows)})


@router.get("/objects/{object_type}")
async def list_objects(
    object_type: str,
    page_size: int = Query(50, alias="pageSize", ge=1, le=500),
    page_token: int = Query(0, alias="pageToken", ge=0),
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    page = await runtime.sets.search(object_type, page_size=page_size, page_token=page_token)
    return envelope(page.to_dict()["data"], meta=page.to_dict()["meta"])


@router.get("/objects/{object_type}/{rid}")
async def get_object(
    object_type: str, rid: str, runtime: Runtime = Depends(runtime_dependency)
) -> dict[str, Any]:
    obj = await runtime.objects.get(rid)
    if obj.object_type != object_type:
        from ontology_runtime.errors import NotFoundError

        raise NotFoundError(f"{rid!r} is not a {object_type}")
    return envelope(obj.to_dict())


@router.post("/objects/{object_type}")
async def create_object(
    object_type: str,
    body: CreateBody,
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    obj = await runtime.objects.create(object_type, body.properties)
    return envelope(obj.to_dict())


@router.patch("/objects/{object_type}/{rid}")
async def update_object(
    object_type: str,
    rid: str,
    body: UpdateBody,
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    obj = await runtime.objects.update(rid, body.properties, expected_version=body.expectedVersion)
    return envelope(obj.to_dict())


@router.delete("/objects/{object_type}/{rid}")
async def delete_object(
    object_type: str,
    rid: str,
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    await runtime.objects.soft_delete(rid)
    return envelope({"rid": rid, "deleted": True})


@router.get("/objects/{object_type}/{rid}/links/{link_name}")
async def get_linked_objects(
    object_type: str,
    rid: str,
    link_name: str,
    runtime: Runtime = Depends(runtime_dependency),
) -> dict[str, Any]:
    obj = await runtime.objects.get(rid)
    view = runtime.registry.link_on(obj.object_type, link_name)
    targets = await runtime.links.targets(view, rid)
    return envelope([t.to_dict() for t in targets], meta={"count": len(targets)})


@router.get("/audit/actionRuns")
async def list_action_runs(
    runtime: Runtime = Depends(runtime_dependency),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    from sqlalchemy import desc, select

    from ontology_runtime.db.models import ActionRunRow

    rows = (
        await runtime.session.scalars(
            select(ActionRunRow).order_by(desc(ActionRunRow.created_at)).limit(limit)
        )
    ).all()
    return envelope(
        [
            {
                "runId": str(row.id),
                "actionType": row.action_type,
                "actor": row.actor,
                "status": row.status,
                "dryRun": row.dry_run,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
                "proposalRid": row.proposal_rid,
            }
            for row in rows
        ]
    )
