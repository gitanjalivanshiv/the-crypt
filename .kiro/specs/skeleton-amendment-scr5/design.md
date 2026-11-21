# Design: skeleton-amendment-scr5

## Overview
Two independent changes. No new import edges, so no import-linter contract is affected.

## Change 1: output budget
`skeleton/personas/llm.py`: `LLMRequest.max_tokens: int = 4096`.

`skeleton/personas/generator.py`: `ToolLoopGenerator.__init__` gains `max_tokens: int = 4096` as the last parameter (keyword-compatible with all existing callers). It is stored as `self._max_tokens` and passed as `max_tokens=self._max_tokens` in the single `LLMRequest(...)` call inside the tool loop. The literal 4096 appears in `generator.py` as a default only. No new constant is exported.

No adapter change. `from_sdk_response` still raises on `stop_reason=max_tokens`; that behaviour is correct and untouched.

## Change 2: failure detail
`skeleton/verify/flow.py`:
```python
_DETAIL_MAX = 300
...
except Exception as exc:  # noqa: BLE001 - generator is untrusted; any failure fails the attempt
    detail = f"{type(exc).__name__}: {exc}"[:_DETAIL_MAX]
    return _Attempt((), (), AttemptFailure("generator_error", detail))
```
`_record` passes `failure_detail=attempt.failure.detail` in the failed branch. The accepted and banished branches leave it `None`. No new branch is added.

`skeleton/verify/models.py`: `AttemptRecord.failure_detail: str | None = None`, after `failure_kind`.

A generator whose exception `__str__` itself raises would escape the handler. That is accepted: the flow's contract covers ordinary exceptions, and a guard would add a branch that no real case reaches.

### Why the record, and not only `AttemptFailure`
`AttemptFailure.detail` is read only by `render_feedback`, which feeds the next prompt. Changing line 66 alone would not reach `AttemptRecord`, `AnswerResult` or the run files. Hence the new field.

### Keeping the message out of the prompt
`render_feedback` (`generator.py`) currently prints `({kind}: {detail})`. For `generator_error` it now prints only the kind, so provider text (request ids, echoed fragments) is not sent back to the model. For `unparseable` the detail is a fixed parser reason and stays.

### Never logged
No logging call is added. The text lives only in `AttemptFailure` (in memory) and `AttemptRecord.failure_detail` (structured result).

## Change 3: types
`AttemptRecord` is an OpenAPI model, so `types.generated.ts` changes. Regenerate with `scripts/gen-ts-types.sh` and add `failure_detail?: string | null;` to `AttemptRecord` in `skeleton/ui-shell/src/types.ts`. Verify with `scripts/gen-ts-types.sh --check`.

## Tests
- `tests/personas/test_llm.py` or the existing LLM test file: default `max_tokens == 4096`.
- `tests/personas/test_generator.py`: a `FakeLLMClient` records requests. Default generator sends 4096 on every request across a tool round. `max_tokens=n` sends `n`. `render_feedback` of `AttemptFailure("generator_error", "ProviderError: secret-ish text")` omits the text; the `unparseable` rendering is unchanged.
- `tests/verify/test_flow.py`:
  - Update `test_generator_raises_both_times_declines`: second-attempt feedback is `AttemptFailure("generator_error", "RuntimeError: boom")` and `failure_detail == "RuntimeError: boom"` on both records.
  - New: a message of 1000 characters yields a `failure_detail` of exactly 300 characters that starts with `"RuntimeError: "`.
  - New (or extended): an accepted attempt and a banished attempt have `failure_detail is None`; an unparseable attempt carries the parser reason.
- Existing leak tests are untouched.

## Risks
- Gate: the new code has no new branches, so 100% holds with the extended tests. Checked by `./scripts/check-verify.sh`.
- API schema: one optional field with a default, so existing clients and tests are unaffected. Checked by the UI suite and the `--check` run.
- Run 1 data in `medium/eval/runs/` is left in place and not deleted. It is ignored in the write-up (R5).
