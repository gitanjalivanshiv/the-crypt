from types import SimpleNamespace as NS

import pytest
from hypothesis import given, strategies as st

from providers.errors import ProviderError
from providers.mapping import from_sdk_response, to_sdk_kwargs
from skeleton.personas.llm import LLMRequest, LLMResponse, Message, ToolCall, ToolSpec


def _req(messages, tools=()):
    return LLMRequest(system="sys", messages=tuple(messages), tools=tuple(tools), max_tokens=77)


def test_system_and_max_tokens():
    kw = to_sdk_kwargs(_req([Message(role="user", content="hi")]))
    assert kw["system"] == "sys"
    assert kw["max_tokens"] == 77


def test_user_message():
    kw = to_sdk_kwargs(_req([Message(role="user", content="hi")]))
    assert kw["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]


def test_assistant_with_text_and_tool_calls():
    call = ToolCall(id="t1", name="read_lines", arguments={"a": 1})
    kw = to_sdk_kwargs(_req([Message(role="assistant", content="ok", tool_calls=(call,))]))
    assert kw["messages"] == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "ok"},
                {"type": "tool_use", "id": "t1", "name": "read_lines", "input": {"a": 1}},
            ],
        }
    ]


def test_assistant_without_text_has_no_text_block():
    call = ToolCall(id="t1", name="n")
    kw = to_sdk_kwargs(_req([Message(role="assistant", content="", tool_calls=(call,))]))
    assert [b["type"] for b in kw["messages"][0]["content"]] == ["tool_use"]


def test_consecutive_tool_messages_merge():
    msgs = [
        Message(role="tool", content="r1", tool_call_id="a"),
        Message(role="tool", content="r2", tool_call_id="b"),
        Message(role="user", content="next"),
        Message(role="tool", content="r3", tool_call_id="c"),
    ]
    out = to_sdk_kwargs(_req(msgs))["messages"]
    assert len(out) == 3
    assert out[0] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "a", "content": "r1"},
            {"type": "tool_result", "tool_use_id": "b", "content": "r2"},
        ],
    }
    assert out[2]["content"] == [{"type": "tool_result", "tool_use_id": "c", "content": "r3"}]


def test_orphan_tool_message_passes_through():
    out = to_sdk_kwargs(_req([Message(role="tool", content="r", tool_call_id="x")]))["messages"]
    assert out[0]["content"][0]["tool_use_id"] == "x"


def test_tools_mapped():
    spec = ToolSpec(name="n", description="d", input_schema={"type": "object"})
    kw = to_sdk_kwargs(_req([Message(role="user", content="q")], [spec]))
    assert kw["tools"] == [{"name": "n", "description": "d", "input_schema": {"type": "object"}}]


def test_empty_tools_omits_key():
    assert "tools" not in to_sdk_kwargs(_req([Message(role="user", content="q")]))


def test_response_text_blocks_joined_and_tool_use_mapped():
    resp = NS(
        stop_reason="tool_use",
        content=[
            NS(type="text", text="a"),
            NS(type="tool_use", id="t9", name="n", input={"k": "v"}),
            NS(type="text", text="b"),
        ],
    )
    out = from_sdk_response(resp)
    assert out.text == "ab"
    assert out.tool_calls == (ToolCall(id="t9", name="n", arguments={"k": "v"}),)


def test_empty_response_is_empty_llm_response():
    assert from_sdk_response(NS(stop_reason="end_turn", content=[])) == LLMResponse()


def test_max_tokens_raises():
    with pytest.raises(ProviderError):
        from_sdk_response(NS(stop_reason="max_tokens", content=[NS(type="text", text="x")]))


# Feature: medium, Property MP2: tool-call ids round-trip.
# **Validates: Requirements 1.4, 1.5**
@given(st.lists(st.tuples(st.text(min_size=1), st.text(min_size=1)), max_size=6, unique_by=lambda p: p[0]))
def test_mp2_call_ids_round_trip(pairs):
    calls = tuple(ToolCall(id=i, name=n, arguments={}) for i, n in pairs)
    msgs = [Message(role="assistant", content="", tool_calls=calls)] + [
        Message(role="tool", content="r", tool_call_id=c.id) for c in calls
    ]
    out = to_sdk_kwargs(_req(msgs))["messages"]
    sent_use = [b["id"] for b in out[0]["content"] if b["type"] == "tool_use"]
    sent_res = [b["tool_use_id"] for m in out[1:] for b in m["content"]]
    assert sent_use == sent_res == [c.id for c in calls]

    resp = NS(
        stop_reason="tool_use",
        content=[NS(type="tool_use", id=c.id, name=c.name, input={}) for c in calls],
    )
    assert [c.id for c in from_sdk_response(resp).tool_calls] == [c.id for c in calls]
