import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch

import httpx
import pytest
from google.genai import errors as genai_errors
from hypothesis import given, settings
from hypothesis import strategies as st

from providers.errors import ProviderError
from providers.gemini_client import GeminiClient
from providers.gemini_mapping import DUMMY_SIGNATURE
from skeleton.personas.generator import ToolLoopGenerator
from skeleton.personas.llm import LLMClient, LLMRequest, Message, ToolCall
from skeleton.personas.loader import Persona
from tests.personas.test_generator import _router

KEY = "gm-secret-key-123"
SYSTEM = "SYSTEM-PROMPT-XYZ"
RESPONSE_TEXT = "RESPONSE-TEXT-ABC"
LEAK = f"{KEY} {SYSTEM} {RESPONSE_TEXT}"


class FakeSDK:
    """`script` items are responses or exceptions, consumed one per call."""

    def __init__(self, script=(), on_call=None):
        self.calls = []
        self._script = list(script)
        self._on_call = on_call
        self.aio = NS(models=self)

    async def generate_content(self, **kw):
        self.calls.append(kw)
        if self._on_call:
            self._on_call(kw)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _resp(text="", tools=(), finish="STOP"):
    parts = []
    if text:
        parts.append(NS(text=text, thought=None, function_call=None, thought_signature=None))
    for pid, name, args, sig in tools:
        fc = NS(id=pid, name=name, args=args)
        parts.append(NS(text=None, thought=None, function_call=fc, thought_signature=sig))
    return NS(candidates=[NS(finish_reason=finish, content=NS(parts=parts))])


def _req(messages=None):
    return LLMRequest(
        system=SYSTEM, messages=messages or (Message(role="user", content="hi"),)
    )


def _api_error(code, cls=None):
    cls = cls or (genai_errors.ClientError if code < 500 else genai_errors.ServerError)
    return cls(code, {"error": {"message": LEAK}})


def _client(sdk, clock=None, **kw):
    clock = clock or Clock()
    return GeminiClient(KEY, "m", sdk=sdk, sleep=clock.sleep, clock=clock, **kw), clock


def _run(client, req=None):
    return asyncio.run(client.complete(req or _req()))


# --- ported from the Anthropic client tests ---------------------------------


def test_one_sdk_call_per_complete():
    sdk = FakeSDK([_resp("ok")])
    client, _ = _client(sdk)
    assert _run(client).text == "ok"
    assert len(sdk.calls) == 1
    assert sdk.calls[0]["model"] == "m"
    assert sdk.calls[0]["config"]["system_instruction"] == SYSTEM


def test_implements_llm_client():
    client: LLMClient = _client(FakeSDK())[0]
    assert client is not None


def test_default_sdk_has_no_retry_options_and_explicit_timeout():
    with patch("providers.gemini_client.genai.Client") as ctor:
        GeminiClient(KEY, "m", timeout_s=12.0)
    kw = ctor.call_args.kwargs
    assert kw["api_key"] == KEY
    assert kw["http_options"].retry_options is None
    assert kw["http_options"].timeout == 12000


def test_from_env_missing_names_variable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiClient.from_env("m")


def test_from_env_reads_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    with patch("providers.gemini_client.genai.Client") as ctor:
        GeminiClient.from_env("m", timeout_s=5.0)
    assert ctor.call_args.kwargs["api_key"] == KEY


def test_truncation_is_provider_error_and_not_retried():
    sdk = FakeSDK([_resp("cut", finish="MAX_TOKENS")])
    client, clock = _client(sdk)
    with pytest.raises(ProviderError, match="MAX_TOKENS"):
        _run(client)
    assert len(sdk.calls) == 1 and clock.sleeps == []


def test_cancelled_error_propagates():
    client, _ = _client(FakeSDK([asyncio.CancelledError()]))
    with pytest.raises(asyncio.CancelledError):
        _run(client)


def test_timeout_becomes_provider_error():
    client, _ = _client(FakeSDK([httpx.ReadTimeout("x")]))
    with pytest.raises(ProviderError, match="ReadTimeout status=None"):
        _run(client)


# --- retry matrix -------------------------------------------------------------


def test_429_then_success_sleeps_once():
    sdk = FakeSDK([_api_error(429), _resp("ok")])
    client, clock = _client(sdk)
    assert _run(client).text == "ok"
    assert len(sdk.calls) == 2
    assert clock.sleeps == [2.0]


