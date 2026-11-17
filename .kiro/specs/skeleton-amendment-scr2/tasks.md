# Implementation Plan: skeleton-amendment-scr2

Three tasks. If this list grows, the scope has drifted: cut the spec before running any task. Nothing under `skeleton/verify/` may be edited by any task.

- [x] 1. Make `VerifyConfig` injectable through `ApiConfig`
  - In `skeleton/api/app.py` add `verify: VerifyConfig = VerifyConfig()` as the last field of `ApiConfig`.
  - At the `run_grounded_turn` call in the `ask` route, replace `cfg=VerifyConfig()` with `cfg=cfg.verify`. Rename nothing.
  - Check: `scripts/run-tests.sh tests/api` is green with no test edits.
  - _Requirements: R1.1, R1.2, R1.3, R1.4_

- [x] 2. Test that injected `allowed_numbers` takes effect
  - In `tests/api/test_ask.py` give `_ask` an optional `cfg` parameter defaulting to `ApiConfig()`, then add one test: the default config declines a claim containing a bare `42` with `unbacked_number`, and `ApiConfig(verify=VerifyConfig(allowed_numbers=frozenset({"42"})))` answers it. `FakeLLMClient` only.
  - _Requirements: R2.1, R2.2, R2.3_

- [x] 3. Verify containment
  - Run the full Python suite, the UI suite, the four import-linter contracts and `./scripts/check-verify.sh`. Confirm `git diff --stat` shows only `skeleton/api/app.py` and `tests/api/test_ask.py`.
  - Record in `docs/KIRO-USAGE.md`, under "Skeleton change requests", that SCR-2 was taken pre-emptively and why.
  - _Requirements: R3.1, R3.2, R3.3, R3.4_
