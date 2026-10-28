"""Proposal approval: runs the proposed action through the same applier."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed


def _invalid(path: str, message: str, code: str = "invalid") -> ValidationFailed:
    return ValidationFailed([{"code": code, "path": path, "message": message}])


async def apply_approved_proposal(context: EditContext, params: dict[str, Any]) -> None:
    """Validate and stage the target action's edits inside the approval transaction.

    The nested action is built with the same EditContext, so its edits land in the
    same EditBatch and the same audit path — no second writer, no double audit.
    """
    proposal = await context.require(params["proposal"])
    if proposal.object_type != "ActionProposal":
        raise _invalid("proposal", "ActionProposal 객체가 아닙니다.")

    status = proposal.properties.get("status")
    if status != "proposed":
        raise _invalid(
            "proposal",
            f"{status} 상태의 제안은 승인할 수 없습니다.",
            code="proposal_state_invalid",
        )

    action_name = proposal.properties.get("actionType")
    if not action_name:
        raise _invalid("proposal", "제안에 actionType이 없습니다.")

    action_def = context.registry.bundle.action_types.get(str(action_name))
    if action_def is None:
        raise _invalid("proposal", f"알 수 없는 액션 {action_name!r}입니다.")
    if action_def.apiName in {
        "ApproveActionProposal",
        "RejectActionProposal",
        "ExpireActionProposal",
    }:
        raise _invalid("proposal", "제안 처리 액션은 제안으로 실행할 수 없습니다.")

    proposed_params = dict(proposal.properties.get("params") or {})
    approved_overrides = params.get("approvedParams") or {}
    if approved_overrides:
        if not isinstance(approved_overrides, dict):
            raise _invalid("approvedParams", "승인 파라미터는 객체여야 합니다.")
        proposed_params.update(approved_overrides)

    from ontology_runtime.actions.rules import build_action_edits

    await build_action_edits(context, action_def, proposed_params)

    now = dt.datetime.now(dt.UTC).isoformat()
    await context.modify(
        proposal.rid,
        {
            "status": "approved",
            "approvedBy": context.actor,
            "approvedAt": now,
            "decidedAt": now,
            "decidedParams": proposed_params,
            "feedbackNote": params.get("note") or proposal.properties.get("feedbackNote"),
        },
    )
    context.scratch["approvedProposalRid"] = proposal.rid
    context.scratch["approvedAction"] = action_def.apiName
