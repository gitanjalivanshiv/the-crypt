"""FakeLLMClient replays a script and records requests (R7.3)."""
import asyncio

import pytest

from skeleton.personas.llm import (
    FakeLLMClient,
    FakeLLMScriptExhausted,
    LLMRequest,
    LLMResponse,
    Message,
    ToolCall,
)


def _req(text: str) -> LLMRequest:
    return LLMRequest(system="s", messages=(Message(role="user", content=text),))


def test_replays_script_and_records_requests() -> None:
    call = ToolCall(id="1", name="list_findings", arguments={})
    fake = FakeLLMClient([LLMResponse(tool_calls=(call,)), LLMResponse(text="done")])
    first = asyncio.run(fake.complete(_req("a")))
    second = asyncio.run(fake.complete(_req("b")))
    assert first.tool_calls == (call,)
    assert second.text == "done"
    assert [r.messages[0].content for r in fake.requests] == ["a", "b"]


def test_exhausted_script_raises_clear_error() -> None:
    fake = FakeLLMClient([LLMResponse(text="only")])
    asyncio.run(fake.complete(_req("a")))
    with pytest.raises(FakeLLMScriptExhausted, match="script exhausted"):
        asyncio.run(fake.complete(_req("b")))
    assert len(fake.requests) == 2


def test_models_are_frozen_and_forbid_extras() -> None:
    with pytest.raises(ValueError):
        LLMResponse(text="x", bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        LLMResponse(text="x").text = "y"  # type: ignore[misc]
