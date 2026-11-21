# Requirements: provider-gemini

## Introduction

The Medium has one `LLMClient`, `providers.AnthropicClient`. This spec adds a second, `providers.GeminiClient`, for the Google Gemini API, and makes it the default. The free tier removes the runtime spend that `tech.md` budgets for.

The contract does not change: `async def complete(self, request: LLMRequest) -> LLMResponse`, raising `providers.errors.ProviderError` on any failure. Nothing under `skeleton/` changes (Medium R9).

Facts checked against Google's current documentation on 2026-11-21, not taken from the brief:

- Free-tier model: `gemini-4-hydrogen`. Gemini 4 Carbon, Argon and Neon are not on the free tier.
- Gemini 3 and 4 return a unique `id` on every `functionCall` and expect it echoed in the `functionResponse`. The brief says Gemini has no call ids. For these models that is out of date. The adapter uses the provider id when present and synthesises one only when it is absent (R2).
- Gemini 3 and 4 reject (HTTP 400) a request whose history has a `functionCall` in the current turn without a `thought_signature`. `ToolCall` has no field for it and `skeleton/` cannot change. The documented escape is the dummy signature `skip_thought_signature_validator` (R2.5).
- Google labels `generateContent` "legacy" in favour of the Interactions API. It is still supported, and the brief's shapes (`system_instruction`, `finish_reason`, `function_response`) are `generateContent`. This spec uses it.
- `google.genai.errors.APIError.__str__` embeds the response body. The adapter never formats `str(exc)`.

## Scope

In: `providers/gemini_client.py`, `providers/gemini_mapping.py`, `providers/select.py`, their tests, the two entry points, one import-linter edit, one dependency, and amendments to Medium R1.6, R1.10 and R1.14.

Out, explicitly:

- Anything under `skeleton/`. A need there is a stop condition (Medium R9.1): record a skeleton change request in `docs/KIRO-USAGE.md` and stop.
- Any change to `AnthropicClient`, `providers/mapping.py` or their tests, and any retry logic in the Anthropic adapter.
- The Interactions API, streaming, thinking configuration, `Retry-After` handling, jitter, and a persisted thought-signature cache.
- Persona, harness bands and the question set.

## Glossary

- **Transient status**: HTTP 429 or 503 from the provider.
- **Deferred generation**: a call rejected with a transient status. The model produced nothing, so repeating the call is transport behaviour and not a second opinion.

---

## R1. Adapter shape

**User story:** As the system, I want a Gemini `LLMClient` that is structured like the Anthropic one, so that a reader of one understands the other.

### Acceptance criteria

1. THE adapter SHALL be `providers/gemini_client.py` (class `GeminiClient`) and `providers/gemini_mapping.py`, beside `anthropic_client.py` and `mapping.py`. Tests SHALL be `tests/providers/test_gemini_client.py` and `tests/providers/test_gemini_mapping.py`.
2. `GeminiClient` SHALL implement `skeleton.personas.llm.LLMClient`.
3. `gemini_mapping.py` SHALL import no SDK, exactly as `mapping.py` does: requests become plain dicts, responses are read by attribute. `gemini_client.py` SHALL be the only module that imports `google.genai`.
4. THE SDK client SHALL be injectable (`sdk=`), so tests need no key and no network.
5. `GeminiClient.from_env(model, **kw)` SHALL read `GEMINI_API_KEY` and raise `ProviderError` naming the variable when it is unset or empty. The default constructor SHALL take the key as an argument. Nothing under `skeleton/` reads a key.
6. THE default SDK client SHALL be built with no SDK retry options, so the SDK adds no hidden retry layer. A test asserts this.
7. THE per-attempt timeout SHALL be explicit (`timeout_s`, default 60.0) and an attempt that exceeds it SHALL raise `ProviderError`.

## R2. Request and response translation

**User story:** As the system, I want each Gemini difference handled in the mapping, so that the flow and the generator never see them.

### Acceptance criteria

