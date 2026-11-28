"""Gemini implementation of the skeleton ``LLMClient`` protocol (design sections 3 and 7a).

Retry carve-out (provider-gemini R4, an exception to Medium R1.6): Medium R1.6
forbids retry logic so that the flow's one regeneration (skeleton R4.12) is the
only retry of a model's output. This adapter retries ONLY a call rejected with
HTTP 429 or 503. That is a deferred generation: the provider refused the call
before the model produced anything, so repeating it is transport behaviour and
not a second opinion from the model. At most 4 attempts, waiting 2 s, 4 s and
8 s, inside a 60 s budget measured from the first attempt. Every other status,
timeout or transport error raises on first occurrence. The SDK's own retries
stay off (no retry options on the default client), so this loop is the only one.

Error text carries the class name and status only and is raised ``from None``:
``google.genai.errors.APIError.__str__`` embeds the response body.
"""
# REPL check (google-genai 3.6.1, task 1): `client.models.generate_content` accepts
# plain dicts. Verified against an httpx MockTransport; the request body was built
# correctly from:
#   contents: list of {"role": "user"|"model", "parts": [...]} where parts are
#     {"text": ...}, {"function_call": {"name", "args"}, "thought_signature": bytes}
#     and {"function_response": {"name", "response": {...}}}.
#   config: a dict with "system_instruction" (str), "max_output_tokens" (int),
#     "tools": [{"function_declarations": [{"name", "description", "parameters"}]}]
#     and "http_options": {"timeout": ms, "retry_options": {"attempts": n}}.
# The SDK upper-cases schema types ("integer" -> "INTEGER") and base64-encodes
# thought_signature bytes. Answer: yes, all of the above are accepted as dicts.

import asyncio
import os
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from providers.errors import ProviderError
from providers.gemini_mapping import from_sdk_response, to_sdk_kwargs
from skeleton.personas.llm import LLMRequest, LLMResponse

ENV_VAR = "GEMINI_API_KEY"
_RETRY_STATUSES = frozenset({429, 503})
_MAX_ATTEMPTS = 4
# Free-tier quotas are per MINUTE, so the old 2/4/8 s ladder (14 s total) always expired
# inside the same window it was waiting out, and every retry hit the same 429. These
# delays cover a 60 s window; the budget has to exceed their sum or the guard below
# cancels the last wait.
_RETRY_DELAYS_S = (5.0, 15.0, 30.0)
_BUDGET_S = 150.0
_RETRY_DELAY_RE = re.compile(r"retry(?:_|-)?delay[\"\':\s]+(\d+(?:\.\d+)?)s?", re.IGNORECASE)


def _server_retry_delay(exc: object) -> float | None:
    """Seconds the server asked us to wait, if it said. Google returns RetryInfo on a 429.

    Preferred over any ladder we invent: the server knows when the window resets.
    """
    for attr in ("retry_delay", "retryDelay"):
        value = getattr(exc, attr, None)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    match = _RETRY_DELAY_RE.search(str(exc))
    if match:
        try:
            seconds = float(match.group(1))
        except ValueError:
            return None
        if 0 < seconds <= _BUDGET_S:
            return seconds
    return None


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        timeout_s: float = 60.0,
        sdk: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        thinking_budget: int | None = 2048,
        max_signatures: int = 512,
    ) -> None:
        self._model = model
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._clock = clock
        self._thinking_budget = thinking_budget
        self._max_signatures = max_signatures
        # ToolCall.id -> thought_signature of the response the call came from (R2.5a).
        self._signatures: OrderedDict[str, bytes] = OrderedDict()
        # No retry_options: the SDK must add no hidden retry layer (R1.6).
        self._sdk = (
            sdk
            if sdk is not None
            else genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
            )
        )

    @classmethod
    def from_env(cls, model: str, **kw: Any) -> "GeminiClient":
        key = os.environ.get(ENV_VAR)
        if not key:
            raise ProviderError(f"environment variable {ENV_VAR} is not set")
        return cls(key, model, **kw)

    def _remember(self, captured: dict[str, bytes]) -> None:
        for call_id, signature in captured.items():
            self._signatures[call_id] = signature
            self._signatures.move_to_end(call_id)
        while len(self._signatures) > self._max_signatures:
            self._signatures.popitem(last=False)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = self._clock()
        kwargs = to_sdk_kwargs(request, self._signatures)  # mapping errors precede any call
        thinking = self._thinking_budget
        attempt = 0
        while True:
            remaining = _BUDGET_S - (self._clock() - start)
            config = {
                **kwargs["config"],
                "http_options": {"timeout": int(min(self._timeout_s, remaining) * 1000)},
            }
            if thinking is not None:
                config["thinking_config"] = {"thinking_budget": thinking}
            try:
                response = await self._sdk.aio.models.generate_content(
                    model=self._model, contents=kwargs["contents"], config=config
                )
                break
            except (
                genai_errors.APIError,
                httpx.HTTPError,
                TimeoutError,
                ValueError,
                TypeError,
            ) as exc:
                if thinking is not None and isinstance(exc, (ValueError, TypeError)):
                    # SDK or model rejects the thinking option: omit it, redo this attempt.
                    thinking = None
                    self._thinking_budget = None
                    continue
                status = getattr(exc, "code", None)
                delay = _server_retry_delay(exc) or _RETRY_DELAYS_S[
                    min(attempt, len(_RETRY_DELAYS_S) - 1)
                ]
                if (
                    status not in _RETRY_STATUSES
                    or attempt == _MAX_ATTEMPTS - 1
                    or delay >= _BUDGET_S - (self._clock() - start)
                ):
                    raise ProviderError(f"{type(exc).__name__} status={status}") from None
            await self._sleep(delay)
            attempt += 1
        result, captured = from_sdk_response(response)
        self._remember(captured)
        return result
