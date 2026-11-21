# Requirements: skeleton-amendment-scr5

## Introduction
Skeleton change request SCR-5 was found by running the Medium's harness, not by review. The first live run aborted after 3 consecutive provider errors and reported a 66.7% declined share. Neither number measures the grounding rule. The real error, recovered by instrumenting the adapter:

    ProviderError: response truncated: stop_reason=max_tokens
       max_tokens=1024  system_len=4434  msgs=13

Run 1 is an artefact. It is discarded and not tuned against.

Two defects:
1. `LLMRequest.max_tokens` defaults to 1024 (`skeleton/personas/llm.py`) and `ToolLoopGenerator` never overrides it. A grounded answer embeds a verbatim quote per citation, so three or four claims exceed the budget. The adapter raises on truncation (Medium R1.8, correct). Both attempts fail the same way and the turn declines.
2. `skeleton/verify/flow.py` records `AttemptFailure("generator_error", type(exc).__name__)`. The detail is the class name only. The message that names the cause never reaches `AttemptRecord`, `AnswerResult` or the harness run files. Defect 1 cost a full diagnostic session for this reason.

## Scope
Two defects. Nothing else.

Out of scope, explicitly:
- Any other skeleton change, and SCR-1, SCR-3, SCR-4.
- Any retry or backoff logic. `max_retries=0` stays.
- Any change to the adapter, the harness, the bands or the question set.
- Weakening the coverage gate or using `pragma: no cover`.

## Requirements

### R1. Output budget
User story: As an app author, I want grounded answers to fit the output budget, so that a multi-claim answer is not truncated into a decline.

1. `LLMRequest.max_tokens` defaults to 4096.
2. `ToolLoopGenerator.__init__` takes `max_tokens: int = 4096` and passes it on every `LLMRequest` it builds.
3. A test shows the default request carries 4096, and a generator built with `max_tokens=n` sends `n` on every call (including tool rounds).
4. The default is a ceiling. Output tokens are billed as generated, so an unused ceiling costs nothing.

### R2. Diagnosable generator failure
User story: As a harness operator, I want the message of a failed attempt in the structured result, so that a decline can be diagnosed from the run file.

1. When the generator raises, the recorded detail is `f"{type(exc).__name__}: {exc}"` truncated to at most 300 characters.
2. `AttemptRecord` gains `failure_detail: str | None = None`, filled from the attempt's failure detail for any failed attempt and `None` otherwise. Existing fields keep their names, types and defaults.
3. The field reaches `AnswerResult.attempts`, the `/ask` response and the harness run files (which dump `AnswerResult` with `model_dump`). No harness change is needed.
4. The message is untrusted and may carry model text. It is truncated, written only into the structured record, and never logged. It is also not echoed back to the model: `render_feedback` omits the detail for `generator_error` and keeps it for `unparseable` (fixed parser reasons).
5. The existing tests that assert no key or prompt leaks stay and pass unchanged.
6. `types.generated.ts` is regenerated and `types.ts` gains the field, so `scripts/gen-ts-types.sh --check` passes.

### R3. Coverage gate
1. `skeleton/verify/` stays at 100% line and branch with `./scripts/check-verify.sh`. No `pragma: no cover` is added.
2. The existing flow tests are extended to cover: a short message, a message over 300 characters (truncated to exactly 300), and the non-failed path (`failure_detail` is `None`).
3. If R2 cannot be met without weakening the gate, stop and report. Ship R1 alone.

### R4. Containment
1. All four import-linter contracts pass.
2. The full suite stays green (599 Python, 74 UI at the time of writing; new tests add to the Python count).
3. Changed files are limited to: `skeleton/personas/llm.py`, `skeleton/personas/generator.py`, `skeleton/verify/flow.py`, `skeleton/verify/models.py`, the generated and hand-written UI types, their tests, and `docs/KIRO-USAGE.md`.
4. The task list has at most four tasks.

### R5. Re-run
1. Run 1 is discarded (not tuned against). The harness is re-run from scratch with `uv run python -m medium.eval --runs 2`.
2. `docs/KIRO-USAGE.md`, under "Skeleton change requests", records that SCR-5 was found by the harness rather than by review, and that this is the argument for ordering the harness before the UI.
