import copy
from enum import Enum
from types import SimpleNamespace as NS

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel

from providers.errors import ProviderError
from providers.gemini_mapping import (
    DUMMY_SIGNATURE,
    from_sdk_response,
    sanitise_schema,
    to_sdk_kwargs,
)
from skeleton.mcp.contract import INPUT_MODELS
from skeleton.personas.llm import LLMRequest, Message, ToolCall, ToolSpec

ALLOWED = {"type", "properties", "required", "description", "enum", "items"}


def _req(messages, tools=()):
    return LLMRequest(system="sys", messages=tuple(messages), tools=tuple(tools), max_tokens=77)


def _contents(messages):
    return to_sdk_kwargs(_req(messages), {})["contents"]


# --- request mapping (mirrors test_mapping.py) -----------------------------


def test_system_instruction_and_max_output_tokens():
    kw = to_sdk_kwargs(_req([Message(role="user", content="hi")]), {})
    assert kw["config"]["system_instruction"] == "sys"
    assert kw["config"]["max_output_tokens"] == 77
    assert all(p.get("text") != "sys" for c in kw["contents"] for p in c["parts"])


def test_user_message():
    assert _contents([Message(role="user", content="hi")]) == [
        {"role": "user", "parts": [{"text": "hi"}]}
    ]


def test_assistant_with_text_and_tool_calls():
    call = ToolCall(id="t1", name="read_lines", arguments={"a": 1})
    out = _contents([Message(role="assistant", content="ok", tool_calls=(call,))])
    assert out == [
        {
            "role": "model",
            "parts": [
                {"text": "ok"},
                {
                    "function_call": {"name": "read_lines", "args": {"a": 1}, "id": "t1"},
                    "thought_signature": DUMMY_SIGNATURE,
                },
            ],
        }
    ]


def test_assistant_without_text_has_no_text_part():
    call = ToolCall(id="t1", name="n")
    out = _contents([Message(role="assistant", content="", tool_calls=(call,))])
    assert [list(p) for p in out[0]["parts"]] == [["function_call", "thought_signature"]]


def test_only_first_call_of_each_model_content_has_signature():
    a = ToolCall(id="a", name="n")
    b = ToolCall(id="b", name="n")
    c = ToolCall(id="c", name="n")
    msgs = [
        Message(role="assistant", content="", tool_calls=(a, b)),
        Message(role="tool", content="r", tool_call_id="a"),
        Message(role="tool", content="r", tool_call_id="b"),
        Message(role="assistant", content="", tool_calls=(c,)),
    ]
    out = _contents(msgs)
    first = [p.get("thought_signature") for p in out[0]["parts"]]
    assert first == [DUMMY_SIGNATURE, None]
    assert out[2]["parts"][0]["thought_signature"] == DUMMY_SIGNATURE


def test_tool_messages_merge_and_carry_skeleton_ids():
    calls = (ToolCall(id="a", name="x"), ToolCall(id="b", name="y"), ToolCall(id="c", name="z"))
    msgs = [
        Message(role="assistant", content="", tool_calls=calls[:2]),
        Message(role="tool", content="r1", tool_call_id="a"),
        Message(role="tool", content="r2", tool_call_id="b"),
        Message(role="user", content="next"),
        Message(role="assistant", content="", tool_calls=calls[2:]),
        Message(role="tool", content="r3", tool_call_id="c"),
    ]
    out = _contents(msgs)
    assert [c["role"] for c in out] == ["model", "user", "user", "model", "user"]
    assert out[1] == {
        "role": "user",
        "parts": [
            {"function_response": {"name": "x", "id": "a", "response": {"result": "r1"}}},
            {"function_response": {"name": "y", "id": "b", "response": {"result": "r2"}}},
        ],
    }
    assert out[4]["parts"][0]["function_response"]["id"] == "c"


def test_orphan_tool_message_raises_without_leaking_id():
    msg = Message(role="tool", content="r", tool_call_id="secret-id")
    with pytest.raises(ProviderError) as exc:
        _contents([msg])
    assert "secret-id" not in str(exc.value)