1. Roles: `user` maps to `user`, `assistant` to `model`, and a `tool` message to a `user` content holding `function_response` parts. Consecutive `tool` messages SHALL merge into one content.
2. THE system prompt SHALL go in the request config as `system_instruction` and SHALL NOT appear in `contents`. `max_tokens` SHALL map to `max_output_tokens`.
3. Outbound ids: for each response function call, `ToolCall.id` SHALL be the provider's `id` when it is a non-empty string, otherwise `f"{name}#{index}"` where `index` is the call's position in that response. An id SHALL be unique within one response.
4. Inbound ids: a `tool` message SHALL resolve its `tool_call_id` to a function name by looking it up among the `tool_calls` of earlier `assistant` messages in the same request (latest wins). THE adapter SHALL NOT parse the name out of the id. A `function_call` and its `function_response` SHALL both carry the skeleton's id. A `tool_call_id` that matches no earlier call SHALL raise `ProviderError` with fixed text and no id.
5. THE first `function_call` part of each `model` content SHALL carry a `thought_signature`. Other parts SHALL carry none. THE value SHALL be **the real signature the model returned for that call**, when it is known, and the sentinel `b"skip_thought_signature_validator"` only when it is not.
5a. `GeminiClient` SHALL keep a signature store mapping `ToolCall.id` to the `thought_signature` that accompanied that function call in the response it came from. `from_sdk_response` SHALL return the captured signatures alongside the `LLMResponse`; `to_sdk_kwargs` SHALL take the store as an argument. `gemini_mapping.py` SHALL stay pure and hold no state of its own (R1.3).
5b. THE store SHALL be bounded (at most 512 entries, oldest evicted) so a long-lived client cannot grow without limit. Eviction SHALL fall back to the sentinel, never raise.
5c. Rationale, recorded because the sentinel is the obvious shortcut: Google documents the sentinel as a last resort that degrades model quality, and preserving the real signature as the recommended path. `ToolLoopGenerator` runs up to four tool rounds per attempt, so on the sentinel the model loses its own reasoning between rounds while being asked for exact verbatim quotes and structured JSON. The Medium harness exists to decide whether the grounding rules are tunable; if the adapter degrades the model, a bad result cannot be attributed between the model, the rules and the adapter. The store removes that confound. The sentinel remains the fallback, not the default path.
5d. A test SHALL assert that a replayed assistant turn carries the original signature, and that the sentinel is used only when no signature was captured.
6. Within one `model` content, all `function_call` parts SHALL precede the tool results, and the `function_response` parts SHALL be ordered by the call order of the `assistant` message they answer, whatever order the `tool` messages arrive in. (Google returns a 400 for interleaved or reordered parallel responses.)
7. `function_response.response` SHALL be `{"result": message.content}`.
8. Tool schemas SHALL come from `ToolSpec.input_schema`, sanitised (R3), and be sent as `function_declarations`. An empty `tools` tuple SHALL omit the `tools` key.
9. THE response SHALL map to `LLMResponse`: text parts without `thought` joined into `text`, function-call parts into `ToolCall`. A response with no candidates or no parts SHALL return an empty `LLMResponse`, as the Anthropic mapping does.
10. WHEN the candidate's `finish_reason` is `MAX_TOKENS`, THE mapping SHALL raise `ProviderError("response truncated: finish_reason=MAX_TOKENS")` before reading any content. This is Medium R1.8 and the defect SCR-5 fixed. It SHALL NOT be conditional on there being text.
11. A round-trip test SHALL cover two calls to the same tool in one turn, with and without provider ids: both `ToolCall`s get distinct ids, each result reaches the call it answers, and results arriving in reverse order are still emitted in call order.

## R3. Schema sanitising

**User story:** As the system, I want tool schemas the Gemini API accepts, so that no tool is rejected at request time.

### Acceptance criteria

1. THE sanitiser SHALL keep only `type`, `properties`, `required`, `description`, `enum` and `items`, recursively. Every other key SHALL be dropped, including `additionalProperties`, `title` (at object and property level), `default`, `minimum`, `maximum`, `$defs` and `$ref`.
2. Every `$ref` SHALL be replaced by the inlined definition from `$defs`, then sanitised. A cyclic `$ref` SHALL raise `ProviderError`.
3. `anyOf` of one non-null schema and `null` (a pydantic `Optional`) SHALL collapse to that schema. Any other `anyOf` SHALL collapse to its first non-null branch. The field's optionality is carried by `required`, which the sanitiser keeps.
4. A property NAMED `title`, `default` or any dropped key SHALL be preserved: keys are filtered only where a schema is expected, not inside `properties`.
5. THE sanitiser SHALL NOT mutate its input.
6. A test SHALL sanitise every schema in `skeleton.mcp.contract.INPUT_MODELS` and assert the output contains no key outside the allowed set at any schema position.

## R4. Rate limiting: a narrow exception to Medium R1.6

**User story:** As the operator on a free tier, I want a 429 to be waited out, so that routine rate limiting does not decline a turn.

Medium R1.6 forbids retry logic so that the flow's one regeneration (skeleton R4.12) is the only retry. A 429 is a deferred generation, not a failed one.

### Acceptance criteria

1. THE adapter SHALL retry only when the provider status is 429 or 503. Every other status, timeout and transport error SHALL raise `ProviderError` on the first occurrence with no retry.
2. THE adapter SHALL make at most 4 attempts, wait `2 s`, `4 s`, `8 s` between them (exponential, base 2), and start no attempt and sleep no wait that would pass a 60 s budget measured from the first attempt. Each attempt's timeout SHALL be `min(timeout_s, remaining budget)`.
3. WHEN attempts or budget run out, THE adapter SHALL raise `ProviderError(f"{ClassName} status={status}")` for the last error.
4. THE sleep and clock SHALL be injectable, so tests take no wall time.
5. THE `gemini_client.py` module docstring SHALL state this carve-out and why it is not a second opinion from the model.
6. `AnthropicClient` SHALL gain no retry logic.
7. Medium R1.6 SHALL be amended in `.kiro/specs/medium/requirements.md` to record the carve-out. The amended clause SHALL say that the carve-out covers only a deferred generation (429, 503) in the Gemini adapter and that the flow's one-regeneration rule remains the only retry of a model's output.

