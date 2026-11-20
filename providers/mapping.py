"""Pure translation between skeleton LLM types and Anthropic Messages API shapes.

No SDK import: requests become plain dicts, responses are read by attribute.
"""
from typing import Any

from providers.errors import ProviderError
from skeleton.personas.llm import LLMRequest, LLMResponse, Message, ToolCall


def _tool_result_block(message: Message) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": message.tool_call_id,
        "content": message.content,
    }


def _assistant_message(message: Message) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    blocks.extend(
        {"type": "tool_use", "id": c.id, "name": c.name, "input": dict(c.arguments)}
        for c in message.tool_calls
    )
    return {"role": "assistant", "content": blocks}


def _map_messages(messages: tuple[Message, ...]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    previous_was_tool = False
    for message in messages:
        if message.role == "tool":
            block = _tool_result_block(message)
            if previous_was_tool:
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
            previous_was_tool = True
            continue
        previous_was_tool = False
        if message.role == "assistant":
            out.append(_assistant_message(message))
        else:
            out.append(
                {"role": "user", "content": [{"type": "text", "text": message.content}]}
            )
    return out


def to_sdk_kwargs(request: LLMRequest) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "system": request.system,
        "messages": _map_messages(request.messages),
        "max_tokens": request.max_tokens,
    }
    if request.tools:
        kwargs["tools"] = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": dict(t.input_schema),
            }
            for t in request.tools
        ]
    return kwargs


def from_sdk_response(response: Any) -> LLMResponse:
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise ProviderError("response truncated: stop_reason=max_tokens")
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in getattr(response, "content", None) or ():
        if block.type == "text":
            texts.append(block.text)
        elif block.type == "tool_use":
            calls.append(
                ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            )
    return LLMResponse(text="".join(texts), tool_calls=tuple(calls))
