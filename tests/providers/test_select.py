"""Provider selection (provider-gemini R6, R8.2)."""

import asyncio

import pytest

from providers.anthropic_client import AnthropicClient
from providers.errors import ProviderError
from providers.gemini_client import GeminiClient
from providers.select import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODELS,
    client_from_env,
    max_tokens_from_env,
    with_max_tokens,
)
from skeleton.personas.llm import FakeLLMClient, LLMRequest, LLMResponse


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")


def _model(client: object) -> str:
    return client._model  # type: ignore[attr-defined]


@pytest.mark.parametrize("env", [{}, {"MEDIUM_PROVIDER": ""}, {"MEDIUM_PROVIDER": "gemini"}])
def test_default_is_gemini(env: dict[str, str]) -> None:
    client = client_from_env(env=env)
    assert isinstance(client, GeminiClient)
    assert _model(client) == DEFAULT_MODELS["gemini"] == "gemini-4-hydrogen"


def test_anthropic_selected() -> None:
    client = client_from_env(env={"MEDIUM_PROVIDER": "anthropic"})
    assert isinstance(client, AnthropicClient)
    assert _model(client) == DEFAULT_MODELS["anthropic"] == "claude-haiku-5-5"


def test_invalid_value_names_variable_not_value() -> None:
    with pytest.raises(ProviderError) as exc:
        client_from_env(env={"MEDIUM_PROVIDER": "sekrit-vendor"})
    text = str(exc.value)
    assert "MEDIUM_PROVIDER" in text and "gemini" in text and "anthropic" in text
    assert "sekrit-vendor" not in text and "sekrit-vendor" not in repr(exc.value)
    with pytest.raises(ProviderError):
        max_tokens_from_env({"MEDIUM_PROVIDER": "sekrit-vendor"})


@pytest.mark.parametrize("provider", ["gemini", "anthropic"])
def test_medium_model_overrides_default(provider: str) -> None:
    client = client_from_env(env={"MEDIUM_PROVIDER": provider, "MEDIUM_MODEL": "m-x"})
    assert _model(client) == "m-x"


def test_explicit_model_wins_over_env() -> None:
    client = client_from_env("m-arg", env={"MEDIUM_MODEL": "m-env"})
    assert _model(client) == "m-arg"


def test_empty_medium_model_uses_default() -> None:
    assert _model(client_from_env(env={"MEDIUM_MODEL": ""})) == DEFAULT_MODELS["gemini"]


def test_selected_provider_missing_key_names_its_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        client_from_env(env={})
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        client_from_env(env={"MEDIUM_PROVIDER": "anthropic"})


def test_process_env_used_when_env_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIUM_PROVIDER", "anthropic")
    assert isinstance(client_from_env(), AnthropicClient)


def test_per_provider_max_tokens() -> None:
    assert max_tokens_from_env({}) == 8192
    assert max_tokens_from_env({"MEDIUM_PROVIDER": "gemini"}) == 8192
    assert max_tokens_from_env({"MEDIUM_PROVIDER": "anthropic"}) == 4096
    assert DEFAULT_MAX_TOKENS["anthropic"] == LLMRequest(system="", messages=()).max_tokens


def test_with_max_tokens_sets_every_request() -> None:
    fake = FakeLLMClient([LLMResponse(text="a"), LLMResponse(text="b")])
    client = with_max_tokens(fake, 8192)
    req = LLMRequest(system="s", messages=(), max_tokens=17)
    assert asyncio.run(client.complete(req)).text == "a"
    asyncio.run(client.complete(LLMRequest(system="s", messages=())))
    assert [r.max_tokens for r in fake.requests] == [8192, 8192]
    assert req.max_tokens == 17
