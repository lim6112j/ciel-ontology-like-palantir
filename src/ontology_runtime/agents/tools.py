"""Agent tool surface, generated from the ontology registry.

There is deliberately **no apply tool**. The only write-shaped capability is
`propose_action`, which records an ActionProposal for human approval, so a
prompt injection cannot mutate the ontology.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from typing import Any

from ontology_runtime.agents.provider import ToolCall
from ontology_runtime.errors import OntologyError, PolicyViolation, ValidationFailed
from ontology_runtime.meta import AgentDef, ParameterType
from ontology_runtime.query.object_set import OrderBy
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime

_JSON_TYPE = {
    ParameterType.STRING: "string",
    ParameterType.TEXT: "string",
    ParameterType.INTEGER: "integer",
    ParameterType.DECIMAL: "number",
    ParameterType.BOOLEAN: "boolean",
    ParameterType.DATE: "string",
    ParameterType.TIMESTAMP: "string",
    ParameterType.ENUM: "string",
    ParameterType.OBJECT_REF: "string",
    ParameterType.OBJECT_SET: "array",
    ParameterType.JSON: "object",
}


@dataclass
class ToolOutcome:
    """Result of executing one tool call."""

    content: str
    is_error: bool = False
    proposal_rid: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def build_tool_surface(registry: SchemaRegistry, agent: AgentDef) -> list[dict[str, Any]]:
    """OpenAI-format function definitions the agent may call."""
    tools = [
        _function_tool(
            "search_objects",
            '온톨로지에서 객체를 검색한다. filter는 {"field":..,"op":..,"value":..} '
            '또는 {"and":[...]}/{"or":[...]} 형태다.',
            {
                "objectType": {"type": "string", "description": "예: Outlet, SalesOrder"},
                "filter": {"type": "object", "description": "필터 조건"},
                "orderBy": {"type": "string", "description": "예: orderDate desc"},
                "pageSize": {"type": "integer"},
            },
            required=["objectType"],
        ),
        _function_tool(
            "get_linked_objects",
            "한 객체에서 링크를 따라 연결된 객체를 조회한다.",
            {
                "rid": {"type": "string"},
                "linkName": {"type": "string", "description": "예: lines, stops, driver"},
            },
            required=["rid", "linkName"],
        ),
        _function_tool(
            "validate_action",
            "액션을 실제로 실행하지 않고 검증만 한다. 위반 사항을 확인할 때 사용한다.",
            {
                "actionType": {"type": "string"},
                "params": {"type": "object"},
            },
            required=["actionType", "params"],
        ),
        _function_tool(
            "propose_action",
            "액션을 제안한다. 운영자가 승인해야 실제로 실행된다. "
            "rationale에는 제안 근거를 한국어로 적는다.",
            {
                "actionType": {"type": "string"},
                "params": {"type": "object"},
                "rationale": {"type": "string"},
                "confidence": {"type": "number", "description": "0~1"},
                "targetRid": {"type": "string"},
            },
            required=["actionType", "params", "rationale"],
        ),
    ]

    if agent.allowedFunctions:
        tools.append(
            _function_tool(
                "run_function",
                "읽기 전용 온톨로지 함수를 실행한다.",
                {
                    "name": {"type": "string", "description": ", ".join(agent.allowedFunctions)},
                    "params": {"type": "object"},
                },
                required=["name", "params"],
            )
        )
    return tools


def _function_tool(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


class AgentToolbox:
    """Executes tool calls for one agent invocation, enforcing its allowlists."""

    def __init__(
        self,
        runtime: Runtime,
        agent: AgentDef,
        *,
        run_no: str,
        actor: str,
        tool_log: list[dict[str, Any]],
        proposals: list[str],
    ) -> None:
        self.runtime = runtime
        self.agent = agent
        self.run_no = run_no
        self.actor = actor
        self.tool_log = tool_log
        self.proposals = proposals
        self._proposal_count = 0

    async def execute(self, call: ToolCall) -> ToolOutcome:
        handler = getattr(self, f"_tool_{call.name}", None)
        if handler is None:
            self.tool_log.append(
                {
                    "tool": call.name,
                    "arguments": call.arguments,
                    "result": "unknown tool",
                    "isError": True,
                }
            )
            return ToolOutcome(content=f"알 수 없는 도구입니다: {call.name}", is_error=True)
        try:
            arguments = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            self.tool_log.append(
                {
                    "tool": call.name,
                    "arguments": call.arguments,
                    "result": "invalid json",
                    "isError": True,
                }
            )
            return ToolOutcome(content="도구 인자가 올바른 JSON이 아닙니다.", is_error=True)

        self.tool_log.append({"tool": call.name, "arguments": arguments})
        try:
            outcome: ToolOutcome = await handler(arguments)
        except PolicyViolation as exc:
            outcome = ToolOutcome(content=f"정책 위반: {exc.message}", is_error=True)
        except ValidationFailed as exc:
            outcome = ToolOutcome(
                content=json.dumps({"violations": exc.violations}, ensure_ascii=False),
                is_error=True,
            )
        except OntologyError as exc:
            outcome = ToolOutcome(content=f"오류: {exc.message}", is_error=True)
        self.tool_log[-1]["result"] = outcome.content[:2000]
        self.tool_log[-1]["isError"] = outcome.is_error
        return outcome

    # -- read tools --------------------------------------------------------
    async def _tool_search_objects(self, args: dict[str, Any]) -> ToolOutcome:
        object_type = args.get("objectType")
        if object_type not in self.runtime.registry.bundle.object_types:
            return ToolOutcome(content=f"알 수 없는 objectType입니다: {object_type}", is_error=True)
        page_size = min(int(args.get("pageSize") or 10), self.agent.maxPageSize)
        page = await self.runtime.sets.search(
            object_type,
            filter=args.get("filter"),
            order_by=_parse_order_by(args.get("orderBy")),
            page_size=page_size,
        )
        return ToolOutcome(
            content=json.dumps(
                {"total": page.total, "objects": [o.to_dict() for o in page.objects]},
                ensure_ascii=False,
                default=str,
            ),
            payload={"total": page.total},
        )

    async def _tool_get_linked_objects(self, args: dict[str, Any]) -> ToolOutcome:
        rid = str(args.get("rid") or "")
        link_name = str(args.get("linkName") or "")
        obj = await self.runtime.objects.maybe_get(rid)
        if obj is None:
            return ToolOutcome(content=f"객체를 찾을 수 없습니다: {rid}", is_error=True)
        try:
            view = self.runtime.registry.link_on(obj.object_type, link_name)
        except OntologyError as exc:
            return ToolOutcome(content=exc.message, is_error=True)
        targets = await self.runtime.links.targets(view, rid)
        return ToolOutcome(
            content=json.dumps([o.to_dict() for o in targets], ensure_ascii=False, default=str)
        )

    async def _tool_validate_action(self, args: dict[str, Any]) -> ToolOutcome:
        action = args.get("actionType")
        if action not in self.agent.allowedActionTypes:
            return ToolOutcome(
                content=f"이 에이전트는 {action} 액션을 사용할 수 없습니다.", is_error=True
            )
        result = await self.runtime.validate(action, args.get("params") or {}, actor=self.actor)
        return ToolOutcome(
            content=json.dumps(
                {"valid": result.status != "failed", "violations": result.violations},
                ensure_ascii=False,
            )
        )

    async def _tool_run_function(self, args: dict[str, Any]) -> ToolOutcome:
        name = args.get("name")
        if name not in self.agent.allowedFunctions:
            return ToolOutcome(
                content=f"이 에이전트는 {name} 함수를 호출할 수 없습니다.", is_error=True
            )
        result = await self.runtime.run_function(name, args.get("params") or {}, actor=self.actor)
        return ToolOutcome(content=json.dumps(result, ensure_ascii=False, default=str))

    # -- the only write-shaped tool ---------------------------------------
    async def _tool_propose_action(self, args: dict[str, Any]) -> ToolOutcome:
        action_name = args.get("actionType")
        if action_name not in self.agent.allowedActionTypes:
            raise PolicyViolation(
                f"이 에이전트는 {action_name} 액션을 제안할 수 없습니다.",
                agent=self.agent.apiName,
                actionType=action_name,
            )
        if self._proposal_count >= self.agent.maxProposals:
            return ToolOutcome(
                content=(
                    f"한 번의 실행에서 최대 {self.agent.maxProposals}건까지만 제안할 수 있습니다."
                ),
                is_error=True,
            )

        params = args.get("params") or {}
        validation = await self.runtime.validate(action_name, params, actor=self.actor)
        action_def = self.runtime.registry.action_type(action_name)
        target_rid = args.get("targetRid")
        target_type = _object_type_from_rid(target_rid)

        proposal_rid = await self.runtime.objects.create(
            "ActionProposal",
            {
                "proposalNo": f"PR-{self.run_no[-8:]}-{self._proposal_count + 1:02d}",
                "actionType": action_name,
                "params": params,
                "rationale": args.get("rationale") or "",
                "confidence": float(args.get("confidence") or 0.5),
                "status": "proposed",
                "violations": validation.violations,
                "targetObjectType": target_type,
                "targetRid": target_rid,
                "feedbackNote": f"제안 액션: {action_def.displayName}",
            },
            rid=None,
        )
        self._proposal_count += 1
        self.proposals.append(proposal_rid.rid)

        return ToolOutcome(
            content=json.dumps(
                {
                    "proposalRid": proposal_rid.rid,
                    "status": "proposed",
                    "violations": validation.violations,
                    "note": "운영자 승인 후 실행됩니다.",
                },
                ensure_ascii=False,
            ),
            proposal_rid=proposal_rid.rid,
        )


#: rids look like `ri.<namespace>.object.<typename>.<id>`.
_RID_TYPE_INDEX = 3
_RID_MIN_PARTS = 4


def _object_type_from_rid(rid: Any) -> str | None:
    if not isinstance(rid, str) or rid.count(".") + 1 < _RID_MIN_PARTS:
        return None
    return rid.split(".")[_RID_TYPE_INDEX]


def _parse_order_by(raw: Any) -> list[OrderBy]:
    if not raw:
        return []
    field, _, direction = str(raw).partition(" ")
    return [OrderBy(field=field, direction=direction or "asc")]


def now_run_no(agent_name: str) -> str:
    now = dt.datetime.now(dt.UTC)
    return f"AR-{now.strftime('%Y%m%d%H%M%S')}-{agent_name[:6]}-{now.microsecond:06d}"
