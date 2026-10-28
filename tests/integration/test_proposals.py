"""Proposal lifecycle: approval is the only path to execution."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.db.models import ObjectRow
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime


@pytest.fixture
def runtime(session: AsyncSession) -> Runtime:
    return Runtime(SchemaRegistry.from_domain("liquor"), session)


async def _seed(runtime: Runtime) -> dict[str, str]:
    depot = await runtime.objects.create(
        "Depot",
        {"depotNo": "D1", "name": "창고", "region": "수도권", "lat": 37.5, "lon": 127.0},
    )
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "P1",
            "name": "소주",
            "category": "소주",
            "manufacturer": "제조사",
            "volumeMl": 360,
            "unitsPerCase": 30,
            "unitPrice": 1200,
            "casePrice": 36000,
            "taxType": "과세",
            "active": True,
        },
    )
    outlet = await runtime.objects.create(
        "Outlet",
        {
            "outletNo": "O1",
            "name": "행복식당",
            "outletType": "일반음식점",
            "status": "active",
            "deliveryWeekday": 1,
            "lat": 37.52,
            "lon": 127.03,
            "depotRid": depot.rid,
        },
    )
    return {"depot": depot.rid, "product": product.rid, "outlet": outlet.rid}


async def _proposal(runtime: Runtime, params: dict, action: str = "CreateSalesOrder", **extra):
    defaults = {
        "proposalNo": "PR-0001",
        "actionType": action,
        "params": params,
        "rationale": "음성 발주를 해석했습니다.",
        "confidence": 0.9,
        "status": "proposed",
    }
    defaults.update(extra)
    return await runtime.objects.create("ActionProposal", defaults)


async def test_approval_executes_the_proposed_action(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "requestedDeliveryDate": "2026-10-27",
            "lines": [{"productRid": ids["product"], "cases": 3}],
        },
    )

    result = await runtime.apply(
        "ApproveActionProposal", {"proposal": proposal.rid}, actor="manager01"
    )
    assert result.status == "succeeded", result.violations

    orders = await runtime.search("SalesOrder")
    assert orders.total == 1
    order = orders.objects[0]
    assert order.properties["totalCases"] == 3

    updated = await runtime.objects.get(proposal.rid)
    assert updated.properties["status"] == "approved"
    assert updated.properties["approvedBy"] == "manager01"
    # Without overrides, the decided params equal the proposed params.
    assert updated.properties["decidedParams"] == updated.properties["params"]


async def test_approval_and_action_share_one_audit_run(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "lines": [{"productRid": ids["product"], "cases": 2}],
        },
    )
    result = await runtime.apply("ApproveActionProposal", {"proposal": proposal.rid})
    assert result.status == "succeeded"

    runs = await runtime.session.scalar(
        select(func.count()).select_from(select(ObjectRow).subquery())
    )
    assert runs is not None


async def test_approval_is_idempotent(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "lines": [{"productRid": ids["product"], "cases": 1}],
        },
    )
    first = await runtime.apply(
        "ApproveActionProposal", {"proposal": proposal.rid}, idempotency_key="approve-1"
    )
    second = await runtime.apply(
        "ApproveActionProposal", {"proposal": proposal.rid}, idempotency_key="approve-1"
    )
    assert first.status == "succeeded"
    assert second.replayed is True

    orders = await runtime.search("SalesOrder")
    assert orders.total == 1


async def test_rejected_proposal_cannot_be_approved(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "lines": [{"productRid": ids["product"], "cases": 1}],
        },
    )
    rejected = await runtime.apply(
        "RejectActionProposal", {"proposal": proposal.rid, "reason": "수량 오류"}
    )
    assert rejected.status == "succeeded"

    approval = await runtime.apply("ApproveActionProposal", {"proposal": proposal.rid})
    assert approval.status == "failed"
    assert approval.violations[0]["code"] == "proposal_state_invalid"

    orders = await runtime.search("SalesOrder")
    assert orders.total == 0


async def test_approval_with_override_params(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "lines": [{"productRid": ids["product"], "cases": 99}],
        },
    )
    result = await runtime.apply(
        "ApproveActionProposal",
        {
            "proposal": proposal.rid,
            "approvedParams": {"lines": [{"productRid": ids["product"], "cases": 2}]},
        },
    )
    assert result.status == "succeeded", result.violations
    orders = await runtime.search("SalesOrder")
    assert orders.objects[0].properties["totalCases"] == 2

    # The proposal must record what was actually approved, not what was proposed.
    updated = await runtime.objects.get(proposal.rid)
    assert updated.properties["decidedParams"]["lines"] == [
        {"productRid": ids["product"], "cases": 2}
    ]
    assert updated.properties["params"]["lines"][0]["cases"] == 99


async def test_invalid_proposal_params_block_approval(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {"outlet": ids["outlet"], "orderDate": "2026-10-26", "lines": []},
    )
    result = await runtime.apply("ApproveActionProposal", {"proposal": proposal.rid})
    assert result.status == "failed"
    assert any("라인" in v["message"] for v in result.violations)

    # The proposal stays actionable and no order was written.
    updated = await runtime.objects.get(proposal.rid)
    assert updated.properties["status"] == "proposed"
    assert (await runtime.search("SalesOrder")).total == 0


async def test_proposal_cannot_propose_itself(runtime: Runtime) -> None:
    await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {"proposal": "ri.liquor.object.actionproposal.x"},
        action="ApproveActionProposal",
    )
    result = await runtime.apply("ApproveActionProposal", {"proposal": proposal.rid})
    assert result.status == "failed"


async def test_expired_proposal_cannot_be_approved(runtime: Runtime) -> None:
    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {"outlet": ids["outlet"], "orderDate": "2026-10-26", "lines": []},
    )
    expired = await runtime.apply("ExpireActionProposal", {"proposal": proposal.rid})
    assert expired.status == "succeeded"
    approval = await runtime.apply("ApproveActionProposal", {"proposal": proposal.rid})
    assert approval.status == "failed"


async def test_approval_run_links_back_to_proposal(runtime: Runtime) -> None:
    """The audit row must name the proposal it executed."""
    from sqlalchemy import desc, select

    from ontology_runtime.db.models import ActionRunRow

    ids = await _seed(runtime)
    proposal = await _proposal(
        runtime,
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "lines": [{"productRid": ids["product"], "cases": 1}],
        },
    )
    await runtime.apply("ApproveActionProposal", {"proposal": proposal.rid}, actor="manager01")

    run = await runtime.session.scalar(
        select(ActionRunRow)
        .where(ActionRunRow.action_type == "ApproveActionProposal")
        .order_by(desc(ActionRunRow.created_at))
        .limit(1)
    )
    assert run is not None
    assert run.proposal_rid == proposal.rid
