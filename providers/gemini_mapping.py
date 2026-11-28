"""Pure translation between skeleton LLM types and Gemini generateContent shapes.

No SDK import: requests become plain dicts, responses are read by attribute.
"""
from collections.abc import Mapping
from typing import Any

from providers.errors import ProviderError
from skeleton.personas.llm import LLMRequest, LLMResponse, Message, ToolCall

# Documented last-resort signature for a function call whose real signature is unknown.
DUMMY_SIGNATURE = b"skip_thought_signature_validator"

_KEEP = frozenset({"type", "properties", "required", "description", "enum", "items"})
_DEFS_PREFIX = "#/$defs/"


# --- schema sanitiser ------------------------------------------------------


def _resolve(node: Mapping[str, Any], defs: Mapping[str, Any], seen: frozenset[str]):
    """Inline `$ref` and collapse `anyOf` until the node is a plain schema."""
    while True:
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith(_DEFS_PREFIX):
                raise ProviderError("unsupported $ref in tool schema")
            name = ref[len(_DEFS_PREFIX) :]
            if name in seen:
                raise ProviderError("cyclic $ref in tool schema")
            if name not in defs:
                raise ProviderError("unresolved $ref in tool schema")
            rest = {k: v for k, v in node.items() if k != "$ref"}
            node = {**defs[name], **rest}
            seen = seen | {name}
        elif "anyOf" in node:
            branches = [
                b
                for b in node["anyOf"]
                if isinstance(b, Mapping) and b.get("type") != "null"
            ]
            rest = {k: v for k, v in node.items() if k != "anyOf"}
            node = {**(branches[0] if branches else {}), **rest}
        else:
            return node, seen


def _sanitise(node: Mapping[str, Any], defs: Mapping[str, Any], seen: frozenset[str]):
    node, seen = _resolve(node, defs, seen)
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key not in _KEEP:
            continue
        if key == "properties":
            # Names are kept verbatim; only the values are schemas.
            out[key] = {n: _sanitise(s, defs, seen) for n, s in value.items()}
        elif key == "items":
            if isinstance(value, Mapping):
                out[key] = _sanitise(value, defs, seen)
        elif key in ("required", "enum"):
            out[key] = list(value)
        else:
            out[key] = value
    return out


def sanitise_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of `schema` reduced to the keys the Gemini API accepts."""
    return _sanitise(schema, schema.get("$defs") or {}, frozenset())


# --- request mapping -------------------------------------------------------


def _first_call_signature(call: ToolCall, signatures: Mapping[str, bytes]) -> bytes:
    """Real signature captured for `call`, else the documented sentinel."""
    return signatures.get(call.id) or DUMMY_SIGNATURE


def _model_content(message: Message, signatures: Mapping[str, bytes]) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    if message.content:
        parts.append({"text": message.content})
    for index, call in enumerate(message.tool_calls):
        part: dict[str, Any] = {
            "function_call": {"name": call.name, "args": dict(call.arguments), "id": call.id}
        }
        if index == 0:
            part["thought_signature"] = _first_call_signature(call, signatures)
        parts.append(part)
    return {"role": "model", "parts": parts}


def _map_messages(
    messages: tuple[Message, ...], signatures: Mapping[str, bytes]
) -> list[dict[str, Any]]:
    # id -> (name, (assistant ordinal, index within its calls)); the latest call wins.
    known: dict[str, tuple[str, tuple[int, int]]] = {}
    out: list[dict[str, Any]] = []
    pending: list[tuple[tuple[int, int], dict[str, Any]]] = []

    def flush() -> None:
        if pending:
            pending.sort(key=lambda item: item[0])
            out.append({"role": "user", "parts": [part for _, part in pending]})
            pending.clear()

    for ordinal, message in enumerate(messages):
        if message.role == "tool":
            entry = known.get(message.tool_call_id or "")
            if entry is None:
                raise ProviderError("tool message does not match a prior tool call")
            name, order = entry
            pending.append(
                (
                    order,
                    {
                        "function_response": {
                            "name": name,
                            "id": message.tool_call_id,
                            "response": {"result": message.content},
                        }
                    },
                )
            )
            continue
        flush()
        if message.role == "assistant":
            for index, call in enumerate(message.tool_calls):
                known[call.id] = (call.name, (ordinal, index))
            out.append(_model_content(message, signatures))
        else:
            out.append({"role": "user", "parts": [{"text": message.content}]})
    flush()
    return out


def to_sdk_kwargs(
    request: LLMRequest, signatures: Mapping[str, bytes]
) -> dict[str, Any]:
    """Build SDK kwargs; `signatures` maps ToolCall.id to a captured thought signature."""
    config: dict[str, Any] = {
        "system_instruction": request.system,
        "max_output_tokens": request.max_tokens,
    }
    if request.tools:
        config["tools"] = [
            {
                "function_declarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": sanitise_schema(t.input_schema),
                    }
                    for t in request.tools
                ]
            }
        ]
    return {"contents": _map_messages(request.messages, signatures), "config": config}


# --- response mapping ------------------------------------------------------


def _finish_name(candidate: Any) -> str | None:
    reason = getattr(candidate, "finish_reason", None)
    if reason is None:
        return None
    name = getattr(reason, "name", reason)
    return name if isinstance(name, str) else None


def from_sdk_response(response: Any) -> tuple[LLMResponse, dict[str, bytes]]:
    """Map a response to (LLMResponse, {ToolCall.id: thought_signature})."""
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return LLMResponse(), {}
    candidate = candidates[0]
    if _finish_name(candidate) == "MAX_TOKENS":
        raise ProviderError("response truncated: finish_reason=MAX_TOKENS")
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []
    texts: list[str] = []
    calls: list[ToolCall] = []
    signatures: dict[str, bytes] = {}
    for part in parts:
        if getattr(part, "thought", None):
            continue
        fc = getattr(part, "function_call", None)
        if fc is not None:
            name = fc.name
            provider_id = getattr(fc, "id", None)
            call_id = provider_id if isinstance(provider_id, str) and provider_id else f"{name}#{len(calls)}"
            calls.append(ToolCall(id=call_id, name=name, arguments=dict(fc.args or {})))
            signature = getattr(part, "thought_signature", None)
            if isinstance(signature, bytes) and signature:
                signatures[call_id] = signature
            continue
        text = getattr(part, "text", None)
        if text:
            texts.append(text)
    return LLMResponse(text="".join(texts), tool_calls=tuple(calls)), signatures
