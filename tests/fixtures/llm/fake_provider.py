"""Scripted LLM provider for tests: replays recorded responses in order."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ontology_runtime.agents.provider import LLMResponse, ToolCall


class FakeProvider:
    """Feeds predetermined responses; records every request it receives."""

    def __init__(self, responses: list[LLMResponse], model: str = "fake/model") -> None:
        self._responses = list(responses)
        self.model = model
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        if not self._responses:
            return LLMResponse(content="(no more scripted responses)", finish_reason="stop")
        return self._responses.pop(0)

    @classmethod
    def from_fixture(cls, path: Path | str, model: str = "fake/model") -> FakeProvider:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([_response_from(entry) for entry in payload["responses"]], model=model)


def response(
    *,
    content: str = "",
    tool_calls: list[tuple[str, dict[str, Any]]] | None = None,
    finish_reason: str = "stop",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> LLMResponse:
    calls = [
        ToolCall(id=f"call_{index}", name=name, arguments=json.dumps(args, ensure_ascii=False))
        for index, (name, args) in enumerate(tool_calls or [], start=1)
    ]
    return LLMResponse(
        content=content,
        tool_calls=calls,
        finish_reason=finish_reason if not calls else "tool_calls",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _response_from(entry: dict[str, Any]) -> LLMResponse:
    return response(
        content=entry.get("content", ""),
        tool_calls=[
            (call["name"], call.get("arguments", {})) for call in entry.get("toolCalls", [])
        ],
        finish_reason=entry.get("finishReason", "stop"),
        input_tokens=entry.get("inputTokens", 100),
        output_tokens=entry.get("outputTokens", 50),
    )
