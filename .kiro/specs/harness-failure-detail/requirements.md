# Requirements: harness-failure-detail

## Introduction
Follow-up to SCR-5 (`.kiro/specs/skeleton-amendment-scr5/`), kept as its own spec because SCR-5 put the harness out of scope. SCR-5 added `AttemptRecord.failure_detail`. The harness still drops it. In `medium/eval/__main__.py`, a turn whose attempts all failed with `generator_error` is recorded as the fixed string `"ProviderError: every attempt failed with generator_error"`, and the `AnswerResult` is discarded. The second SCR-5 re-run aborted on three such turns and the run file could not say why.

## Scope
One change in `medium/eval/__main__.py`: carry the attempts' `failure_detail` into the `errors` entry and onto the console. Out of scope: the skeleton, the adapter, the bands, the question set, the metrics, abort and retry logic, and the run-file schema (`errors` stays a list of `{"id", "error"}` string pairs).

## Requirements
### R1. Provider-failed turns carry their cause
1. The `error` string for an all-`generator_error` turn starts with the existing text `ProviderError: every attempt failed with generator_error` and then appends `: ` and the distinct `failure_detail` values of its attempts, in order, joined by `; `.
2. The `ProviderError` raised straight out of `/ask` path and the HTTP non-200 path are unchanged.
3. The console, after the existing `N turn(s) failed: ...` line, prints one `  <id>: <error>` line per error.
4. No new logging. The text is already truncated to 300 characters per attempt by the skeleton.

### R2. Tests and containment
1. A test drives an always-failing client with `ProviderError("boom")` and asserts the run file's `errors[0]["error"]` ends with `ProviderError: boom`, and that two identical attempt details appear once.
2. Existing harness tests pass unchanged. The full suite stays green, `./scripts/check-verify.sh` stays at 100%, and all four import-linter contracts pass.
3. Only `medium/eval/__main__.py` and `tests/medium/test_eval_runner.py` change.
4. At most two tasks.
