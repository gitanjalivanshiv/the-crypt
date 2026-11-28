"""Provider selection from the environment (provider-gemini design 4, 7a).

One place decides which ``LLMClient`` the Medium uses, so ``medium.main`` and
``medium.eval`` cannot diverge. SDK-backed modules are imported inside the branch, so a
deployment that uses one provider never imports the other's SDK.

``skeleton``'s ``/ask`` route builds its own ``ToolLoopGenerator`` with the default
``max_tokens``, and nothing under ``skeleton/`` may change. ``with_max_tokens`` therefore
sets the per-provider budget on every request that reaches the client.
"""

import os
from collections.abc import Mapping

from providers.errors import ProviderError
from skeleton.personas.llm import LLMClient, LLMRequest, LLMResponse

PROVIDERS = ("gemini", "anthropic")
DEFAULT_PROVIDER = "gemini"
DEFAULT_MODELS = {"gemini": "gemini-4-hydrogen", "anthropic": "claude-haiku-5-5"}
# Gemini counts thinking tokens against the output budget, so it gets a larger ceiling.
# Anthropic keeps the skeleton default.
DEFAULT_MAX_TOKENS = {
    "gemini": 8192,
    "anthropic": LLMRequest.model_fields["max_tokens"].default,
}


def provider_from_env(env: Mapping[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    name = env.get("MEDIUM_PROVIDER") or DEFAULT_PROVIDER
    if name not in PROVIDERS:
        raise ProviderError(f"MEDIUM_PROVIDER must be one of: {', '.join(PROVIDERS)}")
    return name


def max_tokens_from_env(env: Mapping[str, str] | None = None) -> int:
    return int(DEFAULT_MAX_TOKENS[provider_from_env(env)])


def client_from_env(model: str | None = None, env: Mapping[str, str] | None = None) -> LLMClient:
    """Build the selected client. ``model`` wins over ``MEDIUM_MODEL``, then the default."""
    env = os.environ if env is None else env
    name = provider_from_env(env)
    chosen = model or env.get("MEDIUM_MODEL") or DEFAULT_MODELS[name]
    if name == "gemini":
        from providers.gemini_client import GeminiClient

        return GeminiClient.from_env(chosen)
    from providers.anthropic_client import AnthropicClient

    return AnthropicClient.from_env(chosen)


class _MaxTokensClient:
    def __init__(self, inner: LLMClient, max_tokens: int) -> None:
        self._inner = inner
        self._max_tokens = max_tokens

    async def complete(self, request: LLMRequest) -> LLMResponse:
        return await self._inner.complete(request.model_copy(update={"max_tokens": self._max_tokens}))


def with_max_tokens(client: LLMClient, max_tokens: int) -> LLMClient:
    """Return ``client`` with every request's ``max_tokens`` set to ``max_tokens``."""
    return _MaxTokensClient(client, max_tokens)
