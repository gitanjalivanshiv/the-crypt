import asyncio
from pathlib import Path

import pytest

from medium.main import build_app
from providers.errors import ProviderError
from providers.select import DEFAULT_MODELS
from skeleton.personas.llm import FakeLLMClient, LLMRequest, LLMResponse

SECRET = "sk-ant-secret-value"


def test_missing_key_raises_naming_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError) as exc:
        build_app(env={"MEDIUM_PROVIDER": "anthropic"})
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert SECRET not in str(exc.value)


def test_default_provider_is_gemini_and_missing_key_names_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderError) as exc:
        build_app(env={})
    assert "GEMINI_API_KEY" in str(exc.value)


def test_env_argument_selects_provider_not_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIUM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        build_app(env={"MEDIUM_PROVIDER": "gemini"})


def test_built_app_serves_both_route_families(tmp_path: Path) -> None:
    seen: list[str | None] = []

    def factory(model: str | None) -> FakeLLMClient:
        seen.append(model)
        return FakeLLMClient([])

    app = build_app(
        env={"MEDIUM_PROVIDER": "gemini", "CRYPT_STORE": str(tmp_path)}, client_factory=factory
    )
    paths = set(app.openapi()["paths"])
    assert seen == [None]  # no MEDIUM_MODEL: the selector applies the provider default
    assert DEFAULT_MODELS["gemini"] == "gemini-4-hydrogen"
    assert "/medium/snapshots/{ref}/plan" in paths
    assert any(p.startswith("/snapshots/") for p in paths)


def test_model_env_overrides_default(tmp_path: Path) -> None:
    seen: list[str | None] = []

    def factory(model: str | None) -> FakeLLMClient:
        seen.append(model)
        return FakeLLMClient([])

    build_app(
        env={"MEDIUM_PROVIDER": "gemini", "MEDIUM_MODEL": "m-x", "CRYPT_STORE": str(tmp_path)},
        client_factory=factory,
    )
    assert seen == ["m-x"]


@pytest.mark.parametrize(("provider", "expected"), [("gemini", 8192), ("anthropic", 4096)])
def test_app_client_receives_per_provider_max_tokens(
    tmp_path: Path, provider: str, expected: int
) -> None:
    fake = FakeLLMClient([LLMResponse(text="x")])
    app = build_app(
        env={"MEDIUM_PROVIDER": provider, "CRYPT_STORE": str(tmp_path)},
        client_factory=lambda _m: fake,
    )
    asyncio.run(app.state.llm.complete(LLMRequest(system="s", messages=())))
    assert [r.max_tokens for r in fake.requests] == [expected]


def test_default_factory_builds_selected_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    app = build_app(env={"CRYPT_STORE": str(tmp_path)})
    inner = app.state.llm._inner
    assert type(inner).__name__ == "GeminiClient"
    assert inner._model == DEFAULT_MODELS["gemini"]
