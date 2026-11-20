"""One real provider call (R1.14). Excluded by default; run with ``-m live``."""
import asyncio
import os

import pytest

from providers.anthropic_client import ENV_VAR, AnthropicClient
from skeleton.personas.llm import LLMRequest, LLMResponse, Message, ToolSpec

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get(ENV_VAR), reason=f"{ENV_VAR} is not set"),
]

LIVE_MODEL = "claude-haiku-4-5"


def test_live_one_tool_request_returns_well_formed_response():
    tool = ToolSpec(
        name="get_weather",
        description="Get the current weather for a city.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    request = LLMRequest(
        system="You are a terse assistant. Use the tool when it applies.",
        messages=(Message(role="user", content="What is the weather in Paris?"),),
        tools=(tool,),
        max_tokens=256,
    )
    response = asyncio.run(AnthropicClient.from_env(LIVE_MODEL).complete(request))

    assert isinstance(response, LLMResponse)
    assert response.text or response.tool_calls
    assert len(response.tool_calls) <= 1
    for call in response.tool_calls:
        assert call.name in {t.name for t in request.tools}
        assert call.id
        assert isinstance(call.arguments, dict)
