# Design: provider-gemini

## 1. Layout

```
providers/
  errors.py            unchanged
  anthropic_client.py  unchanged
  mapping.py           unchanged
  gemini_client.py     NEW  GeminiClient: SDK call, retry on 429/503, error text
  gemini_mapping.py    NEW  pure translation + schema sanitiser, no SDK import
  select.py            NEW  client_from_env(env) -> LLMClient
tests/providers/
  test_gemini_client.py  test_gemini_mapping.py  NEW
  test_live.py           gains one gemini live test (or test_live_gemini.py; see task 6)
```

`select.py` is the one addition beyond the brief's file list. Without it, `main.py` and `eval/__main__.py` each carry the same provider switch and default-model table, and they drift. Dropping it means duplicating about ten lines in two files. The brief's "two files that name a provider" becomes "two files that call `select`", which is stricter.

Import direction is unchanged: `medium -> providers -> skeleton.personas.llm`. `google.genai` is imported only by `gemini_client.py`.

## 2. Mapping (`gemini_mapping.py`)

Same two entry points as `mapping.py`.

```python
def to_sdk_kwargs(request: LLMRequest) -> dict[str, Any]:
    # {"contents": [...], "config": {"system_instruction": str, "max_output_tokens": int,
    #                                "tools": [{"function_declarations": [...]}]}}
def from_sdk_response(response: Any) -> LLMResponse
```

The client passes `contents=` and `config=` to `sdk.aio.models.generate_content(model=..., contents=..., config=...)`. The SDK accepts plain dicts for both (pydantic coerces them), so the mapping stays SDK-free. Task 2 verifies this against the installed SDK before relying on it; if dicts are not accepted for a field, the client converts at the boundary and the mapping stays dict-valued.

### 2.1 Messages

```
user      -> {"role": "user",  "parts": [{"text": ...}]}
assistant -> {"role": "model", "parts": [{"text"?}, {"function_call": {"name","args","id"}, "thought_signature": DUMMY}, {"function_call": ...}]}
tool*     -> {"role": "user",  "parts": [{"function_response": {"name","id","response":{"result": content}}}, ...]}
```

`DUMMY = b"skip_thought_signature_validator"`, on the first function-call part of each model content only. Google's rule is that the first call in each step of the current turn needs a signature. Putting the dummy on every first call is the cheapest rule that satisfies it.

Consequence: the model does not see its own earlier reasoning across tool rounds. This costs answer quality, not correctness. If the harness shows a quality drop, the fix is a skeleton change request adding an opaque `provider_state` field to `ToolCall`. It is not worked around inside the adapter (a client-side cache keyed by id would be hidden state shared across requests).

### 2.2 Ids

Out: `id = part.function_call.id or f"{name}#{index}"`, index per response. Provider ids are used verbatim, so the two ends of a Gemini 3/4 conversation agree.

In: `_name_by_id` is built in one pass over the request's assistant messages (`{call.id: call.name}`, later entries overwrite earlier ones). A tool message looks up its name there. Ids are looked up, never parsed, so a tool named `a#1` cannot confuse the resolver.

Ordering: tool messages that follow one assistant message are grouped and sorted by the index of their `tool_call_id` within that assistant message's `tool_calls`. This is what makes two same-name calls safe when results arrive reversed: Gemini pairs same-name responses by position, so position must equal call order. Unmatched id: `ProviderError("tool message does not match a prior tool call")`.

### 2.3 Response

```python
cand = (response.candidates or [None])[0]
if cand is None: return LLMResponse()
if _finish_name(cand) == "MAX_TOKENS": raise ProviderError("response truncated: finish_reason=MAX_TOKENS")
```

`_finish_name` returns `getattr(fr, "name", fr)`, so it accepts the SDK enum and a plain string in tests. Parts with `thought` truthy are skipped. Thinking tokens count toward `max_output_tokens`, so a thinking model can hit `MAX_TOKENS` with little visible text. This is the SCR-5 failure mode, and the raise is the same as Anthropic's. The default `LLMRequest.max_tokens` of 4096 is not changed.

Other finish reasons (`SAFETY`, `RECITATION`, `STOP`) are not errors. A blocked candidate has no parts and returns an empty `LLMResponse`, which the flow treats as unparseable, same as Anthropic.

### 2.4 Schema sanitiser

```python
_KEEP = {"type", "properties", "required", "description", "enum", "items"}

def sanitise_schema(schema: dict, defs: dict | None = None, _seen: frozenset = frozenset()) -> dict
```

1. Take `$defs` from the root once and pass it down.
2. At a schema position: if `$ref` is present, resolve `#/$defs/<name>` and sanitise the target (a name already in `_seen` raises `ProviderError`).
3. If `anyOf` is present, replace the node by its first branch whose `type` is not `"null"`, then continue.
4. Build the output from `_KEEP` keys only. `properties` maps names to schemas: names are kept verbatim and only the values recurse. `items` recurses. `required` and `enum` are copied.
5. Return a new dict. The input is never mutated.

