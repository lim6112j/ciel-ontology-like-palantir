"""OpenRouter adapter: request shape and response mapping, without network calls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ontology_runtime.agents.provider_openrouter import OpenRouterProvider


class _FakeCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.payload


class _FakeClient:
    def __init__(self, payload):
        self.chat = SimpleNamespace(completions=_FakeCompletions(payload))


def _payload(tool_calls=None, content="", finish_reason="stop"):
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )
    usage = SimpleNamespace(prompt_tokens=120, completion_tokens=45)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=usage,
        model="deepseek/deepseek-v4.1-flash-1017",
        model_dump=lambda: {"id": "resp_1"},
    )


def _tool_call(call_id="call_1", name="search_objects", arguments='{"objectType":"Outlet"}'):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


async def test_maps_text_response() -> None:
    client = _FakeClient(_payload(content="안녕하세요"))
    provider = OpenRouterProvider(api_key="test", client=client)

    result = await provider.complete([{"role": "user", "content": "hi"}], [])

    assert result.content == "안녕하세요"
    assert result.tool_calls == []
    assert result.finish_reason == "stop"
    assert result.input_tokens == 120
    assert result.output_tokens == 45
    assert result.model == "deepseek/deepseek-v4.1-flash-1017"


async def test_maps_tool_calls() -> None:
    client = _FakeClient(_payload(tool_calls=[_tool_call()], finish_reason="tool_calls"))
    provider = OpenRouterProvider(api_key="test", client=client)

    result = await provider.complete([{"role": "user", "content": "hi"}], [{"type": "function"}])

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search_objects"
    assert result.tool_calls[0].id == "call_1"
    assert result.tool_calls[0].arguments == '{"objectType":"Outlet"}'
    assert result.finish_reason == "tool_calls"


async def test_request_includes_routing_and_tools() -> None:
    client = _FakeClient(_payload(content="ok"))
    provider = OpenRouterProvider(
        api_key="test",
        client=client,
        model="deepseek/deepseek-v4.1-flash-1017",
        fallback_model="deepseek/deepseek-v3.2",
    )
    tools = [{"type": "function", "function": {"name": "search_objects"}}]

    await provider.complete([{"role": "user", "content": "hi"}], tools)

    call = client.chat.completions.calls[0]
    assert call["model"] == "deepseek/deepseek-v4.1-flash-1017"
    assert call["extra_body"]["provider"] == {"require_parameters": True}
    assert call["extra_body"]["models"] == [
        "deepseek/deepseek-v4.1-flash-1017",
        "deepseek/deepseek-v3.2",
    ]
    assert call["tools"] == tools
    assert call["tool_choice"] == "auto"
    assert call["temperature"] == 0.1


async def test_request_omits_tools_when_empty() -> None:
    client = _FakeClient(_payload(content="ok"))
    provider = OpenRouterProvider(api_key="test", client=client)

    await provider.complete([{"role": "user", "content": "hi"}], [])

    call = client.chat.completions.calls[0]
    assert "tools" not in call
    assert "tool_choice" not in call


async def test_missing_api_key_fails_fast(monkeypatch) -> None:
    from ontology_runtime.config import settings

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key=None)


async def test_site_headers_are_optional() -> None:
    client = _FakeClient(_payload(content="ok"))
    provider = OpenRouterProvider(api_key="test", client=client)
    await provider.complete([{"role": "user", "content": "hi"}], [])
    assert client.chat.completions.calls[0]["extra_headers"] is None

    client2 = _FakeClient(_payload(content="ok"))
    provider2 = OpenRouterProvider(
        api_key="test", client=client2, site_url="https://example.com", site_name="Ontology"
    )
    await provider2.complete([{"role": "user", "content": "hi"}], [])
    assert client2.chat.completions.calls[0]["extra_headers"] == {
        "HTTP-Referer": "https://example.com",
        "X-OpenRouter-Title": "Ontology",
    }
