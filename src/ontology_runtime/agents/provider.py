"""LLM provider interface and response types.

The runtime speaks one small protocol so the OpenRouter adapter, a fixture
replayer, and any future provider are interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    model: str

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse: ...
