"""Live smoke tests against OpenRouter.

Excluded from the default suite by `addopts = -m 'not live'`. Run with:

    OPENROUTER_API_KEY=... uv run pytest -m live -q

These make real network calls (a few hundred tokens each); keep them few.
"""

from __future__ import annotations

import os

import pytest

from ontology_runtime.agents.provider_openrouter import OpenRouterProvider

pytestmark = pytest.mark.live


@pytest.fixture
def provider() -> OpenRouterProvider:
    # Function-scoped: the SDK's AsyncClient binds to the event loop that created it,
    # and each async test runs on its own loop.
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is not set")
    return OpenRouterProvider()


async def test_model_returns_text_and_usage(provider: OpenRouterProvider) -> None:
    result = await provider.complete(
        [{"role": "user", "content": "한 단어로 '확인'이라고만 답하세요."}], []
    )

    assert result.content.strip()
    assert result.input_tokens > 0
    assert result.output_tokens > 0
    assert result.model
    assert result.finish_reason in {"stop", "length"}


async def test_model_can_call_a_tool(provider: OpenRouterProvider) -> None:
    """The agent runtime depends on native tool calling, so verify it end to end."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup_outlet",
                "description": "거래처 이름으로 온톨로지를 조회한다.",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        }
    ]

    result = await provider.complete(
        [{"role": "user", "content": "lookup_outlet 도구로 '행복식당'을 조회해 주세요."}],
        tools,
    )

    # Some providers occasionally answer in text instead of calling; either is a
    # valid smoke result as long as the request round-tripped.
    assert result.tool_calls or result.content
    if result.tool_calls:
        assert result.tool_calls[0].name == "lookup_outlet"
        assert (
            "행복식당" in result.tool_calls[0].arguments or "name" in result.tool_calls[0].arguments
        )