Step 4 is why a property called `title` survives (R3.4). The 4 real `INPUT_MODELS` use `anyOf`, `default`, `minimum`, `maximum`, `additionalProperties` and `title`, and none uses `$ref`. `$ref` handling is tested with a synthetic nested model.

Lost on purpose: `minimum` and `maximum`. Bounds on `limit`, `line_start` and the like are still enforced server-side by the MCP router's own pydantic validation. Gemini only stops seeing them.

## 3. Client (`gemini_client.py`)

```python
ENV_VAR = "GEMINI_API_KEY"
_RETRY_STATUSES = frozenset({429, 503})
_MAX_ATTEMPTS = 4
_BASE_DELAY_S = 2.0
_BUDGET_S = 60.0

class GeminiClient:
    def __init__(self, api_key, model, *, timeout_s=60.0, sdk=None, sleep=asyncio.sleep,
                 clock=time.monotonic, thinking_budget: int | None = 2048,
                 max_signatures: int = 512): ...
    # self._signatures: OrderedDict[str, bytes]  # ToolCall.id -> thought_signature (R2.5a)
    @classmethod
    def from_env(cls, model, **kw) -> "GeminiClient": ...
    async def complete(self, request) -> LLMResponse: ...
```

Default SDK: `genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))`. No `retry_options`. A test asserts `http_options.retry_options is None`. The injected `sdk` has the shape `sdk.aio.models.generate_content(...)`.

`complete`:

```python
start = clock(); kwargs = to_sdk_kwargs(request)      # mapping errors raise before any call
for attempt in range(_MAX_ATTEMPTS):
    remaining = _BUDGET_S - (clock() - start)
    timeout_ms = int(min(timeout_s, remaining) * 1000)
    try:
        response = await sdk.aio.models.generate_content(
            model=self._model, contents=kwargs["contents"],
            config={**kwargs["config"], "http_options": {"timeout": timeout_ms}},
        )
        break
    except (genai_errors.APIError, httpx.HTTPError, TimeoutError) as exc:
        status = getattr(exc, "code", None)
        delay = _BASE_DELAY_S * 2**attempt
        last = attempt == _MAX_ATTEMPTS - 1
        if status not in _RETRY_STATUSES or last or delay >= _BUDGET_S - (clock() - start):
            raise ProviderError(f"{type(exc).__name__} status={status}") from None
        await sleep(delay)
```

Notes:

- Delays are 2, 4, 8 s: 14 s of waiting over 4 attempts, well inside 60 s. The budget check exists for slow attempts: three 20 s timeouts leave no room for a wait, so the loop stops and raises.
- `status` comes from `exc.code` (`ClientError` 4xx, `ServerError` 5xx). `httpx.HTTPError` has no `code`, so it is never retried.
- The `raise ... from None` sits inside the `except`, so `__cause__` is `None` and `__suppress_context__` hides the SDK error, whose text embeds the response body.
- `asyncio.CancelledError` is a `BaseException`, is not in the tuple, and propagates during an attempt and during `sleep`.
- Only the SDK call is inside the `try`. `from_sdk_response` raising `ProviderError` is not caught and not retried: truncation is a failed generation.

Module docstring states the R4 carve-out in full.

## 4. Selection (`select.py`)

```python
PROVIDERS = ("gemini", "anthropic")
DEFAULT_MODELS = {"gemini": "gemini-4-hydrogen", "anthropic": "claude-haiku-5-5"}

def client_from_env(env: Mapping[str, str] | None = None) -> LLMClient:
    env = os.environ if env is None else env
    name = env.get("MEDIUM_PROVIDER") or "gemini"
    if name not in PROVIDERS: raise ProviderError("MEDIUM_PROVIDER must be one of: gemini, anthropic")
    model = env.get("MEDIUM_MODEL") or DEFAULT_MODELS[name]
    return (GeminiClient if name == "gemini" else AnthropicClient).from_env(model)
```

The SDK-importing modules are imported lazily inside the branch, so an Anthropic-only deployment never imports `google.genai` and the reverse. The error text names the variable and the valid values, never the supplied value.

`client_from_env(model: str | None = None, env=None)`: a `None` model means `MEDIUM_MODEL` from `env`, then the provider default. This makes it a valid `ClientFactory` for `build_app`.

`medium/main.py`: `ClientFactory` becomes `Callable[[str | None], LLMClient]` and the default is `client_from_env`. `build_app` passes `env.get("MEDIUM_MODEL") or None`, and also passes `env` through (via `functools.partial(client_from_env, env=env)` when the default factory is used), so `build_app(env={...})` selects by that env and not by the process env. `build_app`'s signature is otherwise unchanged. `medium.main.DEFAULT_MODEL` is removed, because a single default no longer exists; `tests/medium/test_main.py` imports `DEFAULT_MODELS` from `providers.select` instead.

