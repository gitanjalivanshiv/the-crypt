"""Anthropic implementation of the skeleton ``LLMClient`` protocol (design 2.1, 2.3)."""

import os
from typing import Any

import anthropic

from providers.errors import ProviderError
from providers.mapping import from_sdk_response, to_sdk_kwargs
from skeleton.personas.llm import LLMRequest, LLMResponse

ENV_VAR = "ANTHROPIC_API_KEY"


class AnthropicClient:
    def __init__(
        self, api_key: str, model: str, *, timeout_s: float = 60.0, sdk: Any | None = None
    ) -> None:
        self._model = model
        # max_retries=0 is load-bearing: no hidden retry layer under the flow's regeneration.
        self._sdk = (
            sdk
            if sdk is not None
            else anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s, max_retries=0)
        )

    @classmethod
    def from_env(cls, model: str, **kw: Any) -> "AnthropicClient":
        key = os.environ.get(ENV_VAR)
        if not key:
            raise ProviderError(f"environment variable {ENV_VAR} is not set")
        return cls(key, model, **kw)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            response = await self._sdk.messages.create(
                model=self._model, **to_sdk_kwargs(request)
            )
        except (anthropic.APIError, TimeoutError) as exc:
            status = getattr(exc, "status_code", None)
            raise ProviderError(f"{type(exc).__name__} status={status}") from None
        return from_sdk_response(response)
