"""Provider-neutral LLM interface and a scripted fake (design 7.4, R7.3).
No provider SDK is imported here; the API receives an LLMClient by argument.
"""
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolSpec(_Model):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolCall(_Model):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(_Model):
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


class LLMRequest(_Model):
    system: str
    messages: tuple[Message, ...]
    tools: tuple[ToolSpec, ...] = ()
    max_tokens: int = 4096


class LLMResponse(_Model):
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


class LLMClient(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...


class FakeLLMScriptExhausted(RuntimeError):
    """Raised when a FakeLLMClient is asked for more responses than scripted."""


class FakeLLMClient:
    """Replays scripted responses in order and records every request."""

    def __init__(self, script: list[LLMResponse]) -> None:
        self._script = list(script)
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        index = len(self.requests) - 1
        if index >= len(self._script):
            raise FakeLLMScriptExhausted(
                f"FakeLLMClient script exhausted: call {index + 1} "
                f"but only {len(self._script)} response(s) scripted"
            )
        return self._script[index]
