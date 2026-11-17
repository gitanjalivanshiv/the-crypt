"""Tool-loop generator (design 7.4): one ``Generator`` call is one attempt."""

import json
from collections.abc import Sequence

from pydantic import BaseModel

from skeleton.mcp.contract import (
    INPUT_MODELS,
    TOOL_DESCRIPTIONS,
    ErrorCode,
)
from skeleton.mcp.router import ToolRouter
from skeleton.personas.llm import LLMClient, LLMRequest, Message, ToolCall, ToolSpec
from skeleton.personas.loader import Persona
from skeleton.verify.flow import AttemptFailure
from skeleton.verify.models import Banishment

MAX_TOOL_ROUNDS = 4


def render_feedback(feedback: Sequence[Banishment] | AttemptFailure) -> str:
    """Render the previous attempt's rejections for the model."""
    if isinstance(feedback, AttemptFailure):
        return (
            "Your previous answer could not be used "
            f"({feedback.kind}: {feedback.detail}). Answer again in the required JSON format."
        )
    lines = [f"- {b.reason.value}: {b.message}" for b in feedback]
    return "These claims were rejected:\n" + "\n".join(lines)


class ToolLoopGenerator:
    """Implements ``verify.flow.Generator`` with at most ``MAX_TOOL_ROUNDS`` tool rounds."""

    def __init__(
        self,
        llm: LLMClient,
        persona: Persona,
        router: ToolRouter,
        system_prompt: str,
        question: str,
    ) -> None:
        self._llm = llm
        self._allowed = frozenset(persona.allowed_tools)
        self._router = router
        self._system = system_prompt
        self._question = question
        self._specs = tuple(
            ToolSpec(
                name=name,
                description=TOOL_DESCRIPTIONS[name],
                input_schema=INPUT_MODELS[name].model_json_schema(),
            )
            for name in router.tool_names
            if name in self._allowed
        )

    def _execute(self, call: ToolCall) -> str:
        if call.name not in self._allowed:
            return json.dumps(
                {
                    "error": {
                        "code": ErrorCode.TOOL_NOT_ALLOWED.value,
                        "message": f"tool not allowed for this persona: {call.name}",
                    }
                }
            )
        result = self._router.call(call.name, call.arguments)
        if isinstance(result, BaseModel):
            return result.model_dump_json()
        return json.dumps(result, default=str)

    async def __call__(
        self, attempt: int, feedback: Sequence[Banishment] | AttemptFailure | None
    ) -> str:
        messages: list[Message] = [Message(role="user", content=self._question)]
        if attempt >= 2 and feedback is not None:
            messages.append(Message(role="user", content=render_feedback(feedback)))
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            offered = self._specs if round_no < MAX_TOOL_ROUNDS else ()
            response = await self._llm.complete(
                LLMRequest(system=self._system, messages=tuple(messages), tools=offered)
            )
            if not response.tool_calls or round_no == MAX_TOOL_ROUNDS:
                return response.text
            messages.append(
                Message(role="assistant", content=response.text, tool_calls=response.tool_calls)
            )
            for call in response.tool_calls:
                messages.append(
                    Message(role="tool", content=self._execute(call), tool_call_id=call.id)
                )
        return ""  # unreachable: the loop always returns on its last round