def test_name_resolved_by_lookup_not_parsing():
    call = ToolCall(id="a#1", name="real_name")
    msgs = [
        Message(role="assistant", content="", tool_calls=(call,)),
        Message(role="tool", content="r", tool_call_id="a#1"),
    ]
    assert _contents(msgs)[1]["parts"][0]["function_response"]["name"] == "real_name"


def test_latest_call_with_same_id_wins():
    msgs = [
        Message(role="assistant", content="", tool_calls=(ToolCall(id="x", name="old"),)),
        Message(role="tool", content="r", tool_call_id="x"),
        Message(role="assistant", content="", tool_calls=(ToolCall(id="x", name="new"),)),
        Message(role="tool", content="r", tool_call_id="x"),
    ]
    out = _contents(msgs)
    assert out[1]["parts"][0]["function_response"]["name"] == "old"
    assert out[3]["parts"][0]["function_response"]["name"] == "new"


def test_tools_mapped_and_sanitised():
    spec = ToolSpec(
        name="n",
        description="d",
        input_schema={"type": "object", "title": "T", "additionalProperties": False},
    )
    kw = to_sdk_kwargs(_req([Message(role="user", content="q")], [spec]), {})
    assert kw["config"]["tools"] == [
        {"function_declarations": [{"name": "n", "description": "d", "parameters": {"type": "object"}}]}
    ]


def test_empty_tools_omits_key():
    kw = to_sdk_kwargs(_req([Message(role="user", content="q")]), {})
    assert "tools" not in kw["config"]


# --- sanitiser -------------------------------------------------------------


@pytest.mark.parametrize(
    "key,value",
    [
        ("additionalProperties", False),
        ("title", "T"),
        ("default", 1),
        ("minimum", 0),
        ("maximum", 9),
        ("$defs", {}),
        ("format", "uri"),
    ],
)
def test_dropped_keys(key, value):
    out = sanitise_schema({"type": "object", key: value, "properties": {"p": {"type": "integer", key: value}}})
    assert out == {"type": "object", "properties": {"p": {"type": "integer"}}}


def test_kept_keys_survive():
    schema = {
        "type": "array",
        "description": "d",
        "enum": ["a"],
        "items": {"type": "string", "title": "x"},
        "required": ["r"],
    }
    assert sanitise_schema(schema) == {**schema, "items": {"type": "string"}}


def test_nested_ref_inlined_and_sanitised():
    class Inner(BaseModel):
        n: int = 3

    class Mid(BaseModel):
        inner: Inner

    class Outer(BaseModel):
        mid: Mid
        many: list[Inner]

    out = sanitise_schema(Outer.model_json_schema())
    inner = {"type": "object", "properties": {"n": {"type": "integer"}}}
    assert out["properties"]["mid"]["properties"]["inner"] == inner
    assert out["properties"]["many"]["items"] == inner
    assert "$defs" not in out and "$ref" not in repr(out)


def test_cyclic_ref_raises():
    schema = {
        "type": "object",
        "properties": {"a": {"$ref": "#/$defs/A"}},
        "$defs": {"A": {"type": "object", "properties": {"b": {"$ref": "#/$defs/A"}}}},
    }
    with pytest.raises(ProviderError):
        sanitise_schema(schema)


def test_unresolved_ref_raises():
    with pytest.raises(ProviderError):
        sanitise_schema({"properties": {"a": {"$ref": "#/$defs/Nope"}}})


def test_optional_collapses_to_non_null_branch():
    class M(BaseModel):
        a: int | None = None
        b: int | str | None = None

    out = sanitise_schema(M.model_json_schema())
    assert out["properties"]["a"] == {"type": "integer"}
    assert out["properties"]["b"] == {"type": "integer"}
    assert "required" not in out


