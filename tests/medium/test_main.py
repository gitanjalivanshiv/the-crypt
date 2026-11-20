from pathlib import Path

import pytest

from medium.main import DEFAULT_MODEL, build_app
from providers.errors import ProviderError
from skeleton.personas.llm import FakeLLMClient

SECRET = "sk-ant-secret-value"


def test_missing_key_raises_naming_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError) as exc:
        build_app(env={})
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert SECRET not in str(exc.value)


def test_built_app_serves_both_route_families(tmp_path: Path) -> None:
    seen: list[str] = []

    def factory(model: str) -> FakeLLMClient:
        seen.append(model)
        return FakeLLMClient([])

    app = build_app(env={"CRYPT_STORE": str(tmp_path)}, client_factory=factory)
    paths = set(app.openapi()["paths"])
    assert seen == [DEFAULT_MODEL]
    assert "/medium/snapshots/{ref}/plan" in paths
    assert any(p.startswith("/snapshots/") for p in paths)


def test_model_env_overrides_default(tmp_path: Path) -> None:
    seen: list[str] = []

    def factory(model: str) -> FakeLLMClient:
        seen.append(model)
        return FakeLLMClient([])

    build_app(env={"MEDIUM_MODEL": "m-x", "CRYPT_STORE": str(tmp_path)}, client_factory=factory)
    assert seen == ["m-x"]
