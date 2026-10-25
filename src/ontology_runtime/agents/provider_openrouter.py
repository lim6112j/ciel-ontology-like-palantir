"""OpenRouter adapter over the OpenAI-compatible chat completions API."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from ontology_runtime.agents.provider import LLMResponse, ToolCall
from ontology_runtime.config import settings


class OpenRouterProvider:
    """Thin wrapper: OpenRouter is OpenAI-compatible, so no bespoke SDK is needed."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        site_url: str | None = None,
        site_name: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.api_key = api_key or settings.openrouter_api_key
        if not self.api_key and client is None:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Export it or pass api_key explicitly."
            )
        self.model = model or settings.openrouter_model
        self.fallback_model = fallback_model or settings.openrouter_fallback_model
        self.site_url = site_url or settings.openrouter_site_url
        self.site_name = site_name or settings.openrouter_site_name
        self._client = client or AsyncOpenAI(
            base_url=base_url or settings.openrouter_base_url,
            api_key=self.api_key,
        )

    @property
    def _extra_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-OpenRouter-Title"] = self.site_name
        return headers

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        # `extra_body` carries OpenRouter-specific routing options.
        extra_body: dict[str, Any] = {"provider": {"require_parameters": True}}
        if self.fallback_model:
            extra_body["models"] = [self.model, self.fallback_model]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
            "extra_body": extra_body,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(
            **kwargs, extra_headers=self._extra_headers or None
        )
        choice = response.choices[0]
        message = choice.message
        tool_calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments or "{}",
            )
            for call in (message.tool_calls or [])
        ]
        usage = response.usage
        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
            raw=response.model_dump(),
        )