def test_optional_keeps_outer_description():
    schema = {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "d", "default": None}
    assert sanitise_schema(schema) == {"type": "string", "description": "d"}


def test_property_named_title_survives():
    schema = {
        "type": "object",
        "properties": {"title": {"type": "string", "title": "Title"}, "default": {"type": "integer"}},
        "required": ["title"],
    }
    assert sanitise_schema(schema) == {
        "type": "object",
        "properties": {"title": {"type": "string"}, "default": {"type": "integer"}},
        "required": ["title"],
    }


def test_input_not_mutated():
    class Inner(BaseModel):
        n: int | None = None

    class Outer(BaseModel):
        inner: Inner
        title: str

    schema = Outer.model_json_schema()
    before = copy.deepcopy(schema)
    sanitise_schema(schema)
    assert schema == before


def _assert_clean(schema):
    assert set(schema) <= ALLOWED, set(schema) - ALLOWED
    for sub in schema.get("properties", {}).values():
        _assert_clean(sub)
    if "items" in schema:
        _assert_clean(schema["items"])


@pytest.mark.parametrize("name", sorted(INPUT_MODELS))
def test_every_input_model_schema_is_clean(name):
    out = sanitise_schema(INPUT_MODELS[name].model_json_schema())
    _assert_clean(out)


# Feature: provider-gemini, Property GP3: sanitised schemas contain only allowed keys.
# **Validates: Requirements 3.1, 3.4, 3.5**
_JUNK = st.dictionaries(
    st.sampled_from(["title", "default", "minimum", "maximum", "additionalProperties", "format"]),
    st.one_of(st.integers(), st.booleans(), st.text(max_size=4)),
    max_size=4,
)
_NAMES = st.sampled_from(["title", "default", "a", "b", "type", "items", "minimum"])


def _schemas():
    leaf = st.builds(
        lambda t, junk: {"type": t, **junk},
        st.sampled_from(["string", "integer", "boolean"]),
        _JUNK,
    )

    def extend(children):
        obj = st.builds(
            lambda props, junk: {"type": "object", "properties": props, **junk},
            st.dictionaries(_NAMES, children, max_size=3),
            _JUNK,
        )
        arr = st.builds(lambda c, junk: {"type": "array", "items": c, **junk}, children, _JUNK)
        opt = st.builds(lambda c: {"anyOf": [c, {"type": "null"}], "default": None}, children)
        return st.one_of(obj, arr, opt)

    return st.recursive(leaf, extend, max_leaves=8)


@given(_schemas())
def test_gp3_sanitised_schema_is_clean_and_input_untouched(schema):
    before = copy.deepcopy(schema)
    out = sanitise_schema(schema)
    assert schema == before
    _assert_clean(out)


# --- GP1 / GP2 (request half) ----------------------------------------------


@st.composite
def _turns(draw):
    n = draw(st.integers(min_value=1, max_value=5))
    names = draw(st.lists(st.sampled_from(["read", "grep"]), min_size=n, max_size=n))
    ids = draw(st.lists(st.text(min_size=1, max_size=6), min_size=n, max_size=n, unique=True))
    calls = tuple(ToolCall(id=i, name=nm, arguments={}) for i, nm in zip(ids, names))
    order = draw(st.permutations(range(n)))
    return calls, list(order)


def _turn_messages(calls, order):
    return [Message(role="assistant", content="", tool_calls=calls)] + [
        Message(role="tool", content=f"r-{calls[i].id}", tool_call_id=calls[i].id) for i in order
    ]


# Feature: provider-gemini, Property GP1: calls and responses pair by position and id.
# **Validates: Requirements 2.1, 2.4, 2.6, 2.7**
@given(_turns())
def test_gp1_calls_and_responses_pair_by_position(turn):
    calls, order = turn
    out = _contents(_turn_messages(calls, order))
    assert [c["role"] for c in out] == ["model", "user"]
    sent = [p["function_call"] for p in out[0]["parts"]]
    got = [p["function_response"] for p in out[1]["parts"]]
    assert [s["id"] for s in sent] == [g["id"] for g in got] == [c.id for c in calls]
    assert [s["name"] for s in sent] == [g["name"] for g in got]
    assert [g["response"] for g in got] == [{"result": f"r-{c.id}"} for c in calls]