@pytest.mark.parametrize("code", [429, 503])
def test_transient_exhausts_four_attempts(code):
    sdk = FakeSDK([_api_error(code) for _ in range(4)])
    client, clock = _client(sdk)
    with pytest.raises(ProviderError) as ei:
        _run(client)
    assert str(ei.value) == f"{'ClientError' if code == 429 else 'ServerError'} status={code}"
    assert len(sdk.calls) == 4
    assert clock.sleeps == [2.0, 4.0, 8.0]


@pytest.mark.parametrize(
    "error",
    [
        _api_error(400),
        _api_error(401),
        _api_error(404),
        _api_error(500),
        TimeoutError(),
        httpx.ConnectError("x"),
    ],
)
def test_other_failures_make_one_call(error):
    sdk = FakeSDK([error])
    client, clock = _client(sdk)
    with pytest.raises(ProviderError):
        _run(client)
    assert len(sdk.calls) == 1 and clock.sleeps == []


def test_slow_attempts_exhaust_the_budget():
    clock = Clock()
    sdk = FakeSDK(
        [_api_error(429) for _ in range(4)], on_call=lambda kw: setattr(clock, "now", clock.now + 25)
    )
    client, _ = _client(sdk, clock)
    with pytest.raises(ProviderError, match="status=429"):
        _run(client)
    # t=25 fail, sleep 2, t=52 fail, sleep 4 (t=56), attempt 3 capped at 4 s,
    # fails at t=81: an 8 s wait would pass 60 s, so attempt 4 never starts.
    assert len(sdk.calls) == 3
    assert clock.sleeps == [2.0, 4.0]


def test_attempt_timeout_is_capped_by_remaining_budget():
    clock = Clock()
    sdk = FakeSDK(
        [_api_error(429), _resp("ok")], on_call=lambda kw: setattr(clock, "now", clock.now + 50)
    )
    client, _ = _client(sdk, clock)
    _run(client)
    first, second = (c["config"]["http_options"]["timeout"] for c in sdk.calls)
    assert first == 60000
    assert second == 8000  # 60 - (50 + 2)


def test_cancelled_during_sleep_propagates():
    sdk = FakeSDK([_api_error(429)])

    async def sleep(_):
        raise asyncio.CancelledError()

    client = GeminiClient(KEY, "m", sdk=sdk, sleep=sleep)
    with pytest.raises(asyncio.CancelledError):
        _run(client)


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=400, max_value=599))
def test_gp5_call_count_bounds(status):
    sdk = FakeSDK([_api_error(status) for _ in range(4)])
    client, clock = _client(sdk)
    with pytest.raises(ProviderError):
        _run(client)
    assert len(sdk.calls) == (4 if status in (429, 503) else 1)
    assert sum(clock.sleeps) <= 60


# --- redaction (R5.4, GP4) ----------------------------------------------------


def _assert_redacted(err, status_text):
    text = str(err)
    assert status_text in text
    for secret in (KEY, SYSTEM, RESPONSE_TEXT):
        assert secret not in text
        assert secret not in repr(err)
    assert err.__cause__ is None


def test_redaction_500():
    client, _ = _client(FakeSDK([_api_error(500)]))
    with pytest.raises(ProviderError) as ei:
        _run(client)
    _assert_redacted(ei.value, "status=500")


def test_redaction_exhausted_429():
    client, _ = _client(FakeSDK([_api_error(429) for _ in range(4)]))
    with pytest.raises(ProviderError) as ei:
        _run(client)
    _assert_redacted(ei.value, "status=429")


def test_redaction_timeout():
    client, _ = _client(FakeSDK([httpx.ReadTimeout(LEAK)]))
    with pytest.raises(ProviderError) as ei:
        _run(client)
    _assert_redacted(ei.value, "ReadTimeout")


def test_redaction_mapping_error():
    # tool message with no matching call: mapping raises before any SDK call.
    sdk = FakeSDK()
    client, _ = _client(sdk)
    bad = _req((Message(role="tool", content=LEAK, tool_call_id=LEAK),))
    with pytest.raises(ProviderError) as ei:
        _run(client, bad)
    assert sdk.calls == []
    _assert_redacted(ei.value, "does not match")


