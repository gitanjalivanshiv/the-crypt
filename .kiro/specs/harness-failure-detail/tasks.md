# Implementation Plan: harness-failure-detail

- [x] 1. Carry `failure_detail` into the harness error record and console
  - `medium/eval/__main__.py` as in design.md. Nothing else changes.
  - Add the test from R2.1 to `tests/medium/test_eval_runner.py`.
  - _Requirements: R1.1, R1.2, R1.3, R1.4, R2.1, R2.3_
- [x] 2. Verify containment
  - Full Python suite, `./scripts/check-verify.sh`, `uv run lint-imports`. `git diff --stat` shows only the two files above.
  - _Requirements: R2.2, R2.3, R2.4_