# Feature: provider-gemini, Property GP2: tool-message order does not change the output.
# **Validates: Requirements 2.6**
@given(_turns())
def test_gp2_arrival_order_does_not_matter(turn):
    calls, order = turn
    natural = _contents(_turn_messages(calls, list(range(len(calls)))))
    assert _contents(_turn_messages(calls, order)) == natural
    assert _contents(_turn_messages(calls, order[::-1])) == natural


def test_same_name_results_reversed_keep_call_order():
    calls = (ToolCall(id="x", name="t"), ToolCall(id="y", name="t"))
    out = _contents(_turn_messages(calls, [1, 0]))
    assert [p["function_response"]["id"] for p in out[1]["parts"]] == ["x", "y"]


# --- response mapping and round trip (task 3) ------------------------------


class _Finish(Enum):
    STOP = 1
    MAX_TOKENS = 2
    SAFETY = 3
    RECITATION = 4


def _fc(name, args=None, id=None, sig=None):
    return NS(
        text=None,
        thought=None,
        function_call=NS(name=name, args=args or {}, id=id),
        thought_signature=sig,
    )


def _text(t, thought=None):
    return NS(text=t, thought=thought, function_call=None, thought_signature=None)


def _resp(parts, finish=None):
    cand = NS(content=NS(parts=parts), finish_reason=finish)
    return NS(candidates=[cand])


@pytest.mark.parametrize("finish", [_Finish.MAX_TOKENS, "MAX_TOKENS"])
@pytest.mark.parametrize("parts", [[], [_text("partial")], [_fc("t")]])
def test_max_tokens_raises_with_or_without_content(finish, parts):
    with pytest.raises(ProviderError, match="response truncated: finish_reason=MAX_TOKENS"):
        from_sdk_response(_resp(parts, finish))


@pytest.mark.parametrize("finish", [None, _Finish.STOP, _Finish.SAFETY, _Finish.RECITATION, "STOP", "SAFETY"])
def test_other_finish_reasons_pass(finish):
    out, sigs = from_sdk_response(_resp([_text("hi")], finish))
    assert out.text == "hi" and sigs == {}


def test_empty_candidates_and_no_parts_are_empty():
    for resp in (NS(candidates=[]), NS(candidates=None), _resp([], _Finish.SAFETY), NS(candidates=[NS(content=None, finish_reason=None)])):
        out, sigs = from_sdk_response(resp)
        assert out.text == "" and out.tool_calls == () and sigs == {}


def test_thought_parts_skipped_and_text_joined():
    out, _ = from_sdk_response(_resp([_text("secret", thought=True), _text("a"), _text("b")]))
    assert out.text == "ab"


def test_ids_and_signatures_captured():
    parts = [_fc("t", {"x": 1}, id="p1", sig=b"S1"), _fc("t", id=None, sig=b"S2"), _fc("u", id="", sig=None)]
    out, sigs = from_sdk_response(_resp(parts))
    assert [c.id for c in out.tool_calls] == ["p1", "t#1", "u#2"]
    assert out.tool_calls[0].arguments == {"x": 1}
    assert sigs == {"p1": b"S1", "t#1": b"S2"}


