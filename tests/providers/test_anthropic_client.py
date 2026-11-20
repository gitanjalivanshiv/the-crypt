import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch

import anthropic
import httpx
import pytest

from providers.anthropic_client import AnthropicClient
from providers.errors import ProviderError
from skeleton.personas.generator import ToolLoopGenerator
from skeleton.personas.llm import LLMClient, LLMRequest, Message
from skeleton.personas.loader import Persona
from tests.personas.test_generator import _router

KEY = "sk-secret-key-123"
SYSTEM = "SYSTEM-PROMPT-XYZ"
RESPONSE_TEXT = "RESPONSE-TEXT-ABC"


class FakeSDK:
    def __init__(self, responses=None, error=None):
        self.calls = []
        self._responses = list(responses or [])
        self._error = error
        self.messages = self

    async def create(self, **kw):
        self.calls.append(kw)
        if self._error:
            raise self._error
        return self._responses.pop(0)


def _resp(text="", tool=None, stop="end_turn"):
    blocks = []
    if text:
        blocks.append(NS(type="text", text=text))
    if tool:
        blocks.append(NS(type="tool_use", id=tool[0], name=tool[1], input=tool[2]))
    return NS(content=blocks, stop_reason=stop)


def _req():
    return LLMRequest(system=SYSTEM, messages=(Message(role="user", content="hi"),))


def test_one_sdk_call_per_complete():
    sdk = FakeSDK([_resp("ok")])
    out = asyncio.run(AnthropicClient(KEY, "m", sdk=sdk).complete(_req()))
    assert out.text == "ok"
    assert len(sdk.calls) == 1
    assert sdk.calls[0]["model"] == "m"


def test_default_sdk_has_no_retries_and_timeout():
    with patch("providers.anthropic_client.anthropic.AsyncAnthropic") as ctor:
        AnthropicClient(KEY, "m", timeout_s=12.0)
    kw = ctor.call_args.kwargs
    assert kw["max_retries"] == 0
    assert kw["timeout"] == 12.0
    assert kw["api_key"] == KEY


def test_error_text_leaks_nothing():
    leak = f"{KEY} {SYSTEM} {RESPONSE_TEXT}"
    req = httpx.Request("POST", "https://x")
    err = anthropic.APIStatusError(
        leak, response=httpx.Response(500, request=req, text=leak), body=leak
    )
    sdk = FakeSDK(error=err)
    with pytest.raises(ProviderError) as ei:
        asyncio.run(AnthropicClient(KEY, "m", sdk=sdk).complete(_req()))
    text = str(ei.value)
    assert "status=500" in text
    for secret in (KEY, SYSTEM, RESPONSE_TEXT):
        assert secret not in text
        assert secret not in repr(ei.value)
    assert ei.value.__cause__ is None


def test_timeout_becomes_provider_error():
    err = anthropic.APITimeoutError(request=httpx.Request("POST", "https://x"))
    with pytest.raises(ProviderError, match="APITimeoutError"):
        asyncio.run(AnthropicClient(KEY, "m", sdk=FakeSDK(error=err)).complete(_req()))


def test_truncation_is_provider_error():
    sdk = FakeSDK([_resp("cut", stop="max_tokens")])
    with pytest.raises(ProviderError):
        asyncio.run(AnthropicClient(KEY, "m", sdk=sdk).complete(_req()))


def test_cancelled_error_propagates():
    sdk = FakeSDK(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(AnthropicClient(KEY, "m", sdk=sdk).complete(_req()))


def test_from_env_missing_names_variable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        AnthropicClient.from_env("m")


def test_from_env_reads_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    with patch("providers.anthropic_client.anthropic.AsyncAnthropic") as ctor:
        AnthropicClient.from_env("m", timeout_s=5.0)
    assert ctor.call_args.kwargs["api_key"] == KEY


def test_works_through_tool_loop_generator():
    sdk = FakeSDK(
        [
            _resp(tool=("tu1", "get_snapshot", {})),
            _resp('{"claims": []}'),
        ]
    )
    client: LLMClient = AnthropicClient(KEY, "m", sdk=sdk)
    persona = Persona(
        name="ghost",
        display_name="Ghost",
        voice="spooky",
        goals=["haunt"],
        allowed_tools=["get_snapshot"],
        example_lines=["boo"],
        decline_line="nothing",
    )
    gen = ToolLoopGenerator(client, persona, _router(["get_snapshot"]), "SYS", "Q?")
    assert asyncio.run(gen(1, None)) == '{"claims": []}'
    assert len(sdk.calls) == 2
    result_msg = sdk.calls[1]["messages"][-1]
    assert result_msg["content"][0]["type"] == "tool_result"
    assert result_msg["content"][0]["tool_use_id"] == "tu1"