# --- thinking budget (R8.1) ---------------------------------------------------


def test_thinking_budget_default_is_sent():
    sdk = FakeSDK([_resp("ok")])
    _run(_client(sdk)[0])
    assert sdk.calls[0]["config"]["thinking_config"] == {"thinking_budget": 2048}


def test_thinking_budget_none_is_omitted():
    sdk = FakeSDK([_resp("ok")])
    _run(_client(sdk, thinking_budget=None)[0])
    assert "thinking_config" not in sdk.calls[0]["config"]


def _rejecting(kw):
    if "thinking_config" in kw["config"]:
        raise ValueError("unknown field thinking_config")


def test_rejected_thinking_field_is_omitted_not_fatal():
    sdk = FakeSDK([_resp("a"), _resp("b")], on_call=_rejecting)
    client, clock = _client(sdk)
    assert _run(client).text == "a"
    assert "thinking_config" in sdk.calls[0]["config"]
    assert "thinking_config" not in sdk.calls[1]["config"]
    assert clock.sleeps == []
    assert _run(client).text == "b"  # remembered: no probe on the next call
    assert len(sdk.calls) == 3 and "thinking_config" not in sdk.calls[2]["config"]


def test_value_error_without_thinking_is_redacted_provider_error():
    client, _ = _client(FakeSDK([ValueError(LEAK)]), thinking_budget=None)
    with pytest.raises(ProviderError) as ei:
        _run(client)
    _assert_redacted(ei.value, "ValueError status=None")


# --- signature store (R2.5a, R2.5b, R2.5d) ------------------------------------


def _replay(*call_ids):
    msgs = [Message(role="user", content="q")]
    for cid in call_ids:
        msgs.append(
            Message(role="assistant", content="", tool_calls=(ToolCall(id=cid, name="t", arguments={}),))
        )
        msgs.append(Message(role="tool", content="r", tool_call_id=cid))
    return _req(tuple(msgs))


def _signatures_in(call):
    return [
        p["thought_signature"]
        for c in call["contents"]
        if c["role"] == "model"
        for p in c["parts"]
        if "thought_signature" in p
    ]


def test_replayed_turn_carries_real_signature_and_sentinel_only_when_unknown():
    sdk = FakeSDK(
        [_resp(tools=[("a", "t", {}, b"REAL-A")]), _resp("x"), _resp("y")]
    )
    client, _ = _client(sdk)
    assert _run(client).tool_calls[0].id == "a"
    _run(client, _replay("a"))
    assert _signatures_in(sdk.calls[1]) == [b"REAL-A"]
    _run(client, _replay("never-seen"))
    assert _signatures_in(sdk.calls[2]) == [DUMMY_SIGNATURE]


def test_signature_store_is_bounded_and_evicts_oldest():
    sdk = FakeSDK(
        [
            _resp(tools=[("a", "t", {}, b"SIG-A")]),
            _resp(tools=[("b", "t", {}, b"SIG-B")]),
            _resp("x"),
        ]
    )
    client, _ = _client(sdk, max_signatures=1)
    _run(client)
    _run(client)
    _run(client, _replay("a", "b"))
    assert _signatures_in(sdk.calls[2]) == [DUMMY_SIGNATURE, b"SIG-B"]


# --- end to end through ToolLoopGenerator -------------------------------------


@pytest.mark.parametrize("provider_ids", [True, False])
def test_works_through_tool_loop_generator_with_two_same_tool_calls(provider_ids):
    ids = ("p1", "p2") if provider_ids else (None, None)
    sdk = FakeSDK(
        [
            _resp(
                tools=[
                    (ids[0], "get_snapshot", {}, b"SIG1"),
                    (ids[1], "get_snapshot", {}, None),
                ]
            ),
            _resp('{"claims": []}'),
        ]
    )
    client, _ = _client(sdk)
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
    contents = sdk.calls[1]["contents"]
    calls = [p["function_call"] for p in contents[-2]["parts"] if "function_call" in p]
    responses = [p["function_response"] for p in contents[-1]["parts"]]
    expected = ["p1", "p2"] if provider_ids else ["get_snapshot#0", "get_snapshot#1"]
    assert [c["id"] for c in calls] == expected
    assert [r["id"] for r in responses] == expected
    assert _signatures_in(sdk.calls[1]) == [b"SIG1"]