`medium/eval/__main__.py::_default_client` becomes `return client_from_env()`.

## 5. Config and docs edits

- `.importlinter`: `forbidden_modules` of `no-model-sdks` gains `google` and `google.genai`.
- `pyproject.toml`: add `google-genai`; the `live` marker text names `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`.
- Medium requirements: R1.6 amended (text below), R1.10 and R1.14 adjusted per R7.5.
- Medium design section 2: one line under the retry paragraph pointing at this spec.

Amended R1.6:

> THE adapter SHALL contain no retry logic. THE provider SDK's own automatic retries SHALL be disabled (zero), so the flow's one-regeneration rule (skeleton R4.12) is the only retry of a model's output. **Carve-out (provider-gemini R4):** the Gemini adapter SHALL retry a call rejected with HTTP 429 or 503, because that is a deferred generation and not a failed one. It SHALL make at most 4 attempts, with exponential backoff, within 60 s, and no other status, timeout or error SHALL be retried. The Anthropic adapter has no such carve-out.

## 6. Correctness properties

| # | Property | Covered by |
|---|---|---|
| GP1 | For any list of calls (names may repeat, ids present or absent), assistant plus tool messages map to one `model` content of calls and one `user` content of responses, paired by position, and the response ids are the call ids | hypothesis, `test_gemini_mapping.py` |
| GP2 | Reversed tool-message order yields the same `function_response` order | same |
| GP3 | `sanitise_schema(s)` contains only `_KEEP` keys at every schema position, and does not mutate `s` | hypothesis over generated schemas, plus all `INPUT_MODELS` |
| GP4 | No `ProviderError` from `GeminiClient` contains the key, system prompt or response text, whatever the status | fake SDK errors embedding all three |
| GP5 | The number of SDK calls is 1 for any status outside {429, 503}, and at most 4 for {429, 503}; total scripted sleep is at most 60 s | fake SDK, fake clock |

## 7. Testing

- Default run: fake SDK (`sdk.aio.models.generate_content`), fake `sleep` and `clock`. No key, no network.
- Retry tests: 429 then success (1 sleep of 2 s); 429 x4 raises with 3 sleeps `[2, 4, 8]`; 503 treated like 429; 400, 401, 404, 500, timeout and `httpx` error make exactly one call; slow attempts exhaust the 60 s budget before attempt 4; `CancelledError` during the attempt and during sleep.
- `test_gemini_client.py` also ports: one call per `complete`, default SDK built without retry options, `from_env` missing and present, and a `ToolLoopGenerator` end-to-end run that includes two same-tool calls.
- Live: one request with one tool against `gemini-4-hydrogen`. It asserts a well-formed `LLMResponse`, a non-empty `call.id` and a known tool name. I cannot run it without a key, so task 6 reports it unrun if `GEMINI_API_KEY` is absent. It is also the only check that Google accepts the dummy signature and the echoed ids.

## 7a. Amendments from review (R2.5a to 5d, R8)

**Signature store.** `from_sdk_response` returns `(LLMResponse, dict[str, bytes])`. `complete` merges the captured signatures into `self._signatures`, bounded at `max_signatures` with oldest-first eviction. `to_sdk_kwargs(request, signatures)` uses the real signature for the first `function_call` part of a `model` content and falls back to the sentinel. `gemini_mapping.py` stays pure: the store is owned by the client and passed in.

**Thinking budget.** `complete` sends the SDK's thinking configuration when `thinking_budget` is not `None`, inside a guard so an SDK or model that rejects the field degrades to omitting it rather than failing. Thinking tokens otherwise compete with the answer for `max_output_tokens`, which is SCR-5's failure mode wearing a different hat.

**Per-provider `max_tokens`.** `select.py` carries it: 8192 for Gemini, the skeleton default for Anthropic. Passed into `ToolLoopGenerator`, which SCR-5 made configurable, so nothing under `skeleton/` changes.

## 8. Risks

| Risk | Handling |
|---|---|
| The dummy signature is rejected by `gemini-4-hydrogen` | Live test fails in task 6; stop and report. Do not add a cache. |
| Free-tier daily quota exhausted: a 429 that no backoff clears | Four attempts then `ProviderError`; the harness already aborts after 3 consecutive provider errors. Documented, not solved. |
| Model id changes | `MEDIUM_MODEL` overrides it; the id was checked on 2026-11-21 against `aistudio.google.com/docs/pricing`. |
| Free-tier prompts may be used to improve Google's products | Free tier terms say so. The demo repo is public, but the operator should know. Noted in the final report. |