## R5. Failure text

**User story:** As the operator, I want errors that cannot leak, so that logs and run files are safe to share.

### Acceptance criteria

1. A `ProviderError` from `GeminiClient` SHALL carry the error class name and status only (`f"{type(exc).__name__} status={status}"`, status `None` when absent). It SHALL be raised `from None`, so `__cause__` is `None`.
2. IT SHALL NOT contain the key, the system prompt, the prompt or the model output, in `str()` or `repr()`. The adapter SHALL never format `str(exc)` or `exc.message`.
3. `asyncio.CancelledError` SHALL propagate.
4. THE redaction test of `test_anthropic_client.py` (key, system prompt and response text embedded in the SDK error) SHALL have a counterpart for `GeminiClient`, covering a 500, a 429 that exhausts its attempts, a timeout, and a mapping error.

## R6. Selection and configuration

**User story:** As the operator, I want to choose the provider by environment, so that Gemini is the default and Anthropic stays available.

### Acceptance criteria

1. `MEDIUM_PROVIDER` SHALL select the client: `gemini` (default when unset or empty) or `anthropic`. Any other value SHALL raise `ProviderError` naming the variable and listing the valid values.
2. THE selection SHALL live in one function in `providers/select.py` used by `medium/main.py` and `medium/eval/__main__.py`, so the two entry points cannot diverge. `medium/main.py` SHALL keep its `client_factory` parameter.
3. `MEDIUM_MODEL` SHALL keep overriding the model. Per-provider defaults: Gemini `gemini-4-hydrogen`, Anthropic `claude-haiku-5-5` (today's `medium.main` default). The harness's current Anthropic default, `claude-sonnet-5-5`, is dropped so both entry points share one table. An Anthropic harness run that wants Sonnet sets `MEDIUM_MODEL`.
4. `medium/main.py` and `medium/eval/__main__.py` SHALL be the only files outside `providers/` that name a provider or its key variable. No file under `skeleton/` SHALL contain `gemini`, `google` or `GEMINI` (Medium R1.12).
5. THE existing tests that assume Anthropic as the default SHALL be updated to state the provider they mean. No assertion is weakened.

## R7. Containment and gates

### Acceptance criteria

1. `google` and `google.genai` SHALL be added to `forbidden_modules` of the `no-model-sdks` contract in `.importlinter`. All contracts pass, and the independence test that plants a violation SHALL also plant one importing `google.genai`.
2. `google-genai` SHALL be added to `pyproject.toml` dependencies and `uv.lock`.
3. THE full suite stays green and `./scripts/check-verify.sh` reports 100%. No `pragma: no cover`.
4. ONE live test, marked `live`, mirroring `tests/providers/test_live.py`, SHALL skip unless `GEMINI_API_KEY` is set and SHALL be excluded from the default run. The `live` marker description SHALL name both keys.
5. Medium R1.10 SHALL be amended to name the key variable per adapter, and R1.14 to say one live test per adapter.
6. THE task list SHALL have at most six tasks. `git diff --stat` SHALL show no path under `skeleton/`.

---

## R8. Output budget and thinking tokens

**User story:** As the builder, I want the answer to fit in the output budget, so that the first live run measures grounding rather than truncation.

Design section 2.3 already notes that thinking tokens count toward `max_output_tokens`, so a thinking model can hit `MAX_TOKENS` with little visible text, which is the SCR-5 failure mode on a new provider. The spec as drafted diagnosed this and left it unmitigated. These criteria close it.

### Acceptance criteria

1. `GeminiClient` SHALL accept a `thinking_budget` argument and SHALL send the SDK's thinking configuration when it is set, so reasoning cannot consume the whole output budget. THE default SHALL be a bounded value, not unlimited. IF the chosen model or SDK version does not support the option, THEN the client SHALL omit it rather than fail, and this SHALL be covered by a test with a fake SDK that rejects the field.
2. `providers/select.py` SHALL expose a per-provider default `max_tokens`, and the Gemini default SHALL be **8192**, not the skeleton default of 4096. SCR-5 made `max_tokens` a `ToolLoopGenerator` constructor argument, so this needs no change under `skeleton/`.
3. `medium/main.py` and `medium/eval/__main__.py` SHALL pass that value when constructing `ToolLoopGenerator`. A test SHALL assert the generator receives the per-provider value.
4. THE `MAX_TOKENS` raise of R2.10 SHALL remain. These criteria reduce how often it fires; they do not hide it.
5. IF the first live run still truncates, THEN the thinking budget SHALL be lowered before `max_tokens` is raised again, because thinking tokens are the suspected consumer and raising the ceiling only pays for more of them.