@pytest.mark.parametrize("ids", [("p1", "p2"), (None, None)])
def test_round_trip_two_same_tool_calls_results_reversed(ids):
    resp, sigs = from_sdk_response(
        _resp([_fc("read", {"n": 1}, id=ids[0], sig=b"A"), _fc("read", {"n": 2}, id=ids[1], sig=b"B")])
    )
    c1, c2 = resp.tool_calls
    assert c1.id != c2.id
    msgs = [
        Message(role="assistant", content="", tool_calls=resp.tool_calls),
        Message(role="tool", content="second", tool_call_id=c2.id),
        Message(role="tool", content="first", tool_call_id=c1.id),
    ]
    out = to_sdk_kwargs(_req(msgs), sigs)["contents"]
    sent = [p["function_call"] for p in out[0]["parts"]]
    got = [p["function_response"] for p in out[1]["parts"]]
    assert [s["id"] for s in sent] == [g["id"] for g in got] == [c1.id, c2.id]
    assert [g["response"]["result"] for g in got] == ["first", "second"]
    assert [s["args"] for s in sent] == [{"n": 1}, {"n": 2}]


def test_replayed_turn_carries_original_signature_and_sentinel_only_as_fallback():
    c1 = ToolCall(id="a", name="n")
    c2 = ToolCall(id="b", name="n")
    msgs = [Message(role="assistant", content="", tool_calls=(c1, c2))]
    real = to_sdk_kwargs(_req(msgs), {"a": b"REAL", "b": b"OTHER"})["contents"][0]["parts"]
    assert real[0]["thought_signature"] == b"REAL"
    assert "thought_signature" not in real[1]
    none = to_sdk_kwargs(_req(msgs), {})["contents"][0]["parts"]
    assert none[0]["thought_signature"] == DUMMY_SIGNATURE
    # A signature known only for a later call is not applied to the first.
    later = to_sdk_kwargs(_req(msgs), {"b": b"OTHER"})["contents"][0]["parts"]
    assert later[0]["thought_signature"] == DUMMY_SIGNATURE


# Feature: provider-gemini, Property GP1 (full cycle): response -> request -> ids and order.
# **Validates: Requirements 2.3, 2.4, 2.5, 2.5a, 2.6, 2.11**
@st.composite
def _cycle(draw):
    n = draw(st.integers(min_value=1, max_value=5))
    names = draw(st.lists(st.sampled_from(["read", "grep"]), min_size=n, max_size=n))
    pids = draw(
        st.lists(st.one_of(st.none(), st.just(""), st.text(min_size=1, max_size=5)), min_size=n, max_size=n)
    )
    sigs = draw(st.lists(st.one_of(st.none(), st.binary(min_size=1, max_size=4)), min_size=n, max_size=n))
    order = draw(st.permutations(range(n)))
    return names, pids, sigs, list(order)


@given(_cycle())
def test_gp1_full_cycle(cycle):
    names, pids, sigs, order = cycle
    parts = [_fc(nm, {"i": i}, id=p, sig=s) for i, (nm, p, s) in enumerate(zip(names, pids, sigs))]
    resp, captured = from_sdk_response(_resp(parts))
    calls = resp.tool_calls
    assert [c.name for c in calls] == names
    for i, (c, p) in enumerate(zip(calls, pids)):
        assert c.id == (p if p else f"{names[i]}#{i}")
    if len({c.id for c in calls}) < len(calls):
        return  # provider ids collided; uniqueness is the provider's guarantee
    msgs = [Message(role="assistant", content="", tool_calls=calls)] + [
        Message(role="tool", content=f"r{i}", tool_call_id=calls[i].id) for i in order
    ]
    out = to_sdk_kwargs(_req(msgs), captured)["contents"]
    assert [c["role"] for c in out] == ["model", "user"]
    sent = [p["function_call"] for p in out[0]["parts"]]
    got = [p["function_response"] for p in out[1]["parts"]]
    assert [s["id"] for s in sent] == [g["id"] for g in got] == [c.id for c in calls]
    assert [g["response"]["result"] for g in got] == [f"r{i}" for i in range(len(calls))]
    first = out[0]["parts"][0]["thought_signature"]
    assert first == (sigs[0] or DUMMY_SIGNATURE)
    assert all("thought_signature" not in p for p in out[0]["parts"][1:])


def test_empty_text_part_ignored():
    out, _ = from_sdk_response(_resp([_text(""), _text("x")]))
    assert out.text == "x"
